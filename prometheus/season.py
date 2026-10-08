"""Season stats built on results: Record (schedule-adjusted results) and Luck.

Season stats describe a finished (or in-progress) team-season with hindsight: every
game of the season counts equally, including games played after the one being
described. See `docs/steering/tech.md` for how they differ from forecasts.

- **Record**: how much a team won, given who it played. A Bradley-Terry model is fit
  over every game of a season in every league (international events tie regions
  together). Each game counts as a soft result: a fast win is close to a full win, a
  50-minute win is worth less, as in game-length Elo. A small ridge prior keeps
  teams with few games, or leagues that never meet, from drifting to extremes.
  Published as the chance of beating an average major-league team that season.
- **Luck**: actual win % minus the win % a team's play earned. "Earned" starts as
  the average, over a team's games, of GLORY's per-game model (gold and objective
  stats → result), fit on that season's major-league games. That per-game model
  pulls every team toward 50%, so it is calibrated at the team-season level
  (season win % regressed on the raw average, weighted by games) before the
  difference is taken; otherwise strong teams would always look lucky.
"""

import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.linear_model import LogisticRegression
from sqlalchemy import text

from prometheus.elo import winner_score
from prometheus.regression import fit_glory_pipeline
from prometheus.types import ALL_MAJOR_LEAGUES, GLORY_FEATURES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

MAJORS = [l.value for l in ALL_MAJOR_LEAGUES]
# Prior standard deviation of a team's Record rating, in log-odds. About 1 means a
# typical team is within 2:1 odds of average before any games are seen.
RECORD_PRIOR_SD = 1.0


def load_season_games(years=None, before=None):
    """One row per game in every league: both teams, league, year, length, result.

    `result` is from `teamid`'s point of view. `before` keeps games strictly before
    that date (for point-in-time use).
    """
    conditions = ["TRUE"]
    params = {}
    if years is not None:
        conditions.append(f"m1.year IN ({', '.join(str(int(y)) for y in years)})")
    if before is not None:
        conditions.append("m1.date < :before")
        params["before"] = str(before)[:10]
    stmt = f"""
    SELECT m1.gameid, m1.year, m1.date, m1.league,
           m1.teamid, m1.teamname, m2.teamid AS opp_teamid, m2.teamname AS opp_teamname,
           m1.gamelength, m1.result
    FROM matches m1
        JOIN matches m2 ON m1.gameid = m2.gameid AND m1.teamid < m2.teamid
    WHERE {" AND ".join(conditions)}
    ORDER BY m1.date, m1.gameid
    """
    return pd.read_sql(text(stmt), get_engine(), params=params)


def _team_seasons(games):
    """Per team-season: games, wins, last name, and home league (most-played domestic)."""
    rows = pd.concat(
        [
            games[["year", "date", "league", "teamid", "teamname", "result"]],
            games[["year", "date", "league", "opp_teamid", "opp_teamname", "result"]]
            .rename(columns={"opp_teamid": "teamid", "opp_teamname": "teamname"})
            .assign(result=lambda d: 1 - d["result"]),
        ],
        ignore_index=True,
    ).sort_values("date", kind="mergesort")
    key = ["teamid", "year"]
    seasons = rows.groupby(key).agg(
        teamname=("teamname", "last"),
        games=("result", "size"),
        win_pct=("result", "mean"),
    )
    domestic = rows[~rows["league"].isin(INTERNATIONAL_LEAGUES)]
    home = domestic.groupby(key)["league"].agg(lambda l: l.value_counts().index[0])
    anywhere = rows.groupby(key)["league"].agg(lambda l: l.value_counts().index[0])
    seasons["league"] = home.reindex(seasons.index).fillna(anywhere)
    return seasons.reset_index()


def fit_record(games, prior_sd=RECORD_PRIOR_SD):
    """Bradley-Terry log-odds rating for every team in `games` (one season).

    Each game becomes two weighted rows, a win with weight s and a loss with weight
    1 - s, where s is the game-length winner score from the team's side.

    Returns:
        Series of ratings (log-odds, before centring) indexed by teamid.
    """
    teams = pd.Index(pd.unique(pd.concat([games["teamid"], games["opp_teamid"]])))
    n = len(games)
    rows = np.arange(n)
    x = sparse.csr_matrix(
        (
            np.r_[np.ones(n), -np.ones(n)],
            (
                np.r_[rows, rows],
                np.r_[
                    teams.get_indexer(games["teamid"]),
                    teams.get_indexer(games["opp_teamid"]),
                ],
            ),
        ),
        shape=(n, len(teams)),
    )
    score = winner_score(games["gamelength"].to_numpy(dtype=float))
    soft = np.where(games["result"].to_numpy() == 1, score, 1 - score)
    model = LogisticRegression(C=prior_sd**2, fit_intercept=False, max_iter=1000)
    model.fit(
        sparse.vstack([x, x]),
        np.r_[np.ones(n), np.zeros(n)],
        sample_weight=np.r_[soft, 1 - soft],
    )
    return pd.Series(model.coef_[0], index=teams)


def get_record(games=None, minimum_matches=0, leagues=None):
    """Record for every team-season: chance of beating an average major-league team.

    Args:
        games: Output of `load_season_games` (every league, so international games
            link regions). Loaded for every year when None.
        minimum_matches: Drop team-seasons with fewer games (after fitting).
        leagues: Keep only team-seasons whose home league is in this list.
    Returns:
        DataFrame with teamid, teamname, year, league, games, win_pct, rating
        (log-odds against the average major-league team) and record (0-100).
    """
    if games is None:
        games = load_season_games()
    out = []
    for _, season in games.groupby("year"):
        info = _team_seasons(season).set_index("teamid")
        info["rating"] = fit_record(season)
        major = info["league"].isin(MAJORS)
        centre = (
            info.loc[major, "rating"].mean() if major.any() else info["rating"].mean()
        )
        info["rating"] -= centre
        out.append(info.reset_index())
    df = pd.concat(out, ignore_index=True)
    df["record"] = 100 / (1 + np.exp(-df["rating"]))
    df = df[df["games"] >= minimum_matches]
    if leagues is not None:
        df = df[df["league"].isin([getattr(l, "value", l) for l in leagues])]
    return df.sort_values("record", ascending=False).reset_index(drop=True)


def calibrate_earned(win_pct, raw, weights):
    """(intercept, slope) mapping a raw per-game earned win % to season win %."""
    slope, intercept = np.polyfit(raw, win_pct, 1, w=np.sqrt(weights))
    return intercept, slope


def get_luck(games, features=GLORY_FEATURES, minimum_matches=0):
    """Luck for every major-league team-season: actual minus earned win %.

    Args:
        games: Each year's major-league games, as from `ranking.load_glory_games`.
    Returns:
        DataFrame with teamname, year, league, games, win_pct, expected (earned win
        %, 0-1), luck (win % points, signed) and luck_wins (wins above earned).
    """
    out = []
    for year_games in games.values():
        pipeline = fit_glory_pipeline(year_games, features)
        played = year_games.assign(
            expected=np.clip(pipeline.predict(year_games[features]), 0, 1),
            result=year_games["result"].astype(int),
        )
        season = (
            played.groupby(["teamname", "year", "league"])
            .agg(
                games=("result", "size"),
                win_pct=("result", "mean"),
                raw=("expected", "mean"),
            )
            .reset_index()
        )
        intercept, slope = calibrate_earned(
            season["win_pct"], season["raw"], season["games"]
        )
        season["expected"] = np.clip(intercept + slope * season["raw"], 0, 1)
        out.append(season.drop(columns="raw"))
    df = pd.concat(out, ignore_index=True)
    df = df[df["games"] >= minimum_matches].copy()
    df["luck"] = (df["win_pct"] - df["expected"]) * 100
    df["luck_wins"] = (df["win_pct"] - df["expected"]) * df["games"]
    return df.sort_values("luck", ascending=False).reset_index(drop=True)
