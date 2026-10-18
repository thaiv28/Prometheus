"""Fixed protocol before test scoring, 2026-10-17; one candidate, no tuning.

Add one whole seven-feature block to v2: log(1+career distinct-champion count), career
pick concentration (sum of squared champion shares), pick among the player's
three most-played champions (ties alphabetical), champion-specific prior lane
gold and XP differences at 15 above the player's own prior mean (shrink 100,
units 1000), role different from the player's career modal role, and different
from the team's previous-day role incumbent. Flags are zero without history.
Incumbents use the chronologically last map on each previous day. Pools/roles
use all available prior games; lane data use only player_stats available rows.
No current-day information updates any history until every row is scored.
Five roles summed blue-minus-red; keep v2's four original features. Fit each
2021..2026 test year on 2019..Y-1 using v2's logistic settings and same games.
Primary candidate-v2 paired series bootstrap, all/majors/LPL/international/other,
years and before2025. Report lane coverage by league. No exploratory variants;
2025-26 already viewed while choosing v2. Research only, no production change.
"""

import argparse
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
import draft_walkforward as dw

EXTRA = [
    "breadth",
    "depth",
    "top_pool",
    "lane_gold",
    "lane_xp",
    "role_swap",
    "substitute",
]


def lane_rows():
    with sqlite3.connect(f"file:{dw.DB_PATH}?mode=ro", uri=True) as conn:
        return pd.read_sql(
            "SELECT gameid, playerid, teamid, "
            "goldat15-opp_goldat15 AS gold, "
            "xpat15-opp_xpat15 AS xp FROM player_stats",
            conn,
        )


def features(rows, lanes):
    rows = rows.merge(lanes, on=["gameid", "playerid", "teamid"], how="left")
    rows["observed"] = rows.gold.notna().astype(float)
    # Missing snapshots contribute no count and no sum to either historical mean.
    observed = rows[["playerid", "champion", "day", "gold", "xp", "observed"]].copy()
    observed[["gold", "xp"]] = observed[["gold", "xp"]].fillna(0)
    own = dw.prior_days(observed, ["playerid"], ["gold", "xp", "observed"])
    champ = dw.prior_days(
        observed, ["playerid", "champion"], ["gold", "xp", "observed"]
    )
    for j, name in enumerate(["lane_gold", "lane_xp"]):
        avg = np.divide(
            own[:, j], own[:, 2], out=np.zeros(len(rows)), where=own[:, 2] > 0
        )
        rows[name] = (champ[:, j] - champ[:, 2] * avg) / (champ[:, 2] + 100) / 1000
    rows["lane_history"] = champ[:, 2] > 0
    pools, roles, incumbents = defaultdict(Counter), defaultdict(Counter), {}
    output = []
    for _, group in rows.groupby("day", sort=True):
        for r in group.itertuples():
            pool, role = pools[r.playerid], roles[r.playerid]
            total = sum(pool.values())
            top = sorted(pool, key=lambda c: (-pool[c], c))[:3]
            modal = min(role, key=lambda p: (-role[p], p)) if role else r.position
            incumbent = incumbents.get((r.teamid, r.position), r.playerid)
            output.append(
                (
                    r.Index,
                    np.log1p(len(pool)),
                    sum(n * n for n in pool.values()) / total**2 if total else 0,
                    float(r.champion in top),
                    float(r.position != modal),
                    float(r.playerid != incumbent),
                )
            )
        for r in group.sort_values(["date", "gameid"]).itertuples():
            pools[r.playerid][r.champion] += 1
            roles[r.playerid][r.position] += 1
            incumbents[r.teamid, r.position] = r.playerid
    added = pd.DataFrame(
        output,
        columns=["index", "breadth", "depth", "top_pool", "role_swap", "substitute"],
    ).set_index("index")
    return rows.join(added)


def score(games):
    scored, coefs = [], []
    for year in dw.TEST_YEARS:
        train = games[games.year.between(dw.FIT_FROM, year - 1)]
        test = games[games.year == year].copy()
        if test.empty:
            continue
        for label, cols in [
            ("v2", ["forge_logit", *dw.FEATURES]),
            ("candidate", ["forge_logit", *dw.FEATURES, *EXTRA]),
        ]:
            model = dw._fit(train, cols)
            test[label] = model.predict_proba(test[cols].to_numpy())[:, 1]
            if label == "candidate":
                coefs.append((year, dict(zip(cols, model.coef_[0]))))
        scored.append(test)
    return pd.concat(scored, ignore_index=True), coefs


def report(scored, coefs, elapsed):
    lines = [
        "# Draft player features: fixed walk-forward candidate",
        "",
        __doc__.strip(),
        "",
        f"Feature construction/scoring {elapsed:.1f} seconds (cached production calls; bootstrap reporting excluded). One candidate; no exploratory variants.",
        "",
        "| Slice | Games | v2 LL | Candidate LL | Candidate − v2 (series-bootstrap 95%) |",
        "|---|---:|---:|---:|---|",
    ]
    for name, frame in [
        *dw.slices(scored),
        ("before 2025", scored[scored.year < 2025]),
        *[(str(y), scored[scored.year == y]) for y in dw.TEST_YEARS],
    ]:
        if frame.empty:
            continue
        a, b, d, lo, hi = dw.paired(frame, "candidate", "v2")
        lines.append(
            f"| {name} | {len(frame):,} | {b:.5f} | {a:.5f} | {d:+.5f} ({lo:+.5f} to {hi:+.5f}) |"
        )
    lines += [
        "",
        "## Lane snapshot coverage",
        "",
        "Shares of player rows with a current snapshot (diagnostic only) and prior champion snapshot history, on the scored games. Current snapshots never enter their own features.",
        "",
        "| Slice | Current snapshot | Prior champion snapshot |",
        "|---|---:|---:|",
    ]
    for name, frame in dw.slices(scored):
        lines.append(
            f"| {name} | {frame.snapshot_coverage.mean():.1%} | {frame.history_coverage.mean():.1%} |"
        )
    lines += [
        "",
        "## Added-feature coefficients",
        "",
        "| Year | " + " | ".join(EXTRA) + " |",
        "|---|" + "---:|" * len(EXTRA),
    ]
    for year, coef in coefs:
        lines.append(
            f"| {year} | " + " | ".join(f"{coef[x]:+.4f}" for x in EXTRA) + " |"
        )
    lines += [
        "",
        "Limits: career pools mix changing metas; role/substitute flags are historical proxies, not confirmed lineup announcements. LPL missing snapshots shrink lane signals toward zero. FORGE upstream weights were fit using years included here; 2025–26 were already viewed in v2. No tradable edge or prospective performance established.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/draft_player_feats.md"
    )
    args = parser.parse_args()
    start = time.monotonic()
    print("Loading rows and player features", flush=True)
    rows = features(dw.load_rows(), lane_rows())
    print("Building v2 features", flush=True)
    rows = dw.player_features(rows)
    games = dw.game_table(rows, dw.synergy(rows))
    side = rows.groupby(["gameid", "side"])[EXTRA].sum().unstack("side")
    for name in EXTRA:
        games[name] = games.gameid.map(side[name]["Blue"] - side[name]["Red"])
    coverage = rows.groupby("gameid")[["observed", "lane_history"]].mean()
    games["snapshot_coverage"] = games.gameid.map(coverage.observed)
    games["history_coverage"] = games.gameid.map(coverage.lane_history)
    games = games[games.year >= dw.FIT_FROM].merge(
        pd.read_pickle(dw.CACHE / "forge.pkl"), on="gameid"
    )
    games["forge_logit"] = dw._logit(games.p_forge)
    target = ROOT / "data/research/draft_v2"
    target.mkdir(parents=True, exist_ok=True)
    games.to_pickle(target / "player_feats_games.pkl")
    print("Scoring frozen candidate", flush=True)
    scored, coefs = score(games)
    scored.to_pickle(target / "player_feats_scored.pkl")
    args.out.write_text(report(scored, coefs, time.monotonic() - start))
    print(args.out, flush=True)


if __name__ == "__main__":
    main()
