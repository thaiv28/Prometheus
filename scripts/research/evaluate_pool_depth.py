"""
evaluate_pool_depth.py: does champion-pool depth add to FORGE?

The series research (`docs/research/series_independence.md`) found that the
difference in two teams' champion-pool depth (`champion_pools.py`: the starters'
effective number of champions over the 180 days before a game) predicts results
beyond our call. This scores FORGE with the depth gap added as a third input on
the forecast backtest's games (`evaluate_metrics.py`'s frame, the same
out-of-year win curves and Form), against the published FORGE on the same games:

- Domestic (LCK, LPL, LEC, LCS): Elo + Form against Elo + Form + depth.
- International (teams from two major leagues): Elo against Elo + depth.
- Within other leagues (both teams with Form): Elo + Form against Elo + Form + depth.

Fixed before scoring: the 180-day window, depth as the gap in mean effective pool
size, a missing pool (fewer than four starters with a game in the window) as a gap
of 0. Controls: experience alone (the gap in log games in the window, which pool
depth follows) and depth with experience.

Usage:
    uv run python scripts/research/evaluate_pool_depth.py --out docs/research/pool_depth_report.md
"""

import argparse
import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_metrics as em
from champion_pools import WINDOW_DAYS, team_pools

from prometheus.evaluation import (
    game_losses,
    other_league_games,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

MAJORS = [l.value for l in ALL_MAJOR_LEAGUES]
# (label, extra inputs beyond the published ones)
VARIANTS = [
    ("+ depth", ["depth"]),
    ("+ experience (control)", ["experience"]),
    ("+ depth + experience", ["depth", "experience"]),
]


def add_pool_gaps(frame, pools, team, opponent):
    """Add `depth` and `experience` gaps (team minus opponent; missing is 0) and
    `has_pools` (both teams have one)."""
    out = {}
    for col in ("depth", "experience"):
        values = pools[col] if col == "depth" else np.log1p(pools[col])
        mine = values.reindex(
            pd.MultiIndex.from_arrays([frame["gameid"], frame[team]])
        ).to_numpy()
        theirs = values.reindex(
            pd.MultiIndex.from_arrays([frame["gameid"], frame[opponent]])
        ).to_numpy()
        out[col] = mine - theirs
    has = ~np.isnan(out["depth"])
    return frame.assign(
        depth=np.nan_to_num(out["depth"]),
        experience=np.nan_to_num(out["experience"]),
        has_pools=has,
    )


def compare(frame, base_inputs, label):
    """Rows of a table: each variant against the base on `frame`, all games and slices."""
    base = game_losses(out_of_year_probabilities(frame, base_inputs), frame["won"])
    slices = [
        ("All", np.ones(len(frame), dtype=bool)),
        ("2022 on", (frame["year"] >= 2022).to_numpy()),
        ("2025 on (fearless)", (frame["year"] >= 2025).to_numpy()),
        ("Both teams with a pool", frame["has_pools"].to_numpy()),
    ]
    lines = [
        f"\n### {label}: {len(frame):,} games, {frame['year'].min()}–{frame['year'].max()}\n",
        f"Base: {' + '.join(base_inputs)}. Δ is variant minus base log loss "
        "(negative is better), paired bootstrap over games.\n",
        "| Variant | Games | Base log loss | Variant log loss | Δ (95% CI) |",
        "|---|---|---:|---:|---|",
    ]
    for name, extra in VARIANTS:
        var = game_losses(
            out_of_year_probabilities(frame, base_inputs + extra), frame["won"]
        )
        for slice_name, mask in slices:
            b = base["log_loss"].to_numpy()[mask]
            v = var["log_loss"].to_numpy()[mask]
            mean, lo, hi = paired_bootstrap(v, b)
            lines.append(
                f"| {name}, {slice_name.lower()} | {int(mask.sum()):,} | {b.mean():.4f} "
                f"| {v.mean():.4f} | {mean:+.4f} ({lo:+.4f} to {hi:+.4f}) |"
            )
    return lines


def depth_over_experience(frame, pools):
    """Depth added to Elo + Form + experience, and experience's gain by how
    experienced the less experienced team is (games in the window)."""
    base = ["elo_live", "form"]
    loss = {
        k: game_losses(out_of_year_probabilities(frame, base + extra), frame["won"])[
            "log_loss"
        ].to_numpy()
        for k, extra in (
            ("base", []),
            ("exp", ["experience"]),
            ("both", ["experience", "depth"]),
        )
    }
    mean, lo, hi = paired_bootstrap(loss["both"], loss["exp"])
    lines = [
        f"\nDepth added to Elo + Form + experience: {mean:+.4f} ({lo:+.4f} to {hi:+.4f}).\n",
        "Experience's gain over Elo + Form by the less experienced team's mean games "
        f"per starter in the {WINDOW_DAYS} days before:\n",
        "| Fewer games | Games | Δ (95% CI) |",
        "|---|---:|---|",
    ]
    exp = pools["experience"]
    least = np.fmin(
        exp.reindex(
            pd.MultiIndex.from_arrays([frame["gameid"], frame["teamid"]])
        ).to_numpy(),
        exp.reindex(
            pd.MultiIndex.from_arrays([frame["gameid"], frame["opponent_teamid"]])
        ).to_numpy(),
    )
    for low, high, label in (
        (0, 10, "Under 10"),
        (10, 25, "10–25"),
        (25, np.inf, "25+"),
    ):
        m = (least >= low) & (least < high)
        mean, lo, hi = paired_bootstrap(loss["exp"][m], loss["base"][m])
        lines.append(
            f"| {label} | {int(m.sum()):,} | {mean:+.4f} ({lo:+.4f} to {hi:+.4f}) |"
        )
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    years = em.get_available_years(ALL_MAJOR_LEAGUES)
    games, results, timeline = (
        em.load_games(),
        em.load_results(),
        em.load_elo_timeline(),
    )
    states = em.form_states()
    frame = em.backtest(games, results, timeline, years)
    relative = em.out_of_year_form(frame, states)
    frame = em.add_form(frame, states, relative)
    pools = team_pools()
    frame = add_pool_gaps(frame, pools, "blue_id", "red_id")

    pairs = em.load_pair_games()
    other = other_league_games(pairs, INTERNATIONAL_LEAGUES, MAJORS)
    other = other.assign(
        form=em.form_gap(
            relative, other["gameid"], other["teamid"], other["opponent_teamid"]
        )
    )
    other = other[other["form"].notna()].reset_index(drop=True)
    other = add_pool_gaps(other, pools, "teamid", "opponent_teamid")

    same = (frame["blue_league"] == frame["red_league"]).to_numpy()
    domestic = frame[same & (frame["test_set"] == "Domestic").to_numpy()]
    international = frame[(frame["test_set"] == "International").to_numpy() & ~same]

    lines = [
        f"## Pool depth in FORGE ({datetime.date.today().isoformat()})\n",
        f"Generated by `scripts/research/evaluate_pool_depth.py`. Pool window "
        f"{WINDOW_DAYS} days; depth gap in effective champions, experience gap in "
        "log games; a missing pool is a gap of 0. Each curve is fit on the other "
        "seasons (`out_of_year_probabilities`), as in `evaluate_metrics.py`.\n",
    ]
    lines += compare(domestic.reset_index(drop=True), ["elo_live", "form"], "Domestic")
    lines += compare(
        international.reset_index(drop=True), ["elo_live"], "International"
    )
    lines += compare(other, ["elo_live", "form"], "Within other leagues")
    lines += depth_over_experience(other, pools)
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
