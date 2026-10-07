"""Explicit map discovery, request stops, and training export causality."""

from pathlib import Path
import sys
import urllib.error

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "research"))
import collect_gol_training as collect
from test_gol_pilot import html


def test_map_discovery_uses_explicit_ids_and_rejects_conflicts():
    page = (
        html()
        + '<a href="../game/stats/99/page-game/">Game 1</a><a href="../game/stats/1234/page-game/">Game 2</a>'
    )
    assert collect.maps(page, 99) == [
        {"gol_id": 99, "expected_map": 1},
        {"gol_id": 1234, "expected_map": 2},
    ]
    for bad in [
        html(),
        page.replace("Game 2", "Game 3"),
        page + '<a href="../game/stats/555/page-game/">Game 2</a>',
    ]:
        with pytest.raises(ValueError):
            collect.maps(bad, 99)


def test_cached_resume_does_not_consume_budget(tmp_path, monkeypatch):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    (tmp_path / "known.html").write_text("preserved")
    monkeypatch.setattr(
        collect.pilot.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("Unexpected network"),
    )
    cache = collect.BudgetCache(tmp_path, True, 0, 2)
    assert (
        cache.read("known.html", "https://gol.gg/game/stats/1/page-game/")
        == "preserved"
    )
    with pytest.raises(collect.CollectionStopped, match="request_budget"):
        cache.read("new.html", "https://gol.gg/game/stats/2/page-game/")
    assert cache.requests == 0


@pytest.mark.parametrize("status", [401, 403, 429])
def test_access_or_rate_limit_stops_without_retry(tmp_path, monkeypatch, status):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    calls = []

    def denied(*args, **kwargs):
        calls.append(1)
        raise urllib.error.HTTPError(
            "https://gol.gg/", status, "stop", {"Retry-After": "120"}, None
        )

    monkeypatch.setattr(collect.pilot.urllib.request, "urlopen", denied)
    cache = collect.BudgetCache(tmp_path, True, 10, 2)
    with pytest.raises(collect.CollectionStopped, match=f"http_{status}"):
        cache.read("new.html", "https://gol.gg/game/stats/2/page-game/")
    assert calls == [1] and cache.requests == 1
    assert not (tmp_path / "new.html").exists()


def test_training_export_uses_pregame_elo_and_rejects_duplicates(monkeypatch):
    meta = pd.DataFrame(
        [
            {
                "gameid": game,
                "side": side,
                "date": date,
                "league": "LCK",
                "teamname": side,
                "result": int(side == "Blue"),
                "pre_match_elo": rating,
            }
            for game, date in [("a", "2023-02-01"), ("b", "2026-02-01")]
            for side, rating in [("Blue", 1600), ("Red", 1500)]
        ]
    )
    monkeypatch.setattr(collect.pd, "read_sql", lambda *a, **k: meta)
    row = {"oe_gameid": "a", "minute": 10, "blue_gold": 16000, "red_gold": 15000}
    for kind in collect.pilot.OBJECTIVES:
        row[f"blue_{kind}"] = 1
        row[f"red_{kind}"] = 0
    frame = pd.DataFrame([row, dict(row, oe_gameid="b")])
    result = collect.training_frame(frame)
    assert (
        len(result) == 1
        and result.iloc[0].gold_gap == 1000
        and result.iloc[0].elo_gap == 100
    )
    assert result.iloc[0].blue_won == 1 and result.iloc[0].year == 2023
    assert "post_match_elo" not in result
    with pytest.raises(ValueError, match="Duplicate"):
        collect.training_frame(pd.concat([frame, frame]))
    meta["pre_match_elo"] = meta.pre_match_elo.astype(float)
    meta.loc[meta.gameid.eq("a") & meta.side.eq("Blue"), "pre_match_elo"] = float("inf")
    assert collect.training_frame(frame).empty


def test_partial_order_reaches_multiple_strata():
    assert list(collect.interleave([[1, 2, 3], [4, 5], [6]])) == [1, 4, 6, 2, 5, 3]


def test_run_preserves_partial_maps_then_resumes_from_cache(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json

    monkeypatch.setattr(collect, "seed_cache", lambda path: None)
    monkeypatch.setattr(
        collect.audit, "STRATA", [{"league": "LCK", "year": 2024, "tournament": "demo"}]
    )
    monkeypatch.setattr(
        collect.audit,
        "listing",
        lambda *a: [{"gol_id": 999990, "listing_date": "2024-01-01"}],
    )
    monkeypatch.setattr(
        collect,
        "maps",
        lambda *a: [
            {"gol_id": 999990, "expected_map": 1},
            {"gol_id": 999995, "expected_map": 2},
        ],
    )
    monkeypatch.setattr(collect.pilot.time, "sleep", lambda *a: None)
    folder = tmp_path / "html"
    folder.mkdir()
    (folder / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    (
        folder
        / ("listing-" + collect.hashlib.sha256(b"demo").hexdigest()[:12] + ".html")
    ).write_text("listing")
    (folder / "999990-game.html").write_text("existing summary")
    calls = []

    class Response:
        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def read(self):
            return b"new page"

    def fetched(request, **kwargs):
        calls.append(request.full_url)
        return Response(request.full_url)

    monkeypatch.setattr(collect.pilot.urllib.request, "urlopen", fetched)
    exports = []

    def exported(args, samples, progress):
        exports.append((list(samples), dict(progress)))
        progress.update(training_rows=len(samples), ready_games=len(samples))

    monkeypatch.setattr(collect, "export", exported)
    args = SimpleNamespace(
        artifacts=tmp_path,
        fetch=True,
        max_requests=1,
        delay=2,
        out=tmp_path / "report.md",
    )
    collect.run(args)
    assert (
        len(exports[-1][0]) == 1
        and exports[-1][1]["stop_reason"] == "request_budget_reached"
    )
    assert (folder / "999990-timeline.html").exists()
    assert len(json.loads((tmp_path / "samples.json").read_text())) == 1
    args.max_requests = 2
    collect.run(args)
    assert (
        len(exports[-1][0]) == 2
        and exports[-1][1]["stop_reason"] == "selected_events_download_complete"
    )
    assert len(calls) == 3  # second run fetches only the missing second-map pair


@pytest.mark.parametrize(
    "network_error",
    [
        urllib.error.URLError("DNS unavailable"),
        TimeoutError("The read operation timed out"),
        ConnectionResetError("Connection reset by peer"),
    ],
)
def test_transport_failure_stops_and_exports_instead_of_spending_budget(
    tmp_path, monkeypatch, network_error
):
    from types import SimpleNamespace
    import json

    monkeypatch.setattr(collect, "seed_cache", lambda path: None)
    monkeypatch.setattr(
        collect.audit, "STRATA", [{"league": "LCK", "year": 2024, "tournament": "demo"}]
    )
    monkeypatch.setattr(collect.audit, "listing", lambda *a: [{"gol_id": 999990}])
    folder = tmp_path / "html"
    folder.mkdir()
    (folder / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    (
        folder
        / ("listing-" + collect.hashlib.sha256(b"demo").hexdigest()[:12] + ".html")
    ).write_text("listing")
    prior = {"gol_id": 999987, "expected_map": 1}
    (tmp_path / "samples.json").write_text(json.dumps([prior]))
    calls = []

    def failed(*a, **k):
        calls.append(1)
        raise network_error

    monkeypatch.setattr(collect.pilot.urllib.request, "urlopen", failed)
    exports = []

    def exported(args, samples, progress):
        assert samples == [prior]
        exports.append(dict(progress))
        progress.update(training_rows=0, ready_games=0)

    monkeypatch.setattr(collect, "export", exported)
    collect.run(
        SimpleNamespace(
            artifacts=tmp_path,
            fetch=True,
            max_requests=300,
            delay=2,
            out=tmp_path / "report.md",
        )
    )
    assert calls == [1] and exports[0]["stop_reason"].startswith("network_error:")
    assert len(exports[0]["discovery_errors"]) == 1
