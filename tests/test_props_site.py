from prometheus.site import config as site_config
from prometheus.site import props as site_props


def _view():
    player = {
        "role": "Jungle",
        "name": "Yike",
        "slug": "yike",
        "median": 8,
        "p10": 4,
        "p90": 14,
        "recent": 8.4,
    }
    lines = {
        "underdog": {
            "line": "12.5",
            "over": 16,
            "side": "under",
            "p_side": 84,
            "break_even": 58,
            "clears": True,
            "one_sided": False,
            "app_over": 48,
        }
    }
    stats = [
        {
            "key": key,
            "label": label,
            "n_lines": 1 if key == "kills" else 0,
            "teams": [
                {
                    "name": "Karmine Corp",
                    "slug": None,
                    "players": [{**player, "lines": lines if key == "kills" else {}}],
                }
            ],
        }
        for key, label in site_props.STATS
    ]
    match = {
        "id": "m1",
        "start": "2026-10-15T18:00Z",
        "day": "Thursday 15 October",
        "time": "18:00",
        "league": "Worlds",
        "event": "Worlds 2026 Play-In",
        "best_of": 5,
        "maps": 3,
        "team1": "Cloud9",
        "team2": "Karmine Corp",
        "slug1": "cloud9",
        "slug2": None,
        "pct1": 31,
        "stats": stats,
        "n_lines": 1,
    }
    return {
        "matches": [match],
        "lines_total": 1,
        "lines_since": "2026-10-12",
        "lines_read": "2026-10-12T22:23Z",
        "scorecard": site_props.scorecard_rows(__import__("pandas").DataFrame()),
        "settled": 0,
        "apps": [{"key": k, "label": label} for k, label in site_props.APPS],
        "stats": [{"key": k, "label": label} for k, label in site_props.STATS],
        "break_even": 58,
    }


def test_render_props_page(tmp_path, monkeypatch):
    monkeypatch.setattr(site_config, "OUTPUT_DIR", str(tmp_path))
    site_props.render_props(_view())
    html = (tmp_path / "props.html").read_text()
    assert "Cloud9" in html and 'href="teams/cloud9.html"' in html
    assert 'href="players/yike.html"' in html
    assert "pp-line--clears" in html and ">12.5<" in html
    assert "Underdog 48" in html
    assert "Jungle" not in html and "pp-role" not in html
    assert 'id="pp-only" checked' in html
    # One register per stat; only the first is shown without JS.
    assert html.count('class="register-figure pp-stat"') == 4
    assert html.count('data-stat="kills">') == 1
    assert "No line has settled yet" in html
    assert 'aria-current="page">Props' in html


def test_default_maps():
    assert [site_props.default_maps(b) for b in (1, 3, 5)] == [1, 2, 3]


def test_matches_without_lines_start_hidden(tmp_path, monkeypatch):
    monkeypatch.setattr(site_config, "OUTPUT_DIR", str(tmp_path))
    view = _view()
    bare = {**view["matches"][0], "id": "m2", "n_lines": 0}
    bare["stats"] = [{**s, "n_lines": 0} for s in bare["stats"]]
    view["matches"].append(bare)
    site_props.render_props(view)
    html = (tmp_path / "props.html").read_text()
    assert '<article class="pp-match" data-match="m1"' in html
    m2 = html[html.index('data-match="m2"') :].split(">", 1)[0]
    assert m2.endswith("hidden")
