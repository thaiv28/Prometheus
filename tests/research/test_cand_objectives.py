"""The objective rows and columns in cand_objectives.py."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
spec = importlib.util.spec_from_file_location("cand", RESEARCH / "cand_objectives.py")
cand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cand)
from train_time_model_v2 import feed_rows


def side(gold, towers=0, dragons=0, barons=0, inhibitors=0, kills=0):
    return {
        "gold": gold,
        "towers": towers,
        "dragons": dragons,
        "barons": barons,
        "inhibitors": inhibitors,
        "kills": kills,
    }


def sample(at, blue, red, state="in_game", flat=False):
    return {"at": at, "state": state, "flat": flat, "blue": blue, "red": red}


def joined_map():
    return {
        "oe_gameid": "g1",
        "series_key": "a|b|2024-01-01",
        "year": 2024,
        "date": "2024-01-01 10:00:00",
        "league": "LCK",
        "start": "2024-01-01T10:00:00Z",
        "blue_elo": 1500.0,
        "red_elo": 1450.0,
        "won": 1,
        "gamelength": 1800,
        "samples": [
            sample("2024-01-01T10:01:00Z", side(3000), side(3000)),
            sample("2024-01-01T10:02:00Z", side(0), side(3100)),  # no gold: dropped
            sample("2024-01-01T10:03:00Z", side(5000), side(5000), state="paused"),
            sample(
                "2024-01-01T10:20:00Z",
                side(30000, towers=3, dragons=4, kills=9),
                side(28000, towers=1, dragons=1, barons=1, kills=5),
            ),
            sample("2024-01-01T10:30:00Z", side(50000), side(40000), state="finished"),
        ],
    }


def test_values_are_blue_minus_red_with_a_soul_flag():
    v = cand.objective_values(
        side(1, towers=3, dragons=4, barons=1, inhibitors=1, kills=10),
        side(1, towers=1, dragons=2, kills=12),
    )
    assert v == {
        "towers": 2,
        "dragons": 2,
        "barons": 1,
        "inhibitors": 1,
        "kills": -2,
        "soul": 1,
    }
    both = cand.objective_values(side(1, dragons=4), side(1, dragons=5))
    assert both["soul"] == 0 and both["dragons"] == -1
    assert cand.objective_values(side(1, dragons=3), side(1, dragons=4))["soul"] == -1


def test_rows_follow_feed_rows_filter_and_order():
    m = joined_map()
    feed, _ = feed_rows([m])
    obj = cand.objective_rows([m])
    assert len(obj) == len(feed) == 2
    assert obj.game_id.tolist() == feed.game_id.tolist()
    assert obj.seconds.tolist() == feed.seconds.tolist()
    last = obj.iloc[-1]
    assert (last.towers, last.dragons, last.barons, last.kills, last.soul) == (
        2,
        3,
        -1,
        4,
        1,
    )


def test_attach_checks_positions():
    m = joined_map()
    feed, _ = feed_rows([m])
    obj = cand.objective_rows([m])
    part = feed.iloc[[1]]
    out = cand.attach(part, obj, len(feed))
    assert out.index.tolist() == [1] and out.iloc[0].towers == 2
    shifted = part.copy()
    shifted["seconds"] += 1
    with pytest.raises(ValueError):
        cand.attach(shifted, obj, len(feed))
    with pytest.raises(ValueError):
        cand.attach(part, obj, len(feed) + 1)


def test_columns_are_x_and_x_times_time():
    data = pd.DataFrame({"towers": [2, -1], "time": [0.5, 1.5]})
    cols = cand.add_columns(data, ["towers"])
    assert cols == ["obj_towers", "obj_towers_time"]
    assert data.obj_towers_time.tolist() == [1.0, -1.5]
