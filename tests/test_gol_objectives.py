"""Locked partitions, no future fitting, paired series resampling, cohort gates."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "research"))
import evaluate_gol_objectives as exp


def cohort():
    rng = np.random.default_rng(42)
    records = []
    for year in [2022, 2023, 2024, 2025]:
        for i in range(90):
            gold = float(rng.normal(0, 2000))
            elo = float(rng.normal(0, 120))
            row = {
                "oe_gameid": f"{year}/{i}",
                "gol_id": year * 1000 + i,
                "series_first_id": year * 1000 + i // 3,
                "minute": 15,
                "date": pd.Timestamp(f"{year}-06-01", tz="UTC") + pd.Timedelta(days=i),
                "year": year,
                "league": "LCK",
                "won": int(i % 2),
                "blue_won": int(i % 2),
                "training_ready": True,
                "objective_boundary_events": 0,
                "gold_gap": gold,
                "elo_gap": elo,
            }
            for c in exp.OBJECTIVES:
                row[c] = int(rng.integers(-2, 3))
            row["atakhan_gap"] = 0
            row["voidgrubs_gap"] = 0
            records.append(row)
    return pd.DataFrame(records).sort_values("date")


def test_split_is_chronological_and_never_separates_series():
    frame = cohort()
    train, cal, test = exp.split(frame)
    assert (
        set(train.year) == {2022, 2023}
        and set(cal.year) == {2024}
        and set(test.year) == {2025}
    )
    assert set(train.series_first_id).isdisjoint(test.series_first_id)
    frame.loc[frame.year.eq(2025), "series_first_id"] = train.iloc[0].series_first_id
    with pytest.raises(ValueError, match="straddles"):
        exp.split(frame)


def test_future_features_and_targets_cannot_change_fitted_parameters():
    train, cal, test = exp.split(cohort())
    cols = exp.columns_for(train, exp.BASE + exp.OBJECTIVES)
    assert "atakhan_gap" not in cols
    _, _, before = exp.champions.fit_predict(train, cal, test, cols, "stats")
    altered = test.copy()
    altered["won"] = 1 - altered.won
    altered[cols] = 999999
    _, _, after = exp.champions.fit_predict(train, cal, altered, cols, "stats")
    assert before == after


def test_load_gates_verified_sample_and_keeps_series_identity(tmp_path):
    frame = cohort().drop(columns=["won", "series_first_id"])
    path = tmp_path / "dataset.csv"
    frame.to_csv(path, index=False)
    samples = tmp_path / "samples.json"
    samples.write_text(
        json.dumps(cohort()[["gol_id", "series_first_id"]].to_dict("records"))
    )
    with pytest.raises(ValueError, match="Need 1000"):
        exp.load_dataset(path, samples)
    loaded = exp.load_dataset(path, samples, min_games=300)
    assert len(loaded) == 360
    frame.loc[0, "objective_boundary_events"] = 1
    frame.to_csv(path, index=False)
    with pytest.raises(ValueError, match="boundary"):
        exp.load_dataset(path, samples, min_games=300)


def test_paired_identical_predictions_have_zero_delta_and_interval():
    frame = cohort().query("year==2025")
    p = np.full(len(frame), 0.6)
    result = exp.paired_stats(frame, p, p)
    assert (
        result["delta"] == result["low"] == result["high"] == result["cluster_se"] == 0
    )
    assert result["series"] == 30


def test_complete_experiment_reports_identical_cohorts_and_development_curves():
    source = cohort()
    frame = pd.concat(
        [source.assign(minute=m) for m in [10, 15, 20]], ignore_index=True
    )
    frames, parameters = exp.evaluate(frame)
    assert len(frames["metrics"]) == 6 and len(parameters) == 6
    assert frames["metrics"].test_games.eq(90).all()
    for minute in [10, 15, 20]:
        p = frames["predictions"].query("minute==@minute")
        ids = p.groupby("variant").oe_gameid.apply(set)
        assert ids.iloc[0] == ids.iloc[1]
    assert frames["learning_curves"].development_games.eq(90).all()
    assert frames["power_estimates"].observed_series.eq(30).all()
    assert "Fixed method" in exp.report(frames, {"games": 360})
