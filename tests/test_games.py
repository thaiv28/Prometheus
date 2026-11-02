"""Offline game-feed grouping, fault isolation and shared-register rendering."""

import copy
import datetime
import json
from pathlib import Path

import pytest

from prometheus.site import config, games
from prometheus.site.render import env

NOW = datetime.datetime(2026, 10, 29, 18, tzinfo=datetime.UTC)
FIXTURE = Path(__file__).parent / "fixtures" / "game_feed.json"


@pytest.fixture
def feed():
    return json.loads(FIXTURE.read_text())


def rows(days):
    return [row for day in days for row in day["rows"]]


def test_game_view(feed):
    view = games.game_view(feed, NOW)
    assert [r["id"] for r in rows(view["upcoming"])] == ["up1", "up2"]
    assert view["upcoming_count"] == 2
    assert [r["id"] for r in rows(view["live"])] == ["live1"]
    live = rows(view["live"])[0]
    assert live["score"] == "1–0" and live["call"] is None
    assert [r["id"] for r in rows(view["past"])] == ["final-new"]
    assert [m["key"] for m in view["months"]] == ["2026-10", "2026-09"]
    old = rows(view["months"][1]["days"])[0]
    assert old["reconstructed"] and old["call"] == "right"
    final = rows(view["past"])[0]
    assert final["winner"] is None and final["call"] is None
    assert final["score"] == "1–1"
    first, unknown = rows(view["upcoming"])
    assert first["pct1"] + first["pct2"] == 100
    assert (first["mkt1"], first["mkt2"]) == (62, 38)
    assert first["mkt_url"] == "https://kalshi.com/test"
    assert first["mkt_at"] == "29 Oct 18:00 UTC"
    assert unknown["best_of"] == 1 and not unknown["bo_known"]
    assert view["leagues"] == ["VCT", "Other"] and view["major_set"] == ["VCT"]
    assert view["filter_noun"] == "tiers" and view["all_label"] == "All tiers"
    assert view["recent_days"] == config.RECENT_RESULT_DAYS
    for key in ("source", "model", "data_through", "name", "game"):
        assert view[key] == feed[key]


@pytest.mark.parametrize(
    "probability,winner,call",
    [(0.5, 1, "even"), (0.4, 1, "missed"), (0.4, 2, "right"), (0.6, None, None)],
)
def test_game_call(feed, probability, winner, call):
    entry = {**feed["matches"][0], "p_series": probability, "winner": winner}
    assert games.game_row(entry, feed["model"])["call"] == call


def test_render_game_pages(feed, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    original = copy.deepcopy(config.NAV)
    monkeypatch.setitem(env.globals, "nav", [*config.NAV, games.nav_group([feed])])
    games.render_game_pages([feed], NOW)
    assert config.NAV == original
    folder = tmp_path / "other"
    assert json.loads((folder / "valorant.json").read_text()) == feed
    html = (folder / "valorant.html").read_text()
    assert (
        "Other games" in html
        and 'href="../other/valorant.html" aria-current="page"' in html
    )
    assert 'data-select="VCT"' in html and 'data-majors="Majors"' in html
    assert 'picker-label">tiers' in html and "All tiers</button>" in html
    assert "CC BY-SA 3.0" in html and 'href="https://liquipedia.net/valorant/"' in html
    assert 'id="live"' in html and 'id="upcoming"' in html and 'id="past"' in html
    assert 'class="fx-bo">—</td>' in html
    assert 'colspan="10"' in html and 'colspan="11"' not in html
    assert ">Blend<" not in html and ">Tier</th>" in html
    assert "Nova &amp; Co" in html and ">1–0</a>" in html
    assert 'href="valorant/2026-09.html"' in html
    assert "../js/predictions.js?" in html and "live_overview.js" not in html
    for month, relation, other in [
        ("2026-10", "next", "2026-09"),
        ("2026-09", "prev", "2026-10"),
    ]:
        page = (folder / "valorant" / f"{month}.html").read_text()
        assert f'href="{other}.html" rel="{relation}"' in page
        assert 'href="../valorant.html"' in page
        assert "../../js/predictions.js?" in page
        assert "CC BY-SA 3.0" in page and ">Tier</th>" in page
    assert (
        "Rebuilt after the match: note 3"
        in (folder / "valorant" / "2026-09.html").read_text()
    )


def test_empty_feed(feed, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    feed["matches"] = []
    games.render_game_pages([feed], NOW)
    html = (tmp_path / "other/valorant.html").read_text()
    assert "No rated matches this week." in html and 'id="live"' not in html
    assert not (tmp_path / "other/valorant").exists()
    games.render_game_pages([], NOW)


def test_load_feeds(feed, tmp_path, caplog):
    assert games.load_feeds(tmp_path / "missing") == []
    assert "missing folder" in caplog.text
    (tmp_path / "valid.json").write_text(json.dumps(feed))
    second = {**feed, "game": "aaa", "name": "AAA"}
    (tmp_path / "second.json").write_text(json.dumps(second))
    for name, contents in {
        "bad": "{",
        "version": json.dumps({**feed, "version": 2}),
        "path": json.dumps({**feed, "game": "../bad"}),
        "missing-key": "{}",
        "bad-row": json.dumps({**feed, "matches": [{"status": "oops"}]}),
        "not-object": "[]",
    }.items():
        (tmp_path / f"{name}.json").write_text(contents)
    assert [f["name"] for f in games.load_feeds(tmp_path)] == ["AAA", "Valorant"]
    assert caplog.text.count("skipped") == 6


def test_dota_feed_pages(feed, tmp_path, monkeypatch):
    feed.update(game="dota2", name="Dota 2", model="Synthetic Dota model")
    feed["source"]["url"] = "https://liquipedia.net/dota2/"
    source = tmp_path / "feeds"
    source.mkdir()
    (source / "dota2.json").write_text(json.dumps(feed))
    loaded = games.load_feeds(source)
    assert loaded == [feed]
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setitem(env.globals, "nav", [*config.NAV, games.nav_group(loaded)])
    view = games.game_view(feed, NOW)
    assert view["upcoming_count"] == 2
    assert len(rows(view["live"])) == 1 and len(view["months"]) == 2
    games.render_game_pages(loaded, NOW)
    folder = tmp_path / "other"
    assert json.loads((folder / "dota2.json").read_text()) == feed
    html = (folder / "dota2.html").read_text()
    assert "Dota 2" in html and 'href="../other/dota2.html"' in html
    assert 'id="live"' in html and 'id="upcoming"' in html and 'id="past"' in html
    assert (folder / "dota2" / "2026-09.html").exists()
