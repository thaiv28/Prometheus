"""Chronology, execution selection and bankroll accounting in the research study."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "live_trading", ROOT / "scripts/research/live_trading.py"
)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_walk_forward_never_learns_current_or_unavailable_series():
    n = 202
    train = pd.DataFrame(
        {
            "month": "2026-01",
            "series": np.repeat(np.arange(101), 2),
            "game": np.arange(n),
            "series_end": pd.Timestamp("2026-01-20", tz="UTC"),
            "p_lag": np.tile([0.4, 0.6], 101),
            "p": np.tile([0.3, 0.7], 101),
            "won": np.tile([0, 1], 101),
        }
    )
    test = train.iloc[:2].copy()
    test["month"] = "2026-02"
    test["series"] = [1000, 1001]
    test["game"] = [1000, 1001]
    test["series_end"] = pd.Timestamp("2026-02-01", tz="UTC")
    unavailable = train.iloc[:2].copy()
    unavailable["series"] = 2000
    unavailable["game"] = [2000, 2001]
    unavailable["series_end"] = pd.Timestamp("2026-01-31T23:00Z")
    rows = pd.concat([train, unavailable, test], ignore_index=True)
    before, fits = study.walk_forward(rows)
    rows.loc[rows.series.isin([1000, 1001, 2000]), "won"] = (
        1 - rows.loc[rows.series.isin([1000, 1001, 2000]), "won"]
    )
    after, later_fits = study.walk_forward(rows)
    assert fits == later_fits
    np.testing.assert_array_equal(before.blend, after.blend)
    assert fits[0]["train_maps"] == 202
    assert fits[0]["train_series"] == 101
    assert pd.Timestamp(fits[0]["latest_training_available"]) < pd.Timestamp(
        "2026-02-01", tz="UTC"
    )


def test_entry_requires_net_edge_and_fresh_valid_state_and_first_map_only():
    rows = pd.DataFrame(
        {
            "game": [1] * 6,
            "series": [1] * 6,
            "arrival": pd.date_range("2026-03-01", periods=6, freq="min", tz="UTC"),
            "blend": [0.56, 0.7, 0.7, 0.7, 0.7, 0.9],
            "won": 1,
            "p_lag": 0.5,
            "p_clv": 0.6,
            "cost0_21": 0.5,
            "cost1_21": 0.5,
            "n_21": 2,
            "range_21": 0.01,
            "flat": [False, True, False, False, False, False],
            "objectives_valid": [True, True, False, True, True, True],
            "quiet": [1, 1, 1, 11, 1, 1],
        }
    )
    bets = study.select(rows)
    assert len(bets) == 1
    assert bets.arrival.iloc[0] == rows.arrival.iloc[4]
    assert bets.eff.iloc[0] == pytest.approx(0.5175)
    # The first row's raw .06 gap is below .05 after fees.
    assert 0.56 - study.effective_cost(0.5) < 0.05
    stale = rows.assign(n_21=1)
    assert study.select(stale).empty
    crossed = rows.assign(range_21=0.02)
    assert study.select(crossed).empty


def test_market_orientation_and_cost_stress():
    row = pd.DataFrame(
        {
            "game": [1],
            "series": [1],
            "arrival": [pd.Timestamp("2026-03-01", tz="UTC")],
            "blend": [0.2],
            "won": [0],
            "p_lag": [0.4],
            "p_clv": [0.3],
            "cost0_21": [0.4],
            "cost1_21": [0.55],
            "n_21": [2],
            "range_21": [0.01],
            "flat": [False],
            "objectives_valid": [True],
            "quiet": [1],
        }
    )
    bet = study.select(row, stress=0.02).iloc[0]
    assert bet.side == 1 and bet.win == 1
    assert bet.price == pytest.approx(0.62)  # max(.55, 1-.4) + stress
    assert bet.prob == pytest.approx(0.8)
    assert bet.clv == pytest.approx(0.08)


def test_kelly_reserves_cash_and_caps_exposure_until_settlement():
    t = pd.Timestamp("2026-03-01", tz="UTC")
    bets = pd.DataFrame(
        {
            "arrival": [t, t + pd.Timedelta(minutes=1)],
            "end": [t + pd.Timedelta(minutes=30)] * 2,
            "series": [1, 1],
            "prob": [0.75, 0.75],
            "eff": [0.5, 0.5],
            "win": [1, 0],
        }
    )
    result = study.kelly(bets, 1)
    assert result["terminal"] == pytest.approx(100)  # $50 win, $50 loss
    assert result["max_held"] == pytest.approx(1)
    sequential = study.kelly(bets, 1, sequential=True)
    assert sequential["terminal"] == pytest.approx(75)  # $50 win, then $75 loss
    capped = study.kelly(bets, 1, map_cap=0.01, series_cap=0.015)
    assert capped["terminal"] == pytest.approx(100.5)
    assert capped["max_held"] == pytest.approx(0.015)
