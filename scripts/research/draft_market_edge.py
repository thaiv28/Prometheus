"""Draft v2 market edge: fixed protocol before scoring (2026-10-17).

Research only. Reuse draft_walkforward's cached annual out-of-sample shifts.
SPLIT remains 2026-05-01; all market-weight/cap/edge choices use only earlier
maps. These halves were already viewed by v2, so this is retrospective.

Primary entry -60 seconds relative to OE's start; +45 seconds secondary.
Fit a nonnegative shift weight in [0,2], Kalshi logit coefficient fixed at 1,
no intercept, total logistic loss plus 4*w*w/2. For caps .25/.5/1 log-odds,
clip the raw shift then fit the weight. Choose cap and after-fee edge from
.02/.03/.05/.10 by total first-half quarter-Kelly log growth, requiring >=30
first-half bets; deterministic tie order. Freeze on the second half.

Primary paper execution requires a market trade and own-side taker trade
within 30 seconds before entry. Decision uses only entry information, costs
at least the latest side-implied market price and worst own-side trade in
the preceding 30 seconds. Require an own-side trade in (entry, entry+15s]
as a fill proxy; use the worse of the decision cost and those later trades.
Choose side/size/threshold before observing that later window; no cancellation
on an adverse later price, except impossible >=$1 all-in cost. Thus future
trades never choose the side and an adverse fill is kept, even if edge vanishes.
Fee is ceil(.07*q*(1-q)*100)/100 per contract, normalized to all-in stake.
Quarter Kelly fraction is fixed from decision cost, capped at 10% bankroll.
Flat ROI and log growth use identical actual all-in fill costs. Synthetic
fractional bankroll sizing, no simultaneous-series portfolio optimization.
Sensitivity: 120s and 600s stale bounds, and last-only 600s (no future-fill
requirement), all with the primary selected settings unchanged. +45s has
its own first-half selection, secondary only. No post-test variant selection.

Report series-bootstrap 95% intervals, price movement toward the shift at
+1/+3/+5 minutes, by league and favourite/long shot; report missing quotes.
Primary forecast comparisons are fitted market+shift vs v2 weight-one shift
and vs Kalshi on identical maps, rather than the pre-market v2 map call.
No priced pre-2025 data means that requested slice is unavailable.

Run: uv run python scripts/research/draft_market_edge.py --out docs/research/draft_market_edge.md
Offline only: never fetch or write into shared trade/raw directories.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
import draft_walkforward as dw
import evaluate_live as el

from prometheus import markets, schedule
from prometheus.elo import get_latest_elos
from prometheus.evaluation import resamples

CAPS = (0.25, 0.5, 1.0)
EDGES = (0.02, 0.03, 0.05, 0.10)
ENTRIES = (-60, 45)
STALENESS = (30, 120, 600)
CACHE = ROOT / "data/research/draft_market_edge"


def total_cost(q):
    """Conservative per-contract taker fee rounded to the cent."""
    return q + math.ceil(round(0.07 * q * (1 - q) * 100, 8)) / 100


def state(tp, at, stale):
    """Decision state plus later fill proxies; never silently hold a stale price."""
    p = el.price_at(tp, at, stale=stale)
    out = {"market": p}
    for side in (0, 1):
        recent = tp[
            (tp["at"] <= at)
            & (tp["at"] >= at - pd.Timedelta(seconds=stale))
            & (tp.back == side)
        ]
        future = tp[
            (tp["at"] > at)
            & (tp["at"] <= at + pd.Timedelta(seconds=15))
            & (tp.back == side)
        ]
        last = float(recent.cost.iloc[-1]) if len(recent) else np.nan
        now = p if side == 0 else 1 - p if p is not None else np.nan
        out[f"last{side}"] = last
        decision = (
            max(float(recent.cost.max()), now)
            if len(recent) and p is not None
            else np.nan
        )
        out[f"decision{side}"] = decision
        out[f"fill{side}"] = (
            max(decision, float(future.cost.max())) if len(future) else np.nan
        )
    return out


def build():
    """Join cached annual shifts to cached tapes, keeping one event per OE game."""
    baseline = pd.read_pickle(dw.CACHE / "kalshi_maps.pkl")
    duplicates = int(baseline.gameid.duplicated().sum())
    baseline = baseline.drop_duplicates("gameid").set_index("gameid")
    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    by_pair = dict(list(el.oe_games().groupby(["blue", "red"])))
    rows, seen = [], set()
    for event in markets.events(json.loads(el.MARKET_LIST.read_text())):
        hit = el.match_oe_game(event, matcher, by_pair)
        if hit is None:
            continue
        game, blue = hit
        gid = game.gameid
        if gid not in baseline.index or gid in seen:
            continue
        seen.add(gid)
        g = baseline.loc[gid]
        tp = el.tape(event, el.premap_trades(event, game.date, "", fetch=False), blue)
        for entry in ENTRIES:
            at = game.date + pd.Timedelta(seconds=entry)
            for stale in STALENESS:
                s = state(tp, at, stale)
                # Close timestamps are relative to map start, not entry.
                for minute in (1, 3, 5):
                    s[f"close{minute}"] = el.price_at(
                        tp, game.date + pd.Timedelta(minutes=minute), stale=30
                    )
                rows.append(
                    {
                        "gameid": gid,
                        "day": g.day,
                        "year": int(g.day[:4]),
                        "series": g.series,
                        "league": g.league,
                        "won": g.won,
                        "shift": g["shift"],
                        "entry": entry,
                        "stale": stale,
                        **s,
                    }
                )
        if len(seen) % 1000 == 0:
            print(f"tapes {len(seen)}", flush=True)
    return pd.DataFrame(rows), duplicates


def fit_weight(first, cap):
    """Refuse held-out rows so a caller cannot accidentally refit on the test."""
    if (first.day >= dw.SPLIT).any():
        raise ValueError("weight fit includes held-out maps")
    x = first["shift"].clip(-cap, cap).to_numpy()
    z, y = dw._logit(first.market), first.won.to_numpy()

    def objective(w):
        a = z + w * x
        return np.sum(np.logaddexp(0, a) - y * a) + 2 * w * w

    opt = minimize_scalar(objective, bounds=(0, 2), method="bounded")
    choices = [0.0, float(opt.x), 2.0]
    return min(choices, key=objective)


def probability(frame, cap, weight):
    if weight == 0:
        return frame.market.to_numpy(dtype=float)
    return expit(dw._logit(frame.market) + weight * frame["shift"].clip(-cap, cap))


def bets(frame, cap, weight, edge, mode="strict"):
    """Decision/size frozen before adverse fill, at most one bet per map."""
    out = []
    for r, pblue in zip(frame.itertuples(index=False), probability(frame, cap, weight)):
        choices = []
        for side, p in ((0, pblue), (1, 1 - pblue)):
            q = getattr(r, f"last{side}" if mode == "last" else f"decision{side}")
            if not np.isfinite(q) or not 0 < q < 1:
                continue
            cost = total_cost(q)
            if cost >= 1 or p - cost < edge:
                continue
            f = min(0.1, 0.25 * max(0, (p - cost) / (1 - cost)))
            choices.append((p - cost, side, p, q, f))
        if not choices:
            continue
        _, side, p, q, fraction = max(choices, key=lambda x: (x[0], -x[1]))
        actual = q if mode == "last" else getattr(r, f"fill{side}")
        if not np.isfinite(actual) or not 0 < actual < 1:
            continue
        paid = total_cost(actual)
        if paid >= 1:
            continue
        won = bool(r.won) == (side == 0)
        roi = float(won) / paid - 1
        b = {
            "gameid": r.gameid,
            "series": r.series,
            "day": r.day,
            "league": r.league,
            "side": side,
            "p": p,
            "cost": paid,
            "roi": roi,
            "growth": np.log1p(fraction * roi),
            "favourite": (r.market >= 0.5 if side == 0 else r.market <= 0.5),
        }
        for m in (1, 3, 5):
            close = getattr(r, f"close{m}")
            b[f"clv{m}"] = (
                ((close if side == 0 else 1 - close) - paid)
                if pd.notna(close)
                else np.nan
            )
        out.append(b)
    return pd.DataFrame(
        out,
        columns=[
            "gameid",
            "series",
            "day",
            "league",
            "side",
            "p",
            "cost",
            "roi",
            "growth",
            "favourite",
            "clv1",
            "clv3",
            "clv5",
        ],
    )


def select(first):
    if (first.day >= dw.SPLIT).any():
        raise ValueError("policy selection includes held-out maps")
    trials = []
    for cap in CAPS:
        w = fit_weight(first, cap)
        for edge in EDGES:
            b = bets(first, cap, w, edge)
            trials.append(
                {
                    "cap": cap,
                    "weight": w,
                    "edge": edge,
                    "bets": len(b),
                    "growth": float(b.growth.sum()),
                    "roi": float(b.roi.mean()) if len(b) else np.nan,
                }
            )
    valid = [t for t in trials if t["bets"] >= 30]
    return (max(valid, key=lambda t: t["growth"]) if valid else None), trials


def interval(frame, column):
    f = frame.dropna(subset=[column])
    if f.empty:
        return "unavailable"
    values = f[column].to_numpy(dtype=float)
    codes = pd.factorize(f.series)[0]
    groups = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    draws = [values[i].mean() for i in resamples(groups, 2000)]
    return dw._ci(values.mean(), *np.percentile(draws, [2.5, 97.5]))


def no_policy_diagnostics(second, trials):
    """Report every declared cap without selecting a test-period winner."""
    lines = [
        "",
        "No policy means zero second-half bets and zero total Kelly log growth; per-bet ROI, growth intervals, favourite/long-shot returns and fill sensitivities are not estimable. The development minimum is retained unchanged.",
        "",
        "### Forecast diagnostics (all three declared caps; none selected)",
        "",
        "| Cap | Slice | Maps | Fitted − v2 weight-one shift LL (95%) | Fitted − Kalshi LL (95%) |",
        "|---:|---|---:|---|---|",
    ]
    for cap in CAPS:
        weight = next(t["weight"] for t in trials if t["cap"] == cap)
        f = second.assign(
            candidate=probability(second, cap, weight),
            v2=expit(dw._logit(second.market) + second["shift"]),
        )
        for label, part in [
            *dw.slices(f),
            *((str(y), g) for y, g in f.groupby("year")),
        ]:
            if not part.empty:
                lines.append(
                    f"| {cap:.2f} | {label} | {len(part)} | {dw._ci(*dw.paired(part, 'candidate', 'v2')[2:])} | {dw._ci(*dw.paired(part, 'candidate', 'market')[2:])} |"
                )
    lines += [
        "",
        "### Second-half movement toward the draft shift",
        "",
        "All eligible maps, independent of the unselected betting policy. Positive means price moves in the shift's direction. Close trades must be ≤30 seconds old; values are probability units. This is price movement rather than executable CLV. No selected bets exist for after-fee CLV.",
        "",
        "| Slice | Map time | Maps with close | Movement (series-bootstrap 95%) |",
        "|---|---|---:|---|",
    ]
    for label, part in dw.slices(second):
        for m in (1, 3, 5):
            move = part.assign(
                move=np.sign(part["shift"]) * (part[f"close{m}"] - part.market)
            )
            lines.append(
                f"| {label} | +{m} min | {move.move.notna().sum()} | {interval(move, 'move')} |"
            )
    return lines


def render(frame, duplicates, elapsed):
    lines = [
        "# Draft v2: market edge under stricter fills",
        "",
        "Protocol fixed in `scripts/research/draft_market_edge.py` before scoring. All choices use maps before 2026-05-01; second-half results never select settings. Twelve cap/edge settings per entry (three fitted capped weights × four edges). Both halves were previously viewed in v2; this is retrospective research, not a fresh holdout.",
        "",
        f"{frame.gameid.nunique():,} unique cached priced OE games; {duplicates} duplicate baseline row removed. Offline cached trades only. Entry times use OE's approximate map start. Primary: −60 s, trades at most 30 s old, a same-side trade in the next 15 s, worse of nearby costs. Fixed side and quarter-Kelly size precede the fill; adverse fills are retained. Per-contract taker fees round upward to a cent. ROI uses all-in dollars, as does Kelly growth. Sensitivities use the primary settings unchanged.",
        "",
        "Kalshi's coefficient is fixed at 1; shift weight in [0,2] has ridge penalty 4. Before-2025 priced maps: unavailable. No order-book/queue/size evidence; nearby trades do not demonstrate an executable fill. Fractional bankroll accounting ignores simultaneous exposure.",
    ]
    policies = {}
    for entry in ENTRIES:
        eligible = frame[
            (frame.entry == entry)
            & (frame.stale == 30)
            & frame.market.between(0.001, 0.999)
        ].copy()
        first, second = (
            eligible[eligible.day < dw.SPLIT],
            eligible[eligible.day >= dw.SPLIT],
        )
        chosen, trials = select(first)
        policies[entry] = chosen
        lines += [
            "",
            f"## Entry {entry:+d} seconds ({'primary' if entry == -60 else 'secondary'})",
            "",
            f"Recent market-price coverage: first half {len(first):,}, second half {len(second):,} maps.",
            "",
            "| Cap | Fitted weight | Edge | First-half bets | First-half ROI | Total log growth |",
            "|---:|---:|---:|---:|---:|---:|",
        ]
        for t in trials:
            lines.append(
                f"| {t['cap']:.2f} | {t['weight']:.3f} | {t['edge']:.2f} | {t['bets']} | {format(t['roi'], '+.4f') if t['bets'] else '—'} | {t['growth']:+.4f} |"
            )
        if chosen is None:
            lines += [
                "",
                "Inconclusive: no setting had 30 first-half fill proxies; no primary policy selected.",
            ]
            lines += no_policy_diagnostics(second, trials)
            continue
        cap, weight, edge = (chosen[k] for k in ("cap", "weight", "edge"))
        lines += [
            "",
            f"Locked policy: cap {cap:.2f}, weight {weight:.3f}, edge {edge:.2f}.",
            "",
            "| Half / fill sensitivity | Maps with price | Bets | Flat ROI (95%) | Kelly log growth/bet (95%) |",
            "|---|---:|---:|---|---|",
        ]
        for half, test in (("first", False), ("second", True)):
            for stale, mode in (
                (30, "strict"),
                (120, "strict"),
                (600, "strict"),
                (600, "last"),
            ):
                f = frame[
                    (frame.entry == entry)
                    & (frame.stale == stale)
                    & frame.market.between(0.001, 0.999)
                    & ((frame.day >= dw.SPLIT) == test)
                ]
                b = bets(f, cap, weight, edge, mode)
                lines.append(
                    f"| {half}, {stale}s, {mode} | {len(f)} | {len(b)} | {interval(b, 'roi')} | {interval(b, 'growth')} |"
                )
        lines += [
            "",
            "### Second half: fitted market shift against v2 and Kalshi",
            "",
            "| Slice | Maps | Candidate − weight-one v2 shift LL (95%) | Candidate − Kalshi LL (95%) |",
            "|---|---:|---|---|",
        ]
        second = second.assign(
            candidate=probability(second, cap, weight),
            v2=expit(dw._logit(second.market) + second["shift"]),
        )
        for label, f in list(dw.slices(second)) + [
            (str(y), g) for y, g in second.groupby("year")
        ]:
            if len(f):
                lines.append(
                    f"| {label} | {len(f)} | {dw._ci(*dw.paired(f, 'candidate', 'v2')[2:])} | {dw._ci(*dw.paired(f, 'candidate', 'market')[2:])} |"
                )
        b = bets(second, cap, weight, edge)
        lines += [
            "",
            "### Second-half primary fills by league and side",
            "",
            "| Slice | Bets | ROI (95%) | Kelly growth/bet (95%) |",
            "|---|---:|---|---|",
        ]
        groups = (
            [("all", b)]
            + [(str(lg), g) for lg, g in b.groupby("league")]
            + [
                ("favourite", b[b.favourite == True]),
                ("long shot", b[b.favourite == False]),
            ]
        )
        for label, g in groups:
            lines.append(
                f"| {label} | {len(g)} | {interval(g, 'roi')} | {interval(g, 'growth')} |"
            )
        lines += [
            "",
            "### Second-half price movement",
            "",
            "Positive move: blue price rises when the draft shift is positive (and conversely). Trade at each close must be ≤30 s old. CLV includes fill cost and fees; each interval resamples series.",
            "",
            "| Map time | Maps with entry and close | Move toward shift (95%) | Bets with close | After-fee CLV (95%) |",
            "|---|---:|---|---:|---|",
        ]
        for m in (1, 3, 5):
            move = second.assign(
                move=np.sign(second["shift"]) * (second[f"close{m}"] - second.market)
            )
            lines.append(
                f"| +{m} min | {move.move.notna().sum()} | {interval(move, 'move')} | {b[f'clv{m}'].notna().sum()} | {interval(b, f'clv{m}')} |"
            )
        if entry == -60:
            lines += [
                "",
                "Verdict: the primary ROI and Kelly intervals, and fill limitations above, decide whether an edge is established; no subgroup or secondary entry is promoted after scoring.",
            ]
    roots = [
        ROOT / "data",
        ROOT.parent / "Prometheus/data",
        ROOT.parent / "lol-live/data",
    ]
    books = sorted(
        {
            str(p)
            for root in roots
            if root.exists()
            for p in root.rglob("pre_quotes.jsonl")
        }
    )
    lines += [
        "",
        "## Book coverage and limits",
        "",
        f"Local pre_quotes.jsonl files found: {len(books)}. "
        + (
            "; ".join(books)
            if books
            else "No saved pre-map books in the searched local data directories; remote backup storage was not inspected."
        ),
        "",
        "This tests trades as conservative fill proxies. It cannot verify asks, available depth, latency, partial fills, champion availability before the start, or prospective profitability. Market prices are not the book. The 12 development settings and descriptive slices create selection uncertainty; reported intervals condition on the selected first-half policy. No production changes, weights, site or CI jobs.",
        "",
        f"Offline run wall time: {elapsed:.1f} s (timed before report bootstraps).",
    ]
    return "\n".join(lines) + "\n", policies


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--rebuild", action="store_true")
    a = p.parse_args()
    start = time.monotonic()
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "states.pkl"
    if path.exists() and not a.rebuild:
        frame, duplicates = pd.read_pickle(path)
    else:
        frame, duplicates = build()
        pd.to_pickle((frame, duplicates), path)
    report, policies = render(frame, duplicates, time.monotonic() - start)
    a.out.write_text(report)
    (CACHE / "selected.json").write_text(json.dumps(policies, indent=2))
    print(f"wrote {a.out}; total {time.monotonic() - start:.1f}s", flush=True)


if __name__ == "__main__":
    main()
