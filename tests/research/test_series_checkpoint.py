"""The series-lead check at gold checkpoints in series_checkpoint.py."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.special import expit

PATH = (
    Path(__file__).resolve().parents[2]
    / "scripts"
    / "research"
    / "series_checkpoint.py"
)
spec = importlib.util.spec_from_file_location("series_checkpoint", PATH)
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)


def synthetic(lead_effect, n=6000, seed=1):
    """Maps whose result depends on the live call's log-odds plus lead_effect * lead."""
    rng = np.random.default_rng(seed)
    x = rng.normal(0, 1, n)
    lead = rng.choice([-2, -1, 0, 1, 2], n)
    y = (rng.random(n) < expit(x + lead_effect * lead)).astype(int)
    return pd.DataFrame(
        {
            "series": np.arange(n),
            "year": np.where(np.arange(n) < n * 2 // 3, 2020, 2025),
            "k": 2,
            "result": y,
            "lead": lead,
            "shift": 0.0,
            "q": expit(x),
            "minute": 0,
        }
    )


def test_finds_a_real_lead_effect():
    (r,) = sc.evaluate(synthetic(0.4), np.random.default_rng(0))
    assert r["lead_lo"] > 0.2
    assert r["fitted"][2] < 0  # the whole interval improves on the live call


def test_no_lead_effect_is_not_a_gain():
    (r,) = sc.evaluate(synthetic(0.0), np.random.default_rng(0))
    assert r["lead_lo"] < 0 < r["lead_hi"]
    assert r["fitted"][1] < 0 < r["fitted"][2] or r["fitted"][0] >= 0


def test_series_ci_resamples_whole_series():
    diff = np.array([1.0, 1.0, -1.0, -1.0])
    mean, lo, hi = sc.series_ci(diff, np.array([0, 0, 1, 1]), np.random.default_rng(0))
    assert mean == pytest.approx(0.0)
    assert lo == pytest.approx(-1.0) and hi == pytest.approx(1.0)
