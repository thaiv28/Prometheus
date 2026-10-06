"""
elo_variants_gold.py: gold-based margins of victory for player-built Elo, tuned on
seasons up to 2021 and compared with the published game-length margin on 2022 onward.

Every candidate is tuned with `elo_variants.held_out` (objective: domestic Elo-live log
loss on the training seasons) and reported on the held-out seasons, whatever the result.
The best candidate is picked by its training-season log loss, not its held-out one.

Usage:
    VECLIB_MAXIMUM_THREADS=1 uv run python scripts/elo_variants_gold.py
"""

import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_variants as ev  # noqa: E402

GL = ev.game_length_margin()


def gold_diff(center, scale, lower):
    """Winner gold minus loser gold, logistic into (lower, 1)."""
    return ev.with_fallback(lambda g: ev.bounded(g["w_totalgold"] - g["l_totalgold"], scale, center, lower))


def gold_share(center, scale, lower):
    """Winner's share of both teams' gold, logistic into (lower, 1)."""
    return ev.with_fallback(
        lambda g: ev.bounded(g["w_totalgold"] / (g["w_totalgold"] + g["l_totalgold"]), scale, center, lower)
    )


def gold_per_minute(center, scale, lower):
    """Gold difference per game minute, logistic into (lower, 1)."""
    return ev.with_fallback(
        lambda g: ev.bounded((g["w_totalgold"] - g["l_totalgold"]) / (g["gamelength"] / 60), scale, center, lower)
    )


def gold_and_length(weight, scale):
    """weight x gold-difference score + (1 - weight) x published game-length score."""
    def margin(g):
        gold = ev.bounded(g["w_totalgold"] - g["l_totalgold"], scale, 10000, 0.65)
        return weight * gold + (1 - weight) * GL(g)
    return ev.with_fallback(margin)


def binary():
    """No margin: the winner scores 1."""
    return lambda g: np.ones(len(g))


def game_length_control():
    """The published margin, with only K tuned (a control for the K grid)."""
    return GL


CANDIDATES = [
    ("Control: game length, K tuned", game_length_control, {"K": [14, 17, 20, 24, 28, 32]}),
    ("Binary result (no margin)", binary, {"K": [10, 12, 14, 17, 20, 24]}),
    ("Gold difference", gold_diff,
     {"center": [5000, 10000], "scale": [2500, 5000, 10000], "lower": [0.55, 0.7], "K": [20, 30]}),
    ("Gold share", gold_share,
     {"center": [0.53, 0.55], "scale": [0.01, 0.02, 0.04], "lower": [0.55, 0.7], "K": [20, 30]}),
    ("Gold diff per minute", gold_per_minute,
     {"center": [250, 350], "scale": [75, 150, 300], "lower": [0.55, 0.7], "K": [20, 30]}),
    ("Gold diff + game length blend", gold_and_length,
     {"weight": [0.25, 0.5, 0.75], "scale": [2500, 5000], "K": [20, 30]}),
    # Second pass: the first grids' best share and per-minute points sat on the K and
    # lower-bound edges (K 30, lower 0.55), so extend past them (still training-only).
    ("Gold share (extended grid)", gold_share,
     {"center": [0.55, 0.57], "scale": [0.02], "lower": [0.51, 0.55], "K": [30, 40, 50]}),
    ("Gold diff per minute (extended grid)", gold_per_minute,
     {"center": [350, 450], "scale": [75], "lower": [0.51, 0.55], "K": [30, 40, 50]}),
]


def main():
    start = time.time()
    inputs = ev.load_inputs()
    held_rows, train_rows, picks = [], [], []
    n_points = 0
    for label, make, grid in CANDIDATES:
        t = time.time()
        r = ev.held_out(inputs, make, grid, label)
        n_points += len(ev.param_grid(grid))
        held_rows.append(r.row)
        train_scores = ev.score(inputs, r.pre_match, years=r.train_years)
        train_rows.append(ev.compare(inputs, inputs.baseline_scores(r.train_years), train_scores,
                                     f"{label} {r.params}", years=r.train_years))
        picks.append((r.tuning["objective"].iloc[0], label, r.params))
        print(f"  {label}: {time.time() - t:.1f} s")

    base_train = inputs.baseline_scores(sorted(y for y in inputs.frame["year"].unique() if y <= ev.TUNE_LAST_YEAR),
                                        forge=False)
    print(f"\nBaseline training-season domestic Elo log loss: "
          f"{base_train.log_loss('elo_live', 'Domestic').mean():.5f}")
    print("\nTraining objective (domestic Elo log loss, 2014–2021), best first:")
    for obj, label, params in sorted(picks, key=lambda p: p[0]):
        print(f"  {obj:.5f}  {label} {params}")
    print(f"\nCandidates: {len(CANDIDATES)} families, {n_points} grid points")
    print("\n## Held-out seasons (2022 on)\n")
    print(ev.COMPARE_HEADER)
    print("\n".join(held_rows))
    print("\n## Training seasons (2014–2021, in sample for the tuned parameters)\n")
    print(ev.COMPARE_HEADER)
    print("\n".join(train_rows))
    print(f"\nTotal runtime: {time.time() - start:.0f} s")


if __name__ == "__main__":
    main()
