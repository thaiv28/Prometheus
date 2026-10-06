import datetime
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prometheus import markets

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "evaluate_markets", ROOT / "scripts" / "evaluate_markets.py"
)
evaluate_markets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(evaluate_markets)


def _market(
    side,
    team1="T1",
    team2="Gen.G",
    result="yes",
    when="Aug 3, 2026 at 2:00 PM EDT",
    map_no=None,
    event="KXLOLGAME-X",
):
    where = f"map {map_no} in the" if map_no else "the"
    return {
        "ticker": f"{event}-{side}",
        "event_ticker": event,
        "rules_primary": f"If {side} wins {where} LCK 2026: {team1} vs. {team2} League of Legends match originally scheduled for {when}, then the market resolves to Yes.",
        "result": result,
        "open_time": "2026-08-02T18:00:00Z",
        "close_time": "2026-08-03T21:00:00Z",
        "volume_fp": "100.00",
    }


def test_parse_market_reads_teams_and_converts_eastern_time():
    m = markets.parse_market(_market("Gen.G"))
    assert (m["team1"], m["team2"], m["side"], m["map"], m["won"]) == (
        "T1",
        "Gen.G",
        "Gen.G",
        None,
        True,
    )
    assert m["start"] == datetime.datetime(
        2026, 8, 3, 18, 0, tzinfo=datetime.timezone.utc
    )


def test_parse_market_handles_winter_time_maps_and_day_only_rules():
    m = markets.parse_market(
        _market("T1", when="Jan 15, 2026 at 5:00 AM EST", map_no=1)
    )
    assert m["map"] == 1
    assert m["start"] == datetime.datetime(
        2026, 1, 15, 10, 0, tzinfo=datetime.timezone.utc
    )
    day_only = markets.parse_market(_market("T1", when="Apr 2, 2026"))
    assert day_only["start"] == datetime.datetime(
        2026, 4, 2, 4, 0, tzinfo=datetime.timezone.utc
    )


def test_parse_market_keeps_a_colon_inside_the_event_name():
    m = _market("Deer Gaming", team1="Deer Gaming", team2="Ruddy Corporation")
    m["rules_primary"] = m["rules_primary"].replace(
        "LCK 2026", "NLC 2026 (Summer: Regular Season)"
    )
    parsed = markets.parse_market(m)
    assert (parsed["event"], parsed["team1"]) == (
        "NLC 2026 (Summer: Regular Season)",
        "Deer Gaming",
    )


def test_parse_market_skips_markets_settled_at_a_price():
    assert markets.parse_market(_market("T1", result="scalar")) is None


def test_events_group_contracts_and_take_team1_result():
    rows = markets.events([_market("T1", result="no"), _market("Gen.G", result="yes")])
    assert len(rows) == 1
    assert rows[0]["won1"] is False
    assert len(rows[0]["markets"]) == 2


def _candle(end, bid, ask, live=True):
    key = "close_dollars" if live else "close"
    return {
        "end_period_ts": end,
        "yes_bid": {key: str(bid)},
        "yes_ask": {key: str(ask)},
    }


def test_quote_at_takes_last_two_sided_quote_by_the_time():
    candles = [
        _candle(100, 0.40, 0.44),
        _candle(200, 0.0, 1.0),
        _candle(300, 0.60, 0.62, live=False),
    ]
    assert markets.quote_at(candles, 250) == pytest.approx((0.42, 0.04))
    assert markets.quote_at(candles, 300) == pytest.approx((0.61, 0.02))
    assert markets.quote_at(candles, 50) == (None, None)


def test_market_chance_averages_both_contracts_and_drops_wide_spreads(monkeypatch):
    start = datetime.datetime(2026, 8, 3, 18, tzinfo=datetime.timezone.utc)
    ts = int(start.timestamp())
    books = {
        "a": [_candle(ts, 0.60, 0.64)],  # T1: 0.62
        "b": [_candle(ts, 0.34, 0.38)],  # Gen.G: 0.36 -> T1 0.64
        "c": [_candle(ts, 0.20, 0.50)],  # too wide
    }
    monkeypatch.setattr(
        evaluate_markets, "cached_candles", lambda ticker: books.get(ticker)
    )
    markets = [
        {"ticker": "a", "side": "T1", "open": "2026-08-02T18:00:00Z", "start": start},
        {
            "ticker": "b",
            "side": "Gen.G",
            "open": "2026-08-02T18:00:00Z",
            "start": start,
        },
    ]
    chance, spread = evaluate_markets.market_chance(markets, "T1", start)
    assert chance == pytest.approx(0.63)
    assert spread == pytest.approx(0.04)
    uncached = [{"ticker": "z", "side": "T1"}]
    assert evaluate_markets.market_chance(uncached, "T1", start) == (None, None)
    wide = [
        {"ticker": "c", "side": "T1", "open": "2026-08-02T18:00:00Z", "start": start}
    ]
    assert evaluate_markets.market_chance(wide, "T1", start) == (None, None)


def test_series_games_counts_wins_around_the_start():
    pairs = pd.DataFrame(
        {
            "team": ["T1", "T1", "T1", "T1"],
            "opponent": ["Gen.G", "Gen.G", "Gen.G", "Gen.G"],
            "result": [1, 0, 1, 1],
            "day": [datetime.date(2026, 8, 3)] * 3 + [datetime.date(2026, 8, 20)],
        }
    )
    start = datetime.datetime(2026, 8, 3, 18, tzinfo=datetime.timezone.utc)
    assert evaluate_markets.series_games(pairs, "T1", "Gen.G", start) == (2, 1)


def test_combined_weights_find_the_informative_forecast():
    rng = np.random.default_rng(1)
    truth = rng.uniform(0.1, 0.9, 3000)
    won = (rng.uniform(size=truth.size) < truth).astype(int)
    frame = pd.DataFrame(
        {"market": truth, "noise": rng.uniform(0.1, 0.9, truth.size), "won1": won}
    )
    w = evaluate_markets.combined_weights(frame, "noise", "market", n_resamples=50)
    assert w["market"][1] < 1 < w["market"][2]
    assert w["ours"][1] < 0 < w["ours"][2]
