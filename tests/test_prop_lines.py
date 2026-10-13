import json

import pytest

from prometheus import prop_lines


def test_stat_and_maps_reads_each_label():
    assert prop_lines._stat_and_maps("Kills on Maps 1+2+3") == ("kills", "1-3")
    assert prop_lines._stat_and_maps("MAPS 1-2 Kills") == ("kills", "1-2")
    assert prop_lines._stat_and_maps("Creep Score") == ("cs", None)
    assert prop_lines._stat_and_maps("Fantasy Points on Maps 1+2+3") == (
        "fantasy",
        "1-3",
    )


def test_parse_underdog_keeps_lol_rows_with_sides():
    data = {
        "appearances": [
            {"id": "a1", "player_id": "p1", "match_id": 7, "team_id": "home"},
            {"id": "a2", "player_id": "p2", "match_id": 8, "team_id": "x"},
        ],
        "players": [
            {
                "id": "p1",
                "sport_id": "LOL",
                "last_name": "Yike",
                "position_name": "Gamer",
            },
            {"id": "p2", "sport_id": "NBA", "last_name": "Someone"},
        ],
        "games": [
            {
                "id": 7,
                "abbreviated_title": "C9 vs KC",
                "home_team_id": "home",
                "scheduled_at": "2026-10-15T18:00:00Z",
                "full_team_names_title": "Cloud9 vs Karmine Corp",
            }
        ],
        "over_under_lines": [
            {
                "id": "l1",
                "stat_value": "12.5",
                "over_under": {
                    "appearance_stat": {
                        "appearance_id": "a1",
                        "display_stat": "Kills on Maps 1+2+3",
                    }
                },
                "options": [
                    {
                        "choice": "higher",
                        "payout_multiplier": "1.05",
                        "odds": {"fantasy": {"probability": "48"}},
                    },
                    {"choice": "lower", "payout_multiplier": "0.91"},
                ],
            },
            {
                "id": "l2",
                "stat_value": "20.5",
                "over_under": {
                    "appearance_stat": {"appearance_id": "a2", "display_stat": "Points"}
                },
                "options": [],
            },
        ],
    }
    rows = prop_lines.parse_underdog(data)
    assert len(rows) == 1
    row = rows[0]
    assert (row["player"], row["team"], row["opponent"]) == ("Yike", "KC", "C9")
    assert (row["stat"], row["maps"], row["line"]) == ("kills", "1-3", 12.5)
    assert (row["over_mult"], row["under_mult"], row["over_prob"]) == (
        1.05,
        0.91,
        pytest.approx(0.48),
    )
    assert set(prop_lines.ROW_FIELDS) <= set(row)


def _turbo_page(root):
    """Encode `root` the way React Router's turbo stream does (flat, by index)."""
    data = []

    def put(value):
        if isinstance(value, dict):
            i = len(data)
            data.append(None)
            data[i] = {f"_{put(k)}": put(v) for k, v in value.items()}
            return i
        if isinstance(value, list):
            i = len(data)
            data.append(None)
            data[i] = [put(v) for v in value]
            return i
        data.append(value)
        return len(data) - 1

    put(root)
    payload = json.dumps(json.dumps(data))
    return f"<script>window.__reactRouterContext.streamController.enqueue({payload});</script>"


def test_parse_pick6_reads_cards_from_the_turbo_stream():
    cards = {
        "pickCardByPickableId": {
            "1": {
                "entities": [{"dkId": 76356, "compIds": [42]}],
                "activePickableMarkets": [
                    {
                        "pickableMarketId": 99,
                        "pickSixMarketId": 453,
                        "targetValue": 7.5,
                        "activeSelections": [
                            {"statLinePropositionId": 1, "standingsMultiplier": 1.0},
                            {"statLinePropositionId": 2, "standingsMultiplier": 0.9},
                        ],
                    }
                ],
            }
        },
        "entityInfoByDkId": {"76356": {"name": "Cube"}},
        "displayTeamById": {"1": {"name": "FLY"}, "2": {"name": "WE"}},
        "competitionById": {
            "42": {
                "startTime": "2026-10-13T06:00:00+00:00",
                "name": "WE @ FLY",
                "totalCompTime": "Maps 1-3",
                "homeTeamId": 1,
                "awayTeamId": 2,
                "leagueAbbr": "Riot",
                "entityCompByDkId": {"76356": {"teamId": 2, "position": "TOP"}},
            }
        },
        "pickSixMarketById": {"453": {"name": "Kills"}},
    }
    html = _turbo_page(
        {"loaderData": {"routes/_homeShared": {"pickCardsResponse": cards}}}
    )
    rows = prop_lines.parse_pick6(html)
    assert len(rows) == 1
    row = rows[0]
    assert (row["player"], row["team"], row["opponent"], row["position"]) == (
        "Cube",
        "WE",
        "FLY",
        "TOP",
    )
    assert (row["stat"], row["maps"], row["line"]) == ("kills", "1-3", 7.5)
    assert (row["over_mult"], row["under_mult"]) == (1.0, 0.9)


def test_parse_pick6_without_a_stream_is_empty():
    assert prop_lines.parse_pick6("<html></html>") == []


def test_collect_keeps_going_when_a_source_fails(tmp_path, monkeypatch):
    def fake_fetch(source, timeout=30):
        if source == "pick6":
            raise OSError("blocked")
        return [{"source": source, "player": "Faker"}]

    monkeypatch.setattr(prop_lines, "fetch", fake_fetch)
    log = tmp_path / "lines.jsonl"
    result = prop_lines.collect(log, ["underdog", "pick6", "prizepicks"])
    assert result["underdog"] == "read 1, logged 1"
    assert result["pick6"].startswith("error")
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert [r["source"] for r in rows] == ["underdog", "prizepicks"]
    assert all("read_at" in r for r in rows)


def test_collect_logs_only_changed_lines(tmp_path, monkeypatch):
    lines = [
        {"source": "underdog", "line_id": "a", "line": 7.5},
        {"source": "underdog", "line_id": "b", "line": 3.5},
    ]
    monkeypatch.setattr(
        prop_lines, "fetch", lambda source, timeout=30: [dict(r) for r in lines]
    )
    log = tmp_path / "lines.jsonl"
    assert prop_lines.collect(log, ["underdog"])["underdog"] == "read 2, logged 2"
    assert prop_lines.collect(log, ["underdog"])["underdog"] == "read 2, logged 0"
    lines[1]["line"] = 4.5
    assert prop_lines.collect(log, ["underdog"])["underdog"] == "read 2, logged 1"
    assert len(log.read_text().splitlines()) == 3


def test_fetch_pick6_reads_every_group(monkeypatch):
    def card(line_id, name):
        return {
            "pickCardByPickableId": {
                line_id: {
                    "entities": [{"dkId": 1, "compIds": [9]}],
                    "activePickableMarkets": [
                        {
                            "pickableMarketId": line_id,
                            "pickSixMarketId": 453,
                            "targetValue": 7.5,
                            "activeSelections": [],
                        }
                    ],
                }
            },
            "entityInfoByDkId": {"1": {"name": name}},
            "competitionById": {
                "9": {"totalCompTime": "Maps 1-3", "entityCompByDkId": {}}
            },
            "pickSixMarketById": {"453": {"name": "Kills"}},
        }

    home = {
        "pickCardsResponse": card("a", "Cube"),
        "pickGroups": [{"pickGroupId": 1}, {"pickGroupId": 2}],
        "selectedPickGroup": {"pickGroupId": 1},
        "allCompetitions": [{"competitionId": 9}],
    }
    pages = {
        prop_lines.PICK6_URL: _turbo_page({"loaderData": {"routes/_homeShared": home}}),
        f"{prop_lines.PICK6_EVENT_URL}/2/9": _turbo_page(
            {
                "loaderData": {
                    "routes/_homeShared": {"pickCardsResponse": card("b", "Karis")}
                }
            }
        ),
    }
    monkeypatch.setattr(
        prop_lines, "_get", lambda url, extra=None, timeout=30: pages[url]
    )
    rows = prop_lines.fetch_pick6(sleep=lambda s: None)
    assert sorted(r["player"] for r in rows) == ["Cube", "Karis"]


def test_parse_prizepicks_drops_combos_and_marks_one_sided():
    data = {
        "included": [
            {
                "type": "new_player",
                "id": "1",
                "attributes": {"name": "Faker", "team": "T1"},
            },
            {
                "type": "new_player",
                "id": "2",
                "attributes": {"name": "Faker + Oner", "team": "T1"},
            },
        ],
        "data": [
            {
                "id": "x",
                "attributes": {
                    "stat_type": "MAPS 1-3 Kills",
                    "line_score": 9.5,
                    "odds_type": "standard",
                },
                "relationships": {"new_player": {"data": {"id": "1"}}},
            },
            {
                "id": "y",
                "attributes": {
                    "stat_type": "MAPS 1-3 Kills",
                    "line_score": 12.5,
                    "odds_type": "demon",
                },
                "relationships": {"new_player": {"data": {"id": "1"}}},
            },
            {
                "id": "z",
                "attributes": {
                    "stat_type": "MAPS 1-3 Kills",
                    "line_score": 20,
                    "odds_type": "standard",
                },
                "relationships": {"new_player": {"data": {"id": "2"}}},
            },
        ],
    }
    rows = {r["line_id"]: r for r in prop_lines.parse_prizepicks(data)}
    assert set(rows) == {"x", "y"}
    assert (rows["x"]["over_mult"], rows["x"]["under_mult"]) == (1.0, 1.0)
    assert (rows["y"]["over_mult"], rows["y"]["under_mult"]) == (None, None)
