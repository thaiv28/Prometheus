import pandas as pd

from prometheus.regression import _fit_glory_model
from prometheus.matches import get_team_averages_frame
from prometheus.types import GLORY_FEATURES, ALL_MAJOR_LEAGUES, ScoreCols
from prometheus import utils

def get_glory_ranking(
    features=None,
    year=None,
    league=None,
    rescale=True,
    baseline=False,
    z_scores=False,
    cols_to_return=None,
    sort_by="score",
    minimum_matches=0,
):
    """Compute GLORY (or GLORB baseline) team rankings.

    Fits the GLORY regression model separately for each requested year (always
    using all major leagues for modeling), scores team season averages, then
    optionally filters to the leagues provided and concatenates yearly results.

    Parameters
    ----------
    features : list[str] | None, optional
        Feature columns to use. Defaults to `GLORY_FEATURES` when None.
    year : int | iterable[int] | None, optional
        Single year, multiple years, or None for all supported years.
    league : str | iterable[str] | None, optional
        League code(s) to include in final output; modeling always uses all major leagues.
    rescale : bool, default True
        If True, rescales raw model scores (or baseline sum) to 0–100.
    baseline : bool, default False
        If True, compute GLORB baseline (equal weights) instead of GLORY regression output.
    z_scores : bool, default True
        If True, adds `era_score` (overall z) and `league_score` (within-league z).
    cols_to_return : list[str] | None, optional
        Additional columns (besides teamname/score/year/league) to keep in output.
    minimum_matches : int, default 0
        Minimum number of matches required for a team-season to be included.

    Returns
    -------
    pandas.DataFrame
        Combined ranking across requested years, sorted by score descending. Columns include
        at least teamname, score, year, league, and optionally era_score / league_score when z_scores is True.
    """
    if features is None:
        features = GLORY_FEATURES

    if cols_to_return is None:
        cols_to_return = ["teamname", "score", "year", "league"]
    else:
        cols_to_return = list(set(cols_to_return + ["teamname"]))

    if year is None:
        years = [2014, 2015, 2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
    elif isinstance(year, (list, tuple, set)):
        years = list(year)
    else:
        years = [year]

    all_rankings = []
    # we have to fit the glory model separately for each year
    for yr in years:
        # we always want to model off all major leagues, then filter down to requested league later
        pipeline, _, _ = _fit_glory_model(features, leagues=ALL_MAJOR_LEAGUES, years=[yr])

        averages = get_team_averages_frame(
            "match_glory_stats",
            minimum_matches=minimum_matches,
            filters={"years": [yr], "leagues": league},
        )

        if not baseline:
            scores = pipeline.predict(averages[features])
        else:
            # GLORB baseline: equal weights for each feature
            scaled_df = pipeline.steps[0][1].transform(averages[features])
            raw = scaled_df.sum(axis=1)

            # 1. Standardize raw baseline scores
            mu = raw.mean()
            sigma = raw.std(ddof=0)
            if sigma == 0 or pd.isna(sigma):
                sigma = 1
            z = (raw - mu) / sigma

            # Baseline scaling: keep values on 0–1 so the later generic *100 produces ~0–100.
            target_mean = 0.8
            target_std = 0.15
            scores = target_mean + target_std * z

        averages["score"] = scores
        ranking_df = averages[cols_to_return]
        ranking_df = ranking_df.sort_values("score", ascending=False).reset_index(
            drop=True
        )
        
        if z_scores:
            overall_std = ranking_df["score"].std()
            if overall_std is None or pd.isna(overall_std) or overall_std == 0:
                overall_std = 1
            ranking_df["era_score"] = (
                ranking_df["score"] - ranking_df["score"].mean()
            ) / overall_std

            # Group by league and calculate z-scores within each league (safe divide)
            def _league_z(g):
                std = g.std()
                if std is None or pd.isna(std) or std == 0:
                    return (g - g.mean()) / 1
                return (g - g.mean()) / std

            ranking_df["league_score"] = ranking_df.groupby("league")[
                "score"
            ].transform(_league_z)

        # rescale to 0-100 for easier interpretability
        if rescale:
            ranking_df["score"] = ranking_df["score"] * 100

        score_cols = [col for col in ScoreCols.__members__ if col in ranking_df.columns]
        ranking_df[score_cols] = ranking_df[score_cols].round(2)

        ranking_df = _filter_leagues(ranking_df, league)
        all_rankings.append(ranking_df)

    # combine individual year rankings into combined ranking
    combined_df = pd.concat(all_rankings, ignore_index=True)
    combined_df = combined_df.sort_values(sort_by, ascending=False).reset_index(
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
