import math

import pandas as pd
import pytest

from prometheus import forge


def test_ratings_are_elo_plus_form_points():
    forms = pd.DataFrame({"teamname": ["A", "B", "C"], "home": ["LCK", "LCK", "LCS"], "form": [0.5, -0.5, 0.0], "year": 2026,
                          "latest_date": "2026-09-01"})
    elos = pd.DataFrame({"teamname": ["A", "B", "C", "D"], "elo": [1700.0, 1600.0, 1450.0, 1500.0]})
    df = forge.forge_ratings(forms, elos).set_index("teamname")
    # D has an Elo but no Form, so it is left out.
    assert sorted(df.index) == ["A", "B", "C"]
    assert df.loc["A", "forge"] == pytest.approx(1700 + 0.5 * forge.FORM_POINTS)
    assert df.loc["C", "league"] == "LCS"


def test_same_league_odds_come_from_the_rating_gap():
    a, b = 1650.0, 1550.0
    p = forge.win_probability(a, b)
    assert p == pytest.approx(1 / (1 + math.exp(-forge.ELO_WEIGHT * 100)))
    assert forge.win_probability(b, a) == pytest.approx(1 - p)
    assert forge.win_probability(1500, 1500) == pytest.approx(0.5)


def test_cross_league_odds_use_elo_only():
    p = forge.win_probability(1900, 1500, same_league=False, elo=1600, opponent_elo=1600)
    assert p == pytest.approx(0.5)


def test_weights_round_trip_and_changes(tmp_path):
    path = tmp_path / "weights.json"
    forge.save_weights({"elo_weight": 0.0030000049, "form_weight": 0.7}, path)
    weights = forge.load_weights(path)
    assert weights == {"elo_weight": 0.003, "form_weight": 0.7}
    changes = forge.weight_changes(weights, {"elo_weight": 0.0033, "form_weight": 0.665})
    assert changes["elo_weight"] == pytest.approx(0.10)
    assert changes["form_weight"] == pytest.approx(0.05)


def test_tracked_weights_are_loaded():
    weights = forge.load_weights()
    assert forge.ELO_WEIGHT == weights["elo_weight"] > 0
    assert forge.FORM_WEIGHT == weights["form_weight"] > 0
    assert forge.CROSS_REGION_ELO_WEIGHT == weights["cross_region_elo_weight"] > 0
