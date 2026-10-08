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
    new = [r for r in rows if r["name"] == "new"][0]
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
    split = [r for r in rows if r["name"].startswith("glory split")][0]
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
