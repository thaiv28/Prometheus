from prometheus.ranking import get_glory_ranking
from prometheus.types import ALL_MAJOR_LEAGUES


def test_glory_custom_leagues_e2e():
    custom_league_df = get_glory_ranking(league=["LCK", "LPL"], year=2022)
    major_league_df = get_glory_ranking(league=ALL_MAJOR_LEAGUES, year=2022)

    assert all(custom_league_df["league"].isin(["LCK", "LPL"]))
    # should be GEN.G and T1 for top of 2022 in both cases
    assert major_league_df.iloc[0].equals(custom_league_df.iloc[0])
    assert major_league_df.iloc[1].equals(custom_league_df.iloc[1])
