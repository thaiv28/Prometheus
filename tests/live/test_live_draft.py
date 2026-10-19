"""Draft identity, exact prior-day histories, fallback and receipt-time gates."""

import copy
import json
import sqlite3
from pathlib import Path

import numpy as np
import pytest

from prometheus.live import draft, timeline
from prometheus.live.draft_export import History

MODEL = Path(timeline.MODEL_PATH).with_name("time_model_draft_v2.json")


@pytest.fixture
def history(tmp_path):
    path = tmp_path / "draft.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE matches(gameid TEXT,teamid TEXT,teamname TEXT,date TEXT,result INT);
            CREATE TABLE game_length_elo(gameid TEXT,teamid TEXT,pre_match_elo REAL);
            CREATE TABLE match_players(gameid TEXT,teamid TEXT,playerid TEXT,playername TEXT,position TEXT,champion TEXT);
        """)
        for g, day, win in [
            ("a", "2024-01-01 12:00:00", 1),
            ("b", "2024-01-02 01:00:00", 0),
        ]:
            for i, team in enumerate(("Blue", "Red")):
                db.execute(
                    "INSERT INTO matches VALUES(?,?,?,?,?)",
                    (g, team, team, day, win if i == 0 else 1 - win),
                )
                db.execute("INSERT INTO game_length_elo VALUES(?,?,1500)", (g, team))
                for role in draft.ROLES:
                    db.execute(
                        "INSERT INTO match_players VALUES(?,?,?,?,?,?)",
                        (g, team, team + role, "Player" + role, role, team + role),
                    )
    state = History(path)
    try:
        yield state.before("2024-01-02").snapshot(), state
    finally:
        state.close()


def observation(at="2024-01-02T12:00:30Z"):
    return {
        "at": at,
        "source_at": at,
        "teams": [
            [
                {
                    "participantId": i * 5 + j + 1,
                    "esportsPlayerId": f"riot-{i}-{j}",
                    "summonerName": "TAG Player" + r,
                    "role": r,
                    "championId": team + r,
                }
                for j, r in enumerate(draft.ROLES)
            ]
            for i, team in enumerate(("Blue", "Red"))
        ],
    }


def page(obs=None, blue=0):
    names = ["Blue", "Red"] if blue == 0 else ["Red", "Blue"]
    return {
        "match": {"teams": [{"name": n} for n in names]},
        "game": {
            "id": "g",
            "blue": blue,
            "start": "2024-01-02T12:00:00Z",
            "draft_observations": [obs or observation()],
        },
    }


def test_history_matches_shrunk_features_and_excludes_whole_current_day(history):
    h, state = history
    roster = draft.resolve(observation(), h, ["Blue", "Red"])
    values = draft.feature_values(roster, h)
    assert values == pytest.approx(
        {"exp": 0, "meta": 5 / 51, "matchup": 5 / 21, "synergy": 10 / 21}
    )
    # Day 2's loss only enters on day 3; both days' residuals then cancel.
    later = state.before("2024-01-03").snapshot()
    assert draft.feature_values(roster, later) == pytest.approx(
        dict.fromkeys(draft.FEATURES, 0)
    )
    with pytest.raises(ValueError, match="chronologically"):
        state.before("2024-01-01")


def test_meta_window_includes_day_minus_60_and_excludes_older(history):
    _, state = history
    # Jan 2 remains at exactly the lower boundary on March 2 (leap year).
    march2 = state.before("2024-03-02").snapshot()
    k = draft.key("top", "Bluetop")
    assert march2["meta"][k] == [-0.5, 1]
    assert k not in state.before("2024-03-03").snapshot()["meta"]


@pytest.mark.parametrize(
    "change, reason",
    [
        (lambda o: o["teams"][0].pop(), "incomplete"),
        (
            lambda o: o["teams"][0][0].update(summonerName="TAG Unknown"),
            "unknown_or_ambiguous",
        ),
        (
            lambda o: o["teams"][0][0].update(championId="NewChampion"),
            "unknown_or_duplicate_champion",
        ),
        (lambda o: o["teams"][0][1].update(participantId=1), "participant_side"),
        (lambda o: o["teams"][0][1].update(role="top"), "invalid_roles"),
        (lambda o: o["teams"][0][0].update(participantId=6), "participant_side"),
        (
            lambda o: o["teams"][1][0].update(esportsPlayerId="riot-0-0"),
            "duplicate_or_missing",
        ),
    ],
)
def test_ambiguous_or_incomplete_metadata_is_refused(history, change, reason):
    h, _ = history
    obs = observation()
    change(obs)
    with pytest.raises(ValueError, match=reason):
        draft.resolve(obs, h, ["Blue", "Red"])


def test_team_scoped_alias_collision_is_refused(history):
    h, _ = history
    h["teams"]["Blue"]["playertop"].append("different-oe-id")
    with pytest.raises(ValueError, match="ambiguous"):
        draft.resolve(observation(), h, ["Blue", "Red"])


def test_first_complete_receipt_is_frozen_and_conflicts_only_stop_future_calls(history):
    h, _ = history
    model = json.loads(MODEL.read_text())
    p = page()
    packet = draft.prepare(p, h, model, 0.6)
    assert packet["status"] == "ready"
    assert not draft.available(packet, "2024-01-02T12:00:29Z", model)
    assert draft.available(packet, "2024-01-02T12:00:30Z", model)
    later = observation("2024-01-02T12:01:00Z")
    later["teams"][0][0]["championId"] = "Unknown"
    p["game"]["draft_observations"].append(later)
    conflict = draft.prepare(p, h, model, 0.7, packet)
    assert conflict["shift"] == packet["shift"]  # don't silently recompute FORGE
    assert draft.available(conflict, "2024-01-02T12:00:59Z", model)
    assert not draft.available(conflict, "2024-01-02T12:01:00Z", model)
    p["game"]["id"] = "other-map"
    assert draft.prepare(p, h, model, 0.6, packet)["status"] == "context_game_mismatch"


def test_current_day_or_future_history_never_reaches_model(history):
    h, _ = history
    model = json.loads(MODEL.read_text())
    h["data_through"] = "2024-01-02 01:00:00"
    assert draft.prepare(page(), h, model, 0.6)["status"] == "history_day_mismatch"


def test_side_flip_preserves_blue_prior(history):
    h, _ = history
    model = json.loads(MODEL.read_text())
    a = draft.prepare(page(), h, model, 0.6)
    b = draft.prepare(page(blue=1), h, model, 0.4)
    assert a["shift"] == pytest.approx(b["shift"])


def frames():
    return [
        {
            "at": f"2024-01-02T12:{minute:02d}:00Z",
            "source_at": f"2024-01-02T12:{minute:02d}:00Z",
            "teams": [
                {
                    "gold": 2500 + minute * 500,
                    "kills": minute,
                    "towers": 0,
                    "dragons": 0,
                    "barons": 0,
                    "inhibitors": 0,
                },
                {
                    "gold": 2500 + minute * 400,
                    "kills": 0,
                    "towers": 0,
                    "dragons": 0,
                    "barons": 0,
                    "inhibitors": 0,
                },
            ],
        }
        for minute in range(6)
    ]


def test_production_fallback_and_candidate_receipt_gate(history):
    h, _ = history
    model = json.loads(MODEL.read_text())
    base = model["fallback_model"]
    p = page()
    p["game"]["frames"] = frames()
    ratings = [{"elo": 1600}, {"elo": 1500}]
    pre, expected = timeline.timeline_calls(copy.deepcopy(p), base, ratings)
    none_pre, none = timeline.timeline_calls(copy.deepcopy(p), model, ratings)
    assert none_pre == pre and none == expected
    packet = draft.prepare(p, h, model, 0.6)
    cand_pre, candidate = timeline.timeline_calls(
        copy.deepcopy(p), model, ratings, draft=packet
    )
    assert cand_pre == pre
    assert candidate[0] == expected[0]  # draft arrived later
    assert candidate[1]["model"] == "time_objectives_draft_v2"
    assert candidate[1]["p"] != expected[1]["p"]
    # Adding later metadata cannot revise calls made before it was received.
    packet["invalid_at"] = "2024-01-02T12:04:00Z"
    _, stopped = timeline.timeline_calls(copy.deepcopy(p), model, ratings, draft=packet)
    assert stopped[:4] == candidate[:4]
    assert stopped[4:] == expected[4:]
    # Invalid objective input retains the existing legacy fallback.
    p["game"]["frames"][2]["teams"][0]["towers"] = None
    _, invalid = timeline.timeline_calls(p, model, ratings, draft=packet)
    assert invalid[2]["model"] == "time_gold_elo_v1"


def test_frozen_export_parity_against_vector_design():
    model = json.loads(MODEL.read_text())
    x = timeline.state_features(
        600,
        12000,
        11000,
        1600,
        1500,
        [
            {"kills": 3, "towers": 1, "dragons": 1, "barons": 0, "inhibitors": 0},
            {"kills": 1, "towers": 0, "dragons": 0, "barons": 0, "inhibitors": 0},
        ],
        0.25,
    ) + [0.1, 0.05]
    z = model["intercept"] + (
        (np.array(x) - model["mean"]) / model["scale"]
    ) @ np.array(model["coef"])
    expected = 1 / (
        1 + np.exp(-(model["calibration_slope"] * z + model["calibration_intercept"]))
    )
    actual = timeline.predict(
        model,
        600,
        12000,
        11000,
        1600,
        1500,
        objectives=[
            {"kills": 3, "towers": 1, "dragons": 1, "barons": 0, "inhibitors": 0},
            {"kills": 1, "towers": 0, "dragons": 0, "barons": 0, "inhibitors": 0},
        ],
        momentum=0.25,
        draft_shift=0.1,
    )
    assert actual == pytest.approx(expected, abs=1e-14)


def test_transfers_use_only_unique_global_names_and_confirmed_team_codes(history):
    h, _ = history
    obs = observation()
    h["teams"]["Blue"].pop("playertop")
    h["players"]["playertop"] = ["Bluetop"]
    assert draft.resolve(obs, h, ["Blue", "Red"])[0]["top"]["player"] == "Bluetop"
    obs["teams"][0][0]["summonerName"] = "BPlayerTop"
    with pytest.raises(ValueError, match="ambiguous"):
        draft.resolve(obs, h, ["Blue", "Red"])
    obs["team_codes"] = ["B", "R"]
    assert draft.resolve(obs, h, ["Blue", "Red"])[0]["top"]["player"] == "Bluetop"
    h["players"]["playertop"].append("different-oe-id")
    with pytest.raises(ValueError, match="ambiguous"):
        draft.resolve(obs, h, ["Blue", "Red"])


def test_parallel_call_is_saved_privately_with_unchanged_baseline(tmp_path):
    from prometheus.live.service import Game

    g = object.__new__(Game)
    g.number, g.id, g.mapping, g.dir = 1, "g", {"score": [0, 0]}, tmp_path / "g"
    g.draft_shadow = {"context": {"status": "ready"}, "call": {"p": 0.75}}
    p = {
        "match": {"series": {"ours": 0.6}},
        "game": {"calls": [{"p": 0.55, "minute": 5}]},
        "status": "live",
    }
    before = copy.deepcopy(p)
    g.journal(p)
    row = json.loads((tmp_path / "calls.jsonl").read_text())
    assert row["p_map"] == 0.55 and row["draft_shadow"]["call"]["p"] == 0.75
    assert p == before


def test_recovered_metadata_cannot_predate_history_and_model_availability(history):
    h, _ = history
    model = json.loads(MODEL.read_text())
    p = page()
    loaded = "2024-01-02T12:00:45Z"
    packet = draft.prepare(p, h, model, 0.6, not_before=loaded)
    assert packet["ready_at"] == loaded
    assert not draft.available(packet, "2024-01-02T12:00:40Z", model)
    # A restart retains the frozen availability, rather than pushing it forward.
    resumed = draft.prepare(p, h, model, 0.7, packet, not_before="2024-01-02T12:02:00Z")
    assert resumed == packet
    # A contradiction already observed before inputs loaded blocks future use.
    bad = observation("2024-01-02T12:00:40Z")
    bad["teams"][0][0]["championId"] = "Unknown"
    p["game"]["draft_observations"].append(bad)
    blocked = draft.prepare(p, h, model, 0.6, not_before=loaded)
    assert blocked["invalid_at"] == loaded
    assert not draft.available(blocked, loaded, model)
