import copy
import datetime as dt
import json

import numpy as np
import pandas as pd
import pytest

from prometheus import regional_calibration as cal
from prometheus import schedule


@pytest.fixture
def artifact(monkeypatch, tmp_path):
    data = {
        "version": cal.VERSION,
        "event_windows": {"EWC-2026": ["2026-07-01", "2026-07-05"]},
        "snapshots": [
            {
                "available_from": "2026-01-10",
                "trained_through": "2026-01-09",
                "n_train": 100,
                "slope": 0.01,
                "effects": {"LCK": 0.2, "LPL": -0.2},
            },
            {
                "available_from": "2026-06-15",
                "trained_through": "2026-06-14",
                "n_train": 200,
                "slope": 0.02,
                "effects": {"LCK": -0.4, "LPL": 0.4},
            },
        ],
        "events": [
            {
                "event": "MSI",
                "start": "2026-06-10",
                "end": "2026-06-20",
                "model": "2026-01-10",
            }
        ],
    }
    path = tmp_path / "calibration.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(cal, "PATH", path)
    cal.load.cache_clear()
    yield data
    cal.load.cache_clear()


def chance(**kwargs):
    return cal.probability(
        0.6, 100.0, "LCK", "LPL", at="2026-06-17", event="MSI", **kwargs
    )


def test_frozen_event_model_ignores_new_snapshot_during_tournament(artifact):
    assert chance() == pytest.approx(1 / (1 + np.exp(-1.4)))
    assert (
        cal.snapshot("2026-06-17", "MSI", "2026-06-17")["available_from"]
        == "2026-01-10"
    )
    assert cal.snapshot("2026-06-17", "Worlds")["available_from"] == "2026-06-15"


def test_before_first_training_data_preserves_original_forecast(artifact):
    assert cal.probability(0.6, 100, "LCK", "LPL", at="2026-01-09", event="MSI") == 0.6


def test_evening_before_event_uses_only_already_available_training(artifact):
    assert (
        cal.snapshot("2026-06-09", "MSI", "2026-06-10")["available_from"]
        == "2026-01-10"
    )
    assert cal.snapshot("2026-06-14", "Worlds")["available_from"] == "2026-01-10"


@pytest.mark.parametrize(
    "event,title,date",
    [
        ("EM", "", "2026-06-17"),
        ("LCK", "", "2026-06-17"),
        ("EWC", "Esports World Cup EMEA Qualifier", "2026-07-02"),
        ("Worlds", "LPL Regional Finals 2026", "2026-06-17"),
        ("EWC", "", "2026-06-17"),
        ("Intl", "Unknown cup", "2026-06-17"),
    ],
)
def test_unvalidated_fixtures_preserve_original_forecast(artifact, event, title, date):
    assert (
        cal.probability(0.6, 100, "LCK", "LPL", at=date, event=event, title=title)
        == 0.6
    )


def test_kill_switch_and_same_home_do_not_change_forecast(artifact, monkeypatch):
    assert cal.probability(0.6, 100, "LCK", "LCK", at="2026-06-17", event="MSI") == 0.6
    monkeypatch.setenv("REGIONAL_CALIBRATION", "0")
    assert chance() == 0.6


def test_symmetry_unknown_effects_and_extreme_finite_gaps(artifact):
    a = chance()
    b = cal.probability(0.4, -100, "LPL", "LCK", at="2026-06-17", event="MSI")
    assert a == pytest.approx(1 - b)
    assert (
        cal.probability(0.5, 0, "NEW_A", "NEW_B", at="2026-06-17", event="MSI") == 0.5
    )
    assert cal.probability(0.5, 1e9, "LCK", "LPL", at="2026-06-17", event="MSI") == 1.0
    assert cal.probability(0.5, -1e9, "LCK", "LPL", at="2026-06-17", event="MSI") == 0.0


def test_utc_boundary_and_missing_home(artifact):
    when = dt.datetime(2026, 1, 10, 0, 30, tzinfo=dt.timezone(dt.timedelta(hours=2)))
    assert cal.day(when) == "2026-01-09"
    assert cal.probability(0.6, 100, None, "LCK", event="MSI") == 0.6
    assert cal.probability(0.6, 100, "Worlds", "LCK", event="MSI") == 0.6


@pytest.mark.parametrize("mutation", ["future", "nan", "unordered"])
def test_invalid_artifact_fails_instead_of_publishing_bad_odds(artifact, mutation):
    data = copy.deepcopy(artifact)
    if mutation == "future":
        data["snapshots"][0]["trained_through"] = "2026-01-10"
    if mutation == "nan":
        data["snapshots"][0]["slope"] = float("nan")
    if mutation == "unordered":
        data["snapshots"].reverse()
    cal.PATH.write_text(json.dumps(data))
    cal.load.cache_clear()
    with pytest.raises(ValueError):
        cal.load()


def test_native_benchmark_uses_identical_runtime_and_leaves_other_events_exact(
    artifact,
):
    f = pd.DataFrame(
        {
            "date": ["2026-06-17"] * 3,
            "league": ["MSI", "EM", "LCK"],
            "elo_live": [100.0] * 3,
            "blue_league": ["LCK"] * 3,
            "red_league": ["LPL", "LPL", "LCK"],
        }
    )
    got = cal.apply_frame(f, np.array([0.6, 0.6, 0.6]))
    assert got[0] == chance()
    np.testing.assert_array_equal(got[1:], [0.6, 0.6])


def test_schedule_routes_by_event_and_records_exact_model_provenance(artifact):
    a = {"league": "LCK", "elo": 1600.0, "forge": 1600.0, "has_form": True}
    b = {"league": "LPL", "elo": 1500.0, "forge": 1500.0, "has_form": True}
    p, _ = schedule.game_probability(a, b, event="MSI", at="2026-06-17")
    assert p == chance()
    p, _ = schedule.game_probability(a, b, event="EM", at="2026-06-17")
    assert p == pytest.approx(1 / (1 + np.exp(-schedule.CROSS_REGION_ELO_WEIGHT * 100)))
    fixtures = pd.DataFrame(
        [
            {
                "match_id": "x",
                "start": pd.Timestamp("2026-06-17", tz="UTC"),
                "team1": "A",
                "team2": "B",
                "best_of": 3,
                "event": "Mid-Season Invitational 2026",
                "event_league": "Mid-Season Invitational",
                "overview_page": "MSI/2026",
            }
        ]
    )
    result = schedule.predict(
        fixtures, pd.DataFrame([a, b], index=["A", "B"]), lambda x: x, at="2026-06-16"
    )[0]
    assert result["calibration"]["model"] == "2026-01-10"
    assert result["calibration"]["trained_through"] == "2026-01-09"
    assert result["p_game"] == round(chance(), 4)
