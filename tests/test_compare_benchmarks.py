import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
_spec = importlib.util.spec_from_file_location(
    "compare_benchmarks", ROOT / "scripts" / "compare_benchmarks.py"
)
cb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cb)
N = 200  # bootstrap resamples, enough for these clear-cut cases


def _forecasts(section, forecast, n=3000, shift=0.0, seed=0, start=0):
    rng = np.random.default_rng(seed)
    loss = rng.uniform(0.3, 0.9, n)
    return pd.DataFrame(
        {
            "section": section,
            "forecast": forecast,
            "gameid": [f"g{i}" for i in range(start, start + n)],
            "teamid": "t",
            "year": 2024,
            "won": 1,
            "log_loss": loss + shift,
            "brier": 0.2,
            "accuracy": 1.0,
        }
    )


def _results(rows):
    return {r["name"].split(" (")[0]: r["result"] for r in rows}


def test_forecasts_better_worse_and_noise():
    base = pd.concat(
        [
            _forecasts("Domestic", "forge"),
            _forecasts("International", "forge"),
            _forecasts("Domestic", "form"),
        ]
    )
    noise = np.random.default_rng(1).normal(0, 0.05, 3000)
    head = pd.concat(
        [
            _forecasts("Domestic", "forge", shift=-0.02),  # better
            _forecasts("International", "forge", shift=0.02),  # worse, guarded
            _forecasts("Domestic", "form", shift=noise),  # noise
        ]
    )
    rows = cb.compare_forecasts(base, head, n_resamples=N)
    by = {(r["section"], r["name"].split(" ")[0]): r for r in rows}
    assert by[("Domestic", "forge")]["result"] == "better"
    assert by[("International", "forge")]["result"] == "worse"
    assert by[("Domestic", "form")]["result"] == "within noise"
    bad = cb.failures(rows)
    assert [(r["section"], r["guarded"]) for r in bad] == [("International", True)]


def test_unguarded_forecast_getting_worse_does_not_fail():
    base = _forecasts("Domestic", "form")
    head = _forecasts("Domestic", "form", shift=0.05)
    rows = cb.compare_forecasts(base, head, n_resamples=N)
    assert rows[0]["result"] == "worse" and not cb.failures(rows)


def test_identical_dumps_are_within_noise_and_unpaired_rows_counted():
    base = _forecasts("Domestic", "forge", n=100)
    # 90 shared games, 10 only in base and 10 only in head.
    head = pd.concat([base.iloc[10:], _forecasts("Domestic", "forge", 10, start=100)])
    (row,) = cb.compare_forecasts(base, head, n_resamples=N)
    assert row["unpaired"] == (10, 10)
    assert row["diff"] == 0 and row["result"] == "within noise"
    assert "90 games" in row["name"]


def test_forecast_only_on_one_side_is_not_paired():
    base = _forecasts("Domestic", "forge", n=50)
    head = pd.concat([base, _forecasts("Domestic", "new", n=50)])
    rows = cb.compare_forecasts(base, head, n_resamples=N)
    new = next(r for r in rows if r["name"] == "new")
    assert new["result"] == "not paired" and new["unpaired"] == (0, 50)
    assert not cb.failures(rows)


def _halves(stat, n=400, noise=0.5, seed=0, n_games=20):
    rng = np.random.default_rng(seed)
    true = rng.normal(0, 1, n)
    win = rng.normal(0, 1, n) + true
    rows = pd.DataFrame(
        {
            "stat": stat,
            "teamname": [f"team{i}" for i in range(n)],
            "year": 2020 + np.arange(n) % 4,
            "full": true,
            "h0": true + rng.normal(0, noise, n),
            "h1": true + rng.normal(0, noise, n),
            "n0": n_games,
            "n1": n_games,
        }
    )
    wins = rows.assign(
        stat="win_pct",
        h0=win + rng.normal(0, 0.5, n),
        h1=win + rng.normal(0, 0.5, n),
    )
    return pd.concat([rows, wins], ignore_index=True)


META = {"min_half_games": 10}


def test_season_stat_less_reliable_head_is_worse():
    base = _halves("glory", noise=0.3)
    head = _halves("glory", noise=1.5)  # same truth, noisier halves
    rows = cb.compare_season_stats(base, META, head, META, n_resamples=N)
    results = _results(rows)
    assert results["glory split-half r"] == "worse"
    assert results["glory r with other half's win %"] == "worse"
    assert len(cb.failures(rows)) == 2


def test_season_stat_same_data_within_noise_and_short_halves_dropped():
    base = _halves("glory")
    head = base.copy()
    head.loc[:9, "n0"] = 5  # below min_half_games: dropped from head only
    rows = cb.compare_season_stats(base, META, head, META, n_resamples=N)
    split = next(r for r in rows if r["name"].startswith("glory split"))
    assert split["result"] == "within noise" and split["unpaired"] == (10, 0)
    assert not cb.failures(rows)


def _aura(n=600, noise=0.5, seed=0):
    rng = np.random.default_rng(seed)
    true = rng.normal(0, 1, n)
    key = pd.DataFrame(
        {
            "playerid": [f"p{i}" for i in range(n)],
            "year": 2022,
            "position": "top",
        }
    )
    halves = key.assign(
        aura_0=true + rng.normal(0, noise, n), aura_1=true + rng.normal(0, noise, n)
    )
    moved = key.assign(aura=true + rng.normal(0, noise, n), aura_next=true)
    teams = n // 2
    win = rng.normal(0, 1, 2 * teams)
    roster = pd.DataFrame(
        {
            "teamname": np.repeat([f"t{i}" for i in range(teams)], 2),
            "year": 2022,
            "half": np.tile([0, 1], teams),
            "win": win,
            "aura": win + rng.normal(0, noise * 2, 2 * teams),
        }
    )
    # Exactly calibrated: in each bin, the share won equals the chance.
    chances = np.arange(0.05, 1, 0.1)
    won = np.concatenate([np.arange(100) < round(c * 100) for c in chances])
    calibration = pd.DataFrame(
        {
            "minute": 15,
            "gameid": range(len(won)),
            "p": np.repeat(chances, 100),
            "won": won.astype(int),
        }
    )
    return {
        "halves": halves,
        "moved": moved,
        "roster": roster,
        "calibration": calibration,
    }


def test_aura_worse_checks_and_ece_limit():
    base, head = _aura(noise=0.3), _aura(noise=1.5)
    rows = cb.compare_aura(base, head, n_resamples=N)
    assert set(_results(rows).values()) == {"worse"}
    assert len(cb.failures(rows)) == 3

    same = cb.compare_aura(base, base, n_resamples=N)
    assert set(_results(same).values()) == {"within noise"}
    assert not cb.failures(same)

    ok = cb.aura_ece(base["calibration"], base["calibration"])
    assert not cb.failures(ok)
    off = base["calibration"].assign(p=lambda d: np.clip(d["p"] + 0.05, 0, 1))
    (row,) = cb.aura_ece(base["calibration"], off)
    assert row["head"] > cb.ECE_LIMIT and cb.failures([row]) == [row]


def test_compare_dirs_and_exit_code(tmp_path):
    for side, shift in (("base", 0.0), ("head", 0.02)):
        (tmp_path / side / "metrics").mkdir(parents=True)
        _forecasts("Domestic", "forge", shift=shift).to_csv(
            tmp_path / side / "metrics" / "forecasts.csv.gz", index=False
        )
        (tmp_path / side / "season").mkdir()
        _halves("glory").to_csv(
            tmp_path / side / "season" / "halves.csv.gz", index=False
        )
        (tmp_path / side / "season" / "metrics.json").write_text(json.dumps(META))
    sections, notes = cb.compare_dirs(tmp_path / "base", tmp_path / "head", N)
    assert [title for title, _ in sections] == ["Forecasts", "Season stats"]
    assert notes[0] == "AURA report: missing from one side, not compared."
    assert notes[1].startswith("Market benchmark: missing from one side")
    report = cb.render(sections, notes)
    assert report.startswith("**Benchmarks: 1 guarded check(s) failed**")
    assert "#### Forecasts" in report and "#### Season stats" in report


def _calls(kind, n=2000, shift=0.0, seed=0, method="forge", major=True):
    rng = np.random.default_rng(seed)
    won = rng.integers(0, 2, n)
    p = np.clip(np.where(won == 1, 0.65, 0.35) + rng.normal(0, 0.1, n), 0.05, 0.95)
    return pd.DataFrame(
        {
            "kind": kind,
            "event_ticker": [f"{kind}{i}" for i in range(n)],
            "team1": "A",
            "method": method,
            "major": major,
            "p": np.clip(p + shift * np.where(won == 1, -1, 1), 0.01, 0.99),
            "won1": won,
        }
    )


def test_markets_worse_calls_fail_and_same_calls_pass():
    base = pd.concat([_calls("series"), _calls("map1", seed=1)])
    same = cb.compare_markets(base, base.copy(), n_resamples=N)
    assert not cb.failures(same)
    assert {r["name"].split(" (")[0] for r in same} == {
        "series log loss, all",
        "series log loss, forge",
        "map1 log loss, all",
    }
    worse = pd.concat([_calls("series", shift=0.08), _calls("map1", seed=1)])
    rows = cb.compare_markets(base, worse, n_resamples=N)
    failed = {r["name"].split(" (")[0] for r in cb.failures(rows)}
    assert failed == {"series log loss, all", "series log loss, forge"}


def _priced(calls, seed=2):
    """Series calls with Kalshi's bet prices: costs near the call, a close nearer
    the result."""
    rng = np.random.default_rng(seed)
    q = np.clip(calls["p"] + rng.normal(0, 0.08, len(calls)), 0.05, 0.95)
    return calls.assign(
        cost1=np.round(q + 0.01, 2),
        cost2=np.round(1 - q + 0.01, 2),
        market_close=np.clip(q + rng.normal(0, 0.03, len(calls)), 0.02, 0.98),
    )


def test_betting_same_calls_zero_difference_and_never_guarded():
    base = _priced(_calls("series", n=600))
    rows, note = cb.compare_betting(base, base.copy(), n_resamples=N)
    assert note is None and rows
    assert {r["slice"] for r in rows} == {"All", "FORGE"}
    assert [r["edge"] for r in rows if r["slice"] == "All"] == list(
        cb.schedule.BET_EDGES
    )
    for r in rows:
        assert r["bets"][0] == r["bets"][1] and not r["guarded"]
        if r["roi_diff"] is not None:
            assert r["roi_diff"] == (0.0, 0.0, 0.0)
    assert not cb.failures(rows)


def test_betting_matches_the_predictions_page():
    calls = _priced(_calls("series", n=400, method="elo", major=False))
    rows, _ = cb.compare_betting(calls, calls.copy(), n_resamples=N)
    entries = [
        {
            "matched": True,
            "winner": 1 if r.won1 else 2,
            "method": "elo",
            "home1": "LFL",
            "start": "2026-01-01T12:00Z",
            "market_12h": {"ours": r.p, "ask1": r.cost1, "ask2": r.cost2},
            "market": {"p": r.market_close, "at": "2026-01-01T11:00Z"},
        }
        for r in calls.itertuples()
    ]
    page = [
        x
        for x in cb.schedule.edge_record(entries, rate=cb.BET_RATE)
        if (x["label"], x["source"]) == ("Other", "saved")
    ]
    ours = [r for r in rows if r["slice"] == "All"]
    for mine, theirs in zip(ours, page, strict=True):
        assert mine["edge"] == theirs["edge"]
        assert mine["bets"][1] == theirs["bets"]
        assert np.isclose(mine["roi"][1], theirs["roi"])
        assert np.isclose(mine["clv"][1], theirs["clv"])
        assert np.isclose(mine["beat"][1], theirs["beat"])


def test_betting_old_base_borrows_prices_and_none_skips(tmp_path):
    head = _priced(_calls("series", n=600))
    old = head.drop(columns=cb.PRICE_COLUMNS).assign(p=lambda d: 1 - d["p"])
    rows, note = cb.compare_betting(old, head, n_resamples=N)
    assert note is None and rows[0]["bets"][0] > 0
    rows, note = cb.compare_betting(old, old.copy(), n_resamples=N)
    assert rows == [] and note.startswith("Betting: neither dump")

    for side, frame in (("base", old), ("head", head)):
        (tmp_path / side / "markets").mkdir(parents=True)
        frame.to_csv(tmp_path / side / "markets" / "calls.csv.gz", index=False)
    sections, notes = cb.compare_dirs(tmp_path / "base", tmp_path / "head", N)
    assert [t for t, _ in sections] == ["Markets", "Betting"]
    report = cb.render(sections, notes)
    assert "#### Betting (report only)" in report
    assert "| All (600) | Any |" in report
    # Betting rows never change the verdict or the exit code.
    markets = dict(sections)["Markets"]
    assert cb.failures([r for _, part in sections for r in part]) == cb.failures(
        markets
    )


def test_floating_point_noise_is_within_noise():
    assert cb._verdict(1e-15, 3e-15, lower_is_better=True) == "within noise"
    assert cb._verdict(-3e-15, -1e-15, lower_is_better=True) == "within noise"
    assert cb._verdict(1e-4, 3e-4, lower_is_better=True) == "worse"
    assert cb._verdict(-3e-4, -1e-4, lower_is_better=True) == "better"


def _prop_scores(shift=0.0, n=3000, seed=0):
    rng = np.random.default_rng(seed)
    loss = rng.gamma(4.0, 0.5, n)
    return pd.DataFrame(
        {
            "measure": "map kills",
            "unit": [f"g{i}|p" for i in range(n)],
            "match": [f"m{i // 10}" for i in range(n)],
            "loss": loss + shift,
        }
    )


def test_props_worse_scores_fail_and_same_scores_pass():
    same = cb.compare_props(_prop_scores(), _prop_scores(), N)
    assert same[0]["result"] == "within noise"
    worse = cb.compare_props(_prop_scores(), _prop_scores(shift=0.05), N)
    assert worse[0]["result"] == "worse" and worse[0]["guarded"]
    assert cb.failures(worse)
    # A measure only one side has is reported, not compared.
    head = pd.concat(
        [_prop_scores(), _prop_scores().assign(measure="Bo5 maps 1-3 kills")]
    )
    rows = cb.compare_props(_prop_scores(), head, N)
    assert [r["result"] for r in rows] == ["not paired", "within noise"]


def _live_calls(shift=0.0, seed=0):
    """In-game calls on 120 maps (40 series) at the seven checkpoints."""
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(120):
        won = int(rng.random() < 0.5)
        for minute in (0, 5, 10, 15, 20, 25, 30):
            p = np.clip(0.5 + (0.3 if won else -0.3) * minute / 30, 0.05, 0.95)
            p = np.clip(
                p + rng.normal(0, 0.05) - (shift if won else -shift), 0.01, 0.99
            )
            rows.append(
                {
                    "game": f"g{g}",
                    "series": f"s{g // 3}",
                    "checkpoint": minute,
                    "ours": p,
                    "kalshi": 0.5,
                    "won": won,
                }
            )
    return pd.DataFrame(rows)


def test_live_worse_calls_fail_by_band_and_same_calls_pass():
    same = cb.compare_live(_live_calls(), _live_calls(), N)
    assert [r["name"].split(" (")[0] for r in same] == [
        "log loss, pregame",
        "log loss, early",
        "log loss, mid",
        "log loss, late",
        "log loss, all",
    ]
    assert all(r["result"] == "within noise" and r["guarded"] for r in same)
    worse = cb.compare_live(_live_calls(), _live_calls(shift=0.1), N)
    assert {r["result"] for r in worse} == {"worse"} and cb.failures(worse)
    # Only one band worse still fails the check.
    head = _live_calls()
    late = head["checkpoint"] >= 25
    head.loc[late, "ours"] = np.where(head.loc[late, "won"] == 1, 0.3, 0.7)
    rows = cb.compare_live(_live_calls(), head, N)
    assert [r["result"] for r in rows if "late" in r["name"]] == ["worse"]
    assert cb.failures(rows)
