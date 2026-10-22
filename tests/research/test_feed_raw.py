"""Raw feed collection, resume boundaries and parity with timeline shards."""

import gzip
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts" / "research"))
import feed_raw
import feed_timelines

START = datetime(2025, 1, 1, tzinfo=UTC)
GAME = {"game_id": "a", "match_id": "m", "league": "LCK", "number": 1}


START_ISO = START.isoformat()


def saved_start(timelines, start=START_ISO):
    (timelines / "games").mkdir(parents=True, exist_ok=True)
    (timelines / "games" / "a.json").write_text(
        json.dumps({"start": start, "blue_id": "blue"})
    )


def window(state="in_game"):
    return {
        "gameMetadata": {"extra": [1, 2]},
        "frames": [{"gameState": state, "participants": [{"gold": 123}]}],
        "unknown": {"keep": True},
    }


def test_fetch_preserves_payload_and_floors_query(monkeypatch):
    payload = window()
    urls = []

    def get(url):
        urls.append(url)
        return payload

    monkeypatch.setattr(feed_timelines, "get", get)
    monkeypatch.setattr(feed_raw, "get", feed_timelines.get)
    assert feed_raw.fetch(feed_raw.WINDOW, "a") is payload
    assert (
        feed_raw.fetch(
            feed_raw.DETAILS, "a", START + timedelta(seconds=19, microseconds=123)
        )
        is payload
    )
    assert urls[0] == feed_raw.WINDOW.format("a")
    assert parse_qs(urlsplit(urls[1]).query) == {
        "startingTime": ["2025-01-01T00:00:10Z"]
    }
    monkeypatch.setattr(feed_raw, "get", lambda url: None)
    assert feed_raw.fetch(feed_raw.WINDOW, "a") is None


def test_saved_start_and_first_finished_frame(monkeypatch, tmp_path):
    saved_start(tmp_path)
    first, running, finished = window(), window(), window("finished")
    details = {"frames": [{"participants": [{"xp": 567, "cs": 89}]}]}
    calls = []

    def fetch(endpoint, game_id, at=None):
        calls.append((endpoint, game_id, at))
        if at is None:
            return first
        if endpoint == feed_raw.DETAILS:
            return details
        return running if at == START else finished

    def unexpected_search(game_id):
        pytest.fail("saved start must avoid searching")

    monkeypatch.setattr(feed_raw, "find_start", unexpected_search)
    monkeypatch.setattr(feed_raw, "fetch", fetch)
    result = feed_raw.collect_game(GAME, tmp_path)
    assert result["start_source"] == "feed_timelines"
    assert result["start"] == START.isoformat()
    assert result["blue_id"] == "blue"
    assert result["first"] is first
    assert result["error"] is None
    assert len(result["samples"]) == 2
    assert result["samples"][0]["window"] is running
    assert result["samples"][1]["window"] is finished
    assert all(s["details"] is details for s in result["samples"])
    assert [c[2] for c in calls] == [
        None,
        START,
        START,
        START + timedelta(seconds=60),
        START + timedelta(seconds=60),
    ]


@pytest.mark.parametrize("saved", [False, True])
def test_missing_start_searches(monkeypatch, tmp_path, saved):
    if saved:
        saved_start(tmp_path, None)
    searches = []

    def find_start(game_id):
        searches.append(game_id)
        return START, "searched-blue"

    monkeypatch.setattr(feed_raw, "find_start", find_start)
    monkeypatch.setattr(feed_raw, "fetch", lambda *args: window("finished"))
    result = feed_raw.collect_game(GAME, tmp_path)
    assert searches == ["a"]
    assert result["start_source"] == "searched"
    assert result["blue_id"] == "searched-blue"


def test_no_start_keeps_first(monkeypatch, tmp_path):
    first = window()
    monkeypatch.setattr(feed_raw, "find_start", lambda game_id: (None, "blue"))
    monkeypatch.setattr(feed_raw, "fetch", lambda *args: first)
    result = feed_raw.collect_game(GAME, tmp_path)
    assert result == dict(
        GAME,
        blue_id="blue",
        start=None,
        start_source="searched",
        first=first,
        samples=[],
        error="no start",
    )


@pytest.mark.parametrize("exhausted", [False, True])
@pytest.mark.parametrize("extra_state", ["in_game", "finished", None])
def test_extra_sample_after_last_sample(monkeypatch, tmp_path, exhausted, extra_state):
    saved_start(tmp_path)
    monkeypatch.setattr(feed_raw, "MAX_MINUTES", 1 if exhausted else 80)
    calls = []
    last = START + timedelta(seconds=60 if exhausted else 0)
    extra = last + timedelta(seconds=30)

    def fetch(endpoint, game_id, at=None):
        calls.append((endpoint, at))
        if endpoint == feed_raw.DETAILS:
            return {"participants": ["raw"]}
        if at == extra:
            return window(extra_state) if extra_state else None
        if at is not None and at > last:
            return None
        return window()

    monkeypatch.setattr(feed_raw, "fetch", fetch)
    result = feed_raw.collect_game(GAME, tmp_path)
    assert result["samples"][-1]["t"] == extra.isoformat()
    assert result["samples"][-1]["details"] == {"participants": ["raw"]}
    assert calls[-2:] == [(feed_raw.WINDOW, extra), (feed_raw.DETAILS, extra)]
    assert result["error"] == (
        None if extra_state == "finished" else "no finished frame"
    )


def schedule(path, count=1):
    path.mkdir(parents=True, exist_ok=True)
    games = [dict(GAME, game_id=str(i)) for i in range(count)]
    (path / "schedule.json").write_text(
        json.dumps({"m": {"start": START.isoformat(), "games": games}})
    )
    return games


def test_collect_atomic_gzip_and_resume(monkeypatch, tmp_path, capsys):
    timelines, out = tmp_path / "timelines", tmp_path / "raw"
    schedule(timelines, 2)
    calls = []

    def collect_game(game, timelines):
        calls.append(game)
        return dict(game, samples=[{"raw": True}], error=None)

    monkeypatch.setattr(feed_raw, "collect_game", collect_game)
    assert feed_raw.collect(out, timelines, limit=1) == 1
    files = list((out / "games").glob("*.json.gz"))
    assert len(files) == 1
    with gzip.open(files[0], "rt") as stream:
        assert json.load(stream) == dict(calls[0], samples=[{"raw": True}], error=None)
    assert not list(out.rglob("*.tmp"))
    assert feed_raw.collect(out, timelines) == 1
    assert feed_raw.collect(out, timelines) == 0
    assert len(calls) == 2
    feed_raw.status(out, timelines)
    assert "2 of 2 maps collected, 2 complete," in capsys.readouterr().out


@pytest.mark.parametrize("shard", [(0, 3), (1, 3), (2, 3)])
@pytest.mark.parametrize("split", [(0, 1), (0, 2), (1, 2)])
def test_partition_matches_timelines(monkeypatch, tmp_path, shard, split):
    timelines, out = tmp_path / "timelines", tmp_path / "raw"
    games = schedule(timelines, 17)
    for directory, suffix in [(timelines, ".json"), (out, ".json.gz")]:
        (directory / "games").mkdir(parents=True)
        for game in games[:3]:
            (directory / "games" / (game["game_id"] + suffix)).touch()
    raw_ids, timeline_ids = [], []

    def result(game, ids):
        ids.append(game["game_id"])
        return dict(game, samples=[], error="no start")

    monkeypatch.setattr(feed_raw, "collect_game", lambda g, t: result(g, raw_ids))
    monkeypatch.setattr(
        feed_timelines, "collect_game", lambda g: result(g, timeline_ids)
    )
    feed_raw.collect(out, timelines, shard=shard, split=split)
    feed_timelines.collect(timelines, shard=shard, split=split)
    assert raw_ids == timeline_ids


@pytest.mark.parametrize(
    "exception,code,prefix,suffix",
    [
        (feed_raw.Refused, 3, "Stopped", " run again later."),
        (feed_raw.Unreachable, 4, "Unreachable", ""),
    ],
)
def test_main_exit_codes(
    monkeypatch, tmp_path, capsys, exception, code, prefix, suffix
):
    def collect(*args):
        raise exception("mock failure")

    monkeypatch.setattr(feed_raw, "collect", collect)
    assert feed_raw.main(["collect", "--out", str(tmp_path)]) == code
    expected = (
        f"{prefix}: mock failure. Saved maps are kept;{suffix}\n"
        if code == 3
        else f"{prefix}: mock failure. Saved maps are kept.\n"
    )
    assert capsys.readouterr().out == expected


def test_old_timeline_without_blue_id_uses_feed_metadata(monkeypatch, tmp_path):
    (tmp_path / "games").mkdir()
    (tmp_path / "games" / "a.json").write_text(json.dumps({"start": START_ISO}))
    first = dict(
        window(), gameMetadata={"blueTeamMetadata": {"esportsTeamId": "meta-blue"}}
    )
    monkeypatch.setattr(
        feed_raw,
        "fetch",
        lambda endpoint, game_id, at=None: first if at is None else window("finished"),
    )
    result = feed_raw.collect_game(GAME, tmp_path)
    assert result["start_source"] == "feed_timelines"
    assert result["blue_id"] == "meta-blue"


def test_fetch_retries_unreachable(monkeypatch):
    attempts = []

    def get(url):
        attempts.append(url)
        if len(attempts) < 3:
            raise feed_raw.Unreachable("timed out")
        return {"frames": []}

    monkeypatch.setattr(feed_raw, "get", get)
    monkeypatch.setattr(feed_raw.time, "sleep", lambda s: None)
    assert feed_raw.fetch(feed_raw.WINDOW, "a") == {"frames": []}
    assert len(attempts) == 3
    attempts.clear()
    monkeypatch.setattr(
        feed_raw, "get", lambda url: (_ for _ in ()).throw(feed_raw.Unreachable("x"))
    )
    with pytest.raises(feed_raw.Unreachable):
        feed_raw.fetch(feed_raw.WINDOW, "a")
