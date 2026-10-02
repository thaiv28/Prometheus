import pandas as pd
import pytest

from prometheus.glorelo import CENTER, glorelo_ratings, win_probability


def _inputs():
    glory_plus = pd.DataFrame(
        {
            "teamname": ["A", "B", "C"],
            "league": ["LCK", "LPL", "LCS"],
            "year": 2026,
            "score": [80.0, 60.0, 40.0],
        }
    )
    elos = pd.DataFrame(
        {
            "teamname": ["A", "B", "C", "D"],
            "elo": [1700.0, 1600.0, 1450.0, 1500.0],
            "latest_date": ["2026-09-01"] * 4,
        }
    )
    return glory_plus, elos


def test_ratings_are_centred_and_ordered():
    df = glorelo_ratings(*_inputs())
    # D has an Elo but no GLORY+ this season, so it is left out.
    assert df["teamname"].tolist() == ["A", "B", "C"]
    assert df["glorelo"].mean() == pytest.approx(CENTER)


def test_win_probability_is_symmetric_and_elo_scaled():
    assert win_probability(1500, 1500) == pytest.approx(0.5)
    assert win_probability(1600, 1500) == pytest.approx(0.64, abs=0.005)
    assert win_probability(1600, 1500) + win_probability(1500, 1600) == pytest.approx(1)


def test_rating_gap_matches_the_fitted_log_odds():
    from prometheus.glorelo import ELO_WEIGHT, GLORY_PLUS_WEIGHT
    import math

    df = glorelo_ratings(*_inputs()).set_index("teamname")
    log_odds = GLORY_PLUS_WEIGHT * (80 - 60) + ELO_WEIGHT * (1700 - 1600)
    p = win_probability(df.loc["A", "glorelo"], df.loc["B", "glorelo"])
    assert p == pytest.approx(1 / (1 + math.exp(-log_odds)))
