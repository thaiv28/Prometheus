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


def test_candidates_share_legacy_fixture_fence_and_emit_both_sides():
    import datetime as dt

    entry = {**fixture(), "p_series": 0.7, "home1": "LFL", "home2": "LFL"}
    now = dt.datetime(2026, 10, 19, 10, tzinfo=dt.UTC)
    saved = alert_contract.candidate(entry, now.isoformat(), "minor-domestic", False)
    assert (
        saved["fixture_id"]
        == alert_contract.identity(entry, entry["alert"])["fixture_id"]
    )
    entry[alert_contract.CANDIDATE_KEY] = saved
    proposals = alert_contract.saved_candidates({"matches": {"m": entry}}, now)
    assert [p["backed_team"] for p in proposals] == ["A", "B"]
    assert [p["probability"] for p in proposals] == ["0.7", "0.3"]
    assert len({p["alert_id"] for p in proposals}) == 2
    assert all(
        p["trading"]["raw_probability"] == float(p["probability"]) for p in proposals
    )
    assert all("original_ask" not in p for p in proposals)


def test_candidates_reject_started_aged_future_and_malformed(monkeypatch):
    import datetime as dt

    now = dt.datetime(2026, 10, 19, 10, tzinfo=dt.UTC)
    entry = {**fixture(), "p_series": 0.7}
    saved = alert_contract.candidate(entry, now.isoformat(), "minor-domestic", False)

    def proposals(record):
        return alert_contract.saved_candidates(
            {"matches": [{alert_contract.CANDIDATE_KEY: record}]}, now
        )

    assert (
        len(proposals({**saved, "at": (now - dt.timedelta(hours=3)).isoformat()})) == 2
    )
    for change in (
        {"start": now.isoformat()},
        {"at": (now - dt.timedelta(hours=3, seconds=1)).isoformat()},
        {"at": (now + dt.timedelta(seconds=1)).isoformat()},
        {"at": "bad"},
        {"teams": ["A", "A"]},
        {"teams": None},
        {"raw": {"A": 0.7}},
        {"raw": {"A": float("nan"), "B": 0.3}},
        {"schema_version": 2},
        {"kind": "old"},
        {"team_homes": []},
        {"event_ticker": ""},
        {"group": "other-cross-league"},
    ):
        assert proposals({**saved, **change}) == []
    assert proposals(None) == []
    monkeypatch.setattr(alert_contract.market_blend, "snapshot", lambda now: None)
    assert proposals(saved) == []
