"""Causal draft fitting, retained missing inputs and CI-compatible pairing."""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/research"))
import live_draft_v3 as lv


def games():
    rng = np.random.default_rng(7)
    frame = pd.DataFrame(
        {
            name: rng.normal(size=48)
            for name in ["forge_logit", *lv.dw.FEATURES, *lv.EXTRA]
        }
    )
    frame["gameid"] = [f"g{i}" for i in range(48)]
    frame["year"] = np.repeat([2022, 2023, 2024, 2025], 12)
    frame["won"] = np.tile([0, 1], 24)
    return frame


def test_draft_targets_do_not_train_their_own_shift():
    original = games()
    a = lv.draft_shifts(original)
    future = original.copy()
    future.loc[future.year >= 2025, "won"] = 1 - future.loc[future.year >= 2025, "won"]
    pd.testing.assert_frame_equal(a, lv.draft_shifts(future))
    # 2024 labels may train 2025 inputs, never their own 2024 inputs.
    future = original.copy()
    future.loc[future.year == 2024, "won"] = 1 - future.loc[future.year == 2024, "won"]
    b = lv.draft_shifts(future)
    ids = original.loc[original.year == 2024, "gameid"]
    pd.testing.assert_frame_equal(a.loc[ids], b.loc[ids])
    with pytest.raises(ValueError, match="duplicate"):
        lv.draft_shifts(pd.concat([original, original.iloc[:1]]))


def test_missing_draft_retains_rows_and_zeroes_both_terms():
    frame = pd.DataFrame(
        {"game_id": ["known", "missing"], "time": [0.5, 1.5]}, index=[9, 4]
    )
    shifts = pd.DataFrame({"v3": [0.4]}, index=["known"])
    out = lv.add_draft(frame, shifts, "v3")
    assert list(out.index) == [9, 4]
    assert list(out.draft) == [0.4, 0]
    assert list(out.draft_time) == [0.2, 0]
    assert list(out.draft_known) == [True, False]
    assert "draft" not in frame


def test_split_rejects_series_crossing_calibration_boundary():
    frame = pd.DataFrame(
        {
            "date": ["2024-12-31", "2025-01-01", "2025-07-01"],
            "source": ["feed"] * 3,
            "seconds": [60] * 3,
            "series": ["a", "a", "b"],
        }
    )
    with pytest.raises(ValueError, match="crosses"):
        lv.split_rows(frame)
    frame["series"] = ["a", "b", "c"]
    assert [len(p) for p in lv.split_rows(frame)] == [1, 1, 1]


def test_research_dump_uses_actual_in_game_checkpoints(tmp_path):
    frame = pd.DataFrame(
        {
            "game_id": ["g", "g"],
            "series": ["s", "s"],
            "date": ["2025-07-02"] * 2,
            "seconds": [299, 601],
            "won": [1, 1],
        }
    )
    lv.checkpoint_dump(frame, np.array([0.6, 0.9]), tmp_path)
    dump = pd.read_csv(tmp_path / "calls.csv.gz")
    # 601s is future information at 10m and cannot be selected there.
    assert list(dump.checkpoint) == [5]
    assert list(dump.ours) == [0.6]
    assert dump.kalshi.isna().all()
    assert (
        json.loads((tmp_path / "metrics.json").read_text())["fit_through"]
        == "2025-06-30"
    )
