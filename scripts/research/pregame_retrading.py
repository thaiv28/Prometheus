"""Pre-match re-trading backtest: one order vs top-ups vs selling vs side swaps.

Replays every priced series hour by hour on Kalshi's hourly candles (bid/ask
close, forward-filled), from DECIDE_HOURS before the scheduled start up to the
start. Each hour recomputes the production blend (frozen raw model chance,
current two-sided mid with spread <= 0.10, the monthly earlier-only snapshot)
and lets a policy act once:

  once      first positive-Kelly buy, then hold (pre-top-up production)
  last      one buy at the last hour before the start (timing reference)
  topup     buy more of the same side, up to 4 orders, later ones >= MIN_ORDER
  trim      topup plus selling the held side down to its Kelly target
  full      buy or sell either side (side swaps), unlimited orders >= MIN_ORDER

Each series gets its own bankroll of 1 at full Kelly with exact held-position
sizing; worst-case loss is capped at SERIES_CAP (the live 10% series cap).
Buys pay the ask (or 1 - opponent bid), sells receive the bid (or
1 - opponent ask); every order pays 0.07*n*c*(1-c), rounded up to 0.0001.
Scores: final log wealth and P&L per series, paired against `once` with a
2,000-draw bootstrap over start weeks. Not modelled: book depth, quotes
inside the hour, concurrent series sharing one bankroll.

Inputs: LoL from data/markets (frames.pkl, candles/); other games from CSVs
exported by each model repo (event_ticker, ticker, team1_side, p, won,
start_utc[, international]) plus that repo's data/kalshi/candles.

Usage: python scripts/research/pregame_retrading.py --game cs2=CSV:CANDLES ...
"""

import argparse
import gzip
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo))
from prometheus import market_blend

FEE, MAX_SPREAD, MAX_PRICE = 0.07, 0.10, 0.99
SERIES_CAP, MIN_ORDER, MAX_LEGS = 0.10, 0.01, 4  # MIN_ORDER: $0.50 of a $50 bankroll
HOLDOUT = pd.Timestamp("2026-10-20", tz="UTC")
POLICIES = ("once", "last", "topup", "trim", "full")


def fee(n, c):
    return math.ceil(FEE * n * c * (1 - c) * 10000 - 1e-9) / 10000


def load_candles(path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt") as handle:
        rows = json.load(handle)
    out = {}
    for r in rows:
        # Kalshi renamed `close` to `close_dollars` in late August 2026.
        bid, ask = (
            (r.get(k) or {}).get("close", (r.get(k) or {}).get("close_dollars"))
            for k in ("yes_bid", "yes_ask")
        )
        if bid is None or ask is None:
            continue
        out[int(r["end_period_ts"])] = (float(bid), float(ask))
    return out


def lol_series(markets_dir):
    frame = pd.read_pickle(markets_dir / "frames.pkl")[0]
    markets = json.loads((markets_dir / "KXLOLGAME.json").read_text())
    by_event = defaultdict(dict)
    for m in markets:
        by_event[m["event_ticker"]][m["yes_sub_title"]] = m["ticker"]
    rows = []
    for r in frame.itertuples():
        tickers = by_event.get(r.event_ticker, {})
        t1, t2 = tickers.get(r.team1), tickers.get(r.team2)
        if not (t1 and t2) or pd.isna(r.p_series) or pd.isna(r.won1):
            continue
        paths = [markets_dir / "candles" / f"{t}.json" for t in (t1, t2)]
        if not all(p.exists() for p in paths):
            continue
        rows.append(
            {
                "game": "lol",
                "event": r.event_ticker,
                "start": pd.Timestamp(r.start),
                "p": float(r.p_series),
                "won1": bool(r.won1),
                "paths": paths,
            }
        )
    return rows


def other_series(game, csv, candles):
    d = pd.read_csv(csv)
    if game == "valorant":  # only domestic Valorant trades
        d = d[d.international.fillna(0).astype(int) == 0]
    files = defaultdict(list)
    for f in candles.iterdir():
        event = f.name.split(".json")[0].rsplit("-", 1)[0]
        files[event].append(f)
    rows = []
    for r in d.itertuples():
        own = candles / f"{r.ticker}.json.gz"
        other = [f for f in files.get(r.event_ticker, []) if f != own]
        if not own.exists() or len(other) != 1 or pd.isna(r.won):
            continue
        t1, t2 = (own, other[0]) if r.team1_side else (other[0], own)
        rows.append(
            {
                "game": game,
                "event": r.event_ticker,
                "start": pd.Timestamp(r.start_utc),
                "p": float(r.p),
                "won1": bool(r.won),
                "paths": [t1, t2],
            }
        )
    return rows


def path_quotes(series, hours):
    """[(ts, (bid1, ask1), (bid2, ask2))] for the decision hours, forward-filled."""
    c1, c2 = (load_candles(p) for p in series["paths"])
    start = int(series["start"].timestamp())
    stamps = sorted(t for t in set(c1) | set(c2) if start - hours * 3600 <= t < start)
    out, q1, q2 = [], None, None
    for t in sorted(set(c1) | set(c2)):
        q1, q2 = c1.get(t, q1), c2.get(t, q2)
        if t in stamps and q1 and q2:
            out.append((t, q1, q2))
    return out


def mid1(q1, q2):
    mids = [
        m
        for (bid, ask), flip in ((q1, False), (q2, True))
        if 0 < bid < ask < 1 and ask - bid <= MAX_SPREAD
        for m in [(bid + ask) / 2]
        for m in [1 - m if flip else m]
    ]
    return sum(mids) / len(mids) if mids else None


def kelly_buy(p, c, w_own, w_other, room):
    """Contracts of the side with chance p at cost c (fee included)."""
    k = (p * (1 - c) * w_other - (1 - p) * c * w_own) / (c * (1 - c))
    return max(0.0, min(k, room / c))


def kelly_sell(p, s, w_own, w_other, held):
    k = ((1 - p) * s * w_own - p * (1 - s) * w_other) / (s * (1 - s))
    return max(0.0, min(k, held))


def replay(series, quotes, policy):
    w = [1.0, 1.0]  # wealth if team 1 / team 2 wins
    held = [0.0, 0.0]
    legs, side, fees = 0, None, 0.0
    steps = quotes[-1:] if policy == "last" else quotes
    for t, q1, q2 in steps:
        if policy in ("once", "last") and legs:
            break
        m = mid1(q1, q2)
        model = market_blend.snapshot(
            pd.Timestamp(t, unit="s", tz="UTC"), series["game"]
        )
        if m is None or model is None:
            continue
        clip = market_blend.load(series["game"]).get("clip") or 1e-6
        p1 = market_blend.combine(series["p"], m, model, clip)
        if p1 is None:
            continue
        probs = (p1, 1 - p1)
        quotes_by = (q1, q2)
        actions = []
        for j in (0, 1):
            o = 1 - j
            if side is not None and j != side and policy != "full":
                continue
            (bid_j, ask_j), (bid_o, ask_o) = quotes_by[j], quotes_by[o]
            buy = min(x for x in (ask_j, 1 - bid_o) if 0 < x < 1)
            if 0 < buy <= MAX_PRICE and (policy == "full" or legs < MAX_LEGS):
                c = buy + FEE * buy * (1 - buy)
                room = SERIES_CAP - (1 - min(w))
                k = math.floor(kelly_buy(probs[j], c, w[j], w[o], room) * 100) / 100
                if k > 0:
                    actions.append(("buy", j, k, buy))
            if policy in ("trim", "full") and held[j] > 0:
                sell = max(x for x in (bid_j, 1 - ask_o) if 0 < x < 1)
                if 0 < sell < 1:
                    s = sell - FEE * sell * (1 - sell)
                    k = (
                        math.floor(kelly_sell(probs[j], s, w[j], w[o], held[j]) * 100)
                        / 100
                    )
                    if k > 0:
                        actions.append(("sell", j, k, sell))
        best, gain = None, 0.0
        base = p1 * math.log(w[0]) + (1 - p1) * math.log(w[1])
        for kind, j, k, price in actions:
            f = fee(k, price)
            nw = list(w)
            if kind == "buy":
                nw[j] += k * (1 - price) - f
                nw[1 - j] -= k * price + f
            else:
                nw[j] -= k * (1 - price) + f
                nw[1 - j] += k * price - f
            if min(nw) <= 0:
                continue
            notional = k * price
            if legs and notional < MIN_ORDER:
                continue
            g = p1 * math.log(nw[0]) + (1 - p1) * math.log(nw[1]) - base
            if g > gain:
                best, gain = (kind, j, k, nw, f), g
        if best:
            kind, j, k, w, f = best
            held[j] += k if kind == "buy" else -k
            side = j if side is None else side
            legs += 1
            fees += f
    final = w[0] if series["won1"] else w[1]
    return final, legs, fees


def main():
    global SERIES_CAP, MIN_ORDER
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markets", type=Path, default=repo / "data" / "markets")
    parser.add_argument("--game", action="append", default=[], help="GAME=CSV:CANDLES")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--cap", type=float, default=SERIES_CAP, help="Series loss cap")
    parser.add_argument("--min-order", type=float, default=MIN_ORDER)
    parser.add_argument("--out", type=Path, help="Write per-series results here")
    args = parser.parse_args()
    SERIES_CAP, MIN_ORDER = args.cap, args.min_order
    series = lol_series(args.markets)
    for spec in args.game:
        game, rest = spec.split("=", 1)
        csv, candles = rest.split(":", 1)
        series += other_series(game, Path(csv), Path(candles))
    rows = []
    for s in series:
        if s["start"] >= HOLDOUT:
            continue
        quotes = path_quotes(s, args.hours)
        if not quotes:
            continue
        row = {
            "game": s["game"],
            "event": s["event"],
            "start": s["start"],
            "hours": len(quotes),
        }
        for policy in POLICIES:
            final, legs, fees = replay(s, quotes, policy)
            row[f"{policy}_w"], row[f"{policy}_legs"], row[f"{policy}_fees"] = (
                final,
                legs,
                fees,
            )
        rows.append(row)
    r = pd.DataFrame(rows)
    r["week"] = r.start.dt.strftime("%G-%V")
    if args.out:
        r.to_csv(args.out, index=False)
    rng = np.random.default_rng(0)
    print(
        f"series {len(r)}, window {args.hours}h, cap {SERIES_CAP:g}, min order {MIN_ORDER:g}"
    )
    for game, g in [("all", r), *r.groupby("game")]:
        traded = g[g.once_legs > 0]
        print(f"\n{game}: {len(g)} series, {len(traded)} traded by once")
        weeks = g.week.to_numpy()
        uniq = np.unique(weeks)
        idx = {w: np.flatnonzero(weeks == w) for w in uniq}
        draws = [
            np.concatenate([idx[w] for w in rng.choice(uniq, len(uniq))])
            for _ in range(2000)
        ]
        base = np.log(g.once_w.to_numpy())
        print(
            f"{'policy':>6} | {'orders':>6} {'fees':>7} | {'P&L/series':>10} {'logG/series':>11} | {'logG vs once [95%]':>26}"
        )
        for policy in POLICIES:
            lg = np.log(g[f"{policy}_w"].to_numpy())
            diff = lg - base
            boot = np.array([diff[d].mean() for d in draws])
            lo, hi = np.quantile(boot, [0.025, 0.975])
            print(
                f"{policy:>6} | {g[f'{policy}_legs'].sum():>6} {g[f'{policy}_fees'].sum():>7.3f} | "
                f"{(g[f'{policy}_w'] - 1).mean() * 1e4:>8.1f}bp {lg.mean() * 1e4:>9.1f}bp | "
                f"{diff.mean() * 1e4:>+8.2f}bp [{lo * 1e4:+.2f}, {hi * 1e4:+.2f}]"
            )


if __name__ == "__main__":
    main()
