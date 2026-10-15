import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import regional_correction as rc


def history():
    n = 180
    return pd.DataFrame(
        {
            "gameid": [f"g{i}" for i in range(n)],
            "day": pd.to_datetime(
                np.repeat(["2019-01-01", "2020-01-01", "2021-01-01"], 60)
            ),
            "event_id": np.repeat(["a", "b", "c"], 60),
            "base_logit": np.tile([-1.0, 0.0, 1.0], 60),
            "home1": ["A"] * n,
            "home2": ["B"] * n,
            "won": np.tile([0, 1, 1, 1, 1, 0], 30),
            "weight": np.ones(n),
        }
    )


def test_future_results_and_vocabulary_cannot_change_earlier_forecasts():
    original = history()
    changed = original.copy()
    changed.loc[changed.event_id == "c", "won"] = (
        1 - changed.loc[changed.event_id == "c", "won"]
    )
    changed.loc[changed.event_id == "c", "home1"] = "UNSEEN"
    a, models_a = rc.event_predictions(original, penalty=4.0, half_life=365.0)
    b, models_b = rc.event_predictions(changed, penalty=4.0, half_life=365.0)
    # Changes in event c cannot alter any earlier prediction or c's fitted state.
    np.testing.assert_array_equal(a[:120], b[:120])
    assert models_a[-1] == models_b[-1]
    assert "UNSEEN" not in models_b[-1]["effects"]


def test_current_event_outcomes_cannot_change_its_frozen_forecasts():
    original = history()
    changed = original.copy()
    changed.loc[changed.event_id == "c", "won"] = (
        1 - changed.loc[changed.event_id == "c", "won"]
    )
    a, _ = rc.event_predictions(original)
    b, _ = rc.event_predictions(changed)
    np.testing.assert_array_equal(a, b)


def test_unfinished_event_is_excluded_even_if_some_games_are_old():
    g = history()
    g.loc[0, "day"] = pd.Timestamp("2022-01-01")
    older = rc.older_events(g, "2021-01-01")
    assert set(older.event_id) == {"b"}


def test_side_swap_reverses_predictions_and_identifies_zero_sum_effects():
    a = history()
    b = a.copy()
    b[["home1", "home2"]] = b[["home2", "home1"]].to_numpy()
    b["base_logit"] = -b.base_logit
    b["won"] = 1 - b.won
    ma = rc.fit(a, "2022-01-01")
    mb = rc.fit(b, "2022-01-01")
    np.testing.assert_allclose(
        rc.expit(ma.logit(a.base_logit, a.home1, a.home2)),
        1 - rc.expit(mb.logit(b.base_logit, b.home1, b.home2)),
        atol=1e-9,
    )
    assert abs(sum(ma.effects.values())) < 1e-12
    assert ma.effects["A"] > ma.effects["B"]
    assert ma.logit([0.0], ["NEW1"], ["NEW2"])[0] == 0.0


def test_calibration_control_and_no_history_have_no_regional_effect():
    g = history()
    model = rc.fit(g, "2022-01-01", regions=False)
    assert model.effects == {} and model.alpha > 0
    empty = rc.fit(g, "2019-01-01")
    assert empty.alpha == 1.0 and not empty.effects


def test_daily_main_roster_ratings_omit_same_day_and_future_updates():
    queries = pd.DataFrame({"teamid": ["a", "a"], "day": ["2020-01-02", "2020-01-03"]})
    timeline = pd.DataFrame(
        {
            "teamid": ["a", "a"],
            "gameid": ["g1", "g2"],
            "date": ["2020-01-01 12:00:00", "2020-01-02 12:00:00"],
            "elo": [1500.0, 1600.0],
            "home": ["LCK", "LCK"],
            "saved_offset": [10.0, 25.0],
        }
    )
    offsets = pd.DataFrame(
        {
            "date": ["2020-01-01 15:00:00", "2020-01-02 15:00:00"],
            "home": ["LCK", "LCK"],
            "current_offset": [15.0, 30.0],
        }
    )
    result = rc.before_day_ratings(queries, timeline, offsets)
    np.testing.assert_array_equal(result.elo, [1505.0, 1605.0])
    timeline.loc[1, "elo"] += 1000
    offsets.loc[1, "current_offset"] += 1000
    changed = rc.before_day_ratings(queries, timeline, offsets)
    assert changed.iloc[0].elo == result.iloc[0].elo


def test_dynamic_fit_responds_to_recency_without_using_future_games():
    g = history()
    g.loc[g.event_id == "a", "won"] = 0
    g.loc[g.event_id != "a", "won"] = 1
    persistent = rc.fit(g, "2022-01-01", half_life=math.inf)
    dynamic = rc.fit(g, "2022-01-01", half_life=365.0)
    assert dynamic.effects["A"] > persistent.effects["A"]


def test_entry_includes_new_opponent_of_an_existing_participant():
    games = pd.DataFrame(
        {
            "id1": ["A", "A", "A"],
            "id2": ["B", "C", "B"],
            "day": pd.to_datetime(["2022-01-01", "2022-01-02", "2022-01-03"]),
            "event_id": ["event"] * 3,
        }
    )
    assert rc.entry_labels(games).entry.tolist() == [True, True, False]


def test_market_price_and_outcome_are_irrelevant_to_event_provenance():
    cached = pd.DataFrame(
        {
            "start": pd.to_datetime(["2026-07-01", "2026-07-15"], utc=True),
            "ours1": ["A", "A"],
            "ours2": ["B", "B"],
            "event": ["EWC EMEA Qualifier", "Esports World Cup 2026"],
            "market_close": [0.1, 0.9],
            "won1": [0, 1],
        }
    )
    games = pd.DataFrame(
        {
            "team": ["A", "A"],
            "opponent": ["B", "B"],
            "league": ["EWC", "EWC"],
            "day": [
                pd.Timestamp("2026-07-01").date(),
                pd.Timestamp("2026-07-15").date(),
            ],
        }
    )
    expected = rc.metadata_exclusions(cached, games)
    cached["market_close"] = 1 - cached.market_close
    cached["won1"] = 1 - cached.won1
    assert rc.metadata_exclusions(cached, games) == expected
    assert expected == (
        {("EWC", pd.Timestamp("2026-07-01"))},
        {pd.Timestamp("2026-07-15")},
    )
