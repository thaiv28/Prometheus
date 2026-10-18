"""The time-spline basis and columns in train_time_model_v3.py."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.interpolate import BSpline

RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
spec = importlib.util.spec_from_file_location("v3", RESEARCH / "train_time_model_v3.py")
v3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v3)


@pytest.mark.parametrize("x", [0, 1, 299.9, 300, 777, 1800, 2399.9, 2400])
def test_basis_matches_scipy_and_sums_to_one(x):
    k, d = v3.KNOTS, v3.DEGREE
    t = np.r_[[k[0]] * d, k, [k[-1]] * d]
    ref = np.nan_to_num(
        [
            BSpline.basis_element(t[i : i + d + 2], extrapolate=False)(x)
            for i in range(len(t) - d - 1)
        ]
    )
    if x == k[-1]:
        ref[-1] = 1.0
    ours = np.array(v3.spline_basis(k, d, x))
    assert np.allclose(ours, ref, atol=1e-12)
    assert ours.sum() == pytest.approx(1.0)


def test_basis_is_held_outside_the_knots():
    k, d = v3.KNOTS, v3.DEGREE
    assert v3.spline_basis(k, d, 3000) == v3.spline_basis(k, d, 2400)
    assert v3.spline_basis(k, d, -5) == v3.spline_basis(k, d, 0)


def test_columns_are_basis_then_each_input_times_it():
    x = v3.spline_features(v3.KNOTS, v3.DEGREE, 900.0, 16000.0, 15000.0, 1700.0, 1600.0)
    basis = v3.spline_basis(v3.KNOTS, v3.DEGREE, 900.0)
    n = len(basis)
    assert len(x) == 4 * n
    assert x[:n] == basis
    assert np.allclose(x[n : 2 * n], [1.0 * b for b in basis])  # gold lead, thousands
    assert np.allclose(x[3 * n :], [1.0 * b for b in basis])  # Elo gap, hundreds
