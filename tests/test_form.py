import numpy as np
import pandas as pd
import pytest

from prometheus import form


def _games(rows):
    """rows: (date, year, league, teamid, gpm). One stat, each row its own game."""
    df = pd.DataFrame(rows, columns=["date", "year", "league", "teamid", "gpm"])
    return df.assign(
        gameid=[f"g{i}" for i in range(len(df))], teamname=df["teamid"], result=1
    )


def test_states_start_average_shrink_and_decay():
    rows = [("2024-01-01", 2024, "LCK", "Z", 1000.0)]  # sets the season's average
    rows += [(f"2024-01-{d:02d}", 2024, "LCK", "A", 2000.0) for d in range(2, 12)]
    games = _games(rows)
    states = form.form_states(games, ["gpm"], half_life=1e9, carry=0.5, prior_games=5)
    a = states[states["teamid"] == "A"]
    # First game: no history, so the team is the season's average so far (Z's game).
    assert a["pre_gpm"].iloc[0] == pytest.approx(1000.0)
    # After n games of 2000 with 5 prior games at the running average, the state
    # moves toward 2000 and never passes it.
    assert a["pre_gpm"].is_monotonic_increasing
    assert a["pre_gpm"].iloc[-1] < 2000
    assert a["form_games"].iloc[-1] == pytest.approx(9)


def test_new_season_carries_part_of_the_weight():
    rows = [(f"2024-01-{d:02d}", 2024, "LCK", "A", 2000.0) for d in range(1, 11)]
    rows += [("2025-01-01", 2025, "LCK", "A", 2000.0)]
    states = form.form_states(
        _games(rows), ["gpm"], half_life=1e9, carry=0.5, prior_games=5
    )
    assert states["form_games"].iloc[-1] == pytest.approx(5.0)


def test_home_league_ignores_international_events():
    rows = [
        ("2024-01-01", 2024, "LCK", "A", 1.0),
        ("2024-05-01", 2024, "MSI", "A", 1.0),
    ]
    states = form.form_states(_games(rows), ["gpm"])
    assert states["home"].tolist() == ["LCK", "LCK"]


def test_league_relative_subtracts_the_league_average_so_far():
    states = pd.DataFrame(
        {
            "home": ["LCK", "LCK", "LCS", "LCK"],
            "year": 2024,
            "date": ["2024-01-01", "2024-01-01", "2024-01-01", "2024-01-02"],
        }
    )
    rel = form.league_relative(states, np.array([2.0, 0.0, 5.0, 4.0]))
    # Day 1 LCK mean is 1; day 2 LCK mean over all three LCK states is 2.
    assert rel.tolist() == pytest.approx([1.0, -1.0, 0.0, 2.0])


def test_opponent_adjust_uses_earlier_seasons():
    rng = np.random.default_rng(0)
    rows = []
    for year in (2023, 2024):
        for g in range(200):
            rows.append((f"{year}-03-01", year, "LCK", f"t{g}", 0.0))
    games = _games(rows)
    elos = pd.DataFrame(
        {
            "gameid": games["gameid"],
            "teamid": games["teamid"],
            "elo": rng.normal(1500, 100, len(games)),
            "opp_elo": rng.normal(1500, 100, len(games)),
        }
    )
    games["gpm"] = 2000 - 2.0 * elos["opp_elo"] + 1.0 * elos["elo"]
    adjusted = form.opponent_adjust(games, ["gpm"], elos)
    # The opponent term is removed: what is left depends on the team's own Elo only.
    resid = adjusted["gpm"] - 1.0 * elos["elo"]
    assert resid.std() == pytest.approx(0, abs=1e-6)


def test_home_league_is_the_most_played_this_season():
    rows = [(f"2024-01-{d:02d}", 2024, "LPL", "A", 1.0) for d in range(1, 6)]
    rows += [
        ("2024-12-01", 2024, "DCup", "A", 1.0),
        ("2025-01-01", 2025, "MSI", "A", 1.0),
    ]
    states = form.form_states(_games(rows), ["gpm"])
    # A winter cup does not move it; before its first 2025 domestic game it keeps LPL.
    assert states["home"].tolist() == ["LPL"] * 7
