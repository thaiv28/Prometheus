import pytest

from prometheus.ranking import get_glory_ranking
from prometheus.types import ALL_MAJOR_LEAGUES

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
    all_teams_df = get_glory_ranking(league=["LCS"], year=2017, minimum_matches=0)
    qualified_teams_df = get_glory_ranking(league=["LCS"], year=2017, minimum_matches=5)

    # Cloud9 Challenger played three games in LCS 2017 (the promotion series), so
    # it is ranked with no minimum and dropped with a minimum of five.
    assert not all_teams_df[all_teams_df["teamname"] == "Cloud9 Challenger"].empty
    assert qualified_teams_df[
        qualified_teams_df["teamname"] == "Cloud9 Challenger"
    ].empty
    assert set(qualified_teams_df["teamname"]) < set(all_teams_df["teamname"])
