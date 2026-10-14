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


def _settled():
    import pandas as pd

    base = {
        "match_id": "m1",
        "start": "2026-10-15T18:00Z",
        "team": "Karmine Corp",
        "opp": "Cloud9",
        "player": "Yike",
        "playerid": "p1",
        "stat": "kills",
        "maps": "1-3",
        "actual": 7,
    }
    return pd.DataFrame(
        [
            {
                **base,
                "source": "underdog",
                "line": 12.5,
                "side": "under",
                "p_side": 0.84,
                "result": "under",
            },
            {
                **base,
                "source": "prizepicks",
                "line": 6.5,
                "side": "under",
                "p_side": 0.55,
                "result": "over",
            },
            {
                **base,
                "source": "pick6",
                "line": 7.0,
                "side": "over",
                "p_side": 0.5,
                "result": "push",
            },
        ]
    )


def test_result_rows_months_and_pages(tmp_path, monkeypatch):
    rows = site_props.result_rows(_settled(), {"p1": "yike"})
    assert len(rows) == 1
    cells = rows[0]["cells"]
    assert (
        cells["underdog"]["call"],
        cells["prizepicks"]["call"],
        cells["pick6"]["call"],
    ) == ("right", "missed", "push")
    assert (
        rows[0]["actual"] == "7"
        and rows[0]["label"] == "15 Oct · Karmine Corp v Cloud9"
    )
    months = site_props.result_months(rows)
    assert [m["key"] for m in months] == ["2026-10"] and months[0]["count"] == 1

    monkeypatch.setattr(site_config, "OUTPUT_DIR", str(tmp_path))
    view = _view()
    view["recent"] = site_props.by_match(rows)
    view["recent_days"] = 3
    view["months"] = months
    site_props.render_props(view)
    site_props.render_prop_results(view)
    page = (tmp_path / "props.html").read_text()
    assert 'href="props-results/2026-10.html"' in page and "pp-res--right" in page
    month = (tmp_path / "props-results" / "2026-10.html").read_text()
    assert (
        'href="../players/yike.html"' in month
        and "pp-res--missed" in month
        and ">push<" in month
    )


def test_lines_payload_keeps_the_standard_line_first():
    import pandas as pd

    common = {
        "match_id": "m1",
        "playerid": "p1",
        "stat": "kills",
        "source": "prizepicks",
        "p_over": 0.3,
        "p_under": 0.7,
        "over_prob": None,
    }
    priced = pd.DataFrame(
        [
            {
                **common,
                "line": 13.5,
                "over_mult": None,
                "under_mult": None,
                "side": None,
                "p_side": None,
                "edge": None,
            },
            {
                **common,
                "line": 9.5,
                "over_mult": 1.0,
                "under_mult": 1.0,
                "side": "under",
                "p_side": 0.7,
                "edge": 0.12,
            },
        ]
    )
    reads = pd.Series(
        pd.to_datetime(["2026-10-14T09:00Z", "2026-10-14T10:17Z"], utc=True)
    )
    payload = site_props.lines_payload(priced, reads)
    assert payload["at"] == "2026-10-14T10:17Z"
    assert len(payload["lines"]) == 1
    cell = payload["lines"][0]
    assert (cell["line"], cell["side"], cell["label"], cell["clears"]) == (
        "9.5",
        "under",
        "PrizePicks",
        True,
    )
