"""Pregame sizing backtest: Kelly fraction x per-series cap on the blend's picks.

Mirrors production: monthly earlier-only blend (scripts/fit_market_blend.fit),
buy the ask when after-fee edge > 0, TRADE_GROUPS, Cloud9 veto, Kelly on free
capital (seed + realized - held), $50 order/exposure caps, $100 UTC-day spend.
Bets settle 4 h after scheduled start. Not modelled: the anti-NA international
veto (no team homes in the input), book depth, partial fills.

Usage: python scripts/research/pregame_sizing.py REBUILT_CSV
"""

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("csv", type=Path, help="Rebuilt pregame market CSV")
args = parser.parse_args()
repo, src = Path(__file__).resolve().parents[2], args.csv
sys.path[:0] = [str(repo / "scripts"), str(repo)]
from fit_market_blend import fit

from prometheus.alert_contract import TRADE_GROUPS

SEED, ORDER, EXPOSURE, DAY = 50.0, 50.0, 50.0, 100.0
d = pd.read_csv(src, parse_dates=["start", "decision", "result_available"])
d = d[d.group.isin(TRADE_GROUPS)]
d = d[
    ~(
        d.team1.str.casefold().str.contains("cloud9")
        | d.team2.str.casefold().str.contains("cloud9")
    )
]
lg = lambda p: np.log(np.clip(p, 1e-6, 1 - 1e-6) / (1 - np.clip(p, 1e-6, 1 - 1e-6)))

rows = []
for month in sorted(d.decision.dt.strftime("%Y-%m").unique()):
    cutoff = pd.Timestamp(month + "-01", tz="UTC")
    f = fit(d, cutoff)
    if f is None:
        continue
    t = d[d.decision.dt.strftime("%Y-%m") == month].copy()
    z = f["market_slope"] * lg(t.market) + f["gap_slope"] * (lg(t.p) - lg(t.market))
    t["blend"] = 1 / (1 + np.exp(-z))
    rows.append(t)
s = pd.concat(rows).sort_values("decision").reset_index(drop=True)


def fee(c):
    return math.ceil(0.07 * c * (1 - c) * 10000 - 1e-9) / 10000


picks = []
for r in s.itertuples():
    best = None
    for side, prob, cost in ((1, r.blend, r.cost1), (2, 1 - r.blend, r.cost2)):
        if not 0 < cost < 0.99:
            continue
        unit = cost + fee(cost)
        edge = prob - unit
        if edge > 0 and (best is None or edge > best[3]):
            best = (side, prob, unit, edge)
    if best:
        won = (r.won == 1) == (best[0] == 1)
        picks.append(
            {
                "decision": r.decision,
                "settle": r.start + pd.Timedelta(hours=4),
                "week": r.week,
                "p": best[1],
                "c": best[2],
                "won": won,
            }
        )
picks = pd.DataFrame(picks)


def simulate(bets, fraction, cap):
    realized, held, open_, day_spend = 0.0, 0.0, [], {}
    peak, worst, largest, placed = SEED, 0.0, 0.0, 0
    for b in bets.itertuples():
        for o in [o for o in open_ if o[0] <= b.decision]:
            open_.remove(o)
            held -= o[1]
            realized += o[2]
        free = SEED + realized - held
        equity = SEED + realized
        peak = max(peak, equity)
        worst = max(worst, 1 - equity / peak)
        if free <= 0:
            continue
        stake = fraction * free * (b.p - b.c) / (1 - b.c)  # Kelly cost
        day = b.decision.date()
        limit = min(ORDER, EXPOSURE - held, DAY - day_spend.get(day, 0), free)
        if cap is not None:
            limit = min(limit, cap * free)
        stake = max(0.0, min(stake, limit))
        if stake < 0.01:
            continue
        placed += 1
        largest = max(largest, stake / free)
        held += stake
        day_spend[day] = day_spend.get(day, 0) + stake
        open_.append((b.settle, stake, stake * (1 / b.c - 1) if b.won else -stake))
    for o in open_:
        realized += o[2]
    equity = SEED + realized
    worst = max(worst, 1 - equity / max(peak, equity))
    return equity / SEED, worst, largest, placed


weeks = picks.week.unique()
rng = np.random.default_rng(0)
samples = [rng.choice(weeks, len(weeks)) for _ in range(400)]
by_week = dict(tuple(picks.groupby("week")))
boot_sets = []
for ws in samples:
    # Resampled weeks keep their own dates; duplicates are shifted a day apart.
    parts = []
    for i, w in enumerate(ws):
        g = by_week[w].copy()
        k = list(ws[:i]).count(w)
        g["decision"] += pd.Timedelta(days=7 * 40 * k)
        g["settle"] += pd.Timedelta(days=7 * 40 * k)
        parts.append(g)
    boot_sets.append(pd.concat(parts).sort_values("decision"))

edge_roi = picks.won / picks.c - 1
print(
    f"series {len(s)} (months {s.decision.dt.strftime('%Y-%m').min()}..{s.decision.dt.strftime('%Y-%m').max()}), "
    f"picks {len(picks)}, flat ROI {edge_roi.mean():+.1%}, mean edge {(picks.p - picks.c).mean() * 100:.1f}c, "
    f"mean price {picks.c.mean():.2f}\n"
)
print(
    f"{'Kelly':>6} {'series cap':>10} | {'ends at':>8} {'worst DD':>9} {'largest':>8} {'bets':>5} | "
    f"{'boot 5%':>8} {'median':>7} {'95%':>6} {'P(lose)':>8}"
)
for fraction in (1.0, 0.5, 0.25):
    for cap in (None, 0.20, 0.10, 0.05):
        m, dd, big, n = simulate(picks, fraction, cap)
        boots = np.array([simulate(b, fraction, cap)[0] for b in boot_sets])
        q = np.quantile(boots, [0.05, 0.5, 0.95])
        print(
            f"{fraction:>6} {('none' if cap is None else f'{cap:.0%}'):>10} | {m:>7.2f}x {dd:>8.0%} {big:>8.0%} {n:>5} | "
            f"{q[0]:>7.2f}x {q[1]:>6.2f}x {q[2]:>5.2f}x {np.mean(boots < 1):>8.0%}"
        )
