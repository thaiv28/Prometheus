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
