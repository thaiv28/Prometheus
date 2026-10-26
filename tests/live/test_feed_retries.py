"""Worker feed recovery and logging, using local files and simulated clocks."""

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from prometheus.live import service


@pytest.fixture
def lag(monkeypatch):
    value = service.FeedLag()
    monkeypatch.setattr(service, "FEED_LAG", value)
    return value


def test_feed_lag_backoff_and_recovery(lag, monkeypatch):
    logger = mock.Mock()
    monkeypatch.setattr(service, "log", logger)
    assert lag.lag("g") == 30
    for expected in (60, 120, 240, 480, 600, 600):
        lag.too_recent("g")
        assert lag.lag("g") == expected
    assert logger.call_count == 5
    assert lag.lag("other") == 30
    for expected in (300, 150, 75, 37, 30):
        for _ in range(29):
            lag.ok("g")
        assert lag.lag("g") > expected
        lag.ok("g")
        assert lag.lag("g") == expected
    lag.too_recent("g")
    for _ in range(29):
        lag.ok("g")
    lag.too_recent("g")  # failure breaks the success streak
    lag.ok("g")
    assert lag.lag("g") == 120


@pytest.mark.parametrize(
    "status,exception",
    [(400, service.TooRecent), (404, ValueError), (403, service.Stop)],
)
def test_fetch_status(monkeypatch, tmp_path, status, exception):
    monkeypatch.setattr(service, "probe", lambda *_: [{"http_status": status}])
    with pytest.raises(exception, match=f"HTTP {status}"):
        service.fetch_json("unused", tmp_path)


def test_discovery_backs_off_and_uses_lag(lag, monkeypatch, tmp_path):
    now = datetime(2026, 10, 26, 12, 0, 9, tzinfo=UTC)
    clock = mock.Mock()
    clock.now.return_value = now
    monkeypatch.setattr(service, "datetime", clock)
    fetch = mock.Mock(side_effect=service.TooRecent("HTTP 400"))
    monkeypatch.setattr(service, "fetch_json", fetch)
    assert service.feed_sides({"id": "g"}, tmp_path) is None
    assert lag.lag("g") == 60
    fetch.side_effect = None
    fetch.return_value = ({}, {})
    assert service.feed_sides({"id": "g"}, tmp_path) is None
    assert "11%3A59%3A00Z" in fetch.call_args.args[0]
    assert lag.successes["g"] == 1


def poll_game():
    game = service.Game.__new__(service.Game)
    game.id, game.state, game.start = "g", "live", {}
    game.feed_failures = 0
    game.collector = mock.Mock()
    game.collector.snapshot.return_value = {"status": "live"}
    game.window = mock.Mock()
    return game


def test_poll_transients_and_consecutive_failure_limit(lag):
    game = poll_game()
    game.window.side_effect = service.TooRecent("HTTP 400")
    game.poll()
    assert game.state == "live"
    assert lag.lag("g") == 60
    game.window.side_effect = ValueError("HTTP 404")
    for _ in range(29):
        game.poll()
    assert game.state == "live"
    assert game.feed_failures == 29
    with pytest.raises(ValueError, match="HTTP 404"):
        game.poll()
    game.window.side_effect = None
    game.window.return_value = (Path("unused"), {}, None)
    game.poll()
    assert game.feed_failures == 0
    game.window.side_effect = ValueError("HTTP 404")
    game.poll()
    assert game.feed_failures == 1


def test_poll_uses_lag_and_success_payload_resets_failures(lag, monkeypatch):
    game = poll_game()
    game.feed_failures = 12
    lag.too_recent(game.id)
    now = datetime(2026, 10, 26, 12, 0, 9, tzinfo=UTC)
    clock = mock.Mock()
    clock.now.return_value = now
    monkeypatch.setattr(service, "datetime", clock)
    game.window.return_value = (
        Path("unused"),
        {"received_at_utc": now.isoformat()},
        {"frames": []},
    )
    game.poll()
    assert game.window.call_args.args[0] == now.replace(second=0) - timedelta(
        seconds=60
    )
    assert game.feed_failures == 0
    assert lag.successes[game.id] == 1


def test_failed_ids_expire_at_five_minutes():
    failed, times = {"g": "HTTP 404", "other": "bad"}, {"g": 100, "other": 200}
    service.expire_failed(failed, times, 399.99)
    assert "g" in failed
    service.expire_failed(failed, times, 400)
    assert failed == {"other": "bad"}
    assert times == {"other": 200}


def test_event_log_excludes_cycles(tmp_path, monkeypatch, capsys):
    path = tmp_path / "worker.jsonl"
    monkeypatch.setattr(service, "LOG_FILE", path)
    service.log("feed_lag", game="g", lag=60)
    service.log("cycle", games=1)
    stdout = capsys.readouterr().out.splitlines()
    assert len(stdout) == 2
    assert path.read_text().splitlines() == stdout[:1]
    monkeypatch.setattr(service, "LOG_FILE", None)
    service.log("tracking", game="g")
    assert path.read_text().splitlines() == stdout[:1]


def test_cloudwatch_log_config():
    config = json.loads(
        (
            Path(__file__).resolve().parents[2] / "deploy/live/cloudwatch-agent.json"
        ).read_text()
    )
    assert config["agent"]["run_as_user"] == "root"
    assert "metrics" not in config
    entries = config["logs"]["logs_collected"]["files"]["collect_list"]
    assert len(entries) == 2
    assert [e["log_group_name"] for e in entries] == [
        "/thaiv/prometheus/live/decisions",
        "/thaiv/prometheus/live/worker",
    ]
    assert (
        entries[0]["file_path"]
        == "/srv/prometheus-live/app/data/live/**/trading/decisions.jsonl"
    )
    assert entries[0]["publish_multi_logs"] is True
    assert entries[1]["file_path"] == "/srv/prometheus-live/app/data/live/worker.jsonl"
    assert all(
        e["timezone"] == "UTC"
        and e["log_stream_name"] == "{instance_id}"
        and "retention_in_days" not in e
        for e in entries
    )


@pytest.mark.parametrize(
    "failures,error", [(1, service.TooRecent), (1, ValueError), (30, ValueError)]
)
def test_run_keeps_transient_games_and_rediscovers_failed_games(
    tmp_path, monkeypatch, lag, failures, error
):
    (tmp_path / "teams.json").write_text("[]")
    game = mock.Mock()
    game.id, game.number, game.state = "g", 1, "live"
    game.mapping = {"match_id": "m", "teams": [{"name": "A"}, {"name": "B"}]}
    game.ticker, game.series_ticker, game.forge = "map", "series", {}
    game.dir = tmp_path
    game.start = {}
    game.feed_failures = 0
    game.collector.snapshot.return_value = {"status": "live"}
    page = {"match": {"id": "m"}, "game": {}}
    game.page.return_value = game.add_quotes.return_value = page
    attempts = []
    clock = [100.5]

    def window(_):
        attempts.append(clock[0])
        if len(attempts) <= failures:
            raise error("HTTP 400" if error is service.TooRecent else "HTTP 404")
        return tmp_path, {}, None

    game.window.side_effect = window
    constructor = mock.Mock(return_value=game)
    # Keep a reference to the real method before replacing the constructor.
    poll = service.Game.poll
    game.poll.side_effect = lambda: poll(game)
    event = {
        "id": "m",
        "state": "inProgress",
        "match": {
            "teams": [{"name": "A"}, {"name": "B"}],
            "games": [{"id": "g", "number": 1, "state": "inProgress"}],
        },
    }
    args = SimpleNamespace(
        team_catalog=tmp_path / "teams.json",
        aliases=tmp_path / "none",
        model=None,
        skip_game=[],
        adopt=[],
        root=tmp_path,
        page_out=tmp_path,
        discover_interval=60,
        interval=10,
        ratings=None,
        forge=False,
        s3=None,
        idle_exit=None,
    )
    logger = mock.Mock()
    waiting = mock.Mock(return_value=[])
    pre = mock.Mock()
    pre.maps = {}
    for name, value in {
        "fetch_json": mock.Mock(
            return_value=({}, {"data": {"schedule": {"events": [event]}}})
        ),
        "pin_order": lambda e, r: e,
        "mapping_for": lambda *a: game.mapping,
        "feed_sides": lambda g, out: g,
        "Game": constructor,
        "PreMaps": lambda _: pre,
        "waiting_pages": waiting,
        "update_lifecycle": lambda *a: False,
        "update_observed": lambda *a: None,
        "write_index": lambda *a: (1, True),
        "log": logger,
    }.items():
        monkeypatch.setattr(service, name, value)
    monkeypatch.setattr(service.time, "time", lambda: clock[0])
    monkeypatch.setattr(service.time, "monotonic", lambda: clock[0])

    def sleep(seconds):
        clock[0] += seconds
        if clock[0] >= 850:
            raise service.Stop("test complete")

    monkeypatch.setattr(service.time, "sleep", sleep)
    assert service.run(args) == service.REFUSED
    failed = [c for c in logger.call_args_list if c.args[0] == "game_failed"]
    assert len(failed) == (1 if failures == 30 else 0)
    assert constructor.call_count == (2 if failures == 30 else 1)
    assert len(attempts) > failures
    if failures == 30:
        # Discovery retries at its first cycle after the 300-second cooldown.
        assert 300 <= attempts[30] - attempts[29] < 360
        assert any("g" in c.args[-1] for c in waiting.call_args_list)
