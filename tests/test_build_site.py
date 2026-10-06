"""Unit tests for the site builder's pure parts: slugs, player listing, rosters,
templates and the search index. No database: frames are built by hand."""

import datetime
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from prometheus.schedule import series_probability

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location("build_site", ROOT / "scripts" / "build_site.py")
build_site = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_site)


def test_slugify_matches_the_shared_fixture():
    # tests/js/names.test.mjs checks the JS slugify against the same file.
    for case in json.loads((ROOT / "tests" / "js" / "slugs.json").read_text()):
        assert build_site._slugify(case["name"]) == case["slug"]


def test_player_slugs_add_the_team_then_a_number_for_shared_names():
    players = pd.DataFrame(
        {
            "playerid": ["p1", "p2", "p3", "p4"],
            "playername": ["Faker", "Viper", "Viper", "Viper"],
            "teamname": ["T1", "Bilibili Gaming", "Young Miracles", "Young Miracles"],
        }
    )
    assert build_site._player_slugs(players).tolist() == [
        "faker",
        "viper-bilibili-gaming",
        "viper-young-miracles",
        "viper-young-miracles-2",
    ]


def _player_frames():
    """Three players: a former LCK starter (2018), a current amateur, and an old amateur."""
    rows = []

    def games(pid, name, team, teamid, league, dates, role="mid", start=1500.0):
        for i, d in enumerate(dates):
            rows.append(
                {"gameid": f"{pid}-{d}", "playerid": pid, "playername": name, "position": role,
                 "teamid": teamid, "teamname": team, "league": league, "home_league": league,
                 "date": d, "year": int(d[:4]), "elo": start + i, "league_offset": 0.0}
            )

    may = [f"2018-05-{d:02d}" for d in range(1, 13)]
    games("lck", "Veteran", "Old Team", "t-old", "LCK", may)
    games("lck", "Vet", "New Team", "t-new", "LCK", ["2018-08-01", "2018-08-02"], start=1600)
    games("now", "Rookie", "Academy", "t-aca", "LCKC", ["2026-09-01", "2026-09-02"], role="sup")
    games("old", "Gone", "Minor", "t-min", "LCKC", ["2016-01-01"])
    history = pd.DataFrame(rows)
    latest = history.groupby("playerid").tail(1).assign(
        latest_date=lambda d: d["date"], games=lambda d: d["playerid"].map(history["playerid"].value_counts())
    )[["playerid", "playername", "position", "teamname", "teamid", "league", "elo", "latest_date", "games"]]
    seasons = (
        history.groupby(["playerid", "year"]).tail(1)
        .assign(latest_date=lambda d: d["date"])
        .merge(history.groupby(["playerid", "year"]).size().rename("games").reset_index(), on=["playerid", "year"])
    )[["playerid", "year", "playername", "position", "teamname", "teamid", "league", "elo", "latest_date", "games"]]
    return history, latest.reset_index(drop=True), seasons


def test_player_listing_rows_and_pages():
    history, latest, seasons = _player_frames()
    rows, pages, listed = build_site.player_pages_and_rows(history, latest, seasons)

    # Listed: ever in a major league, or active within two years. Not the 2016 amateur.
    assert set(listed["playerid"]) == {"lck", "now"}
    now = {r["playername"]: r for r in rows if r["now"]}
    assert set(now) == {"Vet", "Rookie"}
    assert now["Rookie"]["active"] and not now["Vet"]["active"]
    # Season rows: major-league player-seasons with 10+ games only.
    assert [(r["playername"], r["year"]) for r in rows if not r["now"]] == [("Vet", 2018)]

    vet = pages["vet"]
    assert [s["teamname"] for s in vet["stints"]] == ["New Team", "Old Team"]  # newest first
    assert [s["games"] for s in vet["stints"]] == [2, 12]
    assert vet["aliases"] == ["Veteran"]
    assert vet["elo_summary"]["games"] == 14
    assert vet["home_league"] == "LCK"


def _roster_history():
    rows = []
    roles = ["top", "jng", "mid", "bot", "sup"]
    for g, date in enumerate(["2025-03-01", "2025-03-02", "2025-03-03", "2026-02-01"]):
        lineup = [f"{r}1" for r in roles]
        if g == 1:
            lineup[1] = "jng2"  # a sub in jungle for one game
        if g == 3:
            lineup[2] = "mid9"  # new mid in 2026
        for role, pid in zip(roles, lineup):
            rows.append({"gameid": f"g{g}", "date": date, "year": int(date[:4]), "teamname": "T1",
                         "position": role, "playerid": pid, "playername": pid.upper()})
    return pd.DataFrame(rows)


def test_team_rosters_last_lineup_and_seasons():
    rosters = build_site.team_rosters(_roster_history(), {"mid9": "mid9-page"}, {"mid9": 1712.4})
    t1 = rosters["T1"]
    assert t1["last"]["date"] == "2026-02-01"
    assert t1["last"]["active"]
    assert [p["role"] for p in t1["last"]["players"]] == ["top", "jng", "mid", "bot", "sup"]
    mid = t1["last"]["players"][2]
    assert (mid["name"], mid["slug"], mid["elo"]) == ("MID9", "mid9-page", 1712)
    assert t1["last"]["players"][0]["slug"] is None  # no page, no link

    assert [s["year"] for s in t1["seasons"]] == [2026, 2025]
    jungle_2025 = t1["seasons"][1]["roles"][1]
    assert jungle_2025["role"] == "jng"
    assert [(p["name"], p["games"]) for p in jungle_2025["players"]] == [("JNG1", 2), ("JNG2", 1)]
    assert jungle_2025["more"] == 0


def test_team_rosters_cap_extra_players():
    rows = [{"gameid": f"g{i}", "date": f"2025-01-{i + 1:02d}", "year": 2025, "teamname": "X",
             "position": "top", "playerid": f"p{i}", "playername": f"P{i}"} for i in range(6)]
    rosters = build_site.team_rosters(pd.DataFrame(rows), {}, {})
    top = rosters["X"]["seasons"][0]["roles"][0]
    assert len(top["players"]) == 1 + build_site.ROSTER_EXTRAS
    assert top["more"] == 6 - 1 - build_site.ROSTER_EXTRAS


def test_compact_series_rounds_to_pairs():
    compact = build_site.env.filters["compact_series"]
    assert compact([{"date": "2026-01-01", "elo": 1512.6}]) == [["2026-01-01", 1513]]


def test_player_page_renders_stints_and_links():
    history, latest, seasons = _player_frames()
    _, pages, _ = build_site.player_pages_and_rows(history, latest, seasons)
    html = build_site.env.get_template("player.html.j2").render(
        page_key="player", root_path="../", last_update="today", **pages["vet"]
    )
    assert "<h1>Vet</h1>" in html
    assert 'href="../teams/new-team.html"' in html
    assert "Also played as Veteran." in html
    assert 'id="elo-series">[["2018-05-01", 1500]' in html


def _aura_seasons():
    return pd.DataFrame(
        {
            "playerid": ["p1", "p1", "p1", "p2"],
            "playername": ["Mid", "Mid", "Mid", "Nobody"],
            "year": [2024, 2025, 2025, 2025],
            "position": ["mid", "mid", "top", "mid"],
            "teamname": ["Old Team", "New Team", "New Team", "X"],
            "league": ["LCK", "LCK", "LCK", "LEC"],
            "games": [40, 60, 3, 50],
            "aura": [4.123, 6.6, -0.8, 1.0],
            "qualified": [True, True, False, True],
            "role_z": [1.234, 2.0, np.nan, 0.1],
            "role_rank": [3.0, 1.0, np.nan, 5.0],
            "role_count": [30.0, 31.0, np.nan, 31.0],
        }
    )


def test_aura_rows_only_list_qualified_seasons_of_listed_players():
    rows, by_player = build_site.aura_rows_and_seasons(_aura_seasons(), pd.Series({"p1": "mid"}))
    assert [(r["slug"], r["year"], r["aura"]) for r in rows] == [("mid", 2024, 4.12), ("mid", 2025, 6.6)]
    assert list(by_player) == ["mid"]  # p2 has no page
    seasons = by_player["mid"]
    assert [(s["year"], s["position"]) for s in seasons] == [(2025, "mid"), (2025, "top"), (2024, "mid")]
    assert seasons[1]["role_rank"] is None and seasons[0]["role_rank"] == 1


def test_player_page_renders_aura_by_season():
    history, latest, seasons = _player_frames()
    _, pages, _ = build_site.player_pages_and_rows(history, latest, seasons)
    _, by_player = build_site.aura_rows_and_seasons(_aura_seasons(), pd.Series({"p1": "vet"}))
    html = build_site.env.get_template("player.html.j2").render(
        page_key="player", root_path="../", last_update="today", **pages["vet"], aura_seasons=by_player["vet"]
    )
    assert '<h2 id="aura-heading">AURA by season</h2>' in html
    assert "Best AURA season 2025, +6.6 a game, 1st of 31 major-league mid laners that year." in html
    assert "Unranked" in html and "−0.8" in html
    plain = build_site.env.get_template("player.html.j2").render(
        page_key="player", root_path="../", last_update="today", **pages["vet"]
    )
    assert "AURA by season" not in plain and "Best AURA" not in plain


def test_team_page_renders_rosters_with_player_links():
    roster = build_site.team_rosters(_roster_history(), {"mid9": "mid9-page"}, {"mid9": 1712.4})["T1"]
    series = [{"date": "2026-02-01", "elo": 1600.0}]
    html = build_site.env.get_template("team.html.j2").render(
        page_key="team", root_path="../", last_update="today", teamname="T1", slug="t1",
        series=[], elo_series=series, best=None, current_elo=1600, current_forge=None,
        current_league="LCK", leagues=["LCK"], roster=roster,
        elo_summary={"games": 1, "peak": series[0], "low": series[0], "first": series[0], "last": series[0]},
    )
    assert '<h2 id="roster-heading">Roster</h2>' in html
    assert '<a href="../players/mid9-page.html">MID9</a>' in html
    assert 'data-role="Jungle"' in html
    assert "JNG2</a>" not in html and "JNG2 <span" in html  # no page, so no link


def test_player_index_puts_major_leagues_first(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "OUTPUT_DIR", str(tmp_path))
    listed = pd.DataFrame(
        {
            "playername": ["Amateur", "Pro"],
            "slug": ["amateur", "pro"],
            "position": ["mid", "top"],
            "teamname": ["A", "B"],
            "league": ["LCKC", "LCK"],
            "latest_date": ["2026-09-30", "2026-01-01"],
        }
    )
    build_site.write_player_index(listed)
    index = json.loads((tmp_path / "players.json").read_text())
    assert [p["n"] for p in index] == ["Pro", "Amateur"]
    assert index[0] == {"n": "Pro", "s": "pro", "r": "top", "t": "B", "l": "LCK", "d": "2026-01-01"}


def test_header_menus_list_live_stats_with_their_questions():
    menus = {g["name"]: [l["key"] for l in g["links"]] for g in build_site.NAV}
    assert menus == {"Teams": ["glory", "forge", "game_length_elo"], "Players": ["player_elo", "aura"]}
    assert all(l["question"].endswith("?") for g in build_site.NAV for l in g["links"])
    sunset = {m["key"] for m in build_site.SUNSET}
    assert "form" in sunset and not sunset & {k for keys in menus.values() for k in keys}


def test_header_marks_the_menu_that_leads_to_the_page():
    html = build_site.env.get_template("sunset.html.j2").render(
        page_key="form", root_path="", metrics=build_site.SUNSET, last_update="today"
    )
    assert '<summary data-current>Teams</summary>' in html
    assert '<summary>Players</summary>' in html
    assert 'href="sunset.html"' in html


def _log():
    """A prediction log: one LCK match tomorrow, one Worlds match next week, one
    reconstructed EM result, and one unmatched match."""
    def entry(mid, start, league, p, **extra):
        return {"match_id": mid, "start": start, "team1": f"{mid}-a", "team2": f"{mid}-b (Team)",
                "ours1": "T1", "ours2": None if extra.pop("unmatched", False) else "Gen.G",
                "best_of": 3, "league": league, "home1": "LCK", "home2": "LCK", "event": "Cup", "matched": True,
                "p_game": p, "p_series": schedule_series(p), "method": "forge", **extra}
    return {
        "soon": entry("soon", "2026-10-04T08:00Z", "LCK", 0.6),
        "later": entry("later", "2026-10-12T08:00Z", "Worlds", 0.4),
        "past": entry("past", "2026-09-20T08:00Z", "EM", 0.7, winner=2, score1=1, score2=2, reconstructed=True),
        "nope": {"match_id": "nope", "start": "2026-10-04T09:00Z", "matched": False, "league": "EM"},
    }


def schedule_series(p):
    return series_probability(p, 3)


def test_predictions_view_splits_upcoming_past_and_home():
    now = datetime.datetime(2026, 10, 3, 12, tzinfo=datetime.timezone.utc)
    view = build_site.predictions_view(_log(), {"t1"}, now)
    assert [r["id"] for d in view["upcoming"] for r in d["rows"]] == ["soon", "later"]
    assert [r["id"] for d in view["past"] for r in d["rows"]] == ["past"]
    # Home: major and international matches within four days only.
    assert [r["id"] for d in view["home"] for r in d["rows"]] == ["soon"]
    soon = view["upcoming"][0]["rows"][0]
    assert soon["pct1"] + soon["pct2"] == 100 and soon["fav"] == 1
    assert soon["slug1"] == "t1" and soon["slug2"] is None  # Gen.G has no page here
    assert view["upcoming"][0]["label"] == "Sunday 4 October"
    past = view["past"][0]["rows"][0]
    assert past["call"] == "missed" and past["score"] == "1–2" and past["reconstructed"]
    assert view["scorecard"][1]["series"] == 1 and view["scorecard"][0]["series"] == 0
    assert view["leagues"][:2] == ["LCK", "Worlds"]


def test_fixture_row_names_fall_back_to_leaguepedia_without_disambiguation():
    entry = {**_log()["soon"], "ours2": None}
    row = build_site.fixture_row(entry, set())
    assert row["name2"] == "soon-b" and row["slug1"] is None


def test_fixture_row_and_register_carry_the_market_price():
    entry = {**_log()["soon"], "market": {"p": 0.634, "spread": 0.02, "at": "2026-10-03T02:30Z", "ticker": "K"}}
    row = build_site.fixture_row(entry, set())
    assert (row["mkt1"], row["mkt2"], row["mkt_at"]) == (63, 37, "3 Oct 02:30 UTC")
    html = build_site.env.from_string(
        "{% from '_marks.html.j2' import fixtures %}{{ fixtures(days) }}{{ fixtures(days, results=True) }}"
    ).render(days=[{"day": row["day"], "label": "Sunday 4 October", "rows": [row]}])
    assert html.count('class="fx-mkt" style="--m: 63"') == 2  # the caret on both registers
    assert "63–37" in html and ">Kalshi<" in html and 'colspan="11"' in html
    plain = build_site.fixture_row(_log()["soon"], set())
    assert "mkt1" not in plain


def test_predictions_and_home_render_fixtures(tmp_path, monkeypatch):
    monkeypatch.setattr(build_site, "OUTPUT_DIR", str(tmp_path))
    view = build_site.predictions_view(_log(), {"t1"}, datetime.datetime(2026, 10, 3, 12, tzinfo=datetime.timezone.utc))
    build_site.render_predictions(view, {"matches": 4, "matched": 3, "unmatched": []}, "October 3, 2026")
    html = (tmp_path / "predictions.html").read_text()
    assert 'aria-current="page">Predictions' in html
    assert 'data-start="2026-10-04T08:00Z"' in html and "Sunday 4 October" in html
    assert "Missed" in html and 'href="#note-3"' in html
    assert "3 of 4 scheduled matches" in html
    assert 'data-select="LCK,LPL,LEC,LCS,Worlds' in html
    # The home page's compact table: no method column, no results.
    home = build_site.env.from_string(
        "{% from '_marks.html.j2' import fixtures %}{{ fixtures(days, compact=True) }}"
    ).render(days=view["home"])
    assert "fx-by" not in home and "Result" not in home and 'colspan="10"' in home
