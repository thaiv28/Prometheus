import numpy as np
import pandas as pd
import pytest

from prometheus.evaluation import (
    elo_as_of,
    fit_win_curve,
    game_losses,
    out_of_year_probabilities,
    paired_bootstrap,
)


def test_game_losses_known_values():
    losses = game_losses([0.8, 0.8, 0.5], [1, 0, 1])
    assert losses["accuracy"].tolist() == [1.0, 0.0, 0.5]
    assert losses["brier"].tolist() == pytest.approx([0.04, 0.64, 0.25])
    assert losses["log_loss"].tolist() == pytest.approx(
        [-np.log(0.8), -np.log(0.2), -np.log(0.5)]
    )


def test_game_losses_clips_certain_wrong_picks():
    # A 100% pick that loses must not produce an infinite log loss.
    assert np.isfinite(game_losses([1.0], [0])["log_loss"]).all()


def test_win_curve_rises_with_rating_gap():
    rng = np.random.default_rng(0)
    diff = rng.normal(0, 10, 2000)
    won = (rng.random(2000) < 1 / (1 + np.exp(-0.2 * diff))).astype(int)
    curve = fit_win_curve(diff, won)
    low, even, high = curve([-10, 0, 10])
    assert low < even < high
    assert even == pytest.approx(0.5, abs=0.05)


def test_baseline_curve_is_the_blue_win_rate():
    curve = fit_win_curve(None, [1, 1, 1, 0])
    assert curve([0, 0]).tolist() == pytest.approx([0.75, 0.75])


def test_out_of_year_probabilities_ignore_the_scored_year():
    frame = pd.DataFrame(
        {"year": [2023] * 4 + [2024] * 4, "won": [1, 1, 1, 0, 0, 0, 0, 1]}
    )
    probs = out_of_year_probabilities(frame, None)
    # 2023 is predicted from 2024's blue win rate and vice versa.
    assert probs[:4].tolist() == pytest.approx([0.25] * 4)
    assert probs[4:].tolist() == pytest.approx([0.75] * 4)


def test_paired_bootstrap_interval_contains_mean():
    a = np.array([0.5, 0.6, 0.7, 0.4] * 50)
    b = a + 0.1
    mean, lo, hi = paired_bootstrap(a, b)
    assert mean == pytest.approx(-0.1)
    assert lo == pytest.approx(-0.1) and hi == pytest.approx(-0.1)


def test_blend_curve_uses_every_input():
    rng = np.random.default_rng(1)
    x = rng.normal(0, 1, (4000, 2))
    # Only the second input matters.
    won = (rng.random(4000) < 1 / (1 + np.exp(-1.5 * x[:, 1]))).astype(int)
    curve = fit_win_curve(x, won)
    first_up, second_up = curve([[2.0, 0.0], [0.0, 2.0]])
    assert first_up == pytest.approx(0.5, abs=0.05)
    assert second_up > 0.9


def test_out_of_year_probabilities_accept_several_columns():
    rng = np.random.default_rng(2)
    frame = pd.DataFrame(
        {
            "year": np.repeat([2023, 2024], 200),
            "a": rng.normal(size=400),
            "b": rng.normal(size=400),
        }
    )
    frame["won"] = (frame["a"] + frame["b"] + rng.normal(size=400) > 0).astype(int)
    probs = out_of_year_probabilities(frame, ["a", "b"])
    assert probs.notna().all()
    assert probs[frame["a"] + frame["b"] > 1].mean() > 0.7


def test_elo_as_of_adds_league_offset_moves_since_last_game():
    d = pd.Timestamp
    timeline = pd.DataFrame(
        {
            "teamname": ["A", "B", "A", "C"],
            "date": [d("2024-01-01"), d("2024-01-01"), d("2024-02-01"), d("2024-03-01")],
            "elo": [1510.0, 1490.0, 1520.0, 1600.0],
            "home_league": ["LCK", "LCS", "LCK", None],
            "league_offset": [0.0, 0.0, 2.0, 0.0],
        }
    )
    offsets = pd.DataFrame(
        {
            "date": [d("2024-01-15"), d("2024-01-15"), d("2024-02-15"), d("2024-04-01")],
            "league": ["LCK", "LCS", "LCK", "LCK"],
            "league_offset": [2.0, -2.0, 5.0, 9.0],
        }
    )
    elo = elo_as_of(timeline, offsets, d("2024-03-15"))
    # A: last game at offset 2, LCK offset is 5 by the cutoff (the April move is later).
    assert elo["A"] == pytest.approx(1523.0)
    # B: LCS offset fell by 2 after its last game.
    assert elo["B"] == pytest.approx(1488.0)
    # C: no home league, no offset to carry.
    assert elo["C"] == pytest.approx(1600.0)
    # Games on or after the cutoff are ignored.
    assert "C" not in elo_as_of(timeline, offsets, d("2024-03-01")).index


def test_spearman_brown_and_games_for_reliability():
    from prometheus.evaluation import games_for_reliability, spearman_brown

    assert spearman_brown(0.5, 2) == pytest.approx(2 / 3)
    # One game at reliability 0.2 needs 4 games to reach 0.5.
    assert games_for_reliability(0.2, 1) == pytest.approx(4.0)
    # A half of 10 games at 0.5 means 10 games reach 0.5.
    assert games_for_reliability(0.5, 10) == pytest.approx(10.0)
    assert games_for_reliability(0.0, 10) == np.inf
