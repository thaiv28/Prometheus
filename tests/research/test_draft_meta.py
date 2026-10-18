import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "draft_meta", ROOT / "scripts/research/draft_meta.py"
)
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def fixture():
    rows = pd.DataFrame(
        {
            "gameid": ["g1", "g2", "g3", "g4"],
            "day": pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-02", "2020-01-03"]
            ),
            "champion": ["A"] * 4,
            "position": ["mid"] * 4,
            "league": ["LCK"] * 4,
            "wae": [0.5, -0.5, 0.5, 0.0],
            "one": [1.0] * 4,
        }
    )
    patch = pd.Series(
        ["10.1", "10.2", "10.2", "10.2"],
        index=pd.Index(rows.gameid, name="gameid"),
        name="patch",
    )
    bans = pd.DataFrame({"gameid": ["g1", "g2"], "champion": ["A", "A"]})
    return rows, patch, bans


def test_no_same_day_outcome_or_ban_leakage_and_patch_previous_weight():
    rows, patch, bans = fixture()
    actual = dm.features(rows, patch, bans)
    assert actual.loc[0, dm.EXTRA].eq(0).all()
    assert actual.loc[1, "patch_meta"] == 0.25 / 50.5
    assert actual.loc[1, "priority"] == 1 / 20.5
    assert actual.loc[1, "patch_meta"] == actual.loc[2, "patch_meta"]
    rows.loc[1:, "wae"] = 100
    bans.loc[1, "champion"] = "B"
    changed = dm.features(rows, patch, bans)
    np.testing.assert_array_equal(actual.loc[:2, dm.EXTRA], changed.loc[:2, dm.EXTRA])


def test_future_patch_and_champion_changes_do_not_change_earlier_features():
    rows, patch, bans = fixture()
    actual = dm.features(rows, patch, bans)
    patch.iloc[-1] = "99.99"
    rows.loc[3, "champion"] = "B"
    changed = dm.features(rows, patch, bans)
    np.testing.assert_array_equal(actual.loc[:2, dm.EXTRA], changed.loc[:2, dm.EXTRA])


def test_test_year_outcomes_do_not_change_its_fitted_predictions(monkeypatch):
    rng = np.random.default_rng(12)
    games = pd.DataFrame(
        rng.normal(size=(120, 8)), columns=["forge_logit", *dm.dw.FEATURES, *dm.EXTRA]
    )
    games["year"] = np.repeat([2019, 2020, 2021], 40)
    games["won"] = rng.integers(0, 2, len(games))
    monkeypatch.setattr(dm.dw, "TEST_YEARS", [2021])
    actual, coefs = dm.score(games, dm.EXTRA)
    games.loc[games.year == 2021, "won"] ^= 1
    changed, changed_coefs = dm.score(games, dm.EXTRA)
    np.testing.assert_array_equal(actual.candidate, changed.candidate)
    assert coefs == changed_coefs
