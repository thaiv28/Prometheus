"""Riot feed timeline sampling (feed_timelines.py) and the v2 join (train_time_model_v2.py)."""

import importlib.util
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[2] / "scripts" / "research"
sys.path.insert(0, str(RESEARCH))


def module(name):
    spec = importlib.util.spec_from_file_location(name, RESEARCH / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


ft = module("feed_timelines")
v2 = module("train_time_model_v2")
START = datetime(2026, 5, 17, 8, 6, 10, tzinfo=UTC)


def frame(seconds, blue, red, state="in_game"):
    side = lambda gold: {
        "totalGold": gold,
        "totalKills": 0,
        "towers": 0,
        "inhibitors": 0,
        "barons": 0,
        "dragons": ["ocean"],
    }
    at = (START + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
    return {
        "rfc460Timestamp": at,
        "gameState": state,
        "blueTeam": side(blue),
        "redTeam": side(red),
    }


def test_sample_takes_the_first_frame_and_the_last_state():
    s = ft.sample(
        [frame(600, 15000, 14000), frame(609, 15100, 14050, "finished")], START
    )
    assert s["blue"]["gold"] == 15000 and s["red"]["dragons"] == 1
    assert s["state"] == "finished" and not s["flat"]


def test_flat_gold_after_two_minutes_is_a_pause():
    paused = [frame(900, 20000, 20000), frame(909, 20000, 20000)]
    assert ft.sample(paused, START)["flat"]
    # Before passive income starts, flat gold is normal.
    early = [frame(30, 2500, 2500), frame(39, 2500, 2500)]
    assert not ft.sample(early, START)["flat"]


def test_clock_removes_paused_minutes():
    samples = [
        {"at": (START + timedelta(seconds=60 * k)).isoformat(), "flat": k == 3}
        for k in range(6)
    ]
    assert v2.clock(samples, START) == [0, 60, 120, None, 180, 240]


def test_clock_removes_a_marked_pause():
    at = lambda s: (START + timedelta(seconds=s)).isoformat()
    samples = [
        {"at": at(0), "state": "in_game", "flat": False},
        {"at": at(60), "state": "in_game", "flat": False},
        {"at": at(80), "state": "paused", "flat": False},  # frozen frame repeated
        {"at": at(80), "state": "paused", "flat": False},
        {"at": at(1080), "state": "in_game", "flat": False},  # 1,000 s later
    ]
    assert v2.clock(samples, START) == [0, 60, None, None, 80]


def test_team_names_match_loosely():
    assert v2.same_team(
        {"name": "Hanwha Life Esports", "code": "HLE"}, "Hanwha Life Esports"
    )
    assert v2.same_team({"name": "KT Rolster", "code": "KT"}, "KT Rolster")
    assert v2.same_team({"name": "T1", "code": "T1"}, "T1")
    assert not v2.same_team({"name": "Gen.G", "code": "GEN"}, "T1")


def test_schedule_second_run_stops_at_saved_page(monkeypatch, tmp_path):
    requests = []

    def get(url, key=False):
        requests.append(url)
        assert key
        if "/getLeagues?" in url:
            return {"data": {"leagues": [{"slug": "lck", "id": "league"}]}}
        if "/getSchedule?" in url:
            older = "pageToken=older" in url
            return {
                "data": {
                    "schedule": {
                        "events": [
                            {
                                "type": "match",
                                "state": "completed",
                                "startTime": "2025-01-01" if older else "2026-01-01",
                                "match": {"id": "old" if older else "new"},
                            }
                        ],
                        "pages": {"older": None if older else "older"},
                    }
                }
            }
        assert "/getEventDetails?" in url
        return {"data": {"event": {"match": {"teams": [], "games": []}}}}

    monkeypatch.setattr(ft, "get", get)
    monkeypatch.setattr(ft, "LEAGUES", {"lck": "LCK"})
    saved = ft.schedule(tmp_path)
    assert set(saved) == {"new", "old"}
    assert sum("/getSchedule?" in url for url in requests) == 2
    requests.clear()
    assert ft.schedule(tmp_path) == saved
    assert sum("/getSchedule?" in url for url in requests) == 1
    assert not any("/getEventDetails?" in url for url in requests)
