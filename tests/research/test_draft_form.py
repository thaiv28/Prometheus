"""Guards for daily comfort history and development-only half-life selection."""

import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
spec = importlib.util.spec_from_file_location(
    "draft_form", ROOT / "scripts/research/draft_form.py"
)
df = importlib.util.module_from_spec(spec)
spec.loader.exec_module(df)


def test_comfort_excludes_current_day_and_decays_whole_player_history():
    rows = pd.DataFrame(
        {
            "playerid": ["p"] * 4,
            "champion": ["A", "B", "A", "A"],
            "day": pd.to_datetime(
                ["2020-01-01", "2020-01-01", "2020-01-31", "2020-02-01"]
            ),
        }
    )
    out = df.comfort(rows, 30)
    np.testing.assert_allclose(out.loc[:1, "decayed_exp"], 0)
    np.testing.assert_allclose(out.loc[:1, "recency"], np.log1p(365))
    assert np.isclose(out.loc[2, "decayed_exp"], np.log1p(0.5))
    assert np.isclose(out.loc[2, "share"], 0.5 / 6)
    assert np.isclose(out.loc[2, "recency"], np.log1p(30))
    rows.loc[2:, "champion"] = "B"
    changed = df.comfort(rows, 30)
    np.testing.assert_array_equal(out.loc[:1, df.EXTRA], changed.loc[:1, df.EXTRA])


def test_half_life_selection_never_reads_test_years(monkeypatch):
    games = pd.DataFrame({"year": [2019, 2020, 2021], "won": [0, 1, 0]})
    for col in ["forge_logit", *df.dw.FEATURES, *df.EXTRA]:
        games[col] = [0, 1, 999]
    calls = []

    class Model:
        def predict_proba(self, x):
            assert len(x) == 1
            assert np.max(x) == 1
            return np.array([[0.25, 0.75]])

    def fit(frame, cols):
        calls.append(tuple(frame.year))
        return Model()

    monkeypatch.setattr(df.dw, "_fit", fit)
    half, losses = df.choose_half_life({30: games, 90: games, 180: games})
    assert half == 30
    assert set(losses) == {30, 90, 180}
    assert calls == [(2019,)] * 3


def test_walkforward_fits_only_earlier_years(monkeypatch):
    games = pd.DataFrame({"year": [2019, 2020, 2021, 2022], "won": [0, 1, 0, 1]})
    for col in ["forge_logit", *df.dw.FEATURES, *df.EXTRA]:
        games[col] = 0.0
    calls = []

    class Model:
        coef_ = np.zeros((1, 8))

        def predict_proba(self, x):
            return np.tile([0.5, 0.5], (len(x), 1))

    def fit(frame, cols):
        calls.append(tuple(frame.year))
        return Model()

    monkeypatch.setattr(df.dw, "_fit", fit)
    monkeypatch.setattr(df.dw, "TEST_YEARS", [2021, 2022])
    scored, _ = df.score(games)
    assert calls == [(2019, 2020), (2019, 2020), (2019, 2020, 2021), (2019, 2020, 2021)]
    assert list(scored.year) == [2021, 2022]


def test_frozen_cache_keeps_training_years_and_excludes_unrated_games(
    monkeypatch, tmp_path
):
    games = pd.DataFrame({"gameid": ["a", "b", "c"], "year": [2019, 2020, 2021]})
    pd.DataFrame({"gameid": ["a", "b"], "p_forge": [0.4, 0.7]}).to_pickle(
        tmp_path / "forge.pkl"
    )
    monkeypatch.setattr(df.dw, "CACHE", tmp_path)
    monkeypatch.setattr(df.dw, "load_rows", lambda: None)
    monkeypatch.setattr(df.dw, "player_features", lambda rows: rows)
    monkeypatch.setattr(df.dw, "synergy", lambda rows: None)
    monkeypatch.setattr(df.dw, "game_table", lambda rows, synergy: games)
    result = df.base_games()
    assert list(result.year) == [2019, 2020]
    np.testing.assert_allclose(result.forge_logit, np.log([0.4 / 0.6, 0.7 / 0.3]))
    monkeypatch.setattr(
        df.dw,
        "load_rows",
        lambda: (_ for _ in ()).throw(AssertionError("cache reread DB")),
    )
    pd.testing.assert_frame_equal(result, df.base_games())
