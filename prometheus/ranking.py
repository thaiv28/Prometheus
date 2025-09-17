from prometheus.regression import fit_lore_model
from prometheus.matches import get_team_averages_frame


def get_lore_ranking(year=None, league=None):
    pipeline, _, _ = fit_lore_model(league=league, year=year)

    # get average stats for each team in a year
    averages = get_team_averages_frame(
        "match_lore_stats", filters={"year": year, "league": league}
    )

    # Drop teamname before applying pipeline
    features = averages.drop(columns=["teamname"])
    scores = pipeline.predict(features)

    # Create a DataFrame with teamname and scores
    ranking_df = averages[["teamname"]].copy()
    ranking_df["score"] = scores

    # Sort teams from highest to lowest score
    ranking_df = ranking_df.sort_values("score", ascending=False).reset_index(drop=True)

    return ranking_df


if __name__ == "__main__":
    df = get_lore_ranking(year=2018, league=["LPL", "LCK"])
    print(df)
