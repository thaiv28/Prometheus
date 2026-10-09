"""
elo_new_players.py: where should a new player's Elo start?

Player-built Elo seats a new player at the average rating of their league's active
players. Teams fielding players with few career games lose more often than Elo
expects (about 5 points of win chance per extra such player, in every tier), so
that start is too high. This replays Elo (`elo_variants.replay`) with three fixes,
each tuned on seasons up to 2021 and reported on 2022 onwards against Elo before
this research (`BEFORE`) on the same games:

- **Start lower** (`new_player_offset`): a new player's stored rating starts D
  below the league average. Elo is zero-sum inside a league, so a league's mean
  then drifts down with turnover.
- **Start lower, move faster**: the same, plus a player's rating moving m times the
  team's change for their first N games (`provisional_games`, `provisional_factor`).
- **Rookie discount** (`rookie_penalty`, `rookie_games`): a player counts D points
  lower in their first game, the discount fading linearly to nothing over N games.
  It isn't stored in their rating, so league means don't drift.
- **Rookie discount, move faster**: the discount (over 50 games) plus faster moves
  for a player's first 25 games.

Tuning objective, fixed in advance: mean Elo log loss over domestic (major-league)
and within-other-league games up to 2021, games-weighted. Held-out sections
(2022 on): domestic and international Elo and FORGE (`elo_variants.score`),
within other leagues Elo on per-league curves (the published call) and FORGE
(Elo + Form), and cross-league Elo on every league pair.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_new_players.py --out docs/research/elo_new_players.md
"""

import argparse
import datetime
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_variants as ev
import evaluate_metrics as em

from prometheus.evaluation import (
    cross_league_games,
    game_losses,
    other_league_games,
    out_of_year_league_probabilities,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import INTERNATIONAL_LEAGUES

TRAIN_LAST = 2021
# Elo before this research (the comparison baseline): no rookie discount, no faster
# early moves. Every variant starts from it, so the report doesn't change with the
# published defaults in `prometheus/elo.py`.
BEFORE = {
    "new_player_offset": 0,
    "rookie_penalty": 0,
    "rookie_games": 0,
    "provisional_games": 0,
    "provisional_factor": 1.0,
}
DESIGNS = {
    "Start lower": [{"new_player_offset": d} for d in (50, 100, 150, 200, 300, 400)],
    "Start lower, move faster": [
        {
            "new_player_offset": d,
            "provisional_games": n,
            "provisional_factor": m,
        }
        for d in (100, 200, 300)
        for n in (10, 25)
        for m in (1.5, 2, 3)
    ],
    "Rookie discount": [
        {"rookie_penalty": d, "rookie_games": n}
        for d in (25, 50, 75, 100, 150, 200, 300, 400, 600)
        for n in (10, 25, 50, 75, 100)
    ],
    "Rookie discount, move faster": [
        {
            "rookie_penalty": d,
            "rookie_games": 50,
            "provisional_games": 25,
            "provisional_factor": m,
        }
        for d in (50, 100, 200)
        for m in (1.5, 2)
    ],
}


def pair_games(pairs, pre):
    """The DB's pair games with the live Elo gap from replay `pre`."""
    mine = pre.reindex(pd.MultiIndex.from_arrays([pairs["gameid"], pairs["teamid"]]))
    theirs = pre.reindex(
        pd.MultiIndex.from_arrays([pairs["gameid"], pairs["opponent_teamid"]])
    )
    return pairs.assign(elo_live=mine.to_numpy() - theirs.to_numpy())


def other_losses(pairs, pre, years):
    """Within-other-league Elo on per-league curves, curves fit within `years`."""
    other = other_league_games(pair_games(pairs, pre), INTERNATIONAL_LEAGUES, em.MAJORS)
    other = other[other["year"].isin(years)].reset_index(drop=True)
    p = out_of_year_league_probabilities(other)
    return other, game_losses(p, other["won"])["log_loss"].to_numpy()


def cross_losses(pairs, pre, years):
    cross = cross_league_games(pair_games(pairs, pre), INTERNATIONAL_LEAGUES, em.MAJORS)
    cross = cross[cross["year"].isin(years)].reset_index(drop=True)
    p = out_of_year_probabilities(cross, "elo_live")
    return cross, game_losses(p, cross["won"])["log_loss"].to_numpy()


def other_forge_losses(inputs, pairs, pre, years):
    """Within-other-league FORGE (Elo + Form on one curve), Form from the variant's
    opponent adjustment, on games where both teams have Form."""
    states = ev.variant_form_states(inputs, pre)
    frame = ev._with_elo(inputs.frame, pre)
    relative = em.out_of_year_form(frame, states)
    other, _ = other_losses(pairs, pre, years)
    other = other.assign(
        form=em.form_gap(
            relative, other["gameid"], other["teamid"], other["opponent_teamid"]
        )
    )
    other = other[other["form"].notna()].reset_index(drop=True)
    p = out_of_year_probabilities(other, ["elo_live", "form"])
    return other, game_losses(p, other["won"])["log_loss"].to_numpy()


def objective(inputs, pairs, pre, years):
    dom = ev.score(inputs, pre, years=years, forge=False).log_loss(
        "elo_live", "Domestic"
    )
    _, oth = other_losses(pairs, pre, years)
    return np.concatenate([dom, oth]).mean()


def _delta(variant, base):
    mean, lo, hi = paired_bootstrap(variant, base)
    return f"{mean:+.4f} ({lo:+.4f} to {hi:+.4f})"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    years = sorted(inputs.frame["year"].unique())
    train = [y for y in years if y <= TRAIN_LAST]
    test = [y for y in years if y > TRAIN_LAST]
    margin = ev.game_length_margin()
    base_pre = ev.replay(inputs, margin, **BEFORE)

    lines = [
        f"## New players' Elo ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_new_players.py`. Tuned on "
        f"{train[0]}–{train[-1]} (objective: mean Elo log loss over domestic and "
        "within-other-league games), reported on "
        f"{test[0]}–{test[-1]}. Δ is variant minus Elo before it (no discount) log loss (negative is "
        "better), paired bootstrap over games.\n",
        "### Tuning\n",
        "| Design | Best parameters | Train objective | Before |",
        "|---|---|---:|---:|",
    ]
    base_obj = objective(inputs, pairs, base_pre, train)
    chosen = {}
    for design, grid in DESIGNS.items():
        scored = []
        for params in grid:
            pre = ev.replay(inputs, margin, **{**BEFORE, **params})
            scored.append((objective(inputs, pairs, pre, train), params))
            print(f"  {design} {params}: {scored[-1][0]:.5f}", flush=True)
        best_obj, best = min(scored, key=lambda t: t[0])
        chosen[design] = best
        lines.append(f"| {design} | {best} | {best_obj:.5f} | {base_obj:.5f} |")

    base_scores = ev.score(inputs, base_pre, years=test)
    base_other_g, base_other = other_losses(pairs, base_pre, test)
    base_cross_g, base_cross = cross_losses(pairs, base_pre, test)
    base_of_g, base_of = other_forge_losses(inputs, pairs, base_pre, test)
    lines += [
        "\n### Held out\n",
        "| Design | Elo, domestic | Elo, international | FORGE, domestic "
        "| FORGE, international | Elo, other leagues | FORGE, other leagues "
        "| Elo, cross-league |",
        "|---|---|---|---|---|---|---|---|",
        f"| Before (log loss) | {base_scores.log_loss('elo_live', 'Domestic').mean():.4f} "
        f"| {base_scores.log_loss('elo_live', 'International').mean():.4f} "
        f"| {base_scores.log_loss('forge', 'Domestic').mean():.4f} "
        f"| {base_scores.log_loss('forge', 'International').mean():.4f} "
        f"| {base_other.mean():.4f} | {base_of.mean():.4f} | {base_cross.mean():.4f} |",
    ]
    counts = (
        f"Games: domestic {int(base_scores.mask('Domestic').sum()):,}, international "
        f"{int(base_scores.mask('International').sum()):,}, other leagues "
        f"{len(base_other_g):,} (FORGE {len(base_of_g):,}), cross-league "
        f"{len(base_cross_g):,}."
    )
    for design, params in chosen.items():
        pre = ev.replay(inputs, margin, **{**BEFORE, **params})
        s = ev.score(inputs, pre, years=test)
        oth_g, oth = other_losses(pairs, pre, test)
        cr_g, cr = cross_losses(pairs, pre, test)
        of_g, of = other_forge_losses(inputs, pairs, pre, test)
        assert len(oth_g) == len(base_other_g) and len(cr_g) == len(base_cross_g)
        assert len(of_g) == len(base_of_g)
        cells = [
            _delta(s.log_loss(m, t), base_scores.log_loss(m, t))
            for m, t in (
                ("elo_live", "Domestic"),
                ("elo_live", "International"),
                ("forge", "Domestic"),
                ("forge", "International"),
            )
        ] + [_delta(oth, base_other), _delta(of, base_of), _delta(cr, base_cross)]
        lines.append(f"| {design} {params} | " + " | ".join(cells) + " |")
    lines.append(f"\n{counts}\n")
    text = "\n".join(lines) + "\n"
    print(text)
    if args.out:
        args.out.write_text(text)


if __name__ == "__main__":
    main()
