"""Audit sampling and missing-data denominators, independent of network."""

from pathlib import Path
import sys

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "research"))
import audit_gol_coverage as audit


def page(rows, title="LCK Spring 2022"):
    return f'<table class="table_list"><tr><th>{title} results</th></tr>{rows}</table>'


def entry(game, route="summary", date="2022-02-03"):
    return f'<tr><td><a href="../game/stats/{game}/page-{route}/">A vs B</a></td><td>{date}</td></tr>'


def test_listing_retains_only_explicit_dated_series_ids():
    html = page(entry(10) + entry(50, "game") + entry(10))
    rows = audit.listing(html, "LCK Spring 2022")
    assert [r["gol_id"] for r in rows] == [10, 50]
    assert rows[1]["listing_route"] == "game"
    # Never invent 11/12 as additional maps or treat an absent list as zero.
    for bad in [
        page(""),
        page(entry(10), "Another event"),
        page(entry(10, date="2022-02-30")),
        page(entry(10) + entry(10, date="2022-02-04")),
    ]:
        with pytest.raises(ValueError):
            audit.listing(bad, "LCK Spring 2022")


def test_selection_is_fixed_independent_of_order_outcomes_availability():
    rows = [{"gol_id": i, "winner": i % 2} for i in range(100)]
    chosen = audit.select(rows, "event")
    assert len(chosen) == 3
    assert chosen == audit.select(list(reversed(rows)), "event")
    ids = [r["gol_id"] for r in chosen]
    assert ids == [
        r["gol_id"]
        for r in audit.select(
            [dict(r, winner=0, available=False) for r in rows], "event"
        )
    ]
    assert len(audit.select(rows[:2], "event")) == 2


def test_coverage_keeps_failures_and_unknown_duration_denominators():
    inventory = [
        {"tournament": "event", "listed_series": 100, "listing_status": "ok"},
        {
            "tournament": "missing",
            "listed_series": None,
            "listing_status": "unavailable",
        },
    ]
    games = pd.DataFrame(
        [
            {
                "tournament": "event",
                "gol_id": 1,
                "timeline_valid": True,
                "match_status": "matched_rosters",
                "gold_status": "ok",
                "gamelength": 1500,
            },
            {
                "tournament": "event",
                "gol_id": 2,
                "timeline_valid": False,
                "match_status": "unmatched",
                "gold_status": "missing",
                "gamelength": 1200,
            },
            {"tournament": "event", "gol_id": 3},
        ]
    )
    checkpoints = pd.DataFrame(
        [
            {"gol_id": 1, "minute": 10, "training_ready": True},
            {"gol_id": 1, "minute": 15, "training_ready": False},
        ]
    )
    result = audit.summarize(inventory, games, checkpoints)
    r = result.iloc[0]
    assert r.sampled == 3 and r.valid_timelines == 1 and r.oe_matched == 1
    assert r.known_eligible_10m == 2 and r.known_eligible_20m == 1
    assert r.ready_10m == 1 and r.ready_15m == 0
    assert result.iloc[1].listing_status == "unavailable"
    assert pd.isna(result.iloc[1].listed_series)


def test_offline_missing_listings_remain_unavailable(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json

    from sqlalchemy import create_engine, text

    # An empty matches table, so the test doesn't need a built DB.
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE matches (gameid TEXT, date TEXT, teamname TEXT, "
                "side TEXT, gamelength REAL, result INTEGER, league TEXT)"
            )
        )
    monkeypatch.setattr(audit.pilot, "get_engine", lambda: engine)
    cache = tmp_path / "html"
    cache.mkdir()
    (cache / "robots.txt").write_text("User-agent: *\nDisallow: /private/\n")
    audit.run(
        SimpleNamespace(artifacts=tmp_path, fetch=False, out=tmp_path / "report.md")
    )
    result = pd.read_csv(tmp_path / "coverage.csv")
    assert result.listing_status.eq("unavailable").all()
    assert result.listed_series.isna().all()
    assert result.sampled.sum() == 0
    assert (
        json.loads((tmp_path / "manifest.json").read_text())[
            "network_requests_this_run"
        ]
        == 0
    )
