"""Regression coverage for model replay versus immutable forward history."""

import copy
import datetime as dt
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from prometheus import alerts, prediction_backtest, schedule

_spec = importlib.util.spec_from_file_location(
    "restore_alert_history",
    Path(__file__).resolve().parents[1] / "scripts/oneoff/restore_alert_history.py",
)
repair = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(repair)


def entry(mid="m", **extra):
    return dict(
        match_id=mid,
        start="2026-01-03T08:00Z",
        team1="A",
        team2="B",
        ours1="A",
        ours2="B",
        home1="LCK",
        home2="LCK",
        league="LCK",
        event="LCK 2026",
        matched=True,
        best_of=3,
        method="forge",
        p_game=0.55,
        p_series=0.6,
        reconstructed=False,
        winner=1,
        score1=2,
        score2=0,
        **extra,
    )


def test_replay_changes_with_current_model_preserves_every_original_and_uses_12h_day(
    monkeypatch,
):
    monkeypatch.setenv("REGIONAL_CALIBRATION", "0")
    saved = entry("saved")
    saved["alert"] = {
        "side": 2,
        "team": "B",
        "price": 0.35,
        "p": 0.44,
        "at": "2026-01-01T10:00Z",
    }
    rebuilt = entry("rebuilt")
    rebuilt["reconstructed"] = True
    rebuilt["market_12h"] = {
        "p": 0.5,
        "ask1": 0.52,
        "ask2": 0.52,
        "ours": 0.1,
        "at": "2026-01-02T20:00Z",
    }
    log = {"saved": saved, "rebuilt": rebuilt}
    original = copy.deepcopy(log)
    days = []
    gap = [100.0]

    def before(day):
        days.append(day)
        value = gap[0] if day == dt.date(2026, 1, 3) else -100.0
        return pd.DataFrame(
            [
                {
                    "league": "LCK",
                    "elo": 1500 + value,
                    "forge": 1500 + value,
                    "has_form": True,
                },
                {"league": "LCK", "elo": 1500, "forge": 1500, "has_form": True},
            ],
            index=["A", "B"],
        )

    out = prediction_backtest.rebuild(log, None, before)
    assert log == original and out["saved"] == saved
    assert days == [dt.date(2026, 1, 3), dt.date(2026, 1, 2)]
    assert out["rebuilt"]["p_game"] > 0.55
    assert out["rebuilt"]["market_12h"]["ours"] < 0.5
    assert out["rebuilt"]["market_12h"]["p"] == 0.5
    gap[0] = 200.0
    newer = prediction_backtest.rebuild(log, None, before)
    assert newer["rebuilt"]["p_series"] > out["rebuilt"]["p_series"]
    assert log == original


def test_order_changes_keep_alert_team_terms_and_price_orientation_and_frozen_results():
    old = entry()
    old.pop("winner")
    old.pop("score1")
    old.pop("score2")
    old["market"] = {"p": 0.3, "ask1": 0.32, "ask2": 0.73, "at": "2026-01-01T10:00Z"}
    old["market_12h"] = {
        "p": 0.3,
        "ours": 0.4,
        "ask1": 0.32,
        "ask2": 0.73,
        "at": "2026-01-01T10:00Z",
    }
    alerts.record(
        [{"entry": old, "side": 1, "p": 0.4, "price": 0.32, "edge": 0.08}],
        dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
    )
    terms = copy.deepcopy(old["alert"])
    pred = entry()
    pred.update(team1="B", team2="A", ours1="B", ours2="A")
    sched = pd.DataFrame([{**pred, "winner": None, "score1": None, "score2": None}])
    log = {"m": old}
    schedule.update_log(
        log, sched, [pred], dt.datetime(2026, 1, 2, tzinfo=dt.UTC), "2026-01-01"
    )
    a = log["m"]["alert"]
    assert a["team"] == "A" and a["side"] == 2
    assert all(a[k] == terms[k] for k in ("team", "p", "price", "edge", "at"))
    assert old["alert"] == terms  # carry did not mutate the original object
    assert log["m"]["market"]["p"] == 0.7
    assert log["m"]["market_12h"]["ours"] == 0.6
    assert log["m"]["market"]["ask1"] == 0.73
    frozen = copy.deepcopy(log["m"])
    # The result feed reverses again after start. Stored prediction stays B/A.
    done = entry()
    done.update(winner=1, score1=2, score2=0)
    schedule.update_log(
        log,
        pd.DataFrame([done]),
        [done],
        dt.datetime(2026, 1, 4, tzinfo=dt.UTC),
        "2026-01-03",
    )
    assert log["m"]["winner"] == 2 and log["m"]["score2"] == 2
    assert all(
        log["m"][k] == frozen[k]
        for k in (
            "team1",
            "team2",
            "p_game",
            "p_series",
            "alert",
            "market",
            "market_12h",
        )
    )
    assert alerts.paper_record(log)[:2] == (1, 1)


def test_alert_scoring_resolves_identity_even_if_cached_side_is_stale():
    e = entry()
    e["alert"] = {
        "team": "A",
        "side": 2,
        "price": 0.35,
        "p": 0.44,
        "at": "2026-01-01T00:00Z",
    }
    assert alerts.paper_record({"m": e})[:2] == (1, 1)
    e["ours1"] = "C"
    e["team1"] = "C"
    assert alerts.paper_record({"m": e})[:2] == (0, 0)


def test_repair_uses_original_snapshot_terms_not_latest_or_result_and_is_idempotent():
    e = entry(repair.MATCH)
    e.update(
        team1="KT Rolster",
        ours1="KT Rolster",
        team2=repair.TEAM,
        ours2=repair.TEAM,
        start="2026-10-14T09:00Z",
    )
    e["alert"] = {
        "side": 1,
        "p": 0.4424,
        "price": 0.36,
        "edge": 0.0824,
        "at": "2026-10-13T02:29Z",
    }
    original = copy.deepcopy(e)
    source = copy.deepcopy(e)
    source["alert"] = {
        "side": 2,
        "p": 0.4447,
        "price": 0.35,
        "edge": 0.0947,
        "at": "2026-10-12T21:17Z",
    }
    log = {repair.MATCH: e}
    repair.restore(log, iter([("original-version", {repair.MATCH: source})]))
    assert all(e[k] == v for k, v in original.items() if k != "alert")
    assert all(e["alert"][k] == v for k, v in source["alert"].items())
    assert e["alert"]["team"] == repair.TEAM
    assert repair.restore(log, iter([])) is None
    bad = copy.deepcopy(source)
    bad["alert"]["side"] = 1
    with pytest.raises(ValueError, match="disagrees"):
        repair.restore({repair.MATCH: original}, iter([("wrong", {repair.MATCH: bad})]))


def test_provider_id_change_keeps_first_call_alert_and_identity():
    old = entry("original")
    old["alert"] = {
        "team": "A",
        "side": 1,
        "price": 0.35,
        "p": 0.44,
        "at": "2026-01-01T00:00Z",
    }
    old["predicted"] = "2026-01-02T00:00Z"
    frozen = copy.deepcopy(old)
    newer = entry("renamed-round")
    newer["p_game"] = 0.9
    newer["p_series"] = 0.98
    sched = pd.DataFrame([newer])
    log = {"original": old}
    schedule.update_log(
        log, sched, [newer], dt.datetime(2026, 1, 4, tzinfo=dt.UTC), "2026-01-03"
    )
    assert list(log) == ["original"]
    assert log["original"] == frozen


def test_after_original_start_reschedule_or_blank_result_cannot_rewrite_saved_history():
    saved = entry()
    saved["predicted"] = "2026-01-02T00:00Z"
    original = copy.deepcopy(saved)
    moved = entry()
    moved.update(
        start="2026-01-05T08:00Z",
        p_game=0.9,
        p_series=0.98,
        winner=None,
        score1=None,
        score2=None,
    )
    log = {"m": saved}
    schedule.update_log(
        log,
        pd.DataFrame([moved]),
        [moved],
        dt.datetime(2026, 1, 4, tzinfo=dt.UTC),
        "2026-01-03",
    )
    assert log["m"] == original


def test_ambiguous_incoming_fixtures_are_not_merged():
    a, b = entry("one"), entry("two")
    log = {}
    schedule.update_log(
        log,
        pd.DataFrame([a, b]),
        [a, b],
        dt.datetime(2026, 1, 2, tzinfo=dt.UTC),
        "2026-01-01",
    )
    assert set(log) == {"one", "two"}
