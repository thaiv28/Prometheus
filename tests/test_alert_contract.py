import copy

from prometheus import alert_contract, alerts, schedule


def fixture():
    return {
        "match_id": "provider-a",
        "ours1": "A",
        "ours2": "B",
        "team1": "A",
        "team2": "B",
        "start": "2026-10-20T10:00Z",
        "league": "LFL",
        "event": "Summer",
        "market": {"ticker": "KXLOLGAME-TEST"},
        "alert": {
            "side": 1,
            "team": "A",
            "p": 0.6,
            "price": 0.5,
            "edge": 0.1,
            "at": "2026-10-19T10:00Z",
            "group": "minor-domestic",
            "forecast": {"start": "2026-10-20T10:00Z"},
        },
    }


def test_contract_pins_identity_across_provider_order_and_start_changes():
    original = fixture()
    original["alert"]["execution"] = alert_contract.identity(
        original, original["alert"]
    )
    frozen = copy.deepcopy(original["alert"])
    refreshed = {
        **original,
        "match_id": "provider-b",
        "ours1": "B",
        "ours2": "A",
        "team1": "B",
        "team2": "A",
        "start": "2026-10-20T11:00Z",
    }
    refreshed.update(schedule.carry_records(original, refreshed))
    first = alert_contract.saved_alerts({"matches": [original]})[0]
    second = alert_contract.saved_alerts({"matches": [refreshed]})[0]
    assert first == second
    assert second["backed_team"] == "A" and second["probability"] == "0.6"
    assert original["alert"] == frozen


def test_adapter_reads_legacy_posted_records_and_ignores_unposted_paper():
    original = fixture()
    intl = {**original, alerts.INTERNATIONAL_KEY: original["alert"]}
    del intl["alert"]
    paper = {**original, "paper_alert": original["alert"]}
    del paper["alert"]
    assert alert_contract.saved_alerts(
        {"matches": [intl]}
    ) == alert_contract.saved_alerts({"matches": [original]})
    assert alert_contract.saved_alerts({"matches": [paper]}) == []
    both = {**original, alerts.INTERNATIONAL_KEY: {**original["alert"], "p": 0.8}}
    assert len(alert_contract.saved_alerts({"matches": [both]})) == 1
    assert alert_contract.saved_alerts({"matches": [both]})[0]["probability"] == "0.6"


def test_invalid_identity_or_terms_never_become_execution_inputs():
    missing = fixture()
    missing["market"] = {}
    wrong = fixture()
    wrong["alert"]["team"] = "C"
    nan = fixture()
    nan["alert"]["p"] = float("nan")
    assert alert_contract.saved_alerts({"matches": [missing, wrong, nan]}) == []
