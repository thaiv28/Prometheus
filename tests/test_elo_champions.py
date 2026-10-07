"""Matched-C feature ablation and game-aligned paired comparisons."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import evaluate_elo_champions as ablation
from test_champion_interactions import games


def test_both_models_have_identical_numeric_scaling_and_regularization():
    train, calibration, test = games(100), games(60), games(60)
    for part in (train, calibration, test):
        part["elo_gap"] = np.linspace(-150, 150, len(part))
    fitted = []
    for variant, add_elo, _ in ablation.VARIANTS.values():
        assert add_elo
        _, _, params = ablation.experiment.champions.fit_predict(
            train, calibration, test, ["total_gold", "elo_gap"], variant
        )
        fitted.append(params)
    assert fitted[0]["C"] == fitted[1]["C"] == 0.1
    assert fitted[0]["numeric_columns"] == fitted[1]["numeric_columns"]
    assert fitted[0]["scaler_mean"] == fitted[1]["scaler_mean"]
    assert fitted[0]["scaler_std"] == fitted[1]["scaler_std"]
    assert fitted[0]["draft_columns"] == []
    assert fitted[1]["draft_columns"]
    assert all(col.startswith("champion/") for col in fitted[1]["draft_columns"])


def test_paired_scores_align_by_game_id_even_when_rows_are_reordered():
    baseline = pd.DataFrame(
        {
            "gameid": ["a", "b", "c", "d"],
            "date": pd.to_datetime(
                ["2023-01-01", "2023-01-02", "2024-01-01", "2024-01-02"], utc=True
            ),
            "league": ["LCK"] * 4,
            "won": [0, 1, 0, 1],
            "probability": [0.2, 0.8, 0.4, 0.6],
            "raw_probability": [0.2, 0.8, 0.4, 0.6],
            "minute": [15] * 4,
            "year": [2023, 2023, 2024, 2024],
            "base": ["aura_features"] * 4,
            "variant": ["stats_elo"] * 4,
        }
    )
    candidate = baseline.iloc[::-1].copy()
    candidate["variant"] = "champions_elo"
    candidate["probability"] = np.where(candidate.won, 0.9, 0.1)
    predictions = pd.concat([baseline, candidate], ignore_index=True)
    result = ablation.experiment.score(predictions, variants=ablation.VARIANTS)
    row = result[result.variant.eq("champions_elo")].iloc[0]
    expected = np.mean(
        ablation.experiment.snapshots.losses(
            baseline.won.to_numpy(), np.where(baseline.won, 0.9, 0.1)
        )
        - ablation.experiment.snapshots.losses(
            baseline.won.to_numpy(), baseline.probability.to_numpy()
        )
    )
    assert np.isclose(row.delta_base, expected)
    assert row.control == "stats_elo"
    assert row.delta_high < 0
