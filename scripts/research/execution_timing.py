"""When should the executor buy? Hourly replay of the blended net-edge rule.

Offline only: no fetching, fitting or log writes. Inputs are the calibration
audit's `rebuilt.csv` (raw FORGE/Elo series chance from ratings before the
start−12h day) and the cached hourly Kalshi candles in `data/markets/`.
Rules were fixed before scoring:

- At each hourly close from 12h before start to start, the backed side's
  blended chance (packaged monthly snapshot) minus cost minus the executor's
  fee bound must be positive, as `core.plan_order` requires.
- `alert`: first such hour with at least 6h lead (today's alerts, bought at once).
- `delay k`: an alerted fixture bought k hours later only if the edge is still
  positive then, uncapped or capped at the alert's cost (today's executor cap).
- `anytime`: first such hour up to start (the executor deciding by itself).

Each bet buys one contract at the hour's best cost plus 7% quadratic paper fees.
Intervals resample calendar weeks (4,000 draws, seed 42).
"""

import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus import market_blend, markets
from prometheus.alert_contract import TRADE_GROUPS
from prometheus.execution.core import fee_bound

HOURS = range(12, -1, -1)  # lead in hours; 0 is the last close before start
FIRST, HOLDOUT = "2026-05-01", "2026-10-20"  # first blend snapshot; forward holdout


def fresh_book(candles, cutoff):
    """Latest valid hourly close ending within one hour before cutoff."""
    valid = [c for c in candles if 0 <= cutoff - c["end_period_ts"] <= 3600]
    return markets.book_at(sorted(valid, key=lambda c: c["end_period_ts"]), cutoff)


def quotes(row, event, cache):
    """{lead: (team1 mid, cost1, cost2)} from both contracts' hourly closes."""
    books = []
    for m in event["markets"]:
        path = cache / "candles" / f"{m['ticker']}.json"
        if path.exists():
            books.append((m["side"] == event["team1"], json.loads(path.read_text())))
    out = {}
    start = row.start.timestamp()
    for lead in HOURS:
        at = start - lead * 3600
        mids, costs = [], [np.nan, np.nan]
        for first, candles in books:
            bid, ask = fresh_book(candles, at)
            if bid is None or ask - bid > markets.MAX_SPREAD:
                continue
            side = 0 if first else 1
            mids.append((bid + ask) / 2 if side == 0 else 1 - (bid + ask) / 2)
            for i, cost in ((side, ask), (1 - side, 1 - bid)):
                costs[i] = cost if np.isnan(costs[i]) else min(costs[i], cost)
        if mids:
            out[lead] = (float(np.mean(mids)), *costs)
    return out


def signal(raw, quote, at):
    """(side, cost, chance, net edge) for a positive executor edge, else None."""
    mid, *costs = quote
    blend = market_blend.estimate(raw, mid, at.isoformat())
    if blend is None:
        return None
    for side, p in ((0, blend["probability"]), (1, 1 - blend["probability"])):
        cost = costs[side]
        if np.isnan(cost) or not 0 < cost < 1:
            continue
        price = Decimal(str(round(cost, 4)))
        edge = p - cost - float(fee_bound(price, 1, Decimal(".07"), Decimal(".0001")))
        if edge > 0:
            return side, cost, p, edge
    return None


def bet(row, side, cost, lead, quote_close):
    fee = 0.07 * cost * (1 - cost)
    won = row.won if side == 0 else 1 - row.won
    close = quote_close if side == 0 else 1 - quote_close
    return {
        "event_ticker": row.event_ticker,
        "week": row.week,
        "group": row.group,
        "lead": lead,
        "cost": cost,
        "outlay": cost + fee,
        "profit": won - cost - fee,
        "clv": close - cost,
    }


def replay(frame, events, cache):
    policies = {"alert": [], "anytime": []}
    for k in (1, 2, 3):
        policies[f"delay {k} uncapped"] = []
        policies[f"delay {k} capped"] = []
    for row in frame.itertuples():
        event = events.get(row.event_ticker)
        if event is None:
            continue
        book = quotes(row, event, cache)
        if 0 not in book:
            continue  # no closing quote to score CLV
        close = book[0][0]
        signals = {
            lead: s
            for lead in HOURS
            if lead in book
            and (s := signal(row.p, book[lead], row.start - pd.Timedelta(hours=lead)))
        }
        if signals:
            lead = max(signals)
            policies["anytime"].append(bet(row, *signals[lead][:2], lead, close))
        early = [lead for lead in signals if lead >= 6]
        if not early:
            continue
        lead = max(early)
        side, cost = signals[lead][:2]
        policies["alert"].append(bet(row, side, cost, lead, close))
        for k in (1, 2, 3):
            later = signals.get(lead - k)
            if later is None or later[0] != side:
                continue
            item = bet(row, side, later[1], lead - k, close)
            policies[f"delay {k} uncapped"].append(item)
            if later[1] <= cost:
                policies[f"delay {k} capped"].append(item)
    return {name: pd.DataFrame(rows) for name, rows in policies.items()}


def interval(bets, weeks, stat, repeats=4000):
    rng = np.random.default_rng(42)
    by_week = {w: bets[bets.week == w] for w in weeks}
    draws = []
    for _ in range(repeats):
        sample = pd.concat([by_week[w] for w in rng.choice(weeks, len(weeks))])
        draws.append(stat(sample) if len(sample) else np.nan)
    return np.nanpercentile(draws, [2.5, 97.5])


def roi(bets):
    return bets.profit.sum() / bets.outlay.sum()


def line(name, bets, weeks):
    if bets.empty:
        return f"| {name} | 0 | | | | |"
    lo, hi = interval(bets, weeks, roi)
    return (
        f"| {name} | {len(bets)} | {bets.profit.sum():+.2f} | {roi(bets):+.1%} "
        f"({lo:+.1%} to {hi:+.1%}) | {bets.clv.mean():+.3f} | {bets.lead.median():.0f}h |"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuilt", type=Path, required=True)
    parser.add_argument("--cache", type=Path, default=Path("data/markets"))
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    frame = pd.read_csv(args.rebuilt, parse_dates=["start"])
    frame = frame[
        (frame.start >= pd.Timestamp(FIRST, tz="UTC"))
        & (frame.start < pd.Timestamp(HOLDOUT, tz="UTC"))
        & frame.group.isin(TRADE_GROUPS)
    ]
    events = {
        e["event_ticker"]: e
        for e in markets.events(json.loads((args.cache / "KXLOLGAME.json").read_text()))
    }
    bets = replay(frame, events, args.cache)
    weeks = sorted(frame.week.unique())
    alert, anytime = bets["alert"], bets["anytime"]
    late = anytime[anytime.lead < 6]
    rows = [
        line("Alert (≥6h lead, buy at once)", alert, weeks),
        line("Anytime (first edge up to start)", anytime, weeks),
        line("… added: first edge under 6h", late, weeks),
    ]
    for k in (1, 2, 3):
        uncapped, capped = bets[f"delay {k} uncapped"], bets[f"delay {k} capped"]
        above = uncapped[~uncapped.event_ticker.isin(capped.event_ticker)]
        rows += [
            line(f"Delay {k}h, capped at alert cost", capped, weeks),
            line(f"Delay {k}h, uncapped", uncapped, weeks),
            line("… added: cost above alert", above, weeks),
        ]
    digest = hashlib.sha256(args.rebuilt.read_bytes()).hexdigest()
    report = "\n".join(
        [
            f"{len(frame)} series, {FIRST} to {HOLDOUT} (exclusive), trade groups; "
            f"rebuilt.csv SHA256 {digest[:16]}.",
            "",
            "| Policy | Bets | Profit ($/contract) | ROI (95%) | CLV | Median lead |",
            "|---|---:|---:|---:|---:|---:|",
            *rows,
        ]
    )
    print(report)
    if args.out:
        args.out.write_text(report + "\n")


if __name__ == "__main__":
    main()
