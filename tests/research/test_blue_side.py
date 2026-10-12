import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "research"))
_spec = importlib.util.spec_from_file_location(
    "blue_side", ROOT / "scripts" / "research" / "blue_side.py"
)
bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bs)


def _games():
    # A v B: a Bo3 (A wins g1 on blue, B on blue wins g2, A on blue wins g3), then
    # a new series the next day.
    return pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3", "g4"],
            "date": pd.to_datetime(
                [
                    "2026-01-01 10:00",
                    "2026-01-01 11:00",
                    "2026-01-01 12:00",
                    "2026-01-02 10:00",
                ]
            ),
            "league": ["LCK"] * 4,
            "blue": ["A", "B", "A", "A"],
            "red": ["B", "A", "B", "B"],
            "blue_id": ["a", "b", "a", "a"],
            "red_id": ["b", "a", "b", "b"],
            "blue_won": [1, 1, 1, 0],
        }
    )


def test_series_games_split_on_gap():
    g = bs.series_games(_games())
    assert g.set_index("gameid")["game"].to_dict() == {
        "g1": 1,
        "g2": 2,
        "g3": 3,
        "g4": 1,
    }


def test_loser_side_reads_previous_game():
    later = bs.loser_side(bs.series_games(_games())).set_index("gameid")
    # g1's loser B is blue in g2; g2's loser A is blue in g3.
    assert later["loser_blue"].to_dict() == {"g2": True, "g3": True}


def test_loser_picks_series_without_side_is_independent_games():
    p = 0.6
    assert bs.loser_picks_series(p, 3, 0.0, 0.9) == pytest.approx(p**2 * (3 - 2 * p))
    assert bs.loser_picks_series(0.5, 5, 0.2, 0.9) == pytest.approx(0.5)
