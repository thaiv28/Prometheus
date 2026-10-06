"""Visible input boundaries, chronological fit isolation and frozen inference."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import evaluate_visible_elo as visible
from test_champion_interactions import games


def test_visible_cohort_does_not_require_xp_or_draft_but_rich_comparison_does():
    frame = games(3)
    frame["valid_roster"] = True
    frame["league"] = "LCK"
    frame["date"] = pd.Timestamp("2026-01-01", tz="UTC")
    frame["year"] = 2026
    frame["gamelength"] = 1800
    frame["total_kills"] = [2, 3, np.nan]
    frame.index = pd.Index(["a", "b", "c"], name="gameid")
    frame[visible.history.champions.DRAFT_COLS] = np.nan
    frame.loc["b", "top_xp"] = np.nan
    ratings = pd.DataFrame(
        {
            "elo_date": frame.date,
            "elo_won": frame.won,
            "elo_length": frame.gamelength,
            "elo_gap": [100.0, 0.0, -100.0],
        },
        index=frame.index,
    )
    cohorts = visible.cohorts(frame, ratings, 15)
    assert list(cohorts["visible"].index) == ["a", "b"]
    assert list(cohorts["common"].index) == ["a"]


def test_frozen_numeric_export_reproduces_calibrated_and_raw_predictions():
    train, calibration, test = games(100), games(60), games(60)
    for part in (train, calibration, test):
        part["total_kills"] = np.arange(len(part)) % 7 - 3
        part["elo_gap"] = np.linspace(-200, 200, len(part))
    columns = visible.MODELS["scoreboard_elo"]
    p, raw, fitted = visible.history.champions.fit_predict(
        train, calibration, test, columns, "stats"
    )
    params = [
        {
            "minute": 15,
            "year": 2026,
            "cohort": "visible",
            "variant": "scoreboard_elo",
            **fitted,
        }
    ]
    assert fitted["C"] == 1
    assert fitted["draft_columns"] == []
    for i, row in test.iterrows():
        values = (
            params,
            15,
            30000 + row.total_gold,
            30000,
            10 + row.total_kills,
            10,
            1500 + row.elo_gap,
            1500,
        )
        assert np.isclose(visible.predict_visible(*values), p[i])
        assert np.isclose(visible.predict_visible(*values, calibrated=False), raw[i])
    with pytest.raises(ValueError):
        visible.predict_visible(params, 17, 30000, 30000, 0, 0, 1500, 1500)
    with pytest.raises(ValueError):
        visible.predict_visible(params, 15, float("nan"), 30000, 0, 0, 1500, 1500)


def test_2026_changes_cannot_change_fit_or_calibration_parameters():
    train, calibration, test = games(100), games(60), games(60)
    for part in (train, calibration, test):
        part["total_kills"] = np.arange(len(part)) % 7
        part["elo_gap"] = np.linspace(-200, 200, len(part))
    for variant in ("rich_elo", "scoreboard_elo"):
        columns = visible.MODELS[variant]
        _, _, first = visible.history.champions.fit_predict(
            train, calibration, test, columns, "stats"
        )
        future = test.copy()
        future[columns] *= 1000
        future["won"] = 1 - future.won
        _, _, second = visible.history.champions.fit_predict(
            train, calibration, future, columns, "stats"
        )
        assert first == second


def test_protocol_has_no_final_objective_features_and_uses_2022_to_2024_training():
    assert visible.MODELS["scoreboard_elo"] == ["total_gold", "total_kills", "elo_gap"]
    assert not any(
        any(word in col for word in ("tower", "dragon", "baron", "herald", "atakhan"))
        for cols in visible.MODELS.values()
        for col in cols
    )
    data = pd.DataFrame({"year": range(2020, 2028)})
    train, calibration, test = visible.snapshots.temporal_split(data, 2026)
    assert train.year.tolist() == [2022, 2023, 2024]
    assert calibration.year.tolist() == [2025]
    assert test.year.tolist() == [2026]
