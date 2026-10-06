"""Chronology, exported predictions, uncertainty and diagnostic-only calibration."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import evaluate_gol_full as full
from test_gol_objectives import cohort


def frame():
    base = cohort()
    base["blue_gold"] = 25000 + base.gold_gap / 2
    base["red_gold"] = 25000 - base.gold_gap / 2
    return pd.concat([base.assign(minute=m) for m in [10, 15, 20]], ignore_index=True)


def test_temporal_fold_and_whole_series():
    data = frame().query("minute==15")
    train, cal, test = full.temporal_split(data, 2024)
    assert set(train.year) == {2022}
    assert set(cal.year) == {2023}
    assert set(test.year) == {2024}
    data.loc[data.year.eq(2024), "series_first_id"] = train.iloc[0].series_first_id
    with pytest.raises(ValueError, match="straddles"):
        full.temporal_split(data, 2024)


def test_diagnostic_scores_and_series_intervals_are_correct():
    y = np.array([0, 1, 0, 1])
    p = np.array([0.2, 0.8, 0.2, 0.8])
    scores = full.diagnostic_scores(y, p, 0.5)
    assert scores["accuracy"] == scores["roc_auc"] == 1
    assert scores["brier"] == pytest.approx(0.04)
    assert scores["brier_skill_prior"] == pytest.approx(0.84)
    assert scores["ece10"] == pytest.approx(0.2)
    assert scores["confidence_80_n"] == 4
    assert scores["confidence_80_wrong"] == 0
    assert full.interval(np.zeros(4), ["a", "a", "b", "b"], 50) == (0, 0)
    assert np.isnan(full.interval(np.ones(4), ["a"] * 4)[0])


def test_full_synthetic_experiment_and_export_are_causal():
    data = frame()
    results, params = full.evaluate(data, repetitions=30, years=(2025,))
    assert len(results["metrics"]) == 18 and len(params) == 18
    assert results["metrics"].n.eq(90).all()
    for minute, group in results["predictions"].groupby("minute"):
        ids = group.groupby("variant").oe_gameid.apply(set)
        assert all(v == ids.iloc[0] for v in ids)
        for model in [p for p in params if p["minute"] == minute]:
            part = data.query("year==2025 and minute==@minute")
            exported = full.predict(model, part)
            saved = group[group.variant.eq(model["variant"])]
            assert np.allclose(exported, saved.probability, atol=1e-12)
    altered = data.copy()
    altered.loc[altered.year.eq(2025), "won"] = (
        1 - altered.loc[altered.year.eq(2025), "won"]
    )
    changed, after = full.evaluate(altered, repetitions=30, years=(2025,))
    assert params == after  # TEST diagnostic fits never modify the exported models.
    assert not changed["metrics"].accuracy.equals(results["metrics"].accuracy)
    assert results["learning_curves"].development_games.eq(90).all()
    assert results["stress"].scenario.str.contains("round_each_gold_100").any()
    assert results["confidence"].n.gt(0).all()
