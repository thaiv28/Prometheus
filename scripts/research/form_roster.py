"""
form_roster.py: should Form forget a team's stats when its roster changes?

Form's running state belongs to the team id, so a rebuilt roster inherits the old
roster's stats, while Elo moves with the players. `form.form_states(rosters=...)`
scales a team's carried state by retained ** p, retained being the share of this
game's starters who started its previous game. Grid, fixed before scoring:

- **season**: at a new season only, on top of `CARRY` (carry × retained ** p);
- **season, no carry**: at a new season only, instead of `CARRY` (retained ** p);
- **change**: at every lineup change, and at a new season on top of `CARRY`;

each with p in {0.5, 1, 2}. Tuned on seasons up to 2021 (objective: mean FORGE log
loss over domestic major-league and within-other-league games, games-weighted;
curves and Form weights fit out of year within those seasons), the best variant is
reported on 2022 onwards (curves and Form weights fit out of year within those
seasons) against published Form on the same games, paired bootstrap over games:
FORGE domestic, international (cross-region, Elo alone, so unchanged), within
other leagues, and each within 10 games of a starter change.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/form_roster.py --out docs/research/form_roster.md
"""

import argparse
import datetime
import itertools
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_metrics as em

from prometheus import elo, form
from prometheus.evaluation import (
    game_losses,
    other_league_games,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.matches import get_available_years
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

TRAIN_LAST = 2021
SLICE_GAMES = em.ROSTER_SLICE_GAMES
GRID = [
    {"label": label, "roster_power": p, **params}
    for (label, params), p in itertools.product(
        [
            ("season", {"roster_at": "season"}),
            ("season, no carry", {"roster_at": "season", "carry": 1.0}),
            ("change", {"roster_at": "change"}),
        ],
        [0.5, 1.0, 2.0],
    )
]


def load():
    years = get_available_years(ALL_MAJOR_LEAGUES)
    games, results, timeline = (
        em.load_games(),
        em.load_results(),
        em.load_elo_timeline(),
    )
    frame = em.backtest(games, results, timeline, years)
    other = other_league_games(em.load_pair_games(), INTERNATIONAL_LEAGUES, em.MAJORS)
    context = em.load_roster_context()["since_change"]
    since = np.minimum(
        context.reindex(
            pd.MultiIndex.from_arrays([other["gameid"], other["teamid"]])
        ).to_numpy(),
        context.reindex(
            pd.MultiIndex.from_arrays([other["gameid"], other["opponent_teamid"]])
        ).to_numpy(),
    )
    other = other.assign(since_change=since).reset_index(drop=True)
    adjusted = form.opponent_adjust(form.load_form_games())
    return frame, other, adjusted, elo.load_rosters()


def section_losses(frame, other, states, years):
    """Per-game FORGE log loss by section on `years`, curves and Form weights fit
    out of year within them."""
    fr = frame[frame["year"].isin(years)].reset_index(drop=True)
    relative = em.out_of_year_form(fr, states)
    fr = em.add_form(fr, states, relative)
    p = em.forge_probabilities(fr)
    loss = game_losses(p, fr["won"])["log_loss"].to_numpy()
    oth = other[other["year"].isin(years)].reset_index(drop=True)
    oth = oth.assign(
        form=em.form_gap(relative, oth["gameid"], oth["teamid"], oth["opponent_teamid"])
    )
    oth = oth[oth["form"].notna()].reset_index(drop=True)
    oth_loss = game_losses(
        out_of_year_probabilities(oth, ["elo_live", "form"]), oth["won"]
    )["log_loss"].to_numpy()
    dom = (fr["test_set"] == "Domestic").to_numpy()
    recent = (fr["since_change"] <= SLICE_GAMES).to_numpy()
    oth_recent = (oth["since_change"] <= SLICE_GAMES).to_numpy()
    return {
        "Domestic": loss[dom],
        f"Domestic, within {SLICE_GAMES} games of a starter change": loss[dom & recent],
        "International": loss[(fr["test_set"] == "International").to_numpy()],
        "Within other leagues": oth_loss,
        f"Within other leagues, within {SLICE_GAMES} games of a starter change": oth_loss[
            oth_recent
        ],
    }


def objective(sections):
    return np.concatenate(
        [sections["Domestic"], sections["Within other leagues"]]
    ).mean()


def states_for(adjusted, rosters, variant):
    params = {k: v for k, v in variant.items() if k != "label"}
    return form.form_states(adjusted, rosters=rosters, **params)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--out", help="Write the report to this Markdown file")
    args = parser.parse_args()

    frame, other, adjusted, rosters = load()
    years = sorted(frame["year"].unique())
    train = [y for y in years if y <= TRAIN_LAST]
    test = [y for y in years if y > TRAIN_LAST]
    base_states = form.form_states(adjusted)

    base_train = section_losses(frame, other, base_states, train)
    rows = [("Form without rosters", "—", objective(base_train))]
    best, best_obj = None, np.inf
    for variant in GRID:
        obj = objective(
            section_losses(frame, other, states_for(adjusted, rosters, variant), train)
        )
        print(f"{variant['label']} p={variant['roster_power']}: {obj:.5f}")
        rows.append((variant["label"], variant["roster_power"], obj))
        if obj < best_obj:
            best, best_obj = variant, obj

    base_test = section_losses(frame, other, base_states, test)
    var_test = section_losses(frame, other, states_for(adjusted, rosters, best), test)

    lines = [
        f"## Roster-aware Form ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/form_roster.py`. Form's carried state scaled by "
        "retained ** p (share of this game's starters who started the team's previous "
        f"game). Tuned on {train[0]}–{train[-1]}, reported on {test[0]}–{test[-1]}. "
        "Δ is variant minus published FORGE log loss (negative is better), paired "
        "bootstrap over games.\n",
        "### Tuning (FORGE log loss, domestic + within other leagues)\n",
        "| Variant | p | Objective | vs published |",
        "|---|---:|---:|---:|",
    ]
    for label, p, obj in rows:
        lines.append(f"| {label} | {p} | {obj:.5f} | {obj - rows[0][2]:+.5f} |")
    lines += [
        f"\nChosen: **{best['label']}, p = {best['roster_power']}**.\n",
        "### Held out\n",
        "| Section | Games | Published | Variant | Δ (95% CI) |",
        "|---|---:|---:|---:|---|",
    ]
    for section, base in base_test.items():
        var = var_test[section]
        mean, lo, hi = paired_bootstrap(var, base)
        lines.append(
            f"| {section} | {len(base):,} | {base.mean():.4f} | {var.mean():.4f} "
            f"| {mean:+.4f} ({lo:+.4f} to {hi:+.4f}) |"
        )
    report = "\n".join(lines) + "\n"
    print(report)
    if args.out:
        Path(args.out).write_text(report)


if __name__ == "__main__":
    main()
