from prometheus.ranking import get_glory_ranking
from prometheus.types import ALL_MAJOR_LEAGUES


def test_glory_custom_leagues_e2e():
    custom_league_df = get_glory_ranking(league=["LCK", "LPL"], year=2022, minimum_matches=5)
    major_league_df = get_glory_ranking(league=ALL_MAJOR_LEAGUES, year=2022, minimum_matches=5)

    assert all(custom_league_df["league"].isin(["LCK", "LPL"]))
    # should be GEN.G and T1 for top of 2022 in both cases
    assert major_league_df.iloc[0].equals(custom_league_df.iloc[0])
    assert major_league_df.iloc[1].equals(custom_league_df.iloc[1])
    
    
def test_glory_min_matches_e2e():
    all_teams_df = get_glory_ranking(league=['LCS'], minimum_matches=0)
    qualified_teams_df = get_glory_ranking(league=['LCS'], minimum_matches=5)

    # when minimum matches is 5, we shouldn't have Cloud9 Challengers in the list
    assert not all_teams_df.iloc[0].equals(qualified_teams_df.iloc[0])
    assert not all_teams_df[all_teams_df['teamname'] == 'Cloud9 Challenger'].empty
    assert qualified_teams_df[qualified_teams_df['teamname'] == 'Cloud9 Challenger'].empty
