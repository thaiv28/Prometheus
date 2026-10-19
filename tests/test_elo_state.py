"""Resumption and frozen pre-refactor replay parity."""

import json
from pathlib import Path

import pandas as pd

from prometheus.elo import (
    EloState,
    calculate_game_length_elo_change,
    compute_elo_records,
)


def inputs():
    rows = [
        ("g1", "a", "b", 1500, 1, "LCK", "2025-01-01"),
        ("g2", "c", "d", 2200, 0, "LPL", "2025-01-02"),
        ("g3", "a", "c", 1800, 1, "MSI", "2025-04-01"),
        ("g4", "a", "b", 1900, 0, "LCK", "2025-04-03"),
        ("g5", "c", "d", 1400, 1, "LPL", "2025-05-01"),
        ("g6", "a", "c", 2100, 0, "Worlds", "2025-10-01"),
        ("g7", "b", "d", 1700, 1, "Worlds", "2025-10-02"),
        ("g8", "a", "b", 1600, 1, "LCK", "2026-01-01"),
        ("g9", "c", "d", 1800, 1, "LPL", "2026-01-02"),
    ]
    games = pd.DataFrame(
        rows,
        columns=[
            "gameid",
            "teamid",
            "opponent_teamid",
            "gamelength",
            "result",
            "league",
            "date",
        ],
    )
    games["date"] = pd.to_datetime(games.date)
    rosters = {}
    for i, row in enumerate(games.itertuples(index=False)):
        for team in (row.teamid, row.opponent_teamid):
            if team == "d":  # pseudo-player and None dates are also serializable
                continue
            roster = (team + "1", team + "2")
            if team == "a" and i >= 3:
                roster = ("a1", "rookie")
            if team == "c" and i >= 4:
                roster = ("a2", "c2")  # transfer
            if team == "b" and i >= 6:
                roster = ("b1", "late rookie")
            rosters[row.gameid, team] = roster
    return games, rosters


def test_frozen_replay():
    games, rosters = inputs()
    actual = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters, player_records=True
    )
    frozen = json.loads(
        Path(__file__)
        .with_name("fixtures")
        .joinpath("elo_state_before.json")
        .read_text()
    )
    for frame, expected in zip(actual, frozen):
        values = frame.copy()
        if "date" in values:
            values["date"] = values.date.map(str)
        assert values.to_dict("records") == expected


def test_round_trip():
    games, rosters = inputs()
    state = EloState(calculate_game_length_elo_change, rosters=rosters)
    accumulated = [[], [], []]
    for i, row in enumerate(games.itertuples(index=False)):
        if i == 4:
            before = state
            snapshot = state.to_dict()
            state = EloState.from_dict(
                json.loads(json.dumps(snapshot)), calculate_game_length_elo_change
            )
            for attr in (
                "own",
                "members",
                "last_seen",
                "season_counts",
                "last_roster",
                "team_last",
            ):
                assert getattr(state, attr) == getattr(before, attr)
            assert ("team", "d") in state.own
            state.rosters = rosters
        records = state.play(row, row.league, row.date, player_records=True)
        for target, part in zip(accumulated, records):
            target.extend(part)
    full = compute_elo_records(
        games, calculate_game_length_elo_change, rosters=rosters, player_records=True
    )
    for values, frame in zip(accumulated, full):
        pd.testing.assert_frame_equal(
            pd.DataFrame(values, columns=frame.columns), frame, check_exact=True
        )
    for team in ("a", "b", "c", "d"):
        assert (
            state.team_rating(team)
            == full[0].loc[full[0].teamid == team, "main_elo"].iloc[-1]
        )
    assert state.team_rating("unknown") is None


def test_none_dates():
    from collections import namedtuple

    row = namedtuple("Game", "gameid teamid opponent_teamid gamelength result")(
        "x", "a", "b", 1800, 1
    )
    state = EloState(calculate_game_length_elo_change, has_league=False)
    state.play(row, None, None)
    restored = EloState.from_dict(
        json.loads(json.dumps(state.to_dict())), calculate_game_length_elo_change
    )
    assert restored.team_last == {"a": None, "b": None}
    assert restored.last_roster == state.last_roster


def test_player_rating_matches_last_record():
    games, rosters = inputs()
    state = EloState(calculate_game_length_elo_change, rosters=rosters)
    for n, row in enumerate(games.itertuples(index=False), 1):
        state.play(row, row.league, row.date)
        records = compute_elo_records(
            games.iloc[:n],
            calculate_game_length_elo_change,
            rosters=rosters,
            player_records=True,
        )[2].drop_duplicates("playerid", keep="last")
        for player in records.itertuples(index=False):
            # An idle player's stored record predates subsequent league moves.
            if (
                player.home_league == state.player_league[player.playerid]
                and player.league_offset == state.league_offset[player.home_league]
            ):
                assert state.player_rating(player.playerid) == player.post_match_elo
    assert state.player_rating("unknown") is None
