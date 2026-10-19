"""Database-free provisional result refresh."""

import datetime
import importlib.util
import json
import sys
from collections import namedtuple
from pathlib import Path

import pandas as pd
import pytest

from prometheus import fresh, schedule
from prometheus.elo import EloState, calculate_game_length_elo_change


def setup():
    state = EloState(calculate_game_length_elo_change)
    Game = namedtuple("Game", "gameid teamid opponent_teamid gamelength result date")
    for team1, team2, league in [
        ("a", "b", "LCK"),
        ("c", "d", "LPL"),
        ("e", "f", "LEC"),
    ]:
        state.rosters["old" + team1, team1] = (team1 + "1", team1 + "2")
        state.rosters["old" + team1, team2] = (team2 + "1", team2 + "2")
        date = pd.Timestamp("2026-10-17 10:00")
        state.play(Game("old" + team1, team1, team2, 1800, 1, date), league, date)
    inputs = {
        t.upper(): {
            "league": state.home[t],
            "elo": state.team_rating(t),
            "form": 10.0,
            "forge": state.team_rating(t) + 10.0,
            "has_form": True,
            "latest_date": "2026-10-17",
        }
        for t in "abcdef"
    }
    payload = {
        "state": json.loads(json.dumps(state.to_dict())),
        "teams": {t.upper(): t for t in "abcdef"},
        "rosters": {"a": {"local": "a1"}},
        "players": {"local": "wrong", "global": "a2"},
        "data_through": "2026-10-17T10:00:00",
        "recent_games": [["a", "b", "2026-10-17T10:00:00"]],
    }
    return inputs, payload


def game(**kwargs):
    return {
        "game_key": "new",
        "start": pd.Timestamp("2026-10-19 10:00"),
        "team1": "A",
        "team2": "B",
        "winner": 1,
        "gamelength": 1800.0,
        "players1": None,
        "players2": None,
        "event_league": "LoL Champions Korea",
        "event": "LCK",
        **kwargs,
    }


def test_parse_sources(monkeypatch):
    def get(params, sleep):
        if params["tables"].startswith("ScoreboardGames"):
            return [
                {
                    "game_key": "sg",
                    "start": "2026-10-19 10:00:00",
                    "team1": "A",
                    "team2": "B",
                    "win_team": "A",
                    "gamelength": "31.5",
                    "event_league": "LCK",
                    "event": "Cup",
                },
                {
                    "game_key": "empty",
                    "start": "2026-10-19 11:00:00",
                    "team1": "A",
                    "team2": "B",
                    "win_team": "",
                    "gamelength": "",
                },
            ]
        if params["tables"].startswith("ScoreboardPlayers"):
            assert "'sg'" in params["where"]
            return [{"game_key": "sg", "team": "A", "player": "Local"}]
        return [
            {
                "game_key": "sg",
                "start": "2026-10-19 10:00:00",
                "team1": "A",
                "team2": "B",
                "winner": "1",
            },
            {
                "game_key": "msg",
                "start": "2026-10-19 12:00:00",
                "team1": "A",
                "team2": "B",
                "winner": "2",
                "event_league": "LCK",
                "event": "Cup",
            },
        ]

    monkeypatch.setattr(schedule, "_get", get)
    games = fresh.fetch_recent_games("2026-10-18", sleep=lambda _: None)
    assert list(games.game_key) == ["sg", "msg"]
    assert games.iloc[0].gamelength == 1890
    assert games.iloc[0].players1 == ("Local",)
    assert games.iloc[0].players2 is None
    assert pd.isna(games.iloc[1].gamelength)
    assert games.start.dt.tz is None
    assert games.source.tolist() == ["scoreboard", "schedule"]
    assert games.league.isna().all()
    assert "game_number" in games


def test_known_unmatched_and_frozen_form():
    inputs, payload = setup()
    games = pd.DataFrame(
        [
            game(game_key="known", start=pd.Timestamp("2026-10-17 10:15")),
            game(),
            game(game_key="bad", team2="Missing"),
        ]
    )
    ratings, summary = fresh.refreshed_ratings(inputs, payload, games, aliases={})
    assert summary["applied"] == 1
    assert summary["known"] == 1
    assert summary["unmatched"] == ["Missing"]
    assert summary["applied_by_team"] == {"A": 1, "B": 1}
    assert ratings.loc["A", "elo"] > inputs["A"]["elo"]
    assert ratings.loc["B", "elo"] != inputs["B"]["elo"]
    for team in "CDEF":
        assert ratings.loc[team, "elo"] == inputs[team]["elo"]
    assert (ratings.form == 10).all()
    for team in ratings.index:
        assert ratings.loc[team, "forge"] - inputs[team]["forge"] == pytest.approx(
            ratings.loc[team, "elo"] - inputs[team]["elo"]
        )


def test_roster_lookup_order(monkeypatch):
    inputs, payload = setup()
    original = EloState.play
    seen = []

    def play(self, row, league, date, player_records=False):
        seen.append(self.rosters[row.gameid, row.teamid])
        return original(self, row, league, date, player_records)

    monkeypatch.setattr(EloState, "play", play)
    fresh.refreshed_ratings(
        inputs,
        payload,
        pd.DataFrame([game(players1=("Local", "Global", "New Player"))]),
        aliases={},
    )
    assert seen == [("a1", "a2", "lp:new player")]


def test_international_offset_moves_other_teams():
    inputs, payload = setup()
    # B is an idle team in A's home region; D in C's.
    ratings, summary = fresh.refreshed_ratings(
        inputs,
        payload,
        pd.DataFrame([game(team2="C", event_league="World Championship")]),
        aliases={},
    )
    assert summary["applied"] == 1
    assert ratings.loc["B", "elo"] > inputs["B"]["elo"]
    assert ratings.loc["D", "elo"] < inputs["D"]["elo"]
    assert ratings.loc["E", "elo"] == inputs["E"]["elo"]


def test_refresh_log_freezes_started_calls():
    inputs, payload = setup()
    now = datetime.datetime(2026, 10, 19, 12, tzinfo=datetime.UTC)
    sched = pd.DataFrame(
        [
            {
                "match_id": mid,
                "start": pd.Timestamp(start),
                "team1": "A",
                "team2": "B",
                "best_of": 3,
                "winner": None,
                "score1": None,
                "score2": None,
                "event": "LCK",
                "event_league": "LoL Champions Korea",
            }
            for mid, start in [
                ("future", "2026-10-19 14:00"),
                ("started", "2026-10-19 11:00"),
            ]
        ]
    )
    ratings = pd.DataFrame.from_dict(inputs, orient="index").rename_axis("teamname")
    preds = schedule.predict(
        sched, ratings, schedule.TeamMatcher(ratings.reset_index()), at=now
    )
    log = {p["match_id"]: {**p, "data_through": "2026-10-17"} for p in preds}
    old = log["started"].copy()
    old_p = log["future"]["p_game"]
    summary = fresh.refresh_log(
        log,
        now,
        {"teams": inputs, "data_through": "2026-10-17T10:00:00"},
        payload,
        fetch=lambda since: pd.DataFrame([game()]),
        fetch_schedule=lambda start, end: sched,
    )
    assert log["started"] == old
    assert log["future"]["p_game"] > old_p
    assert log["future"]["data_through"] == "2026-10-17"
    assert log["future"]["provisional_games"] == 2
    assert log["future"]["results_through"] == "2026-10-19T10:00Z"
    assert summary["calls_changed"] == 1


@pytest.mark.parametrize("disabled", [True, False])
def test_cli_noop(tmp_path, monkeypatch, disabled):
    spec = importlib.util.spec_from_file_location(
        "refresh_calls", Path(__file__).parents[1] / "scripts/refresh_calls.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    log = tmp_path / "predictions.json"
    log.write_bytes(b'{"untouched": true}\n')
    missing = tmp_path / "missing"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh_calls.py",
            "--log",
            str(log),
            "--inputs",
            str(missing),
            "--state",
            str(missing),
        ],
    )
    monkeypatch.setenv("REFRESH_CALLS", "0" if disabled else "1")
    mod.main()
    assert log.read_bytes() == b'{"untouched": true}\n'


def test_shared_series_start_applies_every_map(monkeypatch):
    inputs, payload = setup()
    seen = []
    original = EloState.play

    def play(self, row, league, date, player_records=False):
        seen.append((row.gamelength, self.rosters.get((row.gameid, row.teamid))))
        return original(self, row, league, date, player_records)

    monkeypatch.setattr(EloState, "play", play)
    _, summary = fresh.refreshed_ratings(
        inputs,
        payload,
        pd.DataFrame(
            [
                game(game_key="map1", gamelength=float("nan")),
                game(game_key="map2", winner=2),
            ]
        ),
        aliases={},
    )
    assert summary["applied"] == 2
    assert summary["known"] == 0
    assert seen == [(1800, None), (1800.0, None)]


def test_cli_fetch_failure_leaves_log_unchanged(tmp_path, monkeypatch):
    import gzip

    spec = importlib.util.spec_from_file_location(
        "refresh_calls", Path(__file__).parents[1] / "scripts/refresh_calls.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    log = tmp_path / "predictions.json"
    schedule.save_log({}, log)
    original = log.read_bytes()
    inputs = tmp_path / "inputs.json"
    inputs.write_text("{}")
    state = tmp_path / "state.json.gz"
    with gzip.open(state, "wt") as stream:
        json.dump({}, stream)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh_calls.py",
            "--log",
            str(log),
            "--inputs",
            str(inputs),
            "--state",
            str(state),
        ],
    )
    monkeypatch.setenv("REFRESH_CALLS", "1")

    def fail(log, *args):
        log["partial"] = {"matched": False}
        raise RuntimeError("Leaguepedia refused the query")

    monkeypatch.setattr(fresh, "refresh_log", fail)
    mod.main()
    assert log.read_bytes() == original


@pytest.mark.parametrize("maps, expected", [(2, 0), (3, 1)])
def test_oe_series_early_dates_consumed_once(maps, expected):
    inputs, payload = setup()
    payload["recent_games"] = [
        ["a", "b", "2026-10-17T09:00:00"],
        ["a", "b", "2026-10-17T09:30:00"],
    ]
    rows = [
        game(game_key=f"map{i}", start=pd.Timestamp("2026-10-17 10:00"))
        for i in range(maps)
    ]
    # Another matchup at the same time must not consume this pair's OE games.
    rows.insert(0, game(team1="C", team2="D", start=rows[0]["start"]))
    _, summary = fresh.refreshed_ratings(
        inputs, payload, pd.DataFrame(rows), aliases={}
    )
    assert summary["known"] == 2
    assert summary["applied"] == expected + 1
    assert summary["applied_by_team"] == {
        "C": 1,
        "D": 1,
        **({"A": 1, "B": 1} if expected else {}),
    }


def test_stale_unmatched_oe_gap_is_known():
    inputs, payload = setup()
    _, summary = fresh.refreshed_ratings(
        inputs,
        payload,
        pd.DataFrame(
            [
                game(start=pd.Timestamp("2026-10-17 03:59")),
                game(game_key="boundary", start=pd.Timestamp("2026-10-17 04:00")),
            ]
        ),
        aliases={},
    )
    assert summary["known"] == summary["stale_skipped"] == 1
    assert summary["applied"] == 1


def test_saved_alias_used_for_games_and_predictions(tmp_path, monkeypatch):
    inputs, payload = setup()
    path = tmp_path / "aliases.json"
    path.write_text(json.dumps({"Unusual Leaguepedia Name": "A"}))
    monkeypatch.setattr(schedule, "ALIASES_PATH", path)
    games = pd.DataFrame([game(team1="Unusual Leaguepedia Name")])
    _, audit = fresh.refreshed_ratings(inputs, payload, games)
    assert audit["applied"] == 1
    assert audit["unmatched"] == []
    sched = pd.DataFrame(
        [
            {
                "match_id": "future",
                "start": pd.Timestamp("2026-10-19 14:00"),
                "team1": "Unusual Leaguepedia Name",
                "team2": "B",
                "best_of": 3,
                "winner": None,
                "score1": None,
                "score2": None,
                "event": "LCK",
                "event_league": "LoL Champions Korea",
            }
        ]
    )
    log = {}
    summary = fresh.refresh_log(
        log,
        datetime.datetime(2026, 10, 19, 12, tzinfo=datetime.UTC),
        {"teams": inputs, "data_through": payload["data_through"]},
        payload,
        fetch=lambda since: games,
        fetch_schedule=lambda start, end: sched,
    )
    assert summary["matched"] == 1
    assert log["future"]["ours1"] == "A"
    assert log["future"]["provisional_games"] == 2


def test_worker_games(tmp_path):
    directory = tmp_path / "match"
    directory.mkdir()
    row = {
        "game_id": "g",
        "number": 2,
        "teams": ["A", "B"],
        "winner": 1,
        "started_at": None,
        "ended_at": "2026-10-19T10:30:00Z",
        "duration_seconds": 1800,
        "players": [["One"] * 5, None],
        "league": "LCK",
        "event": "Cup",
    }
    (directory / "maps.json").write_text(
        json.dumps({"2": row, "3": {**row, "winner": None}})
    )
    games = fresh.worker_games(tmp_path, "2026-10-18")
    assert len(games) == 1
    got = games.iloc[0]
    assert got.game_key == "riot:g"
    assert got.start == pd.Timestamp("2026-10-19 10:00")
    assert got.players1 == ("One",) * 5
    assert got.players2 is None
    assert got.winner == 2
    assert got.source == "worker" and got.league is None  # domestic: home rule
    assert fresh.worker_games(tmp_path, "2026-10-20").empty
    row.update(duration_seconds=None, players=None)
    (directory / "maps.json").write_text(json.dumps({"2": row}))
    got = fresh.worker_games(tmp_path, "2026-10-18").iloc[0]
    assert got.start == pd.Timestamp("2026-10-19 10:30")
    assert pd.isna(got.gamelength)


@pytest.mark.parametrize(
    "sources,expected",
    [
        (["schedule", "worker", "scoreboard"], "scoreboard"),
        (["schedule", "worker"], "worker"),
    ],
)
def test_source_precedence(sources, expected):
    inputs, payload = setup()
    rows = [
        game(
            game_key=source,
            game_number=1,
            source=source,
            team1="B" if source == "worker" else "A",
            team2="A" if source == "worker" else "B",
        )
        for source in sources
    ]
    rows.append(game(game_key="map2", game_number=2, source="worker"))
    _, summary = fresh.refreshed_ratings(
        inputs, payload, pd.DataFrame(rows), aliases={}
    )
    assert summary["applied"] == 2
    assert summary["applied_by_source"] == (
        {"scoreboard": 1, "worker": 1} if expected == "scoreboard" else {"worker": 2}
    )


def test_worker_only_refresh(tmp_path):
    inputs, payload = setup()
    directory = tmp_path / "match"
    directory.mkdir()
    (directory / "maps.json").write_text(
        json.dumps(
            {
                "1": {
                    "game_id": "g",
                    "number": 1,
                    "teams": ["A", "B"],
                    "winner": 0,
                    "started_at": "2026-10-19T10:00:00Z",
                    "ended_at": "2026-10-19T10:30:00Z",
                    "duration_seconds": 1800,
                    "league": "LCK",
                }
            }
        )
    )

    def fail(**kwargs):
        raise RuntimeError("Leaguepedia unavailable")

    sched = pd.DataFrame(
        [
            {
                "match_id": "future",
                "start": pd.Timestamp("2026-10-19 14:00"),
                "team1": "A",
                "team2": "B",
                "best_of": 3,
                "winner": None,
                "score1": None,
                "score2": None,
                "event": "Cup",
                "event_league": "LoL Champions Korea",
            }
        ]
    )
    log = {}
    args = (
        log,
        datetime.datetime(2026, 10, 19, 12, tzinfo=datetime.UTC),
        {"teams": inputs, "data_through": payload["data_through"]},
        payload,
    )
    summary = fresh.refresh_log(
        *args, fetch=fail, fetch_schedule=lambda *args: sched, worker_maps=tmp_path
    )
    assert summary["applied_by_source"] == {"worker": 1}
    assert log["future"]["provisional_games"] == 2

    def no_schedule(*args):
        raise RuntimeError("no schedule")

    with pytest.raises(RuntimeError, match="no schedule"):
        fresh.refresh_log(
            *args, fetch=fail, fetch_schedule=no_schedule, worker_maps=tmp_path
        )


def test_worker_league_maps_international_labels_only():
    from prometheus.fresh import worker_league

    assert worker_league("WLDs") == "Worlds"
    assert worker_league("MSI") == "MSI"
    assert worker_league("LCK") is None
    assert worker_league(None) is None


@pytest.mark.parametrize("applied", [True, False])
@pytest.mark.parametrize("slug_available", [True, False])
def test_cli_live_out(tmp_path, monkeypatch, applied, slug_available):
    import copy
    import gzip
    import io

    spec = importlib.util.spec_from_file_location(
        "refresh_calls_live",
        Path(__file__).resolve().parents[1] / "scripts/refresh_calls.py",
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    teams, state = setup()
    teams["A"]["model_elo"] = 1400.0
    inputs = {
        "schema": 1,
        "data_through": state["data_through"],
        "generated_at": "2026-10-18T00:00:00+00:00",
        "teams": teams,
        "draft": {"games": [{"champion": "Ahri"}]},
    }
    original = copy.deepcopy(inputs)
    inputs_path, state_path, log_path = (
        tmp_path / name for name in ("inputs.json", "state.gz", "log.json")
    )
    inputs_path.write_text(json.dumps(inputs))
    with gzip.open(state_path, "wt") as stream:
        json.dump(state, stream)
    log_path.write_text(json.dumps({"matches": []}))
    out, summary_path = tmp_path / "fresh.json", tmp_path / "summary.json"
    games = pd.DataFrame(
        [game()] if applied else [game(start=pd.Timestamp("2026-10-17 10:15"))]
    )
    real_refresh = fresh.refresh_log

    def refresh(log, now, inputs, state, **kwargs):
        return real_refresh(
            log,
            now,
            inputs,
            state,
            fetch=lambda **kw: games,
            fetch_schedule=lambda *a: pd.DataFrame(),
            **kwargs,
        )

    def urlopen(request, timeout):
        assert request.full_url.endswith("/player-slugs.json")
        assert request.get_header("User-agent") == cli.markets.USER_AGENT
        if not slug_available:
            raise OSError("offline")
        return io.BytesIO(b'{"a1": "one"}')

    monkeypatch.setattr(cli.urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(cli.fresh, "refresh_log", refresh)
    monkeypatch.setattr(schedule, "predict", lambda *a, **kw: [])
    monkeypatch.setenv("REFRESH_CALLS", "1")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "refresh_calls",
            "--inputs",
            str(inputs_path),
            "--state",
            str(state_path),
            "--log",
            str(log_path),
            "--live-out",
            str(out),
            "--site-out",
            str(tmp_path / "site.json"),
            "--summary",
            str(summary_path),
        ],
    )
    cli.main()
    summary = json.loads(summary_path.read_text())
    overlay = json.loads((tmp_path / "site.json").read_text())
    assert bool(overlay["teams"]) == applied
    assert bool(overlay["players"]) == (applied and slug_available)
    assert summary["applied"] == int(applied)
    assert out.exists() == applied
    assert json.loads(inputs_path.read_text()) == original
    if applied:
        payload = json.loads(out.read_text())
        assert payload["draft"] == original["draft"]
        assert payload["schema"] == original["schema"]
        assert payload["data_through"] == original["data_through"]
        assert payload["generated_at"] > original["generated_at"]
        assert payload["results_through"] == summary["results_through"]
        assert set(summary["deltas"]) == {"A", "B"}
        for team, fields in original["teams"].items():
            for key, value in fields.items():
                expected = (
                    value + summary["deltas"].get(team, 0)
                    if key in ("elo", "forge", "model_elo")
                    else value
                )
                assert payload["teams"][team][key] == expected


def test_site_overlay_international_players():
    inputs, payload = setup()
    _, summary, state = fresh.refreshed_ratings(
        inputs,
        payload,
        pd.DataFrame([game(team2="C", league="Worlds")]),
        aliases={},
        return_state=True,
    )
    slugs = {p: f"slug-{p}" for p in state.own if p != "a2"}
    now = datetime.datetime(2026, 10, 19, 12, tzinfo=datetime.UTC)
    overlay = fresh.site_overlay(payload, state, summary, slugs, now)
    assert overlay["base"] == payload["data_through"]
    assert overlay["at"] == "2026-10-19T12:00Z"
    assert overlay["results_through"] == "2026-10-19T10:00Z"
    assert overlay["teams"] == {
        k: round(v, 1) for k, v in summary["deltas"].items() if abs(v) >= 0.05
    }
    before = EloState.from_dict(payload["state"], calculate_game_length_elo_change)
    assert overlay["players"]["slug-b1"] == round(
        state.player_rating("b1") - before.player_rating("b1"), 1
    )
    assert "slug-a2" not in overlay["players"]
    assert "slug-e1" not in overlay["players"]


def test_site_overlay_threshold():
    _, payload = setup()
    state = EloState.from_dict(payload["state"], calculate_game_length_elo_change)
    state.own["a1"] += 0.049
    state.own["a2"] -= 0.16
    overlay = fresh.site_overlay(
        payload,
        state,
        {
            "applied": 1,
            "results_through": "2026-10-19T10:00Z",
            "deltas": {"A": 0.049, "B": -0.16},
        },
        {"a1": "one", "a2": "two"},
        datetime.datetime.now(datetime.UTC),
    )
    assert overlay["teams"] == {"B": -0.2}
    assert overlay["players"] == {"two": -0.2}


@pytest.mark.parametrize("applied", [False, True])
def test_refresh_writes_site_overlay(tmp_path, monkeypatch, applied):
    inputs, payload = setup()
    path = tmp_path / "fresh.json"
    path.write_text('{"old": true}')
    monkeypatch.setattr(schedule, "predict", lambda *a, **kw: [])
    summary = fresh.refresh_log(
        {},
        datetime.datetime.now(datetime.UTC),
        {"teams": inputs, "data_through": payload["data_through"]},
        payload,
        fetch=lambda **kw: pd.DataFrame(
            [game()] if applied else [game(start=pd.Timestamp("2026-10-17 10:15"))]
        ),
        fetch_schedule=lambda *a: pd.DataFrame(),
        site_out=path,
        player_slugs={"a1": "one"},
    )
    overlay = json.loads(path.read_text())
    assert overlay["base"] == payload["data_through"]
    assert bool(overlay["teams"]) == applied
    assert bool(overlay["players"]) == applied
    assert overlay["results_through"] == summary["results_through"]
