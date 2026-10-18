"""The live service's own Elo update between maps in cand_map_elo.py."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
spec = importlib.util.spec_from_file_location("cand", RESEARCH / "cand_map_elo.py")
cand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cand)


def test_service_elo_starts_at_the_series_and_adds_each_finished_map():
    g = pd.DataFrame(
        {
            "gameid": ["a", "b", "c"],
            "teamname": ["T1"] * 3,
            "series": [1, 1, 1],
            # Later rows' own Elo is ignored: only the first map's is used.
            "elo_pre": [1600.0, 9999.0, 9999.0],
            "opp_elo_pre": [1500.0, 0.0, 0.0],
            "gamelength": [1500, 2100, 1800],
            "result": [1, 0, 1],
        }
    )
    step = lambda elo, opponent_elo, game_length, result: 10.0 if result else -4.0
    out = cand.service_elo(g, change=step)
    assert out[("a", "T1")] == (1600.0, 1500.0)
    assert out[("b", "T1")] == (1610.0, 1490.0)
    assert out[("c", "T1")] == (1606.0, 1494.0)


def test_service_elo_uses_the_game_length_update_by_default():
    g = pd.DataFrame(
        {
            "gameid": ["a", "b"],
            "teamname": ["T1", "T1"],
            "series": [1, 1],
            "elo_pre": [1500.0, 0.0],
            "opp_elo_pre": [1500.0, 0.0],
            "gamelength": [1800, 1800],
            "result": [1, 1],
        }
    )
    own, opp = cand.service_elo(g)[("b", "T1")]
    # Even teams, 30-minute win: actual score 0.825, K=20, so +6.5 and zero-sum.
    assert own == pytest.approx(1506.5)
    assert own + opp == pytest.approx(3000.0)
