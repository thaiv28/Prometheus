"""Causality and clock boundaries for the temporal research candidate."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
from cand_temporal import bucket, momentum


def test_momentum_is_causal_and_keeps_games_separate():
    rows = pd.DataFrame(
        {
            "game_id": ["a"] * 5 + ["b"],
            "seconds": [0, 60, 180, 240, 300, 240],
            "blue_gold": [2500, 3500, 6000, 7500, 9000, 99999],
            "red_gold": [2500, 3000, 4000, 4500, 5000, 2500],
            "time": [0, 0.05, 0.15, 0.20, 0.25, 0.20],
        }
    )
    before = momentum(rows)
    assert before.momentum.tolist() == [0, 0, 2, 2.5, 3.5, 0]
    changed = rows.copy()
    changed.loc[4, "blue_gold"] = 999999
    pd.testing.assert_frame_equal(momentum(changed).iloc[:4], before.iloc[:4])
    assert before.loc[3, "momentum_time"] == 0.5


def test_momentum_uses_past_time_not_row_offsets():
    rows = pd.DataFrame(
        {
            "game_id": ["a"] * 3,
            "seconds": [200, 0, 400],
            "blue_gold": [7000, 2500, 12000],
            "red_gold": [5000, 2500, 8000],
            "time": [1 / 6, 0, 1 / 3],
        },
        index=[7, 8, 9],
    )
    assert momentum(rows).momentum.tolist() == [2, 0, 2]
    assert bucket([0, 599, 600, 1199, 1200, 1799, 1800, 2400]).tolist() == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
    ]
