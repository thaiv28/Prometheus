import numpy as np
import pandas as pd
import pytest

from prometheus.evaluation import (
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
