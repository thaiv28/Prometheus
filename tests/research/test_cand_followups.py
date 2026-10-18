"""Check cohort exclusions, side orientation and unavailable-draft behavior."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
from cand_followups import ROLES, checkpoint_frame, draft_columns


def sample():
    players = pd.DataFrame(
        [
            {
                "gameid": "a",
                "position": role,
                "side": side,
                "goldat10": 1000 + 100 * i + extra,
                "csat10": 20 + i + extra / 100,
                "xpat10": 2000 + i + extra,
            }
            for side, extra in [("Blue", 200), ("Red", 0)]
            for i, role in enumerate(ROLES)
        ]
    )
    games = pd.DataFrame(
        [
            {
                "gameid": "a",
                "side": "Blue",
                "league": "LCK",
                "teamname": "A",
                "opp": "B",
                "series_elo": 1600,
                "gamelength": 1800,
                "result": 1,
                "date": "2024-01-01 01:00:00",
            },
            {
                "gameid": "a",
                "side": "Red",
                "league": "LCK",
                "teamname": "B",
                "opp": "A",
                "series_elo": 1500,
                "gamelength": 1800,
                "result": 0,
                "date": "2024-01-01 01:00:00",
            },
        ]
    )
    return players, games


def test_checkpoint_has_exact_totals_and_blue_oriented_gaps():
    p, g = sample()
    row = checkpoint_frame(p, g, 10).iloc[0]
    assert row.blue_gold == 7000 and row.red_gold == 6000
    assert row.top_gold == 200 and row.sup_cs == 2 and row.mid_xp == 200
    assert row.blue_elo == 1600 and row.red_elo == 1500
    assert row.series == "A|B|2024-01-01"
    p["side"] = p.side.map({"Blue": "Red", "Red": "Blue"})
    g["side"] = g.side.map({"Blue": "Red", "Red": "Blue"})
    reverse = checkpoint_frame(p, g, 10).iloc[0]
    assert reverse.top_gold == -200 and reverse.sup_cs == -2
    assert reverse.blue_elo == 1500 and reverse.won == 0


def test_checkpoint_drops_incomplete_rosters_and_ended_games():
    p, g = sample()
    missing = p.copy()
    missing.loc[0, "xpat10"] = np.nan
    assert checkpoint_frame(missing, g, 10).empty
    duplicated = p.copy()
    duplicated.loc[0, "position"] = "jng"
    assert checkpoint_frame(duplicated, g, 10).empty
    g["gamelength"] = 600
    assert checkpoint_frame(p, g, 10).empty


def test_unavailable_draft_keeps_rows_with_zero_shift_without_modifying_input():
    frame = pd.DataFrame({"game_id": ["a", "b"], "time": [0.5, 1.0]})
    shifts = pd.DataFrame({"shift": [0.4]}, index=["a"])
    result = draft_columns(frame, shifts, "shift")
    assert result.game_id.tolist() == ["a", "b"]
    assert result.draft.tolist() == [0.4, 0]
    assert result.draft_time.tolist() == [0.2, 0]
    assert result.draft_known.tolist() == [True, False]
    assert "draft" not in frame
