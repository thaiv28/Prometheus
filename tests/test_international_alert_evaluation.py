"""Critical quote-cutoff and executable-side rules for the offline experiment."""

import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "international_alerts",
    Path(__file__).parents[1] / "scripts/research/international_alerts.py",
)
research = importlib.util.module_from_spec(spec)
spec.loader.exec_module(research)


def candle(end, bid="0.40", ask="0.42"):
    return {
        "end_period_ts": end,
        "yes_bid": {"close_dollars": bid},
        "yes_ask": {"close_dollars": ask},
    }


def test_quote_rejects_future_and_stale_and_sorts_closes():
    assert research.fresh_book([candle(6399), candle(10001)], 10000) == (None, None)
    assert research.fresh_book(
        [candle(10000, "0.50", "0.52"), candle(6400)], 10000
    ) == (0.5, 0.52)


def test_candidates_use_best_available_side_and_actual_ask_not_midpoint():
    frame = pd.DataFrame(
        [
            {
                "persistent_12h": 0.3,
                "cost1": 0.28,
                "cost2": 0.6,
                "won1": False,
                "market_close": 0.35,
            },
            {
                "persistent_12h": 0.6,
                "cost1": 0.58,
                "cost2": 0.45,
                "won1": True,
                "market_close": 0.6,
            },
        ]
    )
    bets = research.candidates(frame)
    assert len(bets) == 1 and bets.iloc[0].side == 2
    assert bets.iloc[0].price == 0.6 and bets.iloc[0].won
    assert bets.iloc[0].clv == pytest.approx(0.05)
