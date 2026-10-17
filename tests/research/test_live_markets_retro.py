import datetime as dt
import importlib.util
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location(
    "live_markets_retro", ROOT / "scripts" / "research" / "live_markets_retro.py"
)
lm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lm)

T0 = pd.Timestamp("2026-05-01T10:00:00Z")


def _event():
    return {
        "team1": "T1",
        "team2": "Gen.G",
        "markets": [
            {"ticker": "M-T1", "side": "T1"},
            {"ticker": "M-GEN", "side": "Gen.G"},
        ],
    }


def _trade(seconds, yes, taker):
    return {
        "created_time": (T0 + pd.Timedelta(seconds=seconds)).isoformat(),
        "yes_price_dollars": f"{yes:.4f}",
        "no_price_dollars": f"{1 - yes:.4f}",
        "taker_side": taker,
        "count_fp": "10",
    }


def test_tape_orients_both_contracts_to_feed_team_zero():
    trades = {
        "M-T1": [_trade(0, 0.60, "yes")],  # someone backs T1 at 0.60
        "M-GEN": [_trade(5, 0.45, "yes"), _trade(9, 0.42, "no")],
    }
    # Feed team 0 is T1 (Kalshi's team1).
    tp = lm.tape(_event(), trades, first_is_team1=True)
    assert list(tp["p0"].round(2)) == [0.60, 0.55, 0.58]
    # Gen.G yes at 0.45 backs team 1; Gen.G no at 0.58 backs team 0.
    assert list(tp["back"]) == [0, 1, 0]
    assert list(tp["cost"].round(2)) == [0.60, 0.45, 0.58]
    # Feed team 0 is Gen.G: every chance and side flips.
    flipped = lm.tape(_event(), trades, first_is_team1=False)
    assert list(flipped["p0"].round(2)) == [0.40, 0.45, 0.42]
    assert list(flipped["back"]) == [1, 0, 1]


def test_quiet_and_cost_read_only_the_past():
    trades = {"M-T1": [_trade(0, 0.60, "yes"), _trade(30, 0.70, "no")]}
    tp = lm.tape(_event(), trades, first_is_team1=True)
    at = T0 + pd.Timedelta(seconds=40)
    assert lm.quiet_for(tp, at) == 10
    assert lm.price_at(tp, at) == 0.70
    assert lm.cost_to_back(tp, at, 0) == 0.60  # last trade backing team 0
    assert abs(lm.cost_to_back(tp, at, 1) - 0.30) < 1e-9
    assert lm.cost_to_back(tp, T0 + pd.Timedelta(seconds=200), 0) is None  # stale
    assert lm.price_at(tp, T0 - pd.Timedelta(seconds=1)) is None


def _map(calls, trades, won0=True):
    tp = lm.tape(_event(), {"M-T1": trades}, first_is_team1=True)
    return {
        "series": "s1",
        "start": T0,
        "end": T0 + pd.Timedelta(minutes=30),
        "won0": won0,
        "tape": tp,
        "calls": pd.DataFrame(
            [
                {"clock": 60.0 * i, "source": T0 + pd.Timedelta(seconds=s), "p0": p}
                for i, (s, p) in enumerate(calls)
            ]
        ),
    }


def test_first_bet_waits_for_a_quiet_market_and_edge():
    trades = [_trade(0, 0.50, "yes"), _trade(55, 0.50, "yes"), _trade(100, 0.50, "yes")]
    # Calls arrive 21 s later: at 21 (quiet 21), 70 (quiet 15), 121 (quiet 21).
    m = _map([(0, 0.52), (49, 0.70), (100, 0.70)], trades)
    bets = lm.first_bets([m], lag=21, quiet=21, edge=0.05)
    assert len(bets) == 1
    assert bets["at"].iloc[0] == T0 + pd.Timedelta(seconds=121)
    assert bets["cost"].iloc[0] == 0.50 and bool(bets["won"].iloc[0])
    # Without a quiet rule the 70 s call bets first.
    first = lm.first_bets([m], lag=21, quiet=0, edge=0.05)
    assert first["at"].iloc[0] == T0 + pd.Timedelta(seconds=70)


def test_bet_on_team_one_when_our_chance_is_low():
    trades = [_trade(0, 0.60, "no")]  # backs team 1 at 0.40
    m = _map([(0, 0.30)], trades, won0=False)
    bets = lm.first_bets([m], lag=10, quiet=10, edge=0.05)
    assert bets["cost"].iloc[0] == 0.40 and bool(bets["won"].iloc[0])
    assert abs(bets["p"].iloc[0] - 0.70) < 1e-9


def test_kelly_and_flat_profit():
    bets = pd.DataFrame(
        {
            "at": [T0, T0 + pd.Timedelta(minutes=1)],
            "p": [0.7, 0.7],
            "cost": [0.5, 0.5],
            "won": [True, False],
            "series": ["a", "b"],
        }
    )
    flat = lm.flat_profit(bets)
    assert abs(flat[0] - (1.0 - 0.04)) < 1e-9  # fee: ceil(0.07 × 2 × 0.25 × 100) cents
    assert abs(flat[1] - (-1.04)) < 1e-9
    growth, multiple, drawdown = lm.kelly_growth(bets)
    assert multiple > 0
    assert growth[0] > 0 > growth[1] and 0 < drawdown < 1


def test_match_market_handles_sponsor_names_and_side_order():
    start = dt.datetime(2026, 5, 1, 10, 30, tzinfo=dt.UTC)
    game = {
        "start": start.isoformat(),
        "teams": [
            {"name": "Beijing JDG Esports", "code": "JDG"},
            {"name": "Xi'an Team WE", "code": "WE"},
        ],
    }
    right = {
        "team1": "Team WE",
        "team2": "JDG",
        "start": start - dt.timedelta(minutes=30),
        "timed": True,
    }
    wrong = {
        "team1": "Ninjas in Pyjamas",
        "team2": "Top Esports",
        "start": start - dt.timedelta(minutes=30),
        "timed": True,
    }
    event, same = lm.match_market(game, [wrong, right])
    assert event is right and same is False
    # A generic word alone ("esports") doesn't match.
    assert lm.match_market(game, [wrong]) is None


def test_our_calls_orient_to_feed_team_zero():
    model = json.loads(lm.MODEL.read_text())
    samples = [
        {
            "at": (T0 + pd.Timedelta(seconds=s)).isoformat(),
            "state": "in_game",
            "blue": {"gold": 2500 + g},
            "red": {"gold": 2500},
        }
        for s, g in ((0, 0), (600, 3000), (660, 3100))
    ]
    game = {
        "start": T0.isoformat(),
        "teams": [{"side": "blue"}, {"side": "red"}],  # labels ignored
        "samples": samples,
    }
    calls = lm.our_calls(game, [1500.0, 1500.0], model, blue=1)
    # Feed team 0 is red: under 50% at equal Elo, and lower once behind in gold.
    assert 0.4 < calls["p0"].iloc[0] < 0.5
    assert (calls["p0"].iloc[1:] < calls["p0"].iloc[0] - 0.1).all()
    assert list(calls["clock"].round()) == [0, 600, 660]


def test_oe_blue_reads_sides_from_the_nearest_game():
    hist = pd.DataFrame(
        {
            "teamname": ["G2", "KOI", "G2", "KOI"],
            "date": pd.to_datetime(
                ["2026-02-23T15:56Z"] * 2 + ["2026-02-20T15:00Z"] * 2, utc=True
            ),
            "side": ["Blue", "Red", "Red", "Blue"],
            "gameid": ["g1", "g1", "g0", "g0"],
            "elo": [1600.0, 1500.0, 1590.0, 1510.0],
        }
    )
    start = pd.Timestamp("2026-02-23T15:57Z")
    assert lm.oe_blue(hist, ["KOI", "G2"], start) == 1
    assert lm.oe_blue(hist, ["G2", "KOI"], start) == 0
    assert lm.oe_blue(hist, ["G2", "KOI"], start + pd.Timedelta(days=1)) is None
    assert lm.elo_before(hist, "G2", "2026-02-23") == 1590.0
