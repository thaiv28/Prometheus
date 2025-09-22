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
    z_scores=True,
    cols_to_return=None,
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
        pipeline, _, _ = _fit_glory_model(features, league=ALL_MAJOR_LEAGUES, year=yr)

        averages = get_team_averages_frame(
            "match_glory_stats",
            minimum_matches=minimum_matches,
            filters={"year": yr, "league": league},
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
        
        if z_scores:
            ranking_df["era_score"] = (
                (ranking_df["score"] - ranking_df["score"].mean())
                / ranking_df["score"].std()
            )
            
            # Group by league and calculate z-scores within each league
            ranking_df["league_score"] = ranking_df.groupby("league")["score"].transform(
                lambda x: (x - x.mean()) / x.std()
            )
        
        # rescale to 0-100 for easier interpretability
        if rescale:
            ranking_df["score"] = ranking_df["score"] * 100

        score_cols = ["score", "era_score", "league_score"] if z_scores else ["score"]
        ranking_df[score_cols] = ranking_df[score_cols].round(2)
        
        

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
