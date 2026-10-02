import pandas as pd
from sklearn.linear_model import LinearRegression

from prometheus.regression import fit_glory_pipeline
from prometheus.matches import (
    get_available_years,
    get_matches_frame,
    team_season_averages,
)
from prometheus.elo import get_pregame_elos
from prometheus.season import get_record, load_season_games
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
    opponent_adjusted=False,
    before=None,
    games=None,
    record=None,
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
        Single year, multiple years, or None for every year in the database.
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
    opponent_adjusted : {False, "record", "elo", True}, default False
        Adjust each game's stats to what they would have been against an average
        major-league opponent that year before averaging. "record" (GLORY on the
        site) measures opponents by their full-season Record, a hindsight season stat
        (see `adjust_for_opponent_record`). "elo" (or True) uses the opponent's
        pre-game Elo, the retired GLORY+ (see `adjust_for_opponent_elo`).
    before : str | datetime.date | None, optional
        If set, only games before this date are used, both to fit the yearly model and
        to average each team-season. Gives the metric as it stood on that date.
    games : dict[int, pandas.DataFrame] | None, optional
        Each year's major-league games from `load_glory_games` (same `before`), so
        callers that rank several ways (GLORY, GLORB, GLORY+) read each year once.
    record : pandas.DataFrame | None, optional
        `season.get_record` output (teamid, year, rating) for the "record"
        adjustment, computed with the same `before`. Fit here when None.

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
        years = get_available_years(ALL_MAJOR_LEAGUES)
    elif isinstance(year, (list, tuple, set)):
        years = list(year)
    else:
        years = [year]

    all_rankings = []
    # we have to fit the glory model separately for each year
    for yr in years:
        # we always want to model off all major leagues, then filter down to requested league later
        year_games = games[yr] if games is not None else _major_league_games(yr, before)
        pipeline = fit_glory_pipeline(year_games, features)

        if opponent_adjusted == "record":
            if record is None:
                record = get_record(load_season_games(years=years, before=before))
            year_games = adjust_for_opponent_record(year_games, features, record)
        elif opponent_adjusted:
            # Adjustment coefficients come from every major-league game that year.
            year_games = adjust_for_opponent_elo(year_games, features)
        elif not _only_major_leagues(league):
            year_games = get_matches_frame(
                "match_glory_stats",
                filters={"years": [yr], "leagues": league, "before": before},
            )
        averages = team_season_averages(
            _filter_leagues(year_games, league), minimum_matches
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
    # Scores are rounded, so ties are common; break them by year for a stable order.
    combined_df = combined_df.sort_values(
        [sort_by, "year"], ascending=[False, True], kind="mergesort"
    ).reset_index(drop=True)
    return combined_df


def load_glory_games(years=None, before=None):
    """Read each year's major-league games once, for reuse across `get_glory_ranking` calls.

    Reading dominates a ranking's cost (fitting a year's model takes milliseconds).

    Returns:
        dict mapping year to its games.
    """
    if years is None:
        years = get_available_years(ALL_MAJOR_LEAGUES)
    return {yr: _major_league_games(yr, before) for yr in years}


def _major_league_games(year, before):
    """Every major-league game in a year (optionally before a date), with GLORY stats."""
    return get_matches_frame(
        "match_glory_stats",
        filters={"years": [year], "leagues": ALL_MAJOR_LEAGUES, "before": before},
    )


def _only_major_leagues(leagues):
    """True when a league filter keeps only major leagues (so major-league games suffice)."""
    if leagues is None:
        return False
    if not isinstance(leagues, (list, tuple, set)):
        leagues = [leagues]
    majors = {l.value for l in ALL_MAJOR_LEAGUES}
    return {getattr(l, "value", l) for l in leagues} <= majors


def adjust_for_opponent_record(games, features, record):
    """Adjust per-game stats for the opponent's full-season strength.

    Like `adjust_for_opponent_elo`, but strength is each team's Record rating for
    the whole season (hindsight), so a season stat depends only on that season's
    games and not on a forecast. Fits `feature ~ own_rating + opponent_rating`
    over the given games, then removes the opponent term relative to the average
    opponent.

    Args:
        games: Per-game rows (one per team per game, both teams of each game).
        features: Feature columns to adjust.
        record: `season.get_record` output with teamid, year and rating.
    Returns:
        New frame with adjusted features and `rating` / `opp_rating` columns. Games
        whose opponent row or rating is missing are dropped.
    """
    ratings = record[["teamid", "year", "rating"]].drop_duplicates(["teamid", "year"])
    games = games.merge(ratings, on=["teamid", "year"])
    opp = games[["gameid", "teamid", "rating"]].rename(
        columns={"teamid": "opp_teamid", "rating": "opp_rating"}
    )
    games = games.merge(opp, on="gameid")
    games = games[games["opp_teamid"] != games["teamid"]].drop(columns="opp_teamid")
    strength = games[["rating", "opp_rating"]]
    opp_offset = games["opp_rating"] - games["opp_rating"].mean()
    for feature in features:
        opp_coef = LinearRegression().fit(strength, games[feature]).coef_[1]
        games[feature] = games[feature] - opp_coef * opp_offset
    return games.reset_index(drop=True)


def adjust_for_opponent_elo(games, features, method="game_length"):
    """Adjust per-game stats for the strength of the opponent.

    For each feature, fits `feature ~ own_elo + opponent_elo` over the given games
    (controlling for the team's own strength), then removes the opponent term
    relative to the average opponent. The same gold-per-minute against a strong
    opponent is therefore worth more than against a weak one.

    Args:
        games: Per-game rows from `get_matches_frame` (one row per team per game).
        features: Feature columns to adjust.
        method: Elo method supplying pre-game ratings.
    Returns:
        New frame with adjusted features and `elo` / `opp_elo` columns. Games
        without an Elo record are dropped.
    """
    years = sorted(int(y) for y in games["year"].unique())
    games = games.merge(get_pregame_elos(method, years), on=["gameid", "teamid"])
    elos = games[["elo", "opp_elo"]]
    opp_offset = games["opp_elo"] - games["opp_elo"].mean()
    for feature in features:
        opp_coef = LinearRegression().fit(elos, games[feature]).coef_[1]
        games[feature] = games[feature] - opp_coef * opp_offset
    return games


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
