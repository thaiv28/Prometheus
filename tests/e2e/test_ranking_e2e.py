import pandas as pd
import pytest

from prometheus.ranking import get_glory_ranking
from prometheus.types import ALL_MAJOR_LEAGUES
from prometheus.utils import get_engine

pytestmark = pytest.mark.e2e


def test_glory_custom_leagues_e2e():
    custom_league_df = get_glory_ranking(
        league=["LCK", "LPL"], year=2022, minimum_matches=5
    )
    major_league_df = get_glory_ranking(
        league=ALL_MAJOR_LEAGUES, year=2022, minimum_matches=5
    )

    assert not custom_league_df.empty
    assert all(custom_league_df["league"].isin(["LCK", "LPL"]))
    # The model is always fit on every major league, so asking for fewer leagues
    # only filters the rows: LCK and LPL teams keep their scores and order.
    in_custom = major_league_df[major_league_df["league"].isin(["LCK", "LPL"])]
    assert in_custom.reset_index(drop=True).equals(custom_league_df)


def test_glory_min_matches_e2e():
    # Set the minimum just above the fewest LCS games any team played in 2017:
    # those teams are ranked with no minimum and dropped with it; the rest stay.
    games = pd.read_sql(
        "SELECT teamname, COUNT(*) AS n FROM matches"
        " WHERE league = 'LCS' AND year = 2017 GROUP BY teamname",
        get_engine(),
    ).set_index("teamname")["n"]
    minimum = int(games.min()) + 1
    few, many = games[games < minimum].index, games[games >= minimum].index
    assert len(many)
    all_teams_df = get_glory_ranking(league=["LCS"], year=2017, minimum_matches=0)
    qualified_teams_df = get_glory_ranking(
        league=["LCS"], year=2017, minimum_matches=minimum
    )

    assert set(few) <= set(all_teams_df["teamname"])
    assert not set(few) & set(qualified_teams_df["teamname"])
    assert set(many) <= set(qualified_teams_df["teamname"])
    assert set(qualified_teams_df["teamname"]) < set(all_teams_df["teamname"])
