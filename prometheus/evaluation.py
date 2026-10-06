"""Scoring helpers for backtesting how well team metrics predict game winners.

A metric gives each team a rating. For one game, the rating gap between the two
teams is turned into a win probability with a logistic curve, and those
probabilities are scored against the real results.
"""

import hashlib

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

EPS = 1e-6


def _as_matrix(diff):
    x = np.asarray(diff, dtype=float)
    return x.reshape(-1, 1) if x.ndim == 1 else x


def fit_win_curve(diff, won):
    """Fit P(win) = sigmoid(a + b . diff) and return a function of diff.

    `diff` is the rating gap from the blue side's point of view, so the
    intercept `a` absorbs the blue-side advantage. It may hold one column (a
    single metric) or several (a blend, with one weight per column). With
    diff=None only the intercept is fit, which is the "blue side wins" baseline.
    """
    won = np.asarray(won, dtype=int)
    if diff is None:
        p = float(np.clip(won.mean(), EPS, 1 - EPS))
        return lambda d: np.full(len(d), p)
    x = _as_matrix(diff)
    # Ratings live on very different scales (Elo ~1500, GLORY 0-100); scaling
    # x keeps the solver well conditioned without changing the fitted curve.
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=1e6).fit(x / scale, won)
    return lambda d: model.predict_proba(_as_matrix(d) / scale)[:, 1]


def out_of_year_probabilities(frame, diff_col):
    """Win probabilities for each game from a curve fit on all *other* years.

    Fitting the curve's two parameters on the same games it scores would leak a
    little; leaving the whole year out avoids that.

    Args:
        frame: One row per game with columns `year`, `won` (blue won) and `diff_col`.
        diff_col: Column (or list of columns, for a blend) holding blue-minus-red
            rating gaps, or None for the blue-side baseline.
    Returns:
        Series of probabilities aligned with `frame`.
    """
    probs = pd.Series(np.nan, index=frame.index)
    for year in frame["year"].unique():
        test = frame["year"] == year
        # With a single season there is nothing to leave out; fit on it directly.
        train = frame[~test] if (~test).any() else frame
        curve = fit_win_curve(
            None if diff_col is None else train[diff_col].to_numpy(), train["won"]
        )
        test_diff = (
            np.zeros(test.sum())
            if diff_col is None
            else frame.loc[test, diff_col].to_numpy()
        )
        probs[test] = curve(test_diff)
    return probs


def game_losses(p, won):
    """Per-game accuracy, Brier score and log loss for predicted probabilities."""
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS)
    won = np.asarray(won, dtype=int)
    # A pick of exactly 50% counts as half right.
    correct = np.where(p == 0.5, 0.5, ((p > 0.5) == (won == 1)).astype(float))
    return pd.DataFrame(
        {
            "accuracy": correct,
            "brier": (p - won) ** 2,
            "log_loss": -(won * np.log(p) + (1 - won) * np.log(1 - p)),
        }
    )


def paired_bootstrap(loss_a, loss_b, n_resamples=2000, seed=0):
    """Mean of (loss_a - loss_b) and its 95% bootstrap interval.

    Both metrics are scored on the same games, so resampling games (not each
    metric separately) gives a much tighter, fairer comparison.
    """
    diff = np.asarray(loss_a, dtype=float) - np.asarray(loss_b, dtype=float)
    rng = np.random.default_rng(seed)
    means = np.array(
        [diff[rng.integers(0, len(diff), len(diff))].mean() for _ in range(n_resamples)]
    )
    return diff.mean(), np.percentile(means, 2.5), np.percentile(means, 97.5)


def elo_as_of(timeline, offsets, cutoff):
    """Each team's published Elo just before `cutoff`, by team name.

    That is its rating after its last game before the cutoff, plus every change to
    its home league's offset since that game (for example from an international
    event it did not attend), as `elo.get_latest_elos` does for the site.

    Args:
        timeline: Elo after every game, oldest first: teamname, date, elo,
            home_league and league_offset (the offset after that game).
        offsets: League-offset history, oldest first: date, league, league_offset.
        cutoff: Timestamp; only games and offset changes strictly before it count.
    Returns:
        Series of Elo ratings indexed by team name.
    """
    last = timeline[timeline["date"] < cutoff].drop_duplicates("teamname", keep="last")
    last = last.set_index("teamname")
    current = offsets[offsets["date"] < cutoff].groupby("league")["league_offset"].last()
    moved = last["home_league"].map(current) - last["league_offset"]
    return last["elo"] + moved.fillna(0)


def season_homes(games, international):
    """Each team's home league per season: the non-international league it played
    most that season (a cup, promotion series or EMEA Masters doesn't change it).

    Homes come from the whole season, so they only choose which games to score;
    they never feed a forecast.

    Args:
        games: One row per game: year, league, teamid, opponent_teamid.
        international: League names of international events.
    Returns:
        `games` with home and opponent_home columns (NaN when a team played only
        international events that season).
    """
    sides = pd.concat(
        [
            games[["year", "league", "teamid"]],
            games[["year", "league", "opponent_teamid"]].rename(columns={"opponent_teamid": "teamid"}),
        ]
    )
    sides = sides[~sides["league"].isin(international)]
    counts = sides.groupby(["teamid", "year", "league"]).size().rename("n").reset_index()
    # Most games first, then league name, so ties resolve the same way every run.
    counts = counts.sort_values(["n", "league"], ascending=[False, True])
    home = counts.drop_duplicates(["teamid", "year"]).set_index(["teamid", "year"])["league"]
    return games.assign(
        home=home.reindex(pd.MultiIndex.from_arrays([games["teamid"], games["year"]])).to_numpy(),
        opponent_home=home.reindex(
            pd.MultiIndex.from_arrays([games["opponent_teamid"], games["year"]])
        ).to_numpy(),
    )


def cross_league_games(games, international, majors):
    """Games between teams from two different home leagues (`season_homes`), in any
    league or event.

    Args:
        games: One row per game: gameid, year, league, teamid, opponent_teamid.
        international: League names of international events.
        majors: League names of the major leagues.
    Returns:
        The cross-league rows with home, opponent_home and kind ("major v major",
        "major v other" or "other v other").
    """
    out = season_homes(games, international)
    out = out[out["home"].notna() & out["opponent_home"].notna() & (out["home"] != out["opponent_home"])]
    n_major = out["home"].isin(majors).astype(int) + out["opponent_home"].isin(majors).astype(int)
    kinds = np.array(["other v other", "major v other", "major v major"])
    return out.assign(kind=kinds[n_major.to_numpy()]).reset_index(drop=True)


def other_league_games(games, international, majors):
    """Games inside one non-major league: both teams' home (`season_homes`) is the
    league the game was played in, and it isn't a major league.

    Args and the games' columns are as for `cross_league_games`.
    """
    out = season_homes(games, international)
    keep = (out["home"] == out["league"]) & (out["opponent_home"] == out["league"]) & ~out["league"].isin(majors)
    return out[keep].reset_index(drop=True)


def spearman_brown(r, factor):
    """Reliability of a measure `factor` times as long, from reliability `r`."""
    return factor * r / (1 + (factor - 1) * r)


def games_for_reliability(r_half, games_per_half, target=0.5):
    """Games a team needs before a stat reaches `target` reliability.

    Steps the split-half reliability down to one game with Spearman-Brown, then
    finds the length where reliability reaches `target`. Returns inf when the
    stat never gets there (reliability at or below 0).
    """
    if r_half <= 0:
        return np.inf
    one_game = r_half / (games_per_half - (games_per_half - 1) * r_half)
    return target * (1 - one_game) / ((1 - target) * one_game)


def correlation_interval(r, n, z=1.96):
    """95% interval for a Pearson correlation from `n` pairs (Fisher z)."""
    if n <= 3:
        return np.nan, np.nan
    centre, half = np.arctanh(np.clip(r, -0.999999, 0.999999)), z / np.sqrt(n - 3)
    return np.tanh(centre - half), np.tanh(centre + half)


def half_of(gameids):
    """0 or 1 for each game, from a hash of its id (stable across runs)."""
    return gameids.map(lambda g: int(hashlib.md5(str(g).encode()).hexdigest()[:8], 16) % 2)


def paired_correlation_bootstrap(pairs_a, pairs_b, n_resamples=2000, seed=0):
    """Difference of two correlations on the same rows, and its 95% bootstrap interval.

    `pairs_a` and `pairs_b` are (x, y) arrays of equal length over the same units
    (players, team-seasons); rows are resampled together.
    """
    xa, ya = (np.asarray(v, dtype=float) for v in pairs_a)
    xb, yb = (np.asarray(v, dtype=float) for v in pairs_b)
    corr = lambda x, y: np.corrcoef(x, y)[0, 1]
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(n_resamples):
        i = rng.integers(0, len(xa), len(xa))
        diffs.append(corr(xa[i], ya[i]) - corr(xb[i], yb[i]))
    return corr(xa, ya) - corr(xb, yb), np.percentile(diffs, 2.5), np.percentile(diffs, 97.5)
