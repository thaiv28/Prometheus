"""Synthetic gol.gg HTML: side attribution, validation and causal checkpoints."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "research"))
import pilot_gol as gol


def row(clock, side, icon, target="", identity=1):
    return f'<tr onmouseover="ShowPoint({identity})"><td>{clock}</td><td><img src="{side}side-icon.png"></td><td>Player</td><td><img src="champions_icon/Nashor.png"></td><td><img src="{icon}"></td><td></td><td>{target}</td></tr>'


def html(rows=None, blue_towers=1):
    if rows is None:
        rows = [
            row("9:59", "blue", "tower-icon.png", "T1 TOP", 1),
            row("10:00", "red", "fire-dragon.png", identity=2),
            row("20:01", "red", "nashor-icon.png", identity=3),
            row("25:01", "red", "elder-dragon.png", identity=4),
        ]
    body = "<title>Red Team vs Blue Team game 2 Timeline</title><h1>Red Team vs Blue Team</h1><h1>30:01</h1><div>2024-01-01</div>"
    for side, towers, dragons, barons, won in [
        ("blue", blue_towers, 0, 0, "LOSS"),
        ("red", 0, 2, 1, "WIN"),
    ]:
        body += f'<div><div><div class="{side}-line-header"><a>{side.title()} Team</a> - {won}</div></div>'
        for label, n in [("Towers", towers), ("Dragons", dragons), ("Nashor", barons)]:
            body += f'<span class="score-box"><img alt="{label}" src="summary.png">{n}</span>'
        body += "</div>"
    body += (
        '<table class="timeline"><tr><th>Time</th></tr>' + "".join(rows) + "</table>"
    )
    return body


def test_taking_side_comes_from_icon_not_title_or_target_and_elder_is_separate():
    info, events, checks = gol.parse_timeline(html(), 99)
    assert info["blue_team"] == "Blue Team"  # Title starts with Red Team.
    assert info["timeline_valid"]
    assert all(c["matches"] for c in checks)
    assert events[0]["kind"] == "tower"  # Champion icon ignored; T1 is a tower tier.
    assert events[0]["side"] == "blue"
    assert events[1]["detail"] == "infernal"
    assert events[3]["kind"] == "elder"


def test_checkpoints_never_include_later_events_and_flag_exact_boundaries():
    info, events, _ = gol.parse_timeline(html(), 99)
    checkpoints = gol.checkpoint_rows(info, events, {})
    ten, fifteen, twenty = checkpoints
    assert ten["blue_tower"] == 1
    assert ten["red_dragon"] == 0
    assert ten["objective_boundary_events"] == 1
    assert fifteen["red_dragon"] == 1
    assert fifteen["red_baron"] == twenty["red_baron"] == 0
    info["gamelength"] = 1200
    assert len(gol.checkpoint_rows(info, events, {})) == 2


def test_invalid_totals_unknown_icons_and_missing_timeline_are_not_zero_features():
    info, events, _ = gol.parse_timeline(html(blue_towers=2), 99)
    assert not info["timeline_valid"]
    assert gol.checkpoint_rows(info, events, {}) == []
    info, events, _ = gol.parse_timeline(
        html().replace("fire-dragon.png", "new-dragon.png"), 99
    )
    assert info["unknown_events"] == 1
    assert not info["timeline_valid"]
    with pytest.raises(ValueError, match="No event timeline"):
        gol.parse_timeline(html().split("<table")[0], 99)
    with pytest.raises(ValueError, match="Unavailable"):
        gol.parse_timeline("<title>Games of Legends</title><h1>Page not found</h1>", 99)


def test_duplicate_ids_bad_clocks_post_end_and_unordered_rows_are_rejected():
    for rows in [
        [
            row("1:00", "blue", "tower-icon.png", identity=1),
            row("2:00", "blue", "tower-icon.png", identity=1),
        ],
        [row("1:99", "blue", "tower-icon.png")],
        [row("31:00", "blue", "tower-icon.png")],
        [
            row("2:00", "blue", "tower-icon.png", identity=1),
            row("1:00", "blue", "tower-icon.png", identity=2),
        ],
    ]:
        with pytest.raises(ValueError):
            gol.parse_timeline(html(rows), 99)


def graph(labels=("10", "15", "20", "20")):
    series = []
    for i in range(10):
        role = ("TOP", "JGL", "MID", "BOT", "SPT")[i % 5]
        color = "1,2,3,1" if i < 5 else "3,2,1,1"
        series.append(
            f"{{label:'{role}',data:[100,200,300,400,],borderColor:'rgba({color})'}}"
        )
    return (
        "var golddatas = {labels:["
        + ",".join(repr(x) for x in labels)
        + "],datasets:["
        + ",".join(series)
        + "]\n};"
    )


def test_gold_parser_checks_side_and_role_order_and_skips_duplicate_final_minute():
    values, status = gol.parse_gold(graph())
    assert status == "ok"
    assert values[10] == {"blue_gold": 500, "red_gold": 500}
    assert 20 not in values
    assert (
        gol.parse_gold(graph().replace("label:'TOP'", "label:'BOT'", 1))[1]
        == "unexpected_role_order"
    )
    assert (
        gol.parse_gold(graph().replace("rgba(1,2,3,1)", "rgba(3,2,1,1)", 1))[1]
        == "unexpected_side_colors"
    )
    assert gol.parse_gold('<script>fetch("gold")</script>') == (
        {},
        "missing_gold_graph",
    )


def test_matching_requires_rosters_and_rejects_ambiguous_candidates(monkeypatch):
    info = {
        "date": "2024-01-01",
        "gamelength": 1800,
        "blue_won": 1,
        "red_won": 0,
        "blue_team": "FearX",
        "red_team": "T1",
    }
    matches = pd.DataFrame(
        {
            "gameid": ["a", "a"],
            "date": pd.to_datetime(["2024-01-01"] * 2, utc=True),
            "teamname": ["BNK FEARX", "T1"],
            "side": ["Blue", "Red"],
            "gamelength": [1800] * 2,
            "result": [1, 0],
        }
    )
    players = {
        side: [{"player": f"{side}{i}", "champion": "X"} for i in range(5)]
        for side in ("blue", "red")
    }
    rows = pd.DataFrame(
        {
            "side": ["Blue"] * 5 + ["Red"] * 5,
            "playername": [f"{s}{i}" for s in ("blue", "red") for i in range(5)],
        }
    )
    monkeypatch.setattr(gol.pd, "read_sql", lambda *a, **k: rows)
    monkeypatch.setattr(gol, "get_engine", lambda: None)
    assert gol.match_oe(info, players, matches)[0] == "a"
    duplicate = matches.copy()
    duplicate["gameid"] = "b"
    assert gol.match_oe(info, players, pd.concat([matches, duplicate])) == (
        None,
        "ambiguous",
    )
    players["blue"][0]["player"] = "different"
    assert gol.match_oe(info, players, matches) == (None, "unmatched")


def test_offline_cache_does_not_make_network_requests_and_robots_are_checked(
    tmp_path, monkeypatch
):
    (tmp_path / "robots.txt").write_text("User-agent: *\nDisallow: /raw/\n")
    (tmp_path / "sample.html").write_text("cached")
    cache = gol.Cache(tmp_path)
    monkeypatch.setattr(
        gol.urllib.request,
        "urlopen",
        lambda *a, **k: pytest.fail("Unexpected network access"),
    )
    assert cache.read("sample.html", "https://gol.gg/game/example") == "cached"
    with pytest.raises(FileNotFoundError):
        cache.read("missing.html", "https://gol.gg/game/example")
    cache.fetch = True
    with pytest.raises(PermissionError):
        cache.read("blocked.html", "https://gol.gg/raw/example")
