"""Shared selection, chronology and frozen forecast regression checks."""

import copy
import datetime as dt
import math

import pytest

from prometheus import alerts, market_blend, trading
from prometheus.alert_contract import saved_alerts, trade_veto
from prometheus.site import trading as record

NOW = dt.datetime(2026, 10, 16, 12, tzinfo=dt.UTC)


def fixture(**changes):
    return {
        "match_id": "f",
        "matched": True,
        "method": "forge",
        "ours1": "A",
        "ours2": "B",
        "home1": "LCK",
        "home2": "LCK",
        "league": "LCK",
        "event": "Summer",
        "start": "2026-10-18T12:00Z",
        "p_series": 0.8,
        "p_game": 0.7,
        "best_of": 3,
        "market": {
            "p": 0.55,
            "ask1": 0.56,
            "ask2": 0.46,
            "at": NOW.strftime("%Y-%m-%dT%H:%MZ"),
            "ticker": "KXLOLGAME-F",
        },
        **changes,
    }


@pytest.mark.parametrize(
    "home1,home2,league,allowed",
    [
        ("LCK", "LCK", "LCK", True),
        ("LFL", "LFL", "LFL", True),
        ("LCK", "LPL", "Worlds", True),
        ("LCK", "LFL", "Worlds", True),
        ("LFL", "PRM", "Worlds", True),
        ("LFL", "PRM", "EM", False),
    ],
)
def test_alerts_and_page_share_five_group_scope(home1, home2, league, allowed):
    entry = fixture(home1=home1, home2=home2, league=league)
    assert bool(trading.quote(entry)) == allowed
    assert bool(alerts.select({"f": entry}, NOW)) == allowed


def test_snapshots_are_causal_and_match_symmetric_logit_blend():
    assert market_blend.estimate(0.8, 0.55, "2026-04-30T23:59:59Z") is None
    assert market_blend.snapshot("2026-05-31T23:59:59Z")["training_series"] == 352
    assert market_blend.snapshot("2026-06-01T00:00:00Z")["training_series"] == 663
    estimate = market_blend.estimate(0.8, 0.55, NOW)
    z = 1.087254056134923 * math.log(0.55 / 0.45) + 0.34280025852274704 * (
        math.log(0.8 / 0.2) - math.log(0.55 / 0.45)
    )
    assert estimate["probability"] == pytest.approx(1 / (1 + math.exp(-z)))
    inverse = market_blend.estimate(0.2, 0.45, NOW)
    assert inverse["probability"] == pytest.approx(1 - estimate["probability"])
    assert market_blend.refresh(estimate, 0.3) < estimate["probability"]
    assert all(
        m["trained_through"] < m["available_from"]
        for m in market_blend.load()["snapshots"]
    )


def test_new_alert_freezes_blend_and_preserves_raw_forecast():
    entry = fixture()
    before = copy.deepcopy(entry)
    quote = trading.quote(entry)
    assert entry == before
    assert alerts.record(alerts.select({"f": entry}, NOW), NOW) == 1
    saved = copy.deepcopy(entry["alert"])
    assert saved["trading"] == quote["pick"]["trading"]
    assert saved["forecast"]["p_series"] == 0.8
    exported = saved_alerts({"matches": {"f": entry}})
    assert exported[0]["trading"] == saved["trading"]
    entry["p_series"] = 0.9
    entry["market"]["p"] = 0.6
    alerts.record(alerts.select({"f": entry}, NOW), NOW)
    assert entry["alert"] == saved


@pytest.mark.parametrize("opponent,home", [("Cloud9", "LCS"), ("Team Liquid", "LCS")])
def test_personal_veto_preserves_notifications_and_pins_home_to_team(opponent, home):
    entry = fixture(ours2=opponent, home2=home, league="Worlds")
    assert alerts.record(alerts.select({"f": entry}, NOW), NOW) == 1
    # Provider reordering cannot attach the NA home to the wrong team.
    entry.update(ours1=opponent, ours2="A", home1=home, home2="LCK")
    contract = saved_alerts({"matches": [entry]})[0]
    assert contract["team_homes"] == {"A": "LCK", opponent: home}
    assert trade_veto(contract)


def test_two_na_teams_at_an_international_event_still_cannot_be_bet_against():
    entry = fixture(home1="LCS", home2="LCS", league="Worlds")
    assert alerts.record(alerts.select({"f": entry}, NOW), NOW) == 1
    contract = saved_alerts({"matches": [entry]})[0]
    assert contract["group"] == "major-domestic"
    assert contract["international"] is True
    assert trade_veto(contract) == "against_north_america_international"


@pytest.mark.parametrize("missing", ["p", "at"])
def test_no_raw_fallback_when_market_input_missing(missing):
    entry = fixture()
    del entry["market"][missing]
    assert trading.quote(entry) is None


def test_positive_gross_edge_can_fail_after_fees():
    entry = fixture(p_series=0.61)
    entry["market"].update(p=0.53, ask1=0.54, ask2=0.47)
    pick = trading.quote(entry)["pick"]
    assert pick["edge"] > 0 > pick["net_edge"]
    assert alerts.select({"f": entry}, NOW) == []


def test_record_uses_early_inputs_and_all_in_outlay_without_mutation():
    entry = fixture(winner=1)
    entry["market_12h"] = {**entry["market"], "ours": 0.8}
    before = copy.deepcopy(entry)
    bets = record.history([entry])
    assert len(bets) == 1
    groups = record.groups([entry])
    assert len(groups) == 5
    row = groups[0]["sources"][0]["rows"][0]
    assert row["roi"] == pytest.approx(bets[0]["profit"] / bets[0]["outlay"])
    assert row["roi_ci"] is None
    assert entry == before
    entry["market_12h"]["at"] = entry["start"]
    assert record.history([entry]) == []
    del entry["market_12h"]["p"]
    assert record.history([entry]) == []
