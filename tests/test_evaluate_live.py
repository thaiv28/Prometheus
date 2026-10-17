import datetime as dt
import importlib.util
import json
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "evaluate_live", ROOT / "scripts" / "evaluate_live.py"
)
el = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(el)

T0 = pd.Timestamp("2026-05-01T10:00:00Z")
FIELDS = list(el.STATS)


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
    }


def test_tape_orients_both_contracts_to_feed_team_zero():
    trades = {
        "M-T1": [_trade(0, 0.60, "yes")],  # someone backs T1 at 0.60
        "M-GEN": [_trade(5, 0.45, "yes"), _trade(9, 0.42, "no")],
    }
    tp = el.tape(_event(), trades, first_is_team1=True)
    assert list(tp["p0"].round(2)) == [0.60, 0.55, 0.58]
    # Gen.G yes at 0.45 backs team 1; Gen.G no at 0.58 backs team 0.
    assert list(tp["back"]) == [0, 1, 0]
    assert list(tp["cost"].round(2)) == [0.60, 0.45, 0.58]
    flipped = el.tape(_event(), trades, first_is_team1=False)
    assert list(flipped["p0"].round(2)) == [0.40, 0.45, 0.42]
    assert list(flipped["back"]) == [1, 0, 1]


def test_market_state_reads_only_the_past():
    trades = {"M-T1": [_trade(0, 0.60, "yes"), _trade(30, 0.70, "no")]}
    tp = el.tape(_event(), trades, first_is_team1=True)
    at = T0 + pd.Timedelta(seconds=40)
    assert el.quiet_for(tp, at) == 10
    assert el.price_at(tp, at) == 0.70
    assert el.cost_to_back(tp, at, 0) == 0.60
    assert abs(el.cost_to_back(tp, at, 1) - 0.30) < 1e-9
    assert el.cost_to_back(tp, T0 + pd.Timedelta(seconds=200), 0) is None
    assert el.quiet_for(tp, T0 - pd.Timedelta(seconds=1)) is None
    # A sample at 19 s: our call arrives at 40 s.
    state = dict(
        zip(el.MARKET_FIELDS, el.market_state(tp, at - pd.Timedelta(seconds=el.LAG)))
    )
    assert state["p_now"] == 0.60 and state["p_lag"] == 0.70 and state["quiet"] == 10
    assert state["trades"] == 2 and abs(state["spread"] - (-0.10)) < 1e-9


def test_match_market_handles_sponsor_names_and_side_order():
    start = dt.datetime(2026, 5, 1, 10, 30, tzinfo=dt.UTC)
    game = {
        "start": start.isoformat(),
        "teams": [
            {"name": "Beijing JDG Esports", "code": "JDG"},
            {"name": "Xi'an Team WE", "code": "WE"},
        ],
    }
    when = start - dt.timedelta(minutes=30)
    right = {"team1": "Team WE", "team2": "JDG", "start": when, "timed": True}
    wrong = {
        "team1": "Ninjas in Pyjamas",
        "team2": "Top Esports",
        "start": when,
        "timed": True,
    }
    event, same = el.match_market(game, [wrong, right])
    assert event is right and same is False
    # A generic word alone ("esports") doesn't match.
    assert el.match_market(game, [wrong]) is None


def _hist():
    return pd.DataFrame(
        {
            "teamname": ["G2", "KOI", "G2", "KOI"],
            "date": pd.to_datetime(
                ["2026-02-23T15:56Z"] * 2 + ["2026-02-20T15:00Z"] * 2, utc=True
            ),
            "side": ["Blue", "Red", "Red", "Blue"],
            "result": [1, 0, 0, 1],
            "gameid": ["g1", "g1", "g0", "g0"],
            "elo": [1600.0, 1500.0, 1590.0, 1510.0],
        }
    )


def test_sides_from_the_feed_or_oracles_elixir():
    start = pd.Timestamp("2026-02-23T15:57Z")
    assert el.oe_blue(_hist(), ["KOI", "G2"], start) == 1
    assert el.oe_blue(_hist(), ["G2", "KOI"], start) == 0
    assert el.oe_blue(_hist(), ["G2", "KOI"], start + pd.Timedelta(days=1)) is None
    assert el.elo_before(_hist(), "G2", "2026-02-23") == 1590.0
    # Map 2 an hour later: KOI 0, G2 1 so far (the map itself never counts).
    later = pd.Timestamp("2026-02-23T16:57Z")
    assert el.score_before(_hist(), ["KOI", "G2"], later) == [0, 1]
    assert el.score_before(_hist(), ["KOI", "G2"], start) == [0, 0]
    game = {"teams": [{"id": "a"}, {"id": "b"}], "blue_id": "b"}
    assert el.feed_blue(game) == 1
    assert el.feed_blue({"teams": [{"id": "a"}, {"id": "b"}]}) is None


def _sample(t, gold0, gold1, market=None):
    team = lambda gold: [gold, 0, 0, 0, 0, 0]
    return {
        "t": t,
        "state": "in_game",
        "flat": False,
        "teams": [team(gold0), team(gold1)],
        "market": market or [0.5, 0.5, 30.0, 0.5, 0.5, 0.5, 3, 0.02],
    }


def _map(samples, blue=1, won0=False, game="m1"):
    return {
        "game": game,
        "series": "s1",
        "league": "LCK",
        "map": 1,
        "start": T0.isoformat(),
        "end": (T0 + pd.Timedelta(minutes=35)).isoformat(),
        "teams": ["A", "B"],
        "blue": blue,
        "won0": won0,
        "pregame_market": [0.5, 0.5, 30.0, 0.5, 0.5, 0.5, 3, 0.02],
        "samples": samples,
    }


def test_map_calls_go_through_the_live_timeline_calls():
    model = json.loads(el.timeline.MODEL_PATH.read_text())
    m = _map(
        [_sample(0, 2500, 2500), _sample(600, 2500, 5500), _sample(660, 2500, 5600)]
    )
    pregame, calls = el.map_calls(m, model, [1500.0, 1500.0], FIELDS)
    # Team 0 plays red: under 50% at equal Elo, and lower once behind in gold.
    assert 0.4 < pregame < 0.5
    # The first frame is a call too (minute 0), as on the live page.
    assert [c["sample"] for c in calls] == [0, 1, 2]
    assert all(c["p"] < pregame - 0.1 for c in calls[1:])
    assert [round(c["minute"]) for c in calls] == [0, 10, 11]


def _calls(rows):
    cols = ["minute", "p", "quiet", "cost0", "cost1", "p_clv"]
    frame = pd.DataFrame(rows, columns=cols)
    return frame.assign(game="m1", series="s1", won=1, pregame=frame["minute"] == 0)


def test_first_bet_waits_for_a_quiet_market_and_edge():
    calls = _calls(
        [
            (0, 0.70, 30, 0.50, 0.50, 0.5),  # pregame: never bet
            (1, 0.52, 30, 0.50, 0.50, 0.5),  # no edge
            (2, 0.70, 15, 0.50, 0.50, 0.5),  # edge, market moved 15 s ago
            (3, 0.70, 25, 0.50, 0.50, 0.6),  # edge and quiet
        ]
    )
    bets = el.first_bets(calls, quiet=21, edge=0.05)
    assert len(bets) == 1 and bets["cost"].iloc[0] == 0.50
    assert bool(bets["won"].iloc[0]) and abs(bets["clv"].iloc[0] - 0.1) < 1e-9
    first = el.first_bets(calls, quiet=0, edge=0.05)
    assert abs(first["clv"].iloc[0]) < 1e-9  # the minute-2 call
    # Backing team 1 when our chance is low; CLV in team 1's terms.
    low = el.first_bets(_calls([(1, 0.30, 30, 0.70, 0.40, 0.45)]), quiet=10, edge=0.05)
    assert low["cost"].iloc[0] == 0.40 and not bool(low["won"].iloc[0])
    assert abs(low["clv"].iloc[0] - 0.15) < 1e-9


def test_kelly_and_flat_profit():
    bets = pd.DataFrame({"p": [0.7, 0.7], "cost": [0.5, 0.5], "won": [True, False]})
    flat = el.flat_profit(bets)
    assert abs(flat[0] - 0.96) < 1e-9  # fee: ceil(0.07 × 2 × 0.25 × 100) cents
    assert abs(flat[1] + 1.04) < 1e-9
    growth, multiple, drawdown = el.kelly_growth(bets)
    assert growth[0] > 0 > growth[1] and 0 < multiple and 0 < drawdown < 1


def _db(path):
    with sqlite3.connect(path) as conn:
        conn.execute(
            "CREATE TABLE matches (gameid, teamid, teamname, date, side, result)"
        )
        conn.execute("CREATE TABLE game_length_elo (gameid, teamid, post_match_elo)")
        for gid, day, elo_a, elo_b in (
            ("g0", "2026-04-30 10:00:00", 1550, 1450),
            ("g1", "2026-05-01 09:00:00", 1700, 1300),  # same day: not yet known
        ):
            conn.execute(
                "INSERT INTO matches VALUES (?,?,?,?,?,?)",
                (gid, "a", "A", day, "Blue", 1),
            )
            conn.execute(
                "INSERT INTO matches VALUES (?,?,?,?,?,?)",
                (gid, "b", "B", day, "Red", 0),
            )
            conn.execute(
                "INSERT INTO game_length_elo VALUES (?,?,?)", (gid, "a", elo_a)
            )
            conn.execute(
                "INSERT INTO game_length_elo VALUES (?,?,?)", (gid, "b", elo_b)
            )


def test_replay_checkpoints_and_dump(tmp_path):
    db = tmp_path / "p.db"
    _db(db)
    samples = [_sample(0, 2500, 2500)] + [
        _sample(
            60 * k + 5,
            2500 + 400 * k,
            2500 + 300 * k,
            [0.5, 0.55, 12.0, 0.55, 0.47, 0.6, 4, 0.02],
        )
        for k in range(1, 32)
    ]
    data = {
        "built": "2026-10-16",
        "fields": {"teams": FIELDS, "market": el.MARKET_FIELDS},
        "counts": {"maps": 1},
        "maps": [_map(samples, blue=0, won0=True)],
    }
    calls, skipped = el.replay(data, db=db)
    assert skipped == 0 and calls["pregame"].sum() == 1
    frame = el.checkpoints(calls)
    assert list(frame["checkpoint"]) == list(el.MINUTES)
    assert (frame["kalshi"] == 0.55).sum() == 6  # in game: Kalshi when our call arrives
    el.write_dump(calls, tmp_path / "dump")
    dump = pd.read_csv(tmp_path / "dump" / "calls.csv.gz")
    assert list(dump.columns) == [
        "game",
        "series",
        "start",
        "checkpoint",
        "ours",
        "kalshi",
        "won",
    ]
    assert np.isfinite(dump["ours"]).all()
    meta = json.loads((tmp_path / "dump" / "metrics.json").read_text())
    assert meta == {"fit_through": "2024-12-31"}  # v1: calibrated on 2024
    assert el.fit_through({"fit_through": "2025-06-30T00:00"}) == "2025-06-30"
