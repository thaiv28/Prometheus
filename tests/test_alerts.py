import datetime
import json

import pytest

from prometheus import alerts, markets

UTC = datetime.UTC
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
        "home1": "LPL",
        "home2": "LPL",
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


def test_select_takes_forge_edges_6_or_more_hours_out_with_fresh_prices():
    log = {
        "edge": _entry("edge"),  # 61 - 54 = +7
        "small": _entry("small", ask1=0.58),  # +3: below the bar
        "elo": _entry("elo", method="elo"),  # not FORGE
        "minor": _entry("minor", home1="LDL", home2="LDL"),  # FORGE outside the majors
        "soon": _entry("soon", start="2026-10-06T14:00Z"),  # 4 hours out
        "late": _entry("late", start="2026-10-09T10:00Z"),  # 72 hours out: no cap
        "stale": _entry("stale", at="2026-10-05T10:00Z"),  # yesterday's price
        "other": _entry("other", p=0.30, ask2=0.62),  # backs team 2: 70 - 62 = +8
    }
    chosen = alerts.select(log, NOW)
    assert [(a["entry"]["match_id"], a["side"]) for a in chosen] == [
        ("edge", 1),
        ("elo", 1),
        ("minor", 1),
        ("other", 2),
        ("late", 1),
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


SLUG = lambda n: n.lower().replace(" ", "-")


def test_update_writes_the_issue_with_links_and_a_comment_for_new_matches():
    log = {"m": _entry("m")}
    alert = alerts.update(log, NOW, "2026-10-05", SLUG, {"jd-gaming"})
    assert (
        alert["title"]
        == "Kalshi edges for Tue 6 Oct: 1 call more than 5 points above Kalshi"
    )
    assert alert["day"] == alerts.day_key(NOW) and alert["title"].startswith(
        alert["day"]
    )
    body = alert["body"]
    row = "| Wed 7 Oct 11:00 / 04:00 | Demacia Cup | **JD Gaming** v LGD Gaming | 61% | 54¢ | **+7.0** |"
    assert row in body
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
    assert alert["new"] == 1 and row in alert["comment"]


def test_update_an_hour_later_edits_quietly_and_marks_a_gone_edge():
    log = {"m": _entry("m")}
    alerts.update(log, NOW, "2026-10-05", SLUG, set())
    later = NOW + datetime.timedelta(hours=1)
    log["m"]["market"].update(
        ask1=0.52, at="2026-10-06T11:00Z"
    )  # edge grows: no new match, no comment
    again = alerts.update(log, later, "2026-10-05", SLUG, set())
    assert (
        again["new"] == 0 and again["comment"] is None and "**+9.0**" in again["body"]
    )
    log["m"]["market"].update(
        ask1=0.60, at="2026-10-06T12:00Z"
    )  # edge gone: still listed, marked
    gone = alerts.update(
        log, NOW + datetime.timedelta(hours=2), "2026-10-05", SLUG, set()
    )
    assert gone["title"].endswith("0 calls more than 5 points above Kalshi (1 gone)")
    assert "gone: +1.0 now (alerted at +7.0)" in gone["body"]
    assert log["m"]["alert"]["price"] == 0.54  # the paper bet keeps its first price
    # Next day: an alert from yesterday that no longer qualifies isn't shown.
    assert (
        alerts.update(
            log, NOW + datetime.timedelta(days=1, hours=-9), "2026-10-05", SLUG, set()
        )
        is None
    )


def test_prices_file_lists_recent_priced_matches():
    log = {
        "m": _entry("m"),
        "old": _entry("old", start="2026-10-01T10:00Z"),
        "nope": {**_entry("nope"), "matched": False},
    }
    out = markets.prices_file(log, NOW)
    assert out["at"] == AT and list(out["matches"]) == ["m"]
    assert out["matches"]["m"] == {
        "p1": 53,
        "p2": 47,
        "at": AT,
        "url": "https://kalshi.com/markets/kxlolgame/league-of-legends-game/kxlolgame-26oct070700jdglgd",
    }


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

    from prometheus.site import config as site_config
    from prometheus.site import predictions

    monkeypatch.setattr(
        site_config, "PREDICTIONS_LOG", str(tmp_path / "predictions.json")
    )
    path = tmp_path / "alert.json"
    log = {"m": _entry("m")}
    coverage = {"priced": 1, "at": AT, "data_through": "2026-10-05"}
    assert predictions.write_kalshi_alert(log, coverage, set(), str(path))["new"] == 1
    issue = json.loads(path.read_text())
    assert issue["day"] == "Kalshi edges for Tue 6 Oct:" and issue["title"].startswith(
        issue["day"]
    )
    assert (
        "alert" in json.loads((tmp_path / "predictions.json").read_text())["matches"][0]
    )
    # No fresh prices (the fetch failed): nothing is written, and an old file goes.
    assert predictions.write_kalshi_alert(log, None, set(), str(path)) is None
    assert not path.exists()


def test_settled_alerts_score_clv_against_the_last_price_for_the_side():
    log = {
        "one": _entry(
            "one",
            winner=1,
            alert={"side": 1, "p": 0.61, "price": 0.54, "edge": 0.07, "at": AT},
        ),
        "two": _entry(
            "two",
            winner=1,
            alert={"side": 2, "p": 0.6, "price": 0.50, "edge": 0.1, "at": AT},
        ),
        "open": _entry(
            "open", alert={"side": 1, "p": 0.61, "price": 0.54, "edge": 0.07, "at": AT}
        ),
    }
    bets = alerts.settled_alerts(log)
    # market.p is 0.53: team1 closed at 53 (bought at 54), team2 at 47 (bought at 50).
    assert [b["clv"] for b in bets] == pytest.approx([-0.01, -0.03])
    assert [b["won"] for b in bets] == [True, False]
    assert alerts.clv_summary(bets) == pytest.approx((-0.02, 0.0))
    assert alerts.clv_summary([]) == (None, None)


def test_minor_domestic_and_other_cross_league_notify_under_the_same_rules():
    log = {
        "minor": _entry("minor", home1="LDL", home2="LDL"),
        "minor_elo": _entry("minor_elo", method="elo", home1="LDL", home2="LDL"),
        "cup": _entry(
            "cup",
            method="elo-cross",
            home1="LFL",
            home2="PRM",
            league="EM",
            event="EMEA Masters",
        ),
    }
    issue = alerts.update(log, NOW, "5 Oct", SLUG, set())
    assert issue["new"] == 3
    assert "## Minor domestic" in issue["comment"]
    assert "## Other cross-league" in issue["comment"]
    assert all("alert" in e and "paper_alert" not in e for e in log.values())
    assert alerts.update(log, NOW, "5 Oct", SLUG, set())["comment"] is None


def test_select_skips_calls_whose_ratings_lack_a_teams_result():
    def settled(mid, start, team1, team2):
        return {
            "match_id": mid,
            "start": start,
            "team1": team1,
            "team2": team2,
            "winner": 1,
        }

    teams = {"team1": "JD Gaming", "team2": "LGD Gaming"}
    log = {
        "stale": _entry("stale", data_through="2026-10-01", **teams),
        "fresh": _entry(
            "fresh",
            start="2026-10-07T12:00Z",
            data_through="2026-10-04",
            team1="Weibo Gaming",
            team2="Top Esports",
        ),
        # JD played on 3 Oct, after the stale call's data: the market knows that result.
        "played": settled(
            "played", "2026-10-03T09:00Z", "JD Gaming", "Bilibili Gaming"
        ),
        # Within a day and a half of now: Oracle's Elixir's usual lag, not staleness.
        "recent": settled(
            "recent", "2026-10-05T09:00Z", "Weibo Gaming", "Ninjas in Pyjamas"
        ),
    }
    assert [a["entry"]["match_id"] for a in alerts.select(log, NOW)] == ["fresh"]


def _international(mid="intl", **extra):
    return _entry(
        mid,
        **{
            "method": "elo-cross",
            "home2": "LCK",
            "league": "Worlds",
            "event": "2026 World Championship",
            "ours2": "Gen.G",
            "calibration": {
                "version": "regional-v1",
                "model": "2026-10-03",
                "trained_through": "2026-10-02",
            },
            **extra,
        },
    )


def test_every_scope_uses_same_timing_prices_and_probability_guards():
    log = {
        "ok": _international("ok"),
        "same": _international("same", home2="LPL"),
        "cup": _international("cup", league="EM", event="EMEA Masters"),
        "qual": _international("qual", event="World Championship Regional Finals"),
        "old": _international("old", calibration=None),
        "stale": _international("stale", at="2026-10-05T10:00Z"),
        "soon": _international("soon", start="2026-10-06T15:59Z"),
        "six": _international("six", start="2026-10-06T16:00Z"),
        "zero": _international("zero", ask1=0, ask2=1),
        "none": _international("none", ask1=None, ask2=None),
        "home": _international("home", home2="Worlds"),
        "missing": _international("missing", home2=None),
        "nan": _international("nan", p_series=float("nan")),
        "invalid": _international("invalid", p_series=1.1),
        "settled": _international("settled", winner=1),
    }
    assert [a["entry"]["match_id"] for a in alerts.select(log, NOW)] == [
        "six",
        "cup",
        "ok",
        "old",
        "qual",
        "same",
    ]


def test_international_skips_results_missing_from_ratings():
    log = {
        "m": _international(
            data_through="2026-10-01", team1="JD Gaming", team2="Gen.G"
        ),
        "result": {
            "match_id": "r",
            "start": "2026-10-03T09:00Z",
            "team1": "JD Gaming",
            "team2": "Other",
            "winner": 1,
        },
    }
    assert alerts.select(log, NOW) == []


def test_international_only_issue_freezes_terms_snapshot_and_sends_one_notification():
    log = {"m": _international()}
    issue = alerts.update(log, NOW, "2026-10-05", SLUG, set())
    assert "1 call more than 5 points" in issue["title"]
    assert "## Major vs major international" in issue["body"]
    assert "experimental" not in issue["body"]
    assert "First chance" in issue["body"] and "First ask" in issue["body"]
    assert "**New:** 1 match" in issue["comment"]
    assert issue["new"] == 1
    assert "alert" in log["m"] and "paper_alert" not in log["m"]
    import copy

    first = copy.deepcopy(log["m"]["alert"])
    later = NOW + datetime.timedelta(hours=1)
    log["m"].update(
        p_series=0.8, calibration={"version": "regional-v1", "model": "later"}
    )
    log["m"]["market"].update(ask1=0.7, at="2026-10-06T11:00Z")
    again = alerts.update(log, later, "2026-10-05", SLUG, set())
    assert again["comment"] is None and again["new"] == 0
    assert "61% | 54¢" in again["body"]  # first terms, not current 80% / 70c
    assert log["m"]["alert"] == first
    log["m"]["winner"] = 1
    assert alerts.paper_record(log)[:3] == (1, 1, 1.0)


def test_mixed_issue_has_separate_records_and_retains_gone_international_call():
    log = {"dom": _entry("dom"), "intl": _international()}
    issue = alerts.update(log, NOW, "2026-10-05", SLUG, set())
    assert "## Major domestic" in issue["body"]
    assert issue["new"] == 2
    assert "**New:** 2 matches" in issue["comment"]
    log["intl"]["market"].update(ask1=0.6, at="2026-10-06T11:00Z")
    later = NOW + datetime.timedelta(hours=1)
    again = alerts.update(log, later, "2026-10-05", SLUG, set())
    assert "gone: +1.0 now (alerted at +7.0)" in again["body"]
    assert again["comment"] is None


def test_international_record_survives_fixture_reordering_and_settles_by_team():
    from prometheus import schedule

    old = _international()
    alerts.record(
        alerts.select({"m": old}, NOW),
        NOW,
        alerts.INTERNATIONAL_KEY,
    )
    refreshed = {**old, "ours1": old["ours2"], "ours2": old["ours1"]}
    refreshed.update(schedule.carry_records(old, refreshed))
    assert refreshed[alerts.INTERNATIONAL_KEY]["side"] == 2
    assert (
        refreshed[alerts.INTERNATIONAL_KEY]["forecast"]
        == old[alerts.INTERNATIONAL_KEY]["forecast"]
    )
    refreshed["winner"] = 2
    assert alerts.paper_record({"m": refreshed}, key=alerts.INTERNATIONAL_KEY)[1] == 1


def test_legacy_international_never_renotifies_or_rewrites_first_terms():
    import copy

    e = _international()
    alerts.record(alerts.select({"m": e}, NOW), NOW, alerts.INTERNATIONAL_KEY)
    original = copy.deepcopy(e[alerts.INTERNATIONAL_KEY])
    e["p_series"] = 0.85
    issue = alerts.update({"m": e}, NOW, "5 Oct", SLUG, set())
    assert issue["new"] == 0 and issue["comment"] is None
    assert "61% | 54¢" in issue["body"]
    assert e[alerts.INTERNATIONAL_KEY] == original and "alert" not in e


def test_unposted_legacy_minor_can_notify_once_at_current_terms_without_rewriting():
    import copy

    e = _entry("minor", home1="LDL", home2="LDL")
    alerts.record(alerts.select({"m": e}, NOW), NOW, "paper_alert")
    original = copy.deepcopy(e["paper_alert"])
    e["p_series"] = 0.7
    issue = alerts.update({"m": e}, NOW, "5 Oct", SLUG, set())
    assert issue["new"] == 1 and e["alert"]["p"] == 0.7
    assert e["paper_alert"] == original
    assert alerts.update({"m": e}, NOW, "5 Oct", SLUG, set())["new"] == 0
