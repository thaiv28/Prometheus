import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from prometheus.elo import (
    calculate_game_length_elo_change,
    compute_elo_records,
    winner_score,
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "research"))
_spec = importlib.util.spec_from_file_location(
    "elo_variants", ROOT / "scripts" / "research" / "elo_variants.py"
)
ev = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ev)


def _games():
    """Six games between three teams in two leagues and one international game."""
    rows = [
        ("g1", "a", "b", 1500, 1, "LCK", "2024-01-01"),
        ("g2", "a", "b", 2400, 0, "LCK", "2024-01-02"),
        ("g3", "c", "d", 1700, 1, "LEC", "2024-01-03"),
        ("g4", "a", "c", 2000, 1, "MSI", "2024-01-04"),
        ("g5", "b", "d", 3000, 0, "MSI", "2024-01-05"),
        ("g6", "a", "b", 1200, 1, "LCK", "2024-01-06"),
    ]
    games = pd.DataFrame(rows, columns=ev.ELO_COLUMNS)
    games["w_totalgold"] = [60000, 70000, np.nan, 65000, 62000, 50000]
    games["l_totalgold"] = [50000, 66000, np.nan, 64000, 52000, 38000]
    return games


def _inputs(rosters=None):
    return SimpleNamespace(games=_games(), rosters=rosters or {})


@pytest.mark.parametrize("result", [0, 1])
@pytest.mark.parametrize("length", [900, 1800, 3000])
def test_margin_change_matches_game_length_change(result, length):
    score = winner_score(length)
    assert ev.margin_elo_change(1620, 1540, score, result) == pytest.approx(
        calculate_game_length_elo_change(1620, 1540, length, result)
    )
    # K scales the change.
    assert ev.margin_elo_change(1620, 1540, score, result, K=40) == pytest.approx(
        2 * calculate_game_length_elo_change(1620, 1540, length, result)
    )


def test_loser_gets_complement_of_winner_score():
    win = ev.margin_elo_change(1500, 1600, 0.9, 1)
    loss = ev.margin_elo_change(1600, 1500, 0.9, 0)
    assert loss == pytest.approx(-win)


def test_replay_with_game_length_margin_reproduces_published_elo():
    rosters = {
        ("g1", "a"): ("p1", "p2"),
        ("g1", "b"): ("p3", "p4"),
        ("g6", "a"): ("p1", "p5"),
    }
    inputs = _inputs(rosters)
    pre = ev.replay(inputs, ev.game_length_margin())
    published, _ = compute_elo_records(
        _games()[ev.ELO_COLUMNS], calculate_game_length_elo_change, rosters=rosters
    )
    expected = published.set_index(["gameid", "teamid"])["pre_match_elo"]
    assert np.abs(pre.to_numpy() - expected.to_numpy()).max() < 1e-9
    assert list(pre.index) == list(expected.index)


def test_bigger_margin_moves_ratings_more():
    inputs = _inputs()
    small = ev.replay(inputs, lambda g: np.full(len(g), 0.6), records=True)
    big = ev.replay(inputs, lambda g: np.full(len(g), 1.0), records=True)
    assert big["elo_change"].iloc[0] > small["elo_change"].iloc[0] > 0


def test_replay_passes_k_and_compute_kwargs():
    inputs = _inputs()
    k20 = ev.replay(inputs, ev.game_length_margin(), records=True)
    k40 = ev.replay(inputs, ev.game_length_margin(), K=40, records=True)
    assert k40["elo_change"].iloc[0] == pytest.approx(2 * k20["elo_change"].iloc[0])
    no_share = ev.replay(
        inputs, ev.game_length_margin(), league_share=0.0, records=True
    )
    assert (no_share["league_offset"] == 0).all()


@pytest.mark.parametrize("bad", [0.5, 1.01, np.nan, 0.2])
def test_replay_rejects_scores_outside_range(bad):
    def margin(g):
        s = np.full(len(g), 0.8)
        s[2] = bad
        return s

    with pytest.raises(ValueError, match="outside"):
        ev.replay(_inputs(), margin)


def test_replay_rejects_wrong_length():
    with pytest.raises(ValueError, match="scores for"):
        ev.replay(_inputs(), lambda g: np.full(3, 0.8))


def test_fallback_fills_missing_stats_with_game_length_score():
    games = _games()
    gap = lambda g: ev.bounded(g["w_totalgold"] - g["l_totalgold"], 5000)
    s = ev.with_fallback(gap)(games)
    assert not np.isnan(s).any()
    assert s[2] == pytest.approx(winner_score(1700))
    assert s[0] == pytest.approx(ev.bounded(10000, 5000))


def test_bounded_stays_in_range_and_rises():
    x = np.array([-1e6, -5000, 0, 5000, 1e6])
    s = ev.bounded(x, 3000, lower=0.6, upper=0.95)
    assert (s >= 0.6).all() and (s <= 0.95).all()
    assert (np.diff(s) > 0).all()
    assert s[2] == pytest.approx(0.775)


def test_per_row_matches_vectorised():
    games = _games()
    row_fn = ev.per_row(lambda r: float(winner_score(r["gamelength"])))
    assert np.allclose(row_fn(games), ev.game_length_margin()(games))


def test_clean_stats_marks_filled_values_missing():
    stats = pd.DataFrame({stat: [3, 2.5, 0] for stat in ev.STATS})
    stats["visionscore"] = [0, 120, 98.4]
    clean = ev.clean_stats(stats)
    assert (
        clean["kills"].tolist()[0] == 3
        and np.isnan(clean["kills"][1])
        and clean["kills"][2] == 0
    )
    assert (
        np.isnan(clean["visionscore"][0])
        and clean["visionscore"][1] == 120
        and np.isnan(clean["visionscore"][2])
    )


def test_pregame_elos_has_both_sides():
    inputs = _inputs()
    pre = ev.replay(inputs, ev.game_length_margin())
    rows = ev.pregame_elos(inputs, pre)
    assert len(rows) == 2 * len(inputs.games)
    g4 = rows[rows["gameid"] == "g4"].set_index("teamid")
    assert g4.loc["a", "opp_elo"] == g4.loc["c", "elo"]


def test_split_years():
    train, test = ev.split_years([2016, 2014, 2021, 2022, 2026, 2022])
    assert train == [2014, 2016, 2021] and test == [2022, 2026]
    with pytest.raises(ValueError):
        ev.split_years([2014, 2015])


def test_param_grid():
    grid = ev.param_grid({"scale": [1, 2], "K": [20, 30]})
    assert len(grid) == 4 and {"scale": 2, "K": 30} in grid
    assert ev.param_grid([{"scale": 1}]) == [{"scale": 1}]
    assert ev._split_params({"scale": 1, "K": 30}) == ({"scale": 1}, {"K": 30})


def _fake_scores(years, loss_by_year):
    """Scores with one domestic game per year and a fixed log loss."""
    games = pd.DataFrame(
        {
            "gameid": [f"g{y}" for y in years],
            "year": years,
            "league": "LCK",
            "test_set": "Domestic",
            "won": 1,
        }
    )
    losses = pd.DataFrame(
        {"accuracy": 1.0, "brier": 0.1, "log_loss": [loss_by_year(y) for y in years]}
    )
    return ev.Scores(games, {"elo_live": losses, "forge": losses})


def test_tuning_sees_train_years_only_and_reports_on_test(monkeypatch):
    seen_years = []

    def fake_replay(inputs, margin_fn, **kw):
        return pd.Series([margin_fn(None)])  # the "Elo" is just the margin's parameter

    def fake_score(inputs, pre, years=None, forge=True):
        seen_years.append(list(years))
        scale = pre.iloc[0]
        # Scale 2 is best on early years, scale 3 on late ones: tuning must pick 2.
        return _fake_scores(years, lambda y: abs(scale - (2 if y <= 2021 else 3)) + 0.5)

    monkeypatch.setattr(ev, "replay", fake_replay)
    monkeypatch.setattr(ev, "score", fake_score)
    frame = pd.DataFrame({"year": [2019, 2020, 2021, 2022, 2023]})
    inputs = ev.Inputs(
        games=None,
        rosters={},
        frame=frame,
        form_games=None,
        db_pre_match=None,
        db_domestic=(),
    )
    inputs.cache["baseline"] = pd.Series([3.0])
    result = ev.held_out(
        inputs,
        lambda scale: lambda g: scale,
        {"scale": [1, 2, 3]},
        "toy",
        verbose=False,
    )

    assert result.params == {"scale": 2}
    assert result.train_years == [2019, 2020, 2021] and result.test_years == [
        2022,
        2023,
    ]
    assert seen_years[:3] == [[2019, 2020, 2021]] * 3  # every tuning run
    assert all(y == [2022, 2023] for y in seen_years[3:])  # variant and baseline
    assert result.tuning["objective"].is_monotonic_increasing
    # Variant (scale 2) loses 1.0 per test game against the baseline's 0.5.
    assert "1.5000 (+1.0000" in result.row


def test_compare_needs_same_games():
    a = _fake_scores([2022, 2023], lambda y: 0.6)
    b = _fake_scores([2022, 2024], lambda y: 0.5)
    with pytest.raises(ValueError, match="different games"):
        ev.deltas(a, b)


def test_compare_row_shows_variant_minus_baseline():
    base = _fake_scores([2022, 2023, 2024], lambda y: 0.6)
    better = _fake_scores([2022, 2023, 2024], lambda y: 0.5)
    row = ev.compare(None, base, better, "better")
    assert row.startswith("| better | 0.5000 (-0.1000, -0.1000 to -0.1000)")
    assert row.count("|") == ev.COMPARE_HEADER.splitlines()[0].count("|")
