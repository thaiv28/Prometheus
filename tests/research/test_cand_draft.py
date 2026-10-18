"""The draft-shift helpers in scripts/research/cand_draft.py."""

import importlib.util
import sqlite3
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))
spec = importlib.util.spec_from_file_location("cand", RESEARCH / "cand_draft.py")
cand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cand)


def test_add_draft_drops_maps_without_a_shift_and_scales_by_time():
    frame = pd.DataFrame({"game_id": ["a", "a", "b", "c"], "time": [0, 0.5, 1, 2]})
    shifts = pd.DataFrame({"shift": [0.4, -0.2]}, index=["a", "c"])
    out = cand.add_draft(frame, shifts, "shift")
    assert list(out.game_id) == ["a", "a", "c"]
    assert np.allclose(out.draft, [0.4, 0.4, -0.2])
    assert np.allclose(out.draft_time, [0.0, 0.2, -0.4])
    assert "draft" not in frame  # the input is not changed


def test_draft_weight_undoes_the_scaling():
    rng = np.random.default_rng(0)
    x = rng.normal(size=(500, 2)) * [3.0, 0.5]
    y = (x[:, 0] + rng.normal(size=500) > 0).astype(int)
    scaler = StandardScaler().fit(x)
    base = LogisticRegression().fit(scaler.transform(x), y)
    raw = base.coef_[0] / scaler.scale_
    fitted = (scaler, base, None)
    cols = ["draft", "draft_time"]
    assert np.isclose(cand.draft_weight(fitted, cols, 0), raw[0])
    assert np.isclose(cand.draft_weight(fitted, cols, 1200), raw[0] + raw[1])
    assert np.isclose(cand.draft_weight(fitted, cols, 600), raw[0] + raw[1] / 2)


def test_draft_terms_leave_out_intercept_and_elo():
    frame = pd.DataFrame({"elo_logit": [1.0], "meta": [0.5], "synergy": [-1.0]})
    coef = {"intercept": 0.1, "elo_logit": 2.0, "meta": 1.0, "synergy": 0.3}
    assert np.allclose(cand.draft_terms(frame, coef), [0.5 - 0.3])


def test_drop_reasons(tmp_path):
    db = tmp_path / "t.db"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE game_length_elo (gameid TEXT, teamid TEXT)")
        conn.execute("CREATE TABLE player_stats (gameid TEXT, champion TEXT)")
        conn.executemany(
            "INSERT INTO game_length_elo VALUES (?, ?)",
            [("a", "x"), ("b", "x"), ("b", "y"), ("c", "x"), ("c", "y")],
        )
        conn.executemany(
            "INSERT INTO player_stats VALUES (?, ?)",
            [("b", "Ahri")] * 9 + [("b", "")] + [("c", "Ahri")] * 10,
        )
    assert cand.drop_reasons(["a", "b", "c", "d"], db) == {
        "no game-length Elo": 2,
        "fewer than ten champions": 1,
        "other": 1,
    }
    assert cand.drop_reasons([], db)["other"] == 0


def test_tiers():
    assert cand.tier("Worlds") == "International"
    assert cand.tier("LCK") == "Major league"
    assert cand.tier("LJL") == "Other"
