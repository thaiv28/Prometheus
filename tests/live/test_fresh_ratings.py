import json
import subprocess
from types import SimpleNamespace

import pytest

from prometheus.live import service


@pytest.mark.parametrize(
    "generated,through,accepted",
    [
        ("2026-10-19T12:00:00+00:00", "2026-10-18", True),
        ("2026-10-19T10:00:00+00:00", "2026-10-18", False),
        ("2026-10-19T11:00:00+00:00", "2026-10-18", False),
        ("2026-10-19T12:00:00+00:00", "2026-10-17", False),
    ],
)
def test_fresh_swap(tmp_path, monkeypatch, generated, through, accepted):
    path = tmp_path / "live_inputs.json"
    base = {
        "generated_at": "2026-10-19T11:00:00+00:00",
        "data_through": "2026-10-18",
        "teams": {"A": {"elo": 1500}},
        "draft": {"kept": True},
    }
    path.write_text(json.dumps(base))
    ratings = service.Ratings(path)
    assert ratings._load() == base["teams"]
    fresh = {
        **base,
        "generated_at": generated,
        "data_through": through,
        "teams": {"A": {"elo": 1510}},
        "results_through": "2026-10-19T11:30Z",
    }

    def run(command, **kwargs):
        assert command == [
            "aws",
            "s3",
            "cp",
            "s3://bucket/prometheus/live-inputs/live_inputs_fresh.json",
            str(tmp_path / "live_inputs_fresh.json.new"),
            "--only-show-errors",
        ]
        assert kwargs["timeout"] == 30 and kwargs["check"] is False
        (tmp_path / "live_inputs_fresh.json.new").write_text(json.dumps(fresh))
        return SimpleNamespace(returncode=0)

    events = []
    monkeypatch.setattr(service.subprocess, "run", run)
    monkeypatch.setattr(service, "log", lambda event, **kw: events.append((event, kw)))
    ratings.refresh_fresh("bucket")
    assert json.loads(path.read_text()) == (fresh if accepted else base)
    assert ratings._load() == (fresh if accepted else base)["teams"]
    assert bool(events) == accepted
    if accepted:
        assert events == [
            ("ratings_refreshed", {"results_through": fresh["results_through"]})
        ]
    assert not (tmp_path / "live_inputs_fresh.json.new").exists()


@pytest.mark.parametrize("failure", ["timeout", "corrupt", "exit"])
def test_failed_refresh_preserves_inputs(tmp_path, monkeypatch, failure):
    path = tmp_path / "live_inputs.json"
    path.write_text("{}")

    def run(command, **kwargs):
        (tmp_path / "live_inputs_fresh.json.new").write_text("bad json")
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 30)
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr(service.subprocess, "run", run)
    service.Ratings(path).refresh_fresh("bucket")
    assert path.read_text() == "{}"
    assert not (tmp_path / "live_inputs_fresh.json.new").exists()
