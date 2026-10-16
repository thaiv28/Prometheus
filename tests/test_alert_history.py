import copy
import datetime

import pytest

from prometheus import alerts, markets, schedule
from prometheus.site import alert_history

NOW = datetime.datetime(2026, 10, 15, 12, tzinfo=datetime.UTC)


def entry(mid="m", key="alert", winner=1):
    return {
        "match_id": mid,
        "start": "2026-10-14T09:00Z",
        "team1": "A",
        "team2": "B",
        "ours1": "A",
        "ours2": "B",
        "winner": winner,
        "score1": 3,
        "score2": 1,
        "p_series": 0.9,
        "market": {"p": 0.6},
        key: {
            "side": 1,
            "team": "A",
            "p": 0.55,
            "price": 0.4,
            "edge": 0.15,
            "at": "2026-10-12T10:00Z",
        },
    }


def test_history_keeps_first_terms_and_separate_profit_with_pending_excluded():
    log = {
        "dom": entry("dom"),
        "intl": entry("intl", alerts.INTERNATIONAL_KEY, 2),
        "minor": entry("minor", "paper_alert", None),
    }
    original = copy.deepcopy(log)
    domestic, international, minor = alert_history.history_view(log, NOW)
    assert domestic["rows"][0]["chance"] == 0.55  # current forecast is .9
    assert domestic["rows"][0]["ask"] == 0.4
    assert domestic["rows"][0]["result"] == "Won"
    assert domestic["summary"]["profit"] == pytest.approx(
        1 / 0.4 - 1 - markets.fee(0.4, 1)
    )
    assert international["summary"]["profit"] == pytest.approx(-1 - markets.fee(0.4, 1))
    assert minor["rows"][0]["profit"] is None and minor["summary"]["profit"] == 0
    assert log == original


def test_history_settles_pinned_team_after_order_change_and_keeps_unresolved_pick():
    old = entry()
    swapped = {
        **old,
        "ours1": "B",
        "ours2": "A",
        "team1": "B",
        "team2": "A",
        "winner": 2,
        "score1": 1,
        "score2": 3,
    }
    swapped.update(schedule.carry_records(old, swapped))
    row = alert_history.history_view({"m": swapped}, NOW)[0]["rows"][0]
    assert (row["back"], row["other"], row["result"], row["score"]) == (
        "A",
        "B",
        "Won",
        "3–1",
    )
    swapped["ours2"] = "C"
    row = alert_history.history_view({"m": swapped}, NOW)[0]["rows"][0]
    assert row["back"] == "A" and row["profit"] is None


def test_history_has_all_records_and_newest_first_without_reconstructed_bets():
    log = {
        "old": entry("old"),
        "new": {**entry("new"), "start": "2026-10-16T09:00Z", "winner": None},
        "replay": {"match_id": "replay", "p_series": 0.99, "reconstructed": True},
    }
    groups = alert_history.history_view(log, NOW)
    assert [r["result"] for r in groups[0]["rows"]] == ["Pending", "Won"]
    assert groups[1]["rows"] == groups[2]["rows"] == []


def test_render_escapes_names_links_back_and_drops_threshold_explanation(tmp_path):
    e = entry()
    e["alert"]["team"] = e["ours1"] = "<script>"
    alert_history.render_alert_history({"m": e}, NOW, tmp_path)
    html = (tmp_path / "alerts.html").read_text()
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "Original picks and prices" in html and 'href="predictions.html"' in html
    assert "International" in html and "No picks yet" in html
    assert (
        "30 series" not in html and "too few" not in html and "sample size" not in html
    )
    assert "Chance" in html and "Outcome" in html and "Profit" in html
