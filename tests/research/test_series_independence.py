"""The beta-binomial series model and the fearless labels in series_independence.py."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prometheus.schedule import series_probability

PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "research"
    / "series_independence.py"
)
spec = importlib.util.spec_from_file_location("series_independence", PATH)
si = importlib.util.module_from_spec(spec)
spec.loader.exec_module(si)


@pytest.mark.parametrize("bo", [1, 3, 5])
@pytest.mark.parametrize("p", [0.2, 0.5, 0.73])
def test_rho_zero_is_independent_games(p, bo):
    assert si.beta_series(p, bo, 0)[()] == pytest.approx(series_probability(p, bo))


@pytest.mark.parametrize("rho", [0.054, 0.127, 0.4])
def test_matches_the_published_formula(rho):
    for p in (0.25, 0.6, 0.9):
        for bo in (3, 5):
            assert si.beta_series(p, bo, rho)[()] == pytest.approx(
                series_probability(p, bo, rho)
            )


def test_series_chance_is_symmetric_and_shrinks_with_rho():
    p = np.array([0.6, 0.7, 0.8])
    for bo in (3, 5):
        assert si.beta_series(p, bo, 0.2) + si.beta_series(1 - p, bo, 0.2) == (
            pytest.approx(1)
        )
        ind, beta = si.beta_series(p, bo, 0), si.beta_series(p, bo, 0.2)
        assert np.all(beta < ind) and np.all(beta > p)


def test_matches_simulation():
    rng = np.random.default_rng(0)
    p, rho, bo = 0.65, 0.25, 5
    kappa = 1 / rho - 1
    pi = rng.beta(p * kappa, (1 - p) * kappa, 200_000)
    games = rng.random((len(pi), bo)) < pi[:, None]
    # play out the series: whoever reaches three wins first
    first = lambda hits: np.where(hits.any(axis=1), hits.argmax(axis=1), bo)
    at_w = first(np.cumsum(games, axis=1) >= 3)
    at_l = first(np.cumsum(~games, axis=1) >= 3)
    assert si.beta_series(p, bo, rho)[()] == pytest.approx(
        (at_w < at_l).mean(), abs=0.004
    )
    length = np.minimum(at_w, at_l) + 1
    probs = si.length_probs(np.array([p]), bo, rho)
    assert sum(probs.values()) == pytest.approx(1)
    for n, q in probs.items():
        assert q == pytest.approx((length == n).mean(), abs=0.004)


def test_sequence_likelihood_at_rho_zero_is_binomial():
    p, w, l = np.array([0.6, 0.3]), np.array([2, 1]), np.array([1, 2])
    expected = -(w * np.log(p) + l * np.log(1 - p)).sum()
    assert si.sequence_nll(p, w, l, 0) == pytest.approx(expected, rel=1e-6)


def test_fit_rho_recovers_simulated_value():
    rng = np.random.default_rng(1)
    rho, n = 0.2, 6000
    p = rng.uniform(0.2, 0.8, n)
    kappa = 1 / rho - 1
    pi = rng.beta(p * kappa, (1 - p) * kappa)
    w, l = np.zeros(n, int), np.zeros(n, int)
    for _ in range(5):
        live = (w < 3) & (l < 3)
        win = rng.random(n) < pi
        w += live & win
        l += live & ~win
    d = pd.DataFrame({"p": p, "w": w, "l": l})
    est, lo, hi = si.fit_rho(d)
    assert lo <= rho <= hi
    assert est == pytest.approx(rho, abs=0.05)


def test_fearless_labels():
    s = pd.DataFrame(
        {
            "league": ["A"] * 20 + ["B"] * 20 + ["C"] * 20,
            "year": 2025,
            "split": "Spring",
            "n": 3,
            "any_rep": [False] * 20
            + [True] * 19
            + [False]
            + [True] * 10
            + [False] * 10,
        }
    )
    labels = si.fearless_labels(s)
    assert labels[("A", 2025, "Spring")] == 1
    assert labels[("B", 2025, "Spring")] == 0
    assert np.isnan(labels[("C", 2025, "Spring")])


def test_rho_per_series_matches_one_at_a_time():
    p, bo = np.array([0.3, 0.6, 0.8]), np.array([3, 5, 3])
    rho = np.array([0.0, 0.1, 0.3])
    each = [si.beta_series(p[i], bo[i], rho[i])[()] for i in range(3)]
    assert si.beta_series(p, bo, rho) == pytest.approx(each)
