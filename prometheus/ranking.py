from prometheus.regression import _fit_glory_model
from prometheus.matches import get_team_averages_frame
from prometheus.types import GLORY_FEATURES


def get_glory_ranking(
    features=None, year=None, league=None, rescale=True, baseline=False
):
    if features is None:
        features = GLORY_FEATURES

    pipeline, _, _ = _fit_glory_model(features, league=league, year=year)

    # get average stats for each team in a year
    averages = get_team_averages_frame(
        "match_glory_stats", filters={"year": year, "league": league}
    )

    if not baseline:
        # predict scores for each team using the regression model
        scores = pipeline.predict(averages[features])
    else:
        # scale scores using only the StandardScaler step of the pipeline, then weight all features equally
        scaled_df = pipeline.steps[0][1].transform(averages[features])
        scores = scaled_df.sum(axis=1)
        # Normalize to 0-1. Necessary since sum is not necessarily in 0-1 range, unlike regression output
        scores = (scores - scores.min()) / (scores.max() - scores.min())

    # Create a DataFrame with teamname and scores
    ranking_df = averages[["teamname"]].copy()
    ranking_df["score"] = scores

    # Sort teams from highest to lowest score
    ranking_df = ranking_df.sort_values("score", ascending=False).reset_index(drop=True)
    if rescale:
        ranking_df["score"] = _rescale(ranking_df["score"], (0, 100))

    return ranking_df


def _rescale(series, scale):
    """Rescales a pandas Series to a given range."""
    series = scale[0] + series * (scale[1] - scale[0])
    return series


if __name__ == "__main__":
    df = get_glory_ranking(
        year=2018, league=["LPL", "LCK", "EU LCS", "NA LCS"], baseline=True
    )
    print(df)
