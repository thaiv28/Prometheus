"""Runtime objective/momentum inference: orientation, causality and fallback."""

import copy
import json
import math
from datetime import UTC, datetime, timedelta

import pytest

from prometheus.live import timeline as t


def model():
    return {
        "schema": "time_objectives_momentum_v1",
        "features": t.STATE_FEATURES,
        "supported_seconds": [0, 2400],
        "mean": [0] * 20,
        "scale": [1] * 20,
        "coef": [0] * 18 + [1, 0],
        "intercept": 0,
        "calibration_slope": 1,
        "calibration_intercept": 0,
    }


def frame(seconds, lead=0, towers=0):
    at = (datetime(2026, 10, 17, tzinfo=UTC) + timedelta(seconds=seconds)).isoformat()
    blue = dict.fromkeys(t.OBJECTIVES[:-1], 0)
    red = blue.copy()
    blue.update(gold=2500 + 20 * seconds + lead, towers=towers)
    red.update(gold=2500 + 20 * seconds)
    return {"at": at, "source_at": at, "teams": [blue, red]}


def page():
    return {
        "game": {
            "blue": 0,
            "frames": [frame(0), frame(60, 1000), frame(180, 2000), frame(240, 4000)],
        }
    }


def test_three_minute_gold_momentum_and_future_invariance():
    p = page()
    ratings = [{"elo": 1500}] * 2
    _, calls = t.timeline_calls(p, model(), ratings)
    assert calls[-1]["p"] == pytest.approx(1 / (1 + math.exp(-3)))
    assert calls[-2]["p"] == pytest.approx(1 / (1 + math.exp(-2)))
    p["game"]["frames"].append(frame(300, -20000))
    _, later = t.timeline_calls(p, model(), ratings)
    assert later[: len(calls)] == calls


def test_match_order_swap_preserves_team_chance_and_series_shift():
    m = model()
    m["coef"][6] = 0.4  # towers
    p = page()
    p["game"]["frames"][-1]["teams"][0]["towers"] = 3
    ratings = [{"elo": 1600}, {"elo": 1500}]
    _, a = t.timeline_calls(p, m, ratings)
    flipped = copy.deepcopy(p)
    flipped["game"]["blue"] = 1
    for f in flipped["game"]["frames"]:
        f["teams"].reverse()
    _, b = t.timeline_calls(flipped, m, ratings[::-1])
    assert a[-1]["p"] + b[-1]["p"] == pytest.approx(1)
    _, shifted = t.timeline_calls(p, m, ratings, shift=0.2)
    z = math.log(a[-1]["p"] / (1 - a[-1]["p"])) + 0.2
    assert shifted[-1]["p"] == pytest.approx(1 / (1 + math.exp(-z)))


def test_missing_or_invalid_objective_counts_fall_back_to_frozen_v1():
    p = page()
    ratings = [{"elo": 1500}] * 2
    old = json.loads(t.LEGACY_MODEL_PATH.read_text())
    for value in [None, -1, True, 1.5]:
        p["game"]["frames"][-1]["teams"][0]["barons"] = value
        _, calls = t.timeline_calls(p, model(), ratings)
        _, legacy = t.timeline_calls(p, old, ratings)
        assert calls[-1]["p"] == legacy[-1]["p"]
        assert calls[-1]["model"] == "time_gold_elo_v1"


def test_objective_feature_semantics_and_contract():
    blue = {"towers": 3, "dragons": 4, "barons": 1, "inhibitors": 2, "kills": 8}
    red = {"towers": 1, "dragons": 2, "barons": 0, "inhibitors": 0, "kills": 5}
    assert t.objective_gaps(blue, red) == [2, 2, 1, 2, 3, 1]
    x = t.state_features(600, 30000, 28000, 1600, 1500, (blue, red), 2)
    assert x[6:] == [2, 1, 2, 1, 1, 0.5, 2, 1, 3, 1.5, 1, 0.5, 2, 1]
    with pytest.raises(ValueError):
        t.predict(model(), 600, 30000, 28000, 1600, 1500)
    m = model()
    m["features"] = t.FEATURES
    with pytest.raises(ValueError):
        t.predict(m, 600, 30000, 28000, 1600, 1500, objectives=(blue, red))


def test_pregame_stays_on_v1_without_objectives_or_history():
    ratings = [{"elo": 1750}, {"elo": 1600}]
    p = {"game": {"blue": 1, "frames": []}}
    pre, calls = t.timeline_calls(p, model(), ratings)
    legacy, _ = t.timeline_calls(p, t.legacy_model(), ratings)
    assert pre == legacy
    assert calls == []
