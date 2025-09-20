import pandas as pd

from prometheus.regression import _fit_glory_model
from prometheus.matches import get_team_averages_frame
from prometheus.types import GLORY_FEATURES, ALL_MAJOR_LEAGUES


def get_glory_ranking(
    features=None,
    year=None,
    league=None,
    rescale=True,
    baseline=False,
    z_scores=False,
    cols_to_return=None,
):
    if features is None:
        features = GLORY_FEATURES

    if cols_to_return is None:
        cols_to_return = ["teamname", "score", "year", "league"]
    else:
        cols_to_return = list(set(cols_to_return + ["teamname"]))

    if year is None:
        years = [2025]
    elif isinstance(year, (list, tuple, set)):
        years = list(year)
    else:
        years = [year]

    all_rankings = []
    # we have to fit the glory model separately for each year
    for yr in years:
        # we always want to model off all major leagues, then filter down to requested league later
        pipeline, _, _ = _fit_glory_model(features, league=ALL_MAJOR_LEAGUES, year=yr)

        averages = get_team_averages_frame(
            "match_glory_stats", filters={"year": yr, "league": league}
        )

        if not baseline:
            scores = pipeline.predict(averages[features])
        else:
            # Rescale to 0-1 because baseline (GLORB) does not ensure 0-1 range like regression output
            scaled_df = pipeline.steps[0][1].transform(averages[features])
            scores = scaled_df.sum(axis=1)
            scores = (scores - scores.min()) / (scores.max() - scores.min())

        averages["score"] = scores
        ranking_df = averages[cols_to_return]
        ranking_df = ranking_df.sort_values("score", ascending=False).reset_index(
            drop=True
        )

        # rescale to 0-100 for easier interpretability
        if rescale:
            ranking_df["score"] = ranking_df["score"] * 100

        ranking_df = _filter_leagues(ranking_df, league)
        all_rankings.append(ranking_df)

    # combine individual year rankings into combined ranking
    combined_df = pd.concat(all_rankings, ignore_index=True)
    combined_df = combined_df.sort_values("score", ascending=False).reset_index(
        drop=True
    )
    return combined_df


def _filter_leagues(df, leagues):
    if leagues is None:
        return df
    if not isinstance(leagues, (list, tuple, set)):
        leagues = [leagues]
    return df[df["league"].isin(leagues)]


if __name__ == "__main__":
    df = get_glory_ranking(
        year=2018, league=["LPL", "LCK", "EU LCS", "NA LCS"], baseline=True
    )
    print(df)
