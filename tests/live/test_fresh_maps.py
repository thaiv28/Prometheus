"""Finished-map handoff, with no external services."""

import json
import sqlite3
import tarfile
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock
from urllib.error import HTTPError

import pytest

from prometheus.live import notify, service


@pytest.fixture
def game(tmp_path, monkeypatch):
    directory = tmp_path / "match" / "game"
    collector = directory / "collector"
    collector.mkdir(parents=True)
    teams = [
        {"name": "A", "code": "AA", "riot_team_id": "a"},
        {"name": "B", "code": "BB", "riot_team_id": "b"},
    ]
    frame = lambda at: {
        "source_timestamp": at,
        "teams": {
            "blue": {
                "team_id": "b",
                "participant_metadata": [
                    {"summonerName": "BB Player" + str(i)} for i in range(4)
                ],
            },
            "red": {
                "team_id": "a",
                "participant_metadata": [
                    {"summonerName": n}
                    for n in ["AA One", "aaTwo", "Three", "AA Four", "AA Five"]
                ],
            },
        },
    }
    with sqlite3.connect(collector / "collector.sqlite3") as db:
        db.execute("CREATE TABLE journal (sequence INTEGER, result TEXT)")
        db.execute(
            "INSERT INTO journal VALUES (1, ?)",
            (
                json.dumps(
                    {
                        "rows": [
                            frame("2026-10-19T10:00:00Z"),
                            frame("2026-10-19T10:30:00Z"),
                        ]
                    }
                ),
            ),
        )
    (directory.parent / "results.json").write_text(
        json.dumps({"1": {"winner": 0, "at": "2026-10-19T10:35:00Z"}})
    )
    monkeypatch.setattr(service, "upload_maps", Mock())
    monkeypatch.setattr(service, "dispatch_prices", Mock())
    return SimpleNamespace(
        dir=directory,
        collector_dir=collector,
        mapping={
            "match_id": "match",
            "league": "LCK",
            "event": "Cup",
            "best_of": 3,
            "teams": teams,
        },
        id="game",
        number=1,
        snapshot_path=lambda: directory.parent / "pages" / "map1.json",
        results=lambda: {
            int(n): r
            for n, r in json.loads(
                (directory.parent / "results.json").read_text()
            ).items()
        },
    )


def test_record_map_and_restart(game):
    game.snapshot_path().parent.mkdir()
    game.snapshot_path().write_text("{}")
    game.state, game.ticker, game.series_ticker = "finished", None, None
    game.results = lambda: {1: {"winner": 0}}
    service.Game.settle(game)
    path = game.dir.parent / "maps.json"
    row = json.loads(path.read_text())["1"]
    assert row["players"] == [["One", "Two", "Three", "Four", "Five"], None]
    assert row["teams"] == ["A", "B"]
    assert row["duration_seconds"] is None  # no found start: joined mid-map
    assert row["winner"] == 0
    assert row["league"] == "LCK"
    original = path.read_bytes()
    service.Game.settle(game)
    assert path.read_bytes() == original
    service.upload_maps.assert_called_once_with(
        game.dir.parent, "match", game.snapshot_path()
    )
    service.dispatch_prices.assert_called_once()


def test_new_settlement(game, monkeypatch):
    game.state, game.ticker = "finished", "ticker"
    game.results = lambda: {}
    game.results_path = game.dir.parent / "results.json"
    game.request_dir = lambda kind: game.dir / kind
    settle = Mock(return_value=True)
    monkeypatch.setattr(service, "settle_map", settle)
    service.Game.settle(game)
    assert (game.dir.parent / "maps.json").exists()
    settle.assert_called_once()


def test_archive_start_and_errors(game):
    with tarfile.open(game.dir / "archive.tar.gz", "w:gz") as archive:
        archive.add(
            game.collector_dir / "collector.sqlite3",
            arcname="collector/collector.sqlite3",
        )
    (game.collector_dir / "collector.sqlite3").unlink()
    (game.dir / "start.json").write_text('{"source_at":"2026-10-19T09:59:59.4Z"}')
    service.record_map(game)
    assert (
        json.loads((game.dir.parent / "maps.json").read_text())["1"]["duration_seconds"]
        == 1801
    )
    (game.dir.parent / "maps.json").write_text("bad")
    service.record_map(game)  # malformed evidence cannot stop polling


@pytest.fixture
def dispatch(monkeypatch):
    monkeypatch.setattr(notify, "_token", None)
    monkeypatch.setattr(notify, "_disabled", False)
    monkeypatch.setattr(notify, "_last_dispatch", None)
    monkeypatch.delenv("PRICES_DISPATCH_TOKEN", raising=False)
    monkeypatch.delenv("PRICES_DISPATCH_PARAMETER", raising=False)
    monkeypatch.setenv("REPOSITORY", "https://github.com/owner/repo.git")
    response = Mock()
    response.__enter__ = Mock(return_value=SimpleNamespace(status=204))
    response.__exit__ = Mock(return_value=False)
    http = Mock(return_value=response)
    monkeypatch.setattr(notify, "urlopen", http)
    return http


def test_env_dispatch_debounce(dispatch, monkeypatch):
    monkeypatch.setenv("PRICES_DISPATCH_TOKEN", "secret")
    command = Mock(side_effect=AssertionError("must use env token"))
    monkeypatch.setattr(notify.subprocess, "run", command)
    now = datetime.now(UTC)
    for seconds in [0, 299, 300]:
        notify.dispatch_prices(now + timedelta(seconds=seconds))
    assert dispatch.call_count == 2
    request = dispatch.call_args.args[0]
    assert request.full_url.endswith(
        "/owner/repo/actions/workflows/prices.yml/dispatches"
    )
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == {"ref": "main"}
    command.assert_not_called()


def test_ssm_cached(dispatch, monkeypatch):
    command = Mock(return_value=SimpleNamespace(stdout="ssm-token\n"))
    monkeypatch.setattr(notify.subprocess, "run", command)
    now = datetime.now(UTC)
    notify.dispatch_prices(now)
    notify.dispatch_prices(now + timedelta(minutes=5))
    command.assert_called_once()
    assert command.call_args.args[0] == [
        "aws",
        "ssm",
        "get-parameter",
        "--name",
        "/thaiv/prometheus/live/prices-dispatch-token",
        "--with-decryption",
        "--query",
        "Parameter.Value",
        "--output",
        "text",
    ]
    assert dispatch.call_args.args[0].get_header("Authorization") == "Bearer ssm-token"


def test_token_failure_disables(dispatch, monkeypatch, capsys):
    command = Mock(side_effect=OSError("unavailable"))
    monkeypatch.setattr(notify.subprocess, "run", command)
    notify.dispatch_prices(datetime.now(UTC))
    notify.dispatch_prices(datetime.now(UTC) + timedelta(hours=1))
    command.assert_called_once()
    dispatch.assert_not_called()
    assert capsys.readouterr().out.count("dispatch_disabled") == 1


def test_http_failure_and_upload(dispatch, monkeypatch, tmp_path):
    monkeypatch.setenv("PRICES_DISPATCH_TOKEN", "token")
    dispatch.side_effect = HTTPError(
        "https://api.github.com", 403, "Forbidden", {}, None
    )
    notify.dispatch_prices(datetime.now(UTC))
    monkeypatch.setenv("ARTIFACTS_BUCKET", "bucket")
    command = Mock(side_effect=OSError("aws missing"))
    monkeypatch.setattr(notify.subprocess, "run", command)
    notify.upload_maps(tmp_path, "match")
    assert command.call_args_list[0].args[0] == [
        "aws",
        "s3",
        "cp",
        str(tmp_path / "maps.json"),
        "s3://bucket/prometheus/live/match/maps.json",
        "--only-show-errors",
    ]
    assert command.call_count == 2  # a failed maps upload doesn't skip results


def test_snapshot_uploads_before_dispatch(game, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_BUCKET", "bucket")
    events = []

    def upload(command, **kwargs):
        source = command[3]
        events.append(command[4])
        assert service.Path(source).exists()
        assert kwargs["check"] and kwargs["timeout"] == 30

    monkeypatch.setattr(notify.subprocess, "run", upload)
    monkeypatch.setattr(service, "upload_maps", notify.upload_maps)
    monkeypatch.setattr(
        service, "dispatch_prices", lambda now: events.append("dispatch")
    )
    game.page = lambda *a, **kw: {"final": False}
    service.record_map(game)
    assert "dispatch" not in events  # snapshot isn't written yet
    events.clear()
    service.Game.write_snapshot(game, {})
    assert events == [
        "s3://bucket/prometheus/live/match/maps.json",
        "s3://bucket/prometheus/live/match/results.json",
        "s3://bucket/prometheus/live/match/pages/map1.json",
        "dispatch",
    ]
    assert json.loads(game.snapshot_path().read_text())["final"]
    events.clear()
    service.Game.write_snapshot(game, {})
    assert not events  # repeated finished polls don't upload again


def test_existing_snapshot_uploads_before_dispatch(game, monkeypatch):
    monkeypatch.setenv("ARTIFACTS_BUCKET", "bucket")
    game.snapshot_path().parent.mkdir()
    game.snapshot_path().write_text("{}")
    events = []
    monkeypatch.setattr(
        notify.subprocess, "run", lambda command, **kw: events.append(command[4])
    )
    monkeypatch.setattr(service, "upload_maps", notify.upload_maps)
    monkeypatch.setattr(
        service, "dispatch_prices", lambda now: events.append("dispatch")
    )
    service.record_map(game)
    assert events[-2:] == [
        "s3://bucket/prometheus/live/match/pages/map1.json",
        "dispatch",
    ]


def test_unsettled_snapshot_does_not_debounce_settlement(game):
    game.page = lambda *a, **kw: {"final": False}
    game.results = lambda: {}
    service.Game.write_snapshot(game, {})
    service.dispatch_prices.assert_not_called()
    service.upload_maps.reset_mock()
    service.record_map(game)  # late settlement, after the final page was written
    service.upload_maps.assert_called_once_with(
        game.dir.parent, "match", game.snapshot_path()
    )
    service.dispatch_prices.assert_called_once()


@pytest.mark.parametrize(
    "started,ended,expected",
    [
        (None, "2026-10-19T10:35:00Z", None),
        ("2026-10-19T11:00:00Z", "2026-10-19T10:35:00Z", None),
    ],
)
def test_record_without_frames(game, started, ended, expected):
    (game.collector_dir / "collector.sqlite3").unlink()
    if started:
        (game.dir / "start.json").write_text(json.dumps({"source_at": started}))
    service.record_map(game)
    row = json.loads((game.dir.parent / "maps.json").read_text())["1"]
    assert row["started_at"] == started
    assert row["ended_at"] == ended
    assert row["duration_seconds"] == expected
    assert row["players"] is None


def test_record_drops_failed_search_and_implausible_length(game):
    (game.dir / "start.json").write_text(
        json.dumps({"source_at": "2026-10-19T09:59:59.4Z", "error": "no frames"})
    )
    service.record_map(game)
    row = json.loads((game.dir.parent / "maps.json").read_text())["1"]
    assert row["duration_seconds"] is None
    (game.dir.parent / "maps.json").unlink()
    (game.dir / "start.json").write_text(
        json.dumps({"source_at": "2026-10-19T10:25:00Z"})
    )
    service.record_map(game)  # five minutes: not a real map length
    row = json.loads((game.dir.parent / "maps.json").read_text())["1"]
    assert row["duration_seconds"] is None
