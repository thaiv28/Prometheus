"""Unit tests for game logs (prometheus/gamelog.py) and the market price export. No database."""

import importlib.util
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prometheus import gamelog
from prometheus.forge import CROSS_REGION_ELO_WEIGHT, ELO_WEIGHT, OTHER_LEAGUE_ELO_WEIGHT
from prometheus.schedule import series_probability
from prometheus.types import GLORY_FEATURES

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "export_market_prices", ROOT / "scripts" / "export_market_prices.py"
)
export_market_prices = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(export_market_prices)


def _game(
    gameid,
    date,
    team,
    opp,
    result,
    side="Blue",
    league="LCK",
    elo_pre=1500.0,
    opp_elo_pre=1500.0,
    change=10.0,
):
    return {
        "gameid": gameid,
        "date": date,
        "year": int(date[:4]),
        "league": league,
        "teamid": f"id-{team}",
        "teamname": team,
        "side": side,
        "gamelength": 1800,
        "result": result,
        "opp_id": f"id-{opp}",
        "opp": opp,
        "elo_pre": elo_pre,
        "elo": elo_pre + change,
        "elo_change": change,
        "opp_elo_pre": opp_elo_pre,
    }


def _games():
    """A vs B: a Bo3 won 2–1 on one evening, then a Bo1 a week later; C plays A once."""
    rows = []
    for gid, date, a_won in [
        ("g1", "2026-01-10 08:00:00", 1),
        ("g2", "2026-01-10 09:00:00", 0),
        ("g3", "2026-01-10 10:00:00", 1),
        ("g4", "2026-01-17 08:00:00", 0),
    ]:
        rows.append(
            _game(gid, date, "A", "B", a_won, "Blue", change=10.0 if a_won else -10.0)
        )
        rows.append(
            _game(
                gid, date, "B", "A", 1 - a_won, "Red", change=-10.0 if a_won else 10.0
            )
        )
    rows.append(_game("g5", "2026-01-18 08:00:00", "A", "C", 1, "Red", change=5.0))
    rows.append(_game("g5", "2026-01-18 08:00:00", "C", "A", 0, "Blue", change=-5.0))
    games = pd.DataFrame(rows)
    games["when"] = pd.to_datetime(games["date"])
    return games


def _states(games, homes=None, form=0.0):
    """Form states with every pre_ stat at `form` (so league-relative Form is 0)."""
    homes = homes or {}
    states = games[["gameid", "teamid", "teamname", "league", "year", "date"]].copy()
    states["home"] = [
        homes.get(t, l) for t, l in zip(games["teamname"], games["league"])
    ]
    for f in GLORY_FEATURES:
        states[f"pre_{f}"] = form
    return states


def test_series_split_on_opponent_and_gap():
    games = gamelog.add_series(_games())
    a = games[games["teamname"] == "A"].sort_values("when")
    assert a["series"].nunique() == 3  # the Bo3, the Bo1 a week later, then C
    assert a["series"].iloc[0] == a["series"].iloc[2] != a["series"].iloc[3]
    b = games[games["teamname"] == "B"]
    assert set(b["series"]).isdisjoint(set(a["series"]))  # each side has its own ids


def test_best_of_reads_the_score():
    assert gamelog.best_of(2, 1) == 3
    assert gamelog.best_of(3, 0) == 5
    assert gamelog.best_of(1, 0) == 1
    assert gamelog.best_of(1, 1) is None


def test_calls_use_forge_within_a_major_league_and_elo_otherwise():
    games = _games()
    games.loc[games["teamname"] == "A", "elo_pre"] = 1600.0
    games.loc[games["opp"] == "A", "opp_elo_pre"] = 1600.0
    weights = {f: 0.0 for f in GLORY_FEATURES}
    called = gamelog.add_calls(games, _states(games, {"C": "LEC"}), weights)
    a_vs_b = called[(called["teamname"] == "A") & (called["opp"] == "B")].iloc[0]
    assert a_vs_b["method"] == "forge"
    assert a_vs_b["p"] == pytest.approx(1 / (1 + math.exp(-ELO_WEIGHT * 100)))
    a_vs_c = called[(called["teamname"] == "A") & (called["opp"] == "C")].iloc[0]
    assert a_vs_c["method"] == "elo-cross"
    assert a_vs_c["p"] == pytest.approx(
        1 / (1 + math.exp(-CROSS_REGION_ELO_WEIGHT * 100))
    )
    # A minor league uses Elo on its own fitted curve.
    minor = gamelog.add_calls(
        games.assign(league="LJL"), _states(games.assign(league="LJL")), weights
    )
    assert minor.iloc[0]["method"] == "elo"
    assert minor.iloc[0]["p"] == pytest.approx(1 / (1 + math.exp(-OTHER_LEAGUE_ELO_WEIGHT * 100)))


def test_calls_skip_games_without_pre_game_elo():
    games = _games()
    games.loc[0, "elo_pre"] = np.nan
    called = gamelog.add_calls(games, _states(games), {})
    assert pd.isna(called.loc[0, "p"]) and called.loc[0, "method"] is None


def _prices():
    return [
        {
            "t1": "B",
            "t2": "A",
            "start": pd.Timestamp("2026-01-10 07:30"),
            "p1": 0.4,
            "ticker": "KX-AB",
        },
        {
            "t1": "A",
            "t2": "B",
            "start": pd.Timestamp("2026-03-01 07:30"),
            "p1": 0.9,
            "ticker": "KX-LATER",
        },
    ]


def test_price_book_orients_and_matches_by_time():
    book = gamelog.PriceBook(_prices())
    assert book.chance("A", "B", pd.Timestamp("2026-01-10 08:00")) == (
        pytest.approx(0.6),
        "KX-AB",
    )
    assert book.chance("B", "A", pd.Timestamp("2026-01-10 08:00")) == (
        pytest.approx(0.4),
        "KX-AB",
    )
    assert book.chance("A", "B", pd.Timestamp("2026-01-17 08:00")) == (
        None,
        None,
    )  # a week off
    assert book.chance("A", "C", pd.Timestamp("2026-01-18 08:00")) == (None, None)


def test_load_prices_adds_the_logs_prices(tmp_path):
    path = tmp_path / "prices.json"
    path.write_text(
        json.dumps(
            [
                {
                    "t1": "A",
                    "t2": "B",
                    "start": "2026-01-10T07:30Z",
                    "p1": 0.6,
                    "ticker": "KX-AB",
                }
            ]
        )
    )
    log = {
        "m1": {
            "matched": True,
            "ours1": "A",
            "ours2": "C",
            "start": "2026-01-18T08:00Z",
            "market": {"p": 0.7, "ticker": "KX-AC", "at": "2026-01-17T10:00Z"},
        },
        "m2": {
            "matched": True,
            "ours1": "A",
            "ours2": "B",
            "start": "2026-01-10T07:30Z",
            "market": {"p": 0.5, "ticker": "KX-AB"},
        },  # the file's price wins
        "m3": {"matched": False},
    }
    prices = gamelog.load_prices(path, log)
    assert [(p["ticker"], p["p1"]) for p in prices] == [("KX-AB", 0.6), ("KX-AC", 0.7)]
    assert prices[0]["start"] == pd.Timestamp("2026-01-10 07:30")
    assert gamelog.load_prices(tmp_path / "missing.json") == []


def _logs():
    games = gamelog.add_series(gamelog.add_calls(_games(), _states(_games()), {}))
    rows = []
    for gid in ["g1", "g2", "g3", "g4", "g5"]:
        for role, name in zip(gamelog.ROLE_ORDER, ["Top", "Jng", "Mid", "Bot", "Sup"]):
            pid = "sub" if (gid == "g2" and role == "mid") else f"a-{role}"
            rows.append(
                {
                    "gameid": gid,
                    "teamid": "id-A",
                    "position": role,
                    "playerid": pid,
                    "playername": "Sub" if pid == "sub" else name,
                    "champion": "Ahri" if role == "mid" else None,
                    "elo_pre": 1500.0,
                    "elo": 1504.0,
                }
            )
    players = pd.DataFrame(rows)
    heads = gamelog.series_heads(games, gamelog.PriceBook(_prices()))
    return games, players, heads


def test_team_log_series_newest_first_with_games_and_lineups():
    games, players, heads = _logs()
    log = gamelog.team_logs(games, players, heads, {"a-mid": "mid-page"})["A"]
    assert [s["o"] for s in log["series"]] == ["C", "B", "B"]
    bo3 = log["series"][2]
    assert (bo3["w"], bo3["x"], len(bo3["g"])) == (2, 1, 3)
    assert bo3["p"] == round(100 * series_probability(0.5, 3))
    assert bo3["k"] == 60 and bo3["kt"] == "KX-AB"
    assert bo3["de"] == 10.0 and bo3["e"] == 1510
    assert "m" not in bo3  # FORGE is the default and left out
    first, second = bo3["g"][0], bo3["g"][1]
    assert first == {
        "r": 1,
        "t": 1800,
        "s": "B",
        "p": 50,
        "de": 10.0,
        "ro": [0, 1, 2, 3, 4],
    }
    assert [log["players"][i] for i in second["ro"]][2] == ["Sub", None]
    assert log["players"][2] == ["Mid", "mid-page"]
    assert "k" not in log["series"][1]  # no price a week later


def test_player_log_keeps_the_teams_score_and_the_players_games():
    games, players, heads = _logs()
    logs = gamelog.player_logs(
        games,
        players,
        heads,
        {"a-mid": "mid-page", "sub": "sub-page"},
        {("g1", "a-mid"): 2.5},
    )
    mid = logs["mid-page"]
    assert mid["teams"] == ["A"]
    bo3 = mid["series"][2]
    assert (bo3["w"], bo3["x"], len(bo3["g"])) == (2, 1, 2)  # sat out game 2
    assert (
        bo3["g"][0]["c"] == "Ahri"
        and bo3["g"][0]["a"] == 2.5
        and "a" not in bo3["g"][1]
    )
    assert bo3["de"] == 8.0 and bo3["tm"] == 0
    assert [len(s["g"]) for s in logs["sub-page"]["series"]] == [1]
    assert "a-top" not in logs  # no page, no log


def test_year_records_count_series_and_logged_games():
    series = [
        {"d": "2026-02-01", "w": 2, "x": 1, "g": [{"r": 1}, {"r": 0}, {"r": 1}]},
        {"d": "2026-01-01", "w": 1, "x": 1, "g": [{"r": 1}, {"r": 0}]},
        {"d": "2025-06-01", "w": 0, "x": 2, "g": [{"r": 0}]},
    ]
    assert gamelog.year_records(series) == [["2026", 1, 0, 3, 2], ["2025", 0, 1, 0, 1]]


def test_export_market_prices_rows():
    frame = pd.DataFrame(
        {
            "ours1": ["A", "C"],
            "ours2": ["B", "D"],
            "event_ticker": ["KX-AB", "KX-CD"],
            "start": [
                pd.Timestamp("2026-05-02 10:00", tz="UTC"),
                pd.Timestamp("2026-05-01 09:00", tz="UTC"),
            ],
            "market_close": [0.61234, np.nan],
        }
    )
    assert export_market_prices.market_prices(frame) == [
        {
            "t1": "A",
            "t2": "B",
            "start": "2026-05-02T10:00Z",
            "p1": 0.6123,
            "ticker": "KX-AB",
        }
    ]
