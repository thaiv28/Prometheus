"""Hourly pages use exactly the build's replay and renderers, without a DB."""

import copy
import datetime
import importlib.util
import io
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from prometheus.site import config, predictions

ROOT = Path(__file__).resolve().parents[1]
NOW = datetime.datetime(2026, 10, 19, 12, tzinfo=datetime.UTC)


def script(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    # dataclasses needs the module in sys.modules
    import sys

    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def entries():
    base = {
        "match_id": "old",
        "start": "2026-10-18T10:00Z",
        "matched": True,
        "method": "forge",
        "p_game": 0.6,
        "p_series": 0.65,
        "ours1": "A",
        "ours2": "B",
        "home1": "LCK",
        "home2": "LCK",
        "league": "LCK",
        "best_of": 3,
        "winner": 1,
        "score1": 2,
        "score2": 0,
        "reconstructed": True,
    }
    return {
        "old": base,
        "saved": {**base, "match_id": "saved", "reconstructed": False},
        "next": {
            **base,
            "match_id": "next",
            "reconstructed": False,
            "start": "2026-10-20T10:00Z",
            "winner": None,
        },
    }


def test_matches_build_path(tmp_path, monkeypatch):
    build = script("build_site")
    log = entries()
    rebuilt = copy.deepcopy(log)
    rebuilt["old"].update(p_game=0.7, p_series=0.75)
    coverage = {"matched": 3, "matches": 3}
    links = {"old": "series-one"}
    teams = {"a", "b"}
    build_out = tmp_path / "build"
    build_out.mkdir()
    monkeypatch.setattr(config, "OUTPUT_DIR", build_out)
    monkeypatch.setattr(build.prediction_backtest, "rebuild", lambda *a: rebuilt)
    monkeypatch.setattr(build, "write_kalshi_alert", lambda *a: None)
    monkeypatch.setattr(build, "render_alert_history", lambda *a: None)
    monkeypatch.setattr(build, "render_live", lambda *a: None)
    monkeypatch.setattr(build.live_results, "load_archive", lambda: {})
    monkeypatch.setattr(
        build.live_results,
        "series_view",
        lambda *a: [{"match_id": "old", "id": "series-one"}],
    )
    monkeypatch.setattr(build.live_results, "month_views", lambda *a: [])
    monkeypatch.setattr(build.live_results, "render_live_results", lambda *a: None)

    class FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            return NOW

    monkeypatch.setattr(build.datetime, "datetime", FixedDateTime)
    build.predictions_pages(
        SimpleNamespace(prediction_log=log, states=None, coverage=coverage), teams
    )
    backtest = json.loads((build_out / "backtest.json").read_text())
    assert json.loads((build_out / "series-links.json").read_text()) == links
    hourly = tmp_path / "hourly"
    predictions.render_from_log(log, backtest, teams, links, coverage, NOW, hourly)
    assert config.OUTPUT_DIR == build_out
    for name in ("predictions.html", "results/2026-10.html", "call-performance.html"):
        assert (hourly / name).read_bytes() == (build_out / name).read_bytes()
    assert "live-results/series-one.html" in (hourly / "predictions.html").read_text()


def test_substitution_only_reconstructed(tmp_path, monkeypatch):
    log = entries()
    original = copy.deepcopy(log)
    replacements = [{**e, "p_game": 0.9, "p_series": 0.95} for e in log.values()]
    captured = {}
    monkeypatch.setattr(
        predictions,
        "predictions_view",
        lambda data, *a, **kw: captured.update(data) or {},
    )
    monkeypatch.setattr(predictions, "render_predictions", lambda *a: None)
    monkeypatch.setattr(predictions, "render_results", lambda *a: None)
    from prometheus.site import call_performance

    monkeypatch.setattr(call_performance, "render_call_performance", lambda *a: None)
    predictions.render_from_log(
        log, {"matches": replacements}, set(), {}, None, NOW, tmp_path
    )
    assert captured["old"]["p_game"] == 0.9
    assert captured["saved"] == log["saved"]
    assert captured["next"] == log["next"]
    assert log == original


@pytest.mark.parametrize("failed", ["teams.json", "series-links.json", "backtest.json"])
def test_fetch_failure_writes_nothing(tmp_path, monkeypatch, failed):
    render = script("render_predictions")
    calls = []

    def fetch(request, timeout):
        name = request.full_url.rsplit("/", 1)[-1]
        calls.append(name)
        assert timeout == 30
        assert request.get_header("User-agent") == render.markets.USER_AGENT
        if name == failed:
            raise OSError("unavailable")
        return io.StringIO(json.dumps([] if name == "teams.json" else {}))

    monkeypatch.setattr(render.urllib.request, "urlopen", fetch)
    out = tmp_path / "out"
    assert not render.run(tmp_path / "missing-log", out)
    assert not out.exists()
    assert len(calls) == len(set(calls))


def test_script_fetches_once_and_uses_summary(tmp_path, monkeypatch):
    render = script("render_predictions")
    artifacts = {
        "teams.json": [{"n": "A", "s": "a"}, {"n": "B", "s": "b"}],
        "series-links.json": {"old": "series-one"},
        "backtest.json": {"matches": []},
    }
    calls = []

    def fetch(request, timeout):
        name = request.full_url.rsplit("/", 1)[-1]
        calls.append(name)
        return io.StringIO(json.dumps(artifacts[name]))

    monkeypatch.setattr(render.urllib.request, "urlopen", fetch)
    log_path = tmp_path / "log.json"
    log_path.write_text(json.dumps({"matches": list(entries().values())}))
    summary = tmp_path / "summary.json"
    summary.write_text(json.dumps({"matched": 3, "matches": 4, "applied": 1}))
    out = tmp_path / "out"
    assert render.run(log_path, out, summary, NOW)
    assert calls == list(artifacts)
    assert (out / "predictions.html").exists()
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*.html")) == [
        "call-performance.html",
        "predictions.html",
        "results/2026-10.html",
    ]
