import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location(
    "live_latency",
    Path(__file__).resolve().parents[2] / "scripts/research/live_latency.py",
)
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)


def test_veto_adjacent_samples_and_map_reset():
    fields = ["gold", "kills", "towers", "inhibitors", "barons", "dragons"]
    start = pd.Timestamp("2026-05-01T00:00:00Z")
    data = {"lag": 21, "fields": {"teams": fields}, "maps": []}
    rows = []
    for game, counters in (
        ("a", [(0, 0), (2, 0), (3, 0), (3, 1)]),
        ("b", [(9, 3), (10, 3)]),
    ):
        samples = []
        for i, (kills, towers) in enumerate(counters):
            # team 1 changes too: total kills, either team's objectives.
            samples.append(
                {
                    "t": 60 * i,
                    "teams": [[10000, 0, 0, 0, 0, 0], [10000, kills, towers, 0, 0, 0]],
                }
            )
            rows.append(
                {
                    "game": game,
                    "minute": i,
                    "arrival": start + pd.Timedelta(seconds=60 * i + 21),
                }
            )
        data["maps"].append(
            {"game": game, "start": start.isoformat(), "samples": samples}
        )
    flagged = study.add_veto(pd.DataFrame(rows), data)
    assert flagged.veto.tolist() == [False, True, False, True, False, False]
    # An omitted prepared call still serves as the previous raw sample.
    sparse = study.add_veto(pd.DataFrame(rows).drop(index=1), data)
    assert sparse[sparse.game.eq("a") & sparse.minute.eq(2)].veto.tolist() == [False]


def test_holdout_removed_before_analysis():
    data = {
        "maps": [{"start": "2026-10-19T23:59:59Z"}, {"start": "2026-10-20T00:00:00Z"}]
    }
    assert study.before_holdout(data)["maps"] == data["maps"][:1]
    assert len(data["maps"]) == 2


def test_paired_zero_for_no_bet_and_series_bootstrap():
    data = {
        "maps": [
            {"game": g, "series": s} for g, s in (("a", "x"), ("b", "x"), ("c", "y"))
        ]
    }
    a = pd.DataFrame({"game": ["a"], "win": [0], "price": [0.5]})
    b = pd.DataFrame({"game": ["b"], "win": [1], "price": [0.5]})
    result = study.paired(data, data, a, b)
    assert result["maps"] == 3
    assert result["sum"] == pytest.approx(1 / study.trading.effective_cost(0.5))
    assert result["mean"] == pytest.approx(result["sum"] / 3)
    assert result == study.paired(data, data, a, b)


def test_veto_reselects_later_first_entry():
    rows = pd.DataFrame(
        {
            "game": [1, 1],
            "series": [1, 1],
            "arrival": pd.date_range("2026-03-01", periods=2, freq="min", tz="UTC"),
            "blend": 0.7,
            "won": 1,
            "p_lag": 0.5,
            "p_clv": 0.6,
            "cost0_30": 0.5,
            "cost1_30": 0.5,
            "n_30": 2,
            "range_30": 0.01,
            "flat": False,
            "objectives_valid": True,
            "quiet": 1,
            "veto": [True, False],
        }
    )
    assert study.trading.select(rows, window=30).arrival.iloc[0] == rows.arrival.iloc[0]
    bets = study.trading.select(rows[~rows.veto], window=30)
    assert len(bets) == 1
    assert bets.arrival.iloc[0] == rows.arrival.iloc[1]


def test_veto_duplicate_source_uses_last_sample_and_preserves_fractional_time():
    start = pd.Timestamp("2026-05-01T00:00:00Z")
    data = {
        "lag": 21,
        "fields": {
            "teams": ["gold", "kills", "towers", "inhibitors", "barons", "dragons"]
        },
        "maps": [
            {
                "game": "a",
                "start": start.isoformat(),
                "samples": [
                    {"t": 0, "teams": [[1, 0, 0, 0, 0, 0], [1, 0, 0, 0, 0, 0]]},
                    {"t": 1.001, "teams": [[2, 2, 0, 0, 0, 0], [2, 0, 0, 0, 0, 0]]},
                    {"t": 1.001, "teams": [[3, 2, 0, 0, 0, 0], [3, 0, 0, 0, 0, 0]]},
                ],
            }
        ],
    }
    rows = pd.DataFrame(
        {
            "game": ["a"],
            "minute": [1],
            "arrival": [start + pd.Timedelta(seconds=1.001) + pd.Timedelta(seconds=21)],
        }
    )
    result = study.add_veto(rows, data)
    assert len(result) == 1
    assert result.veto.tolist() == [False]
