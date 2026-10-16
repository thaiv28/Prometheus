import copy
import datetime

import pytest

from prometheus import markets, schedule
from prometheus.site import call_performance, config, predictions


def call(mid="m", reconstructed=False, **extra):
    return dict(
        match_id=mid,
        start="2026-10-14T10:00Z",
        league="LFL",
        event="Summer",
        home1="LFL",
        home2="LFL",
        ours1="A",
        ours2="B",
        team1="A",
        team2="B",
        p_series=0.8,
        p_game=0.6,
        method="forge",
        best_of=3,
        matched=True,
        winner=2,
        score1=0,
        score2=2,
        reconstructed=reconstructed,
        market_12h={"ours": 0.3, "ask1": 0.35, "ask2": 0.6},
        market={"p": 0.35, "at": "2026-10-14T09:50Z"},
        **extra,
    )


def test_detailed_history_matches_grouped_threshold_returns_without_mutation(
    tmp_path, monkeypatch
):
    log = {"saved": call("saved"), "replay": call("replay", True)}
    original = copy.deepcopy(log)
    view = predictions.predictions_view(
        log, set(), datetime.datetime(2026, 10, 15, tzinfo=datetime.UTC)
    )
    assert len(view["edges"]) == 6
    rows = call_performance.history(log)
    for row in rows:
        assert row["back"] == "B" and row["chance"] == 0.7 and row["ask"] == 0.6
        assert row["edge"] == pytest.approx(0.1)
        assert row["profit"] == pytest.approx(1 / 0.6 - 1 - markets.fee(0.6, 1))
    group = view["edges"][2]
    for source in group["sources"]:
        assert len(source["rows"]) == 1
        summary = source["rows"][0]
        assert summary["edge"] == 0.05 and summary["bets"] == 1
        assert summary["roi"] == rows[0]["profit"]
    assert all(
        [r["edge"] for r in s["rows"]] == list(schedule.BET_EDGES)
        for g in view["performance_edges"]
        for s in g["sources"]
    )
    monkeypatch.setattr(config, "OUTPUT_DIR", str(tmp_path))
    call_performance.render_call_performance(log, view)
    predictions.render_predictions(view, None)
    html = (tmp_path / "call-performance.html").read_text()
    assert "Call history" in html and "Saved" in html and "Backtest" in html
    assert "A" in html and "B" in html
    assert 'href="call-performance.html"' in (tmp_path / "predictions.html").read_text()
    assert log == original


def test_missing_quotes_and_unsettled_results_do_not_enter_history():
    log = {"open": call("open"), "missing": call("missing"), "invalid": call("invalid")}
    log["open"]["winner"] = None
    log["missing"]["market_12h"] = {}
    log["invalid"]["market_12h"].update(ask1=0, ask2=1)
    assert call_performance.history(log) == []
