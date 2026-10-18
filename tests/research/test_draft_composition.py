"""Causal history and chronological-fit guards for composition research."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
spec = importlib.util.spec_from_file_location(
    "draft_composition", ROOT / "scripts/research/draft_composition.py"
)
dc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dc)


def test_profiles_exclude_same_day_and_future_outcomes_and_snapshots():
    rows = pd.DataFrame(
        {
            "champion": ["A"] * 4,
            "position": ["mid"] * 4,
            "day": pd.to_datetime(
                ["2020-01-01", "2020-01-01", "2020-01-02", "2020-01-03"]
            ),
            "wae": [0.5, 0.5, -0.5, 0.5],
            "gamelength": [2000, 2000, 1000, 2000],
            "early_obs": [1.0, 2.0, 3.0, 4.0],
        }
    )
    before = dc.profiles(rows)
    assert list(before.scaling[:2]) == [0, 0]
    assert list(before.early[:2]) == [0, 0]
    assert np.isclose(before.scaling[2], 1 / 102)
    assert np.isclose(before.early[2], 3 / 52)
    rows.loc[2:, ["wae", "early_obs", "gamelength"]] = [100, 100, 100]
    after = dc.profiles(rows)
    np.testing.assert_array_equal(
        before.loc[:2, ["scaling", "early"]], after.loc[:2, ["scaling", "early"]]
    )


def test_augmented_fits_never_see_test_year(monkeypatch):
    games = pd.DataFrame({"year": [2019, 2020, 2021, 2022], "won": [0, 1, 0, 1]})
    for c in ["forge_logit", *dc.dw.FEATURES, *dc.EXTRA]:
        games[c] = 0.0
    calls = []

    class Model:
        coef_ = np.zeros((1, 8))

        def predict_proba(self, x):
            return np.tile([0.5, 0.5], (len(x), 1))

    def fit(frame, cols):
        calls.append(tuple(frame.year))
        return Model()

    monkeypatch.setattr(dc.dw, "_fit", fit)
    monkeypatch.setattr(dc.dw, "TEST_YEARS", [2021, 2022])
    scored, _ = dc.score(games)
    assert calls == [(2019, 2020), (2019, 2020), (2019, 2020, 2021), (2019, 2020, 2021)]
    assert list(scored.year) == [2021, 2022]


def test_frozen_cache_keeps_training_years_and_excludes_unrated_games(
    monkeypatch, tmp_path
):
    games = pd.DataFrame({"gameid": ["a", "b", "c"], "year": [2019, 2020, 2021]})
    pd.DataFrame({"gameid": ["a", "b"], "p_forge": [0.4, 0.7]}).to_pickle(
        tmp_path / "forge.pkl"
    )
    monkeypatch.setattr(dc.dw, "CACHE", tmp_path)
    monkeypatch.setattr(dc.dw, "load_rows", lambda: None)
    monkeypatch.setattr(dc.dw, "player_features", lambda rows: rows)
    monkeypatch.setattr(dc.dw, "synergy", lambda rows: None)
    monkeypatch.setattr(dc.dw, "game_table", lambda rows, synergy: games)
    result = dc.base_games()
    assert list(result.year) == [2019, 2020]
    np.testing.assert_allclose(result.forge_logit, np.log([0.4 / 0.6, 0.7 / 0.3]))
    monkeypatch.setattr(
        dc.dw,
        "load_rows",
        lambda: (_ for _ in ()).throw(AssertionError("cache reread DB")),
    )
    pd.testing.assert_frame_equal(result, dc.base_games())
