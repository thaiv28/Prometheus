"""Pre-match rating orientation, metadata checks and temporal isolation."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import evaluate_snapshot_elo as experiment

from prometheus import elo


def rating_inputs():
    records = pd.DataFrame(
        {
            "gameid": ["g", "g"],
            "teamid": ["b", "r"],
            "pre_match_elo": [1600.0, 1400.0],
            "post_match_elo": [9999.0, 0.0],
        }
    )
    metadata = pd.DataFrame(
        {
            "gameid": ["g", "g"],
            "teamid": ["b", "r"],
            "side": ["Blue", "Red"],
            "date": pd.to_datetime(["2024-01-01"] * 2, utc=True),
            "result": [1, 0],
            "gamelength": [1800, 1800],
        }
    )
    return records, metadata


def test_rating_join_uses_pre_match_values_and_reverses_with_sides():
    records, metadata = rating_inputs()
    ratings = experiment.orient_ratings(records, metadata)
    assert ratings.loc["g", "elo_gap"] == 200
    metadata["side"] = ["Red", "Blue"]
    assert experiment.orient_ratings(records, metadata).loc["g", "elo_gap"] == -200
    with pytest.raises(ValueError):
        experiment.orient_ratings(pd.concat([records, records]), metadata)


def test_missing_opponent_and_mismatched_metadata_are_unavailable():
    records, metadata = rating_inputs()
    ratings = experiment.orient_ratings(records, metadata)
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-01"], utc=True),
            "won": [1],
            "gamelength": [1800],
        },
        index=pd.Index(["g"], name="gameid"),
    )
    assert experiment.attach_ratings(frame, ratings).elo_available.all()
    for col, value in [
        ("won", 0),
        ("gamelength", 1799),
        ("date", pd.Timestamp("2024-01-02", tz="UTC")),
    ]:
        changed = frame.copy()
        changed[col] = value
        attached = experiment.attach_ratings(changed, ratings)
        assert not attached.elo_available.any()
        assert attached.elo_gap.isna().all()
    missing = experiment.orient_ratings(records.iloc[:1], metadata)
    assert not experiment.attach_ratings(frame, missing).elo_available.any()


def test_current_result_and_future_games_cannot_change_current_pre_match_elo():
    games = pd.DataFrame(
        {
            "gameid": ["a", "b", "c"],
            "teamid": ["blue"] * 3,
            "opponent_teamid": ["red"] * 3,
            "gamelength": [1500, 1800, 2100],
            "result": [1, 0, 1],
        }
    )
    first, _ = elo.compute_elo_records(games, elo.calculate_game_length_elo_change)
    changed = games.copy()
    changed.loc[1:, "result"] = [1, 0]
    changed.loc[1:, "gamelength"] = [500, 9999]
    second, _ = elo.compute_elo_records(changed, elo.calculate_game_length_elo_change)
    np.testing.assert_array_equal(
        first[first.gameid.eq("b")].pre_match_elo,
        second[second.gameid.eq("b")].pre_match_elo,
    )
    assert not np.array_equal(
        first[first.gameid.eq("b")].post_match_elo,
        second[second.gameid.eq("b")].post_match_elo,
    )


def test_future_elo_draft_outcomes_do_not_change_fitted_parameters():
    from test_champion_interactions import games

    train, calibration, test = games(100), games(60), games(60)
    for part in (train, calibration, test):
        part["elo_gap"] = np.linspace(-200, 200, len(part))
    columns = ["total_gold", "elo_gap"]
    _, _, first = experiment.champions.fit_predict(
        train, calibration, test, columns, "champions"
    )
    changed = test.copy()
    changed["elo_gap"] *= -1000
    changed["won"] = 1 - changed.won
    changed[experiment.champions.DRAFT_COLS] = "future"
    _, _, second = experiment.champions.fit_predict(
        train, calibration, changed, columns, "champions"
    )
    assert first == second
    assert experiment.champions.YEARS == (2023, 2024, 2025)
    assert experiment.VARIANTS["stats_elo"] == ("stats", True, "stats")
    assert experiment.VARIANTS["champions_elo"] == ("champions", True, "champions")
