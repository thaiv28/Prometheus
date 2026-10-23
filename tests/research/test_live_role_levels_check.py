"""Synthetic role-level matching, orientation, fallback and replay checks."""

import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/research"))
study = importlib.import_module("live_role_levels_check")


def test_raw_match_tolerance():
    at = pd.Timestamp("2026-01-01T00:00:00Z")
    windows = {at: {"level_top": 1}, at + pd.Timedelta(seconds=10): {"level_top": 2}}
    assert study.match_raw(windows, at + pd.Timedelta(seconds=2)) == {"level_top": 1}
    assert study.match_raw(windows, at + pd.Timedelta(seconds=8)) == {"level_top": 2}
    assert study.match_raw(windows, at + pd.Timedelta(seconds=2.001)) is None
    assert study.match_raw({}, at) is None
    assert study.match_raw({at: None}, at) is None


def test_orientation_and_fallback():
    probabilities = study.candidate_probabilities(
        np.array([0.6, 0.6, 0.6, 0.6]),
        np.array([0.7, 0.7, 0.7, 0.7]),
        np.array([0, 1, 0, 1]),
        np.array([True, True, False, False]),
    )
    np.testing.assert_allclose(probabilities, [0.7, 1 - 0.7, 0.6, 0.6])


def calls():
    return pd.DataFrame(
        {
            "game": ["a", "a", "b", "a"],
            "minute": [0.0, 5.0, 5.0, 6.0],
            "pregame": [True, False, False, False],
            "p": [0.4, 0.5, 0.6, 0.7],
            "market": [1, 2, 3, 4],
        },
        index=[7, 4, 9, 1],
    )


def predictions():
    return pd.DataFrame(
        {"game": ["b", "a", "a"], "minute": [5.0, 6.0, 5.0], "level": [0.8, 0.9, 0.3]}
    )


def test_substitution_aligns_and_preserves_pregame():
    original = calls()
    out = study.substitute(original, predictions(), "level")
    expected = original.copy()
    expected["p"] = [0.4, 0.3, 0.8, 0.9]
    pd.testing.assert_frame_equal(out, expected)
    assert original.p.tolist() == [0.4, 0.5, 0.6, 0.7]


@pytest.mark.parametrize("kind", ["missing", "extra", "duplicate", "duplicate_replay"])
def test_substitution_requires_exact_unique_keys(kind):
    rows, probs = calls(), predictions()
    if kind == "missing":
        probs = probs.iloc[:-1]
    elif kind == "extra":
        probs = pd.concat(
            [probs, pd.DataFrame({"game": ["x"], "minute": [5.0], "level": [0.2]})]
        )
    elif kind == "duplicate":
        probs = pd.concat([probs, probs.iloc[:1]])
    else:
        rows = pd.concat([rows, rows.iloc[1:2]])
    with pytest.raises((AssertionError, pd.errors.MergeError)):
        study.substitute(rows, probs, "level")
