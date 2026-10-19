import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "draft_player_feats", ROOT / "scripts/research/draft_player_feats.py"
)
dp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dp)


def fixture():
    rows = pd.DataFrame(
        {
            "gameid": ["a", "b", "c", "d", "e"],
            "playerid": ["p", "p", "q", "p", "q"],
            "teamid": ["t"] * 5,
            "position": ["mid", "mid", "mid", "top", "mid"],
            "champion": ["A", "B", "A", "A", "A"],
            "date": pd.to_datetime(
                ["2020-01-01", "2020-01-02", "2020-01-02", "2020-01-03", "2020-01-03"]
            ),
        }
    )
    rows["day"] = rows.date.dt.normalize()
    lanes = rows[["gameid", "playerid", "teamid"]].assign(
        gold=[100, 300, 999, 500, 0], xp=[200, 600, 999, 1000, 0]
    )
    return rows, lanes


def test_pool_lane_roles_and_incumbents_use_earlier_days_only():
    rows, lanes = fixture()
    actual = dp.features(rows, lanes)
    assert actual.loc[0, dp.EXTRA].eq(0).all()
    assert actual.loc[1, "breadth"] == np.log(2)
    assert actual.loc[1, "depth"] == 1
    assert actual.loc[1, "top_pool"] == 0
    assert actual.loc[2, "substitute"] == 1
    assert actual.loc[3, "role_swap"] == 1
    assert actual.loc[3, "lane_gold"] == (100 - 200) / 101 / 1000
    assert actual.loc[3, "lane_xp"] == (200 - 400) / 101 / 1000
    # q is last starter from the earlier day's chronological maps.
    assert actual.loc[4, "substitute"] == 0
    lanes.loc[lanes.gameid.isin(["b", "c"]), ["gold", "xp"]] = -9999
    rows.loc[2, "champion"] = "Z"
    changed = dp.features(rows, lanes)
    np.testing.assert_array_equal(actual.loc[:2, dp.EXTRA], changed.loc[:2, dp.EXTRA])


def test_missing_snapshots_shrink_to_zero():
    rows, lanes = fixture()
    actual = dp.features(rows, lanes.iloc[:0])
    assert actual[["lane_gold", "lane_xp"]].eq(0).all().all()
    assert not actual.lane_history.any()


def test_fit_never_uses_its_test_year_outcomes(monkeypatch):
    rng = np.random.default_rng(21)
    games = pd.DataFrame(
        rng.normal(size=(120, 5 + len(dp.EXTRA))),
        columns=["forge_logit", *dp.dw.FEATURES, *dp.EXTRA],
    )
    games["year"] = np.repeat([2019, 2020, 2021], 40)
    games["won"] = rng.integers(0, 2, len(games))
    monkeypatch.setattr(dp.dw, "TEST_YEARS", [2021])
    before, coef = dp.score(games)
    games.loc[games.year == 2021, "won"] ^= 1
    after, changed_coef = dp.score(games)
    np.testing.assert_array_equal(before.candidate, after.candidate)
    assert coef == changed_coef
