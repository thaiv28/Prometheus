import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import elo_tempo_surprise as tempo
import elo_variants as ev


def inputs():
    g = pd.DataFrame(
        [
            (f"g{i}", "a", "b", 1200 + i * 150, i % 2, "LCK", f"2024-01-{i + 1:02}")
            for i in range(8)
        ],
        columns=ev.ELO_COLUMNS,
    )
    g["year"] = 2024
    rosters = {
        (f"g{i}", t): tuple(f"{t}{p}" for p in range(5))
        for i in range(8)
        for t in ("a", "b")
    }
    return SimpleNamespace(games=g, rosters=rosters)


def test_future_duration_cannot_change_prior_expectations_or_ratings():
    original = inputs()
    modified = inputs()
    modified.games.loc[4:, "gamelength"] += 1000
    a, da = tempo.replay(original, 0.175)
    b, db = tempo.replay(modified, 0.175)
    # The changed game's expectation and pregame rating also remain unchanged.
    np.testing.assert_array_equal(da["expected"][:5], db["expected"][:5])
    np.testing.assert_array_equal(a.to_numpy()[:10], b.to_numpy()[:10])
    assert not np.array_equal(da["expected"][5:], db["expected"][5:])


def test_side_swap_is_symmetric_for_expectation_and_ratings():
    original = inputs()
    swapped = inputs()
    swapped.games[["teamid", "opponent_teamid"]] = swapped.games[
        ["opponent_teamid", "teamid"]
    ].to_numpy()
    swapped.games["result"] = 1 - swapped.games["result"]
    a, da = tempo.replay(original, 0.1)
    b, db = tempo.replay(swapped, 0.1)
    pd.testing.assert_series_equal(a.sort_index(), b.sort_index())
    np.testing.assert_allclose(da["expected"], db["expected"])


def test_zero_amplitude_matches_constant_soft_result_control():
    pre, _ = tempo.replay(inputs(), 0)
    control = ev.replay(inputs(), lambda g: np.full(len(g), 0.825))
    pd.testing.assert_series_equal(pre, control)


def test_expectation_learns_prior_duration_and_is_gap_symmetric():
    model = tempo.TempoExpectation()
    assert model.predict("LCK", 2024, 100) == 1800
    for _ in range(100):
        model.update("LCK", 2024, 100, 2400)
    assert model.predict("LCK", 2024, 100) > 2200
    assert model.predict("LCK", 2024, 100) == model.predict("LCK", 2024, -100)
    assert model.predict("LCK", 2025, 100) < model.predict("LCK", 2024, 100)


def test_score_bounds_and_monotonic_speed_evidence():
    fast = tempo.surprise_score(-10000, 1800, 0.175)
    ordinary = tempo.surprise_score(1800, 1800, 0.175)
    slow = tempo.surprise_score(10000, 1800, 0.175)
    assert 0.65 <= slow < ordinary < fast <= 1
    assert ordinary == pytest.approx(0.825)
    with pytest.raises(ValueError):
        tempo.surprise_score(1800, 1800, 0.3)


def test_chronological_curves_ignore_future_results():
    import elo_tempo_validation as validation

    frame = pd.DataFrame(
        {
            "year": np.repeat([2020, 2021, 2022, 2023], 8),
            "elo_live": np.tile([-200, -100, -50, -10, 10, 50, 100, 200], 4),
            "won": np.tile([0, 1, 0, 1, 0, 1, 0, 1], 4),
            "league": "LCK",
        }
    )
    modified = frame.copy()
    modified.loc[modified.year == 2023, "won"] = (
        1 - modified.loc[modified.year == 2023, "won"]
    )
    for per_league in (False, True):
        original = validation.earlier_probabilities(
            frame, "elo_live", [2022, 2023], per_league=per_league
        )
        changed = validation.earlier_probabilities(
            modified, "elo_live", [2022, 2023], per_league=per_league
        )
        np.testing.assert_array_equal(original, changed)


def test_market_major_without_form_uses_zero_form(monkeypatch):
    import elo_tempo_validation as validation

    forms = pd.DataFrame(
        {
            "teamname": ["a", "b"],
            "form": [np.nan, np.nan],
            "latest_date": ["2024-12-31", "2024-12-31"],
        }
    )
    monkeypatch.setattr(
        validation.forge, "team_forms", lambda *args, **kwargs: (forms, forms)
    )
    elos = pd.DataFrame(
        {
            "teamname": ["a", "b"],
            "league": ["LCK", "LCK"],
            "elo": [1500, 1600],
            "latest_date": ["2024-12-31", "2024-12-31"],
        }
    )
    frame = pd.DataFrame(
        {
            "ours1": ["a"],
            "ours2": ["b"],
            "start": [pd.Timestamp("2025-01-01")],
            "best_of": [1],
            "major": [True],
        }
    )
    p, methods = validation.market_calls(
        frame,
        pd.DataFrame({"date": ["2024-12-31"]}),
        lambda day: elos,
        {},
        {"elo_weight": 0.004, "form_weight": 1},
        {},
    )
    assert p[0] == pytest.approx(1 / (1 + np.exp(0.4)))
    assert methods[0] == "forge"
