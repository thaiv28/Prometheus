import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/research"))
spec = importlib.util.spec_from_file_location(
    "draft_market_edge", ROOT / "scripts/research/draft_market_edge.py"
)
dm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(dm)


def tape():
    at = pd.Timestamp("2026-04-01T12:00:00Z")
    return at, pd.DataFrame(
        {
            "at": [
                at - pd.Timedelta(seconds=20),
                at - pd.Timedelta(seconds=2),
                at + pd.Timedelta(seconds=5),
            ],
            "p0": [0.4, 0.5, 0.6],
            "back": [0, 1, 0],
            "cost": [0.4, 0.5, 0.6],
        }
    )


def frame(state):
    return pd.DataFrame(
        [
            {
                "close1": np.nan,
                "close3": np.nan,
                "close5": np.nan,
                **state,
                "gameid": "g",
                "day": "2026-04-01",
                "series": "s",
                "league": "LCK",
                "won": 1,
                "shift": 1.0,
            }
        ]
    )


def test_future_trade_never_changes_decision_cost_or_side():
    at, tp = tape()
    before = dm.state(tp, at, 30)
    tp.loc[2, ["p0", "cost"]] = 0.9
    after = dm.state(tp, at, 30)
    assert before["market"] == after["market"] == 0.5
    assert before["decision0"] == after["decision0"] == 0.5
    assert before["fill0"] == 0.6
    assert after["fill0"] == 0.9
    first = dm.bets(frame(before), 1, 2, 0.02)
    adverse = dm.bets(frame(after), 1, 2, 0.02)
    # Keep the selected blue side even after a fill worse than our chance.
    assert first.side.tolist() == adverse.side.tolist() == [0]
    assert adverse.cost.iloc[0] > adverse.p.iloc[0]
    assert first.growth.iloc[0] > adverse.growth.iloc[0]


def test_recent_trade_is_required_for_market_and_own_side():
    at, tp = tape()
    s = dm.state(tp, at, 10)
    assert s["market"] == 0.5
    assert np.isnan(s["decision0"])
    assert dm.bets(frame(s), 1, 2, 0.02).empty
    s = dm.state(tp, at + pd.Timedelta(minutes=2), 30)
    assert s["market"] is None


def test_no_fill_proxy_means_no_bet_but_last_sensitivity_can_trade():
    at, tp = tape()
    s = dm.state(tp.iloc[:2], at, 30)
    assert dm.bets(frame(s), 1, 2, 0.02).empty
    assert len(dm.bets(frame(s), 1, 2, 0.02, "last")) == 1


def test_worst_recent_trade_and_latest_price_floor_are_respected():
    at, tp = tape()
    tp.loc[0, ["p0", "cost"]] = 0.7
    s = dm.state(tp, at, 30)
    assert s["decision0"] == 0.7
    assert s["fill0"] == 0.7


def test_fee_roi_and_growth_share_all_in_cost():
    at, tp = tape()
    b = dm.bets(frame(dm.state(tp, at, 30)), 1, 2, 0.02)
    assert dm.total_cost(0.5) == 0.52
    assert b.cost.iloc[0] == 0.62
    assert b.roi.iloc[0] == pytest.approx(1 / 0.62 - 1)
    assert b.growth.iloc[0] == pytest.approx(np.log1p(0.1 * b.roi.iloc[0]))


def test_test_half_is_never_allowed_in_weight_fit_or_policy_selection():
    f = pd.DataFrame(
        {
            "day": ["2026-04-30", "2026-05-01"],
            "market": [0.5, 0.5],
            "shift": [0.1, 0.1],
            "won": [0, 1],
        }
    )
    with pytest.raises(ValueError, match="held-out"):
        dm.fit_weight(f, 0.5)
    with pytest.raises(ValueError, match="held-out"):
        dm.select(f)


def test_weight_shrinks_and_is_symmetric_under_side_reversal():
    f = pd.DataFrame(
        {
            "day": ["2026-04-30"] * 40,
            "market": [0.4, 0.6] * 20,
            "shift": [0.2, -0.2] * 20,
            "won": [1, 0] * 20,
        }
    )
    weight = dm.fit_weight(f, 0.5)
    reverse = f.assign(market=1 - f.market, shift=-f["shift"], won=1 - f.won)
    assert dm.fit_weight(reverse, 0.5) == pytest.approx(weight, abs=1e-5)
    assert 0 < weight <= 2
    assert np.allclose(
        dm.probability(reverse, 0.5, weight), 1 - dm.probability(f, 0.5, weight)
    )
