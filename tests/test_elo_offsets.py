"""Offset evidence and explicit historical replay parity."""

import json
from types import SimpleNamespace

import pytest
from test_elo_state import test_frozen_replay as frozen_replay

from prometheus.elo import (
    LINK_MODE,
    LINK_SHARE,
    TRANSFER_GAMES,
    TRANSFER_SHARE,
    EloState,
    compute_elo_records,
)


@pytest.mark.parametrize("mode", ["plain", "team"])
def test_zero_shares_match_frozen_fixture(mode, monkeypatch):
    """Reuse the pre-option fixture, exercising explicit options on every frame."""
    import test_elo_state

    original = test_elo_state.compute_elo_records

    def explicit(*args, **kw):
        kw.pop("link_share", None)
        kw.pop("transfer_share", None)
        return original(
            *args,
            link_share=0,
            link_mode=mode,
            transfer_share=0,
            transfer_games=20,
            **kw,
        )

    monkeypatch.setattr(test_elo_state, "compute_elo_records", explicit)
    frozen_replay()


def constant_change(**kw):
    return 10.0


def state(**kw):
    # Isolate each evidence source in the mechanical tests below.
    kw = {"link_share": 0, "transfer_share": 0, **kw}
    obj = EloState(constant_change, player_rd=None, rookie_penalty=0, **kw)
    obj.home.update(a="LCK", b="LPL")
    obj.season_counts.update({("a", None): {"LCK": 10}, ("b", None): {"LPL": 10}})
    return obj


def play(obj, event="Cup", gameid="g"):
    row = SimpleNamespace(
        gameid=gameid, teamid="a", opponent_teamid="b", gamelength=1800, result=1
    )
    return obj.play(row, event, None, player_records=True)


@pytest.mark.parametrize("mode", ["plain", "team"])
def test_links_history_ratings_and_transfer_conversion(mode):
    obj = state(
        link_share=0.5, link_mode=mode, rosters={("g", "a"): ("p",), ("g", "b"): ("q",)}
    )
    teams, offsets, players = play(obj)
    assert {r["league"]: r["league_offset"] for r in offsets} == {"LCK": 5, "LPL": -5}
    assert obj.league_offset["LCK"] == (5 if mode == "plain" else 0)
    assert obj.link_offset.get("LCK", 0) == (5 if mode == "team" else 0)
    for team, player in zip(teams, players):
        assert team["post_match_elo"] == team["main_elo"] == player[4]
        assert obj.player_rating(player[2]) == player[4]
        assert obj.team_rating(team["teamid"]) == team["main_elo"]
    # p moves A -> B. Only plain offsets travel through conversion.
    before = obj.own["p"]
    obj.rosters[("move", "a")] = ("r",)
    obj.rosters[("move", "b")] = ("p",)
    play(obj, event="LPL", gameid="move")
    assert obj.own["p"] == before - 10 + (10 if mode == "plain" else 0)
    # An idle team's last record plus subsequent offset movement reconstructs it.
    idle = state(link_share=0.5, link_mode=mode)
    first, _, _ = play(idle)
    old = first[0]
    idle.home["c"] = "LCK"
    idle.season_counts[("c", None)] = {"LCK": 10}
    row = SimpleNamespace(
        gameid="second", teamid="c", opponent_teamid="b", gamelength=1800, result=1
    )
    idle.play(row, "Cup", None)
    assert old["main_elo"] + idle.rating_offset("LCK") - old[
        "league_offset"
    ] == idle.team_rating("a")


def test_transfer_scaled_change_direction_window_and_resume():
    obj = state(
        transfer_share=0.25,
        transfer_games=2,
        rosters={("g", "a"): ("p",), ("g", "b"): ("q",)},
    )
    play(obj, event="LCK")  # p begins in A; q begins in B
    obj.rosters[("move", "a")] = ("r",)
    obj.rosters[("move", "b")] = ("p",)
    _, offsets, _ = play(obj, event="LPL", gameid="move")
    # p loses 10 in B: A falls by 2.5 and B rises by 2.5.
    assert obj.league_offset["LCK"] == -2.5
    assert obj.league_offset["LPL"] == 2.5
    assert len(offsets) == 2
    assert obj.transfers["p"] == ("LCK", "LPL", 1)
    restored = EloState.from_dict(
        json.loads(json.dumps(obj.to_dict())), constant_change
    )
    assert restored.transfers == obj.transfers
    assert restored.transfer_games == 2
    # International appearance counts toward the window when seated in B.
    play(restored, event="MSI", gameid="last")
    assert "p" not in restored.transfers
    offset = dict(restored.league_offset)
    play(restored, event="LPL", gameid="expired")
    assert dict(restored.league_offset) == offset


def test_transfer_uses_rd_scaled_player_change():
    obj = state(transfer_share=0.1, rosters={("g", "a"): ("p",), ("g", "b"): ("q",)})
    play(obj, event="LCK")
    obj.player_rd = (100, 50, 0)
    obj.rosters[("move", "a")] = ("r",)
    obj.rosters[("move", "b")] = ("p",)
    own_before = obj.own["p"]
    play(obj, event="LPL", gameid="move")
    delta = obj.own["p"] - own_before
    assert delta == -44  # -40 RD-scaled update plus -4 compensation
    assert obj.league_offset["LCK"] == pytest.approx(-4)
    assert obj.league_offset["LPL"] == pytest.approx(4)


def test_international_roster_move_does_not_start_transfer_evidence():
    obj = state(transfer_share=0.25, rosters={("g", "a"): ("p",), ("g", "b"): ("q",)})
    play(obj, event="LCK")
    obj.rosters[("international", "a")] = ("r",)
    obj.rosters[("international", "b")] = ("p",)
    play(obj, event="MSI", gameid="international")
    assert not obj.transfers


def test_link_state_round_trip():
    obj = state(link_share=0.5, link_mode="team")
    play(obj)
    restored = EloState.from_dict(
        json.loads(json.dumps(obj.to_dict())), constant_change
    )
    assert restored.link_offset == obj.link_offset
    assert restored.team_rating("a") == obj.team_rating("a")
    assert play(restored, gameid="next") == play(obj, gameid="next")


@pytest.mark.parametrize("movers", [("p",), ("p", "s")])
def test_transfer_compensates_each_movers_own_evidence(movers):
    obj = state(transfer_share=0.25)
    # Already seated in B: isolate evidence from seating and ordinary updates.
    obj.rosters[("g", "a")] = ("a_player",)
    obj.rosters[("g", "b")] = (*movers, "b_player")
    for player in ("a_player", *movers, "b_player"):
        obj.own[player] = 1200.0
        obj.player_league[player] = "LCK" if player == "a_player" else "LPL"
    for player in movers:
        obj.transfers[player] = ("LCK", "LPL", 20)
    before = {p: obj.player_rating(p) for p in obj.own}
    play(obj, event="LPL")
    adjustment = 0.25 * -10
    for player in movers:
        assert obj.own[player] == before[player] - 10 + adjustment
        # For a single mover, evidence leaves their post-update rating unchanged;
        # with multiple movers, only the OTHER movers' evidence still affects it.
        assert obj.player_rating(player) == (
            before[player] - 10 - (len(movers) - 1) * adjustment
        )
    assert (
        obj.player_rating("b_player")
        == before["b_player"] - 10 - len(movers) * adjustment
    )
    assert (
        obj.player_rating("a_player")
        == before["a_player"] + 10 + len(movers) * adjustment
    )


def test_published_offset_defaults():
    import inspect

    expected = {
        "link_share": LINK_SHARE,
        "link_mode": LINK_MODE,
        "transfer_share": TRANSFER_SHARE,
        "transfer_games": TRANSFER_GAMES,
    }
    assert expected == {
        "link_share": 0.5,
        "link_mode": "team",
        "transfer_share": 0.02,
        "transfer_games": 20,
    }
    obj = EloState(constant_change)
    for name, value in expected.items():
        assert getattr(obj, name) == value
        assert inspect.signature(compute_elo_records).parameters[name].default == value
