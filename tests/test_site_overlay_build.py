"""Small build fakes: listed slugs and register provenance need no database."""

import json
from types import SimpleNamespace

import pandas as pd

from prometheus.site import registers
from scripts import build_site


def test_players_writes_listed_slug_index(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site.site_config, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(build_site, "PlayerTables", lambda *a: None)
    monkeypatch.setattr(build_site, "get_player_history", lambda *a: None)
    monkeypatch.setattr(build_site, "get_player_elos", lambda *a: (None, None))
    listed = pd.DataFrame({"playerid": ["p1", "p2"], "slug": ["one", "one-team"]})
    monkeypatch.setattr(
        build_site, "player_pages_and_rows", lambda *a: ([], {}, listed)
    )
    monkeypatch.setattr(build_site, "render_rankings_page", lambda *a: None)
    monkeypatch.setattr(build_site.aura, "get_aura", lambda **kw: None)
    monkeypatch.setattr(build_site.aura, "season_aura", lambda *a: None)
    monkeypatch.setattr(
        build_site,
        "aura_rows_and_seasons",
        lambda *a: ([{"aura": 1, "league": "LCK", "year": 2026}], {}),
    )
    build_site.players(["LCK"])
    assert json.loads((tmp_path / "player-slugs.json").read_text()) == {
        "p1": "one",
        "p2": "one-team",
    }


def test_rating_register_configs_include_build_timestamp(monkeypatch):
    captured = []
    template = SimpleNamespace(render=lambda **kw: captured.append(kw) or "")
    monkeypatch.setattr(registers.env, "get_template", lambda *a: template)
    monkeypatch.setattr(registers, "write", lambda *a: None)
    monkeypatch.setitem(
        registers.env.globals, "elo_data_through", "2026-10-18T12:30:00"
    )
    for metric, value, entity in [
        ("game_length_elo", "elo", "team"),
        ("player_elo", "elo", "player"),
        ("forge", "forge", "team"),
    ]:
        registers.render_rankings_page(
            {"key": metric}, [], {"valueKey": value, "entity": entity}, {}
        )
        assert captured[-1]["config"]["dataThrough"] == "2026-10-18T12:30:00"
