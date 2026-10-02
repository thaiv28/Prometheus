"""Scoring helpers for backtesting how well team metrics predict game winners.

A metric gives each team a rating. For one game, the rating gap between the two
teams is turned into a win probability with a logistic curve, and those
probabilities are scored against the real results.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

EPS = 1e-6


def _as_matrix(diff):
    x = np.asarray(diff, dtype=float)
    return x.reshape(-1, 1) if x.ndim == 1 else x


def fit_win_curve(diff, won):
    """Fit P(win) = sigmoid(a + b . diff) and return a function of diff.

    `diff` is the rating gap from the blue side's point of view, so the
    intercept `a` absorbs the blue-side advantage. It may hold one column (a
    single metric) or several (a blend, with one weight per column). With
    diff=None only the intercept is fit, which is the "blue side wins" baseline.
    """
    won = np.asarray(won, dtype=int)
    if diff is None:
        p = float(np.clip(won.mean(), EPS, 1 - EPS))
        return lambda d: np.full(len(d), p)
    x = _as_matrix(diff)
    # Ratings live on very different scales (Elo ~1500, GLORY 0-100); scaling
    # x keeps the solver well conditioned without changing the fitted curve.
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=1e6).fit(x / scale, won)
    return lambda d: model.predict_proba(_as_matrix(d) / scale)[:, 1]


def out_of_year_probabilities(frame, diff_col):
    """Win probabilities for each game from a curve fit on all *other* years.

    Fitting the curve's two parameters on the same games it scores would leak a
    little; leaving the whole year out avoids that.

    Args:
        frame: One row per game with columns `year`, `won` (blue won) and `diff_col`.
        diff_col: Column (or list of columns, for a blend) holding blue-minus-red
            rating gaps, or None for the blue-side baseline.
    Returns:
        Series of probabilities aligned with `frame`.
    """
    probs = pd.Series(np.nan, index=frame.index)
    for year in frame["year"].unique():
        test = frame["year"] == year
        # With a single season there is nothing to leave out; fit on it directly.
        train = frame[~test] if (~test).any() else frame
        curve = fit_win_curve(
            None if diff_col is None else train[diff_col].to_numpy(), train["won"]
        )
        test_diff = (
            np.zeros(test.sum())
            if diff_col is None
            else frame.loc[test, diff_col].to_numpy()
        )
        probs[test] = curve(test_diff)
    return probs


def game_losses(p, won):
    """Per-game accuracy, Brier score and log loss for predicted probabilities."""
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    won = np.asarray(won, dtype=int)
    # A pick of exactly 50% counts as half right.
    correct = np.where(p == 0.5, 0.5, ((p > 0.5) == (won == 1)).astype(float))
    return pd.DataFrame(
        {
            "accuracy": correct,
            "brier": (p - won) ** 2,
            "log_loss": -(won * np.log(p) + (1 - won) * np.log(1 - p)),
        }
    )


def paired_bootstrap(loss_a, loss_b, n_resamples=2000, seed=0):
    """Mean of (loss_a - loss_b) and its 95% bootstrap interval.

    Both metrics are scored on the same games, so resampling games (not each
    metric separately) gives a much tighter, fairer comparison.
    """
    diff = np.asarray(loss_a, dtype=float) - np.asarray(loss_b, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.array(
        [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_resamples)]
    )
    return diff.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)
