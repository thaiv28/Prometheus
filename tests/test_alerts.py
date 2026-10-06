import datetime
import json

import pytest

from prometheus import alerts, markets

UTC = datetime.timezone.utc
NOW = datetime.datetime(2026, 10, 6, 10, 0, tzinfo=UTC)
AT = "2026-10-06T10:00Z"


def _entry(
    mid,
    start="2026-10-07T11:00Z",
    p=0.61,
    ask1=0.54,
    ask2=0.47,
    method="forge",
    at=AT,
    **extra,
):
    return {
        "match_id": mid,
        "start": start,
        "matched": True,
        "method": method,
        "p_series": p,
        "ours1": "JD Gaming",
        "ours2": "LGD Gaming",
        "event": "Demacia Cup",
        "league": "DCup",
        "market": {
            "p": 0.53,
            "spread": 0.01,
            "ask1": ask1,
            "ask2": ask2,
            "at": at,
            "ticker": "KXLOLGAME-26OCT070700JDGLGD",
        },
        **extra,
    }


def test_select_takes_forge_edges_in_the_window_with_fresh_prices():
    log = {
        "edge": _entry("edge"),  # 61 - 54 = +7
        "small": _entry("small", ask1=0.58),  # +3: below the bar
        "elo": _entry("elo", method="elo"),  # not FORGE
        "soon": _entry("soon", start="2026-10-06T14:00Z"),  # 4 hours out
        "late": _entry("late", start="2026-10-08T10:00Z"),  # 48 hours out
        "stale": _entry("stale", at="2026-10-05T10:00Z"),  # yesterday's price
        "other": _entry("other", p=0.30, ask2=0.62),  # backs team 2: 70 - 62 = +8
    }
    chosen = alerts.select(log, NOW)
    assert [(a["entry"]["match_id"], a["side"]) for a in chosen] == [
        ("edge", 1),
        ("other", 2),
    ]
    assert chosen[0]["edge"] == pytest.approx(0.07)


def test_record_keeps_the_first_alert_and_paper_record_scores_it_after_fees():
    log = {"m": _entry("m")}
    assert alerts.record(alerts.select(log, NOW), NOW) == 1
    first = dict(log["m"]["alert"])
    log["m"]["market"]["ask1"] = 0.50
    assert alerts.record(alerts.select(log, NOW), NOW) == 0
    assert log["m"]["alert"] == first and first["price"] == 0.54
    assert alerts.paper_record(log) == (0, 0, 0.0, 0.0)  # not played yet
    log["m"]["winner"] = 1
    settled, won, staked, profit = alerts.paper_record(log)
    assert (settled, won, staked) == (1, 1, 1.0)
    assert profit == pytest.approx(1 / 0.54 - 1 - markets.fee(0.54, 1))


def test_issue_lists_matches_with_links_and_the_record():
    log = {"m": _entry("m")}
    chosen = alerts.select(log, NOW)
    title, body = alerts.issue(
        chosen,
        log,
        NOW,
        "2026-10-05",
        lambda n: n.lower().replace(" ", "-"),
        {"jd-gaming"},
    )
    assert (
        title
        == "Kalshi edges for Tue 6 Oct: 1 FORGE call at least 5 points above the price"
    )
    assert title.startswith(alerts.day_key(NOW))
    assert (
        "| Wed 7 Oct 11:00 / 04:00 | Demacia Cup | **JD Gaming** v LGD Gaming | 61% | 54¢ | **+7.0** |"
        in body
    )
    assert (
        "[Kalshi](https://kalshi.com/markets/kxlolgame/league-of-legends-game/kxlolgame-26oct070700jdglgd)"
        in body
    )
    assert (
        "[Prediction](https://prometheus.thaiv.dev/predictions.html?search=JD%20Gaming)"
        in body
    )
    assert "[JD Gaming](https://prometheus.thaiv.dev/teams/jd-gaming.html)" in body
    assert "teams/lgd-gaming.html" not in body  # no page, no link
    assert (
        "none settled yet" in body
        and "games through 2026-10-05" in body
        and "cc @thaiv28" in body
    )


def test_buy_costs_take_the_cheaper_route_and_skip_wide_books():
    row = {
        "markets": [
            {"side": "JDG", "bid": 0.52, "ask": 0.54},
            {"side": "LGD", "bid": 0.45, "ask": 0.47},
        ]
    }
    assert markets.buy_costs(row, "JDG") == pytest.approx(
        (0.54, 0.47)
    )  # JDG: min(.54, 1-.45); LGD: min(.47, 1-.52)
    wide = {"markets": [{"side": "JDG", "bid": 0.30, "ask": 0.60}]}
    assert markets.buy_costs(wide, "JDG") == (None, None)


def test_write_kalshi_alert_writes_the_issue_and_clears_stale_files(
    tmp_path, monkeypatch
):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "build_site",
        Path(__file__).resolve().parent.parent / "scripts" / "build_site.py",
    )
    build_site = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build_site)
    monkeypatch.setattr(
        build_site, "PREDICTIONS_LOG", str(tmp_path / "predictions.json")
    )
    path = tmp_path / "alert.json"
    log = {"m": _entry("m")}
    coverage = {"priced": 1, "at": AT, "data_through": "2026-10-05"}
    assert len(build_site.write_kalshi_alert(log, coverage, set(), str(path))) == 1
    issue = json.loads(path.read_text())
    assert issue["day"] == "Kalshi edges for Tue 6 Oct:" and issue["title"].startswith(
        issue["day"]
    )
    assert (
        "alert" in json.loads((tmp_path / "predictions.json").read_text())["matches"][0]
    )
    # No fresh prices (the fetch failed): nothing is written, and an old file goes.
    assert build_site.write_kalshi_alert(log, None, set(), str(path)) == []
    assert not path.exists()
