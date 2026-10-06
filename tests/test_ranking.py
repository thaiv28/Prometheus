from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from prometheus.ranking import adjust_for_opponent_elo


def _games(n=40, seed=0):
    rng = np.random.default_rng(seed)
    elo = rng.uniform(1400, 1700, n)
    opp_elo = rng.uniform(1400, 1700, n)
    return pd.DataFrame(
        {
            "gameid": [f"g{i}" for i in range(n)],
            "teamid": [f"t{i}" for i in range(n)],
            "year": 2024,
            # Exactly linear in both ratings: strong teams and weak opponents both help.
            "gpm": 1000 + 0.5 * elo - 0.3 * opp_elo,
        }
    ), pd.DataFrame(
        {
            "gameid": [f"g{i}" for i in range(n)],
            "teamid": [f"t{i}" for i in range(n)],
            "elo": elo,
            "opp_elo": opp_elo,
        }
    )


@patch("prometheus.ranking.get_pregame_elos")
def test_adjustment_removes_opponent_effect_only(mock_elos):
    games, elos = _games()
    mock_elos.return_value = elos

    adjusted = adjust_for_opponent_elo(games, ["gpm"])

    # Every game is restated against the average opponent; the team's own
    # strength still shows.
    expected = 1000 + 0.5 * elos["elo"] - 0.3 * elos["opp_elo"].mean()
    assert adjusted["gpm"].to_numpy() == pytest.approx(expected.to_numpy())
    # Centring on the average opponent keeps the overall mean unchanged.
    assert adjusted["gpm"].mean() == pytest.approx(games["gpm"].mean())


@patch("prometheus.ranking.get_pregame_elos")
def test_adjustment_rewards_strong_schedule(mock_elos):
    games, elos = _games()
    mock_elos.return_value = elos

    adjusted = adjust_for_opponent_elo(games, ["gpm"])

    hardest = elos["opp_elo"].idxmax()
    easiest = elos["opp_elo"].idxmin()
    assert adjusted.loc[hardest, "gpm"] > games.loc[hardest, "gpm"]
    assert adjusted.loc[easiest, "gpm"] < games.loc[easiest, "gpm"]


def test_record_adjustment_removes_full_season_opponent_effect():
    from prometheus.ranking import adjust_for_opponent_record

    rng = np.random.default_rng(1)
    teams = [f"t{i}" for i in range(12)]
    rating = dict(zip(teams, rng.normal(0, 1, len(teams))))
    rows = []
    for g in range(200):
        a, b = rng.choice(teams, 2, replace=False)
        for team, opp in ((a, b), (b, a)):
            rows.append({"gameid": f"g{g}", "teamid": team, "year": 2024,
                         "gpm": 1800 + 60 * rating[team] - 40 * rating[opp]})
    games = pd.DataFrame(rows)
    record = pd.DataFrame({"teamid": teams, "year": 2024, "rating": [rating[t] for t in teams]})

    adjusted = adjust_for_opponent_record(games, ["gpm"], record)

    assert len(adjusted) == len(games)
    opp_mean = adjusted["opp_rating"].mean()
    expected = 1800 + 60 * adjusted["rating"] - 40 * opp_mean
    assert adjusted["gpm"].to_numpy() == pytest.approx(expected.to_numpy())


def test_glory_skips_a_season_with_no_qualified_team():
    # Oracle's Elixir files the first games of next year's season early: a year
    # with a handful of games has no team-season to rank yet.
    from prometheus.ranking import get_glory_ranking

    rng = np.random.default_rng(2)

    def season(year, teams, games_each):
        rows = [{"gameid": f"{year}-{t}-{g}", "teamid": t, "teamname": t, "year": year, "league": "LCS",
                 "gpm": rng.normal(1800, 50), "result": int(rng.integers(0, 2))}
                for t in teams for g in range(games_each)]
        return pd.DataFrame(rows)

    games = {2026: season(2026, ["A", "B", "C", "D"], 6), 2027: season(2027, ["A", "B"], 2)}
    ranking = get_glory_ranking(features=["gpm"], year=[2026, 2027], league="LCS", minimum_matches=5, games=games)
    assert set(ranking["year"]) == {2026} and len(ranking) == 4
