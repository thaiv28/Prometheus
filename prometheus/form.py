"""Form (Predictive GLORY) and the GlorELO+ forecast built from it.

GLORY describes a finished season: its weights explain each game's own result from
that game's stats. Form instead asks what a team's stats *before* a game say about
that game. It uses only earlier games, so it never takes a season stat as input.

1. **Opponent-adjusted stats.** Each game's GLORY stats (gold, kills, objectives,
   vision ...) are restated against an average opponent using the opponent's
   pre-game Elo. The coefficients for a season come from earlier seasons only.
2. **A running state per team.** A recency-weighted average of those stats: each
   older game's weight halves every `HALF_LIFE` games, a new season starts from
   `CARRY` of the old season's weight, and the season's average team is mixed in
   as if it were `PRIOR_GAMES` extra games. Before its first game a team is average.
3. **A score.** The state times weights fit (logistic) on blue-minus-red state gaps
   in past domestic major-league games: log-odds of winning.
4. **League-relative Form.** The score minus the average pre-game score of the
   team's home league so far this season. Stats don't compare well across regions
   (a strong team in a weak league posts big numbers), so Form only says how a
   team has played compared with its own league; Elo carries region strength.

GlorELO+ blends them. Between teams from the same home league, the win chance is a
logistic curve on the Elo gap and the Form gap. Between leagues it is Elo's curve
alone, which the backtest found more accurate. A team's GlorELO+ rating is its Elo
plus its Form in Elo points, so a same-league head-to-head is the usual Elo formula
on the ratings, scaled by the blend's Elo weight.

Weights live in `form_weights.json` (Form) and `glorelo_weights.json` (blend),
refreshed by `scripts/evaluate_metrics.py --write-weights`.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sqlalchemy import text

from prometheus.elo import get_pregame_elos
from prometheus.types import GLORY_FEATURES, INTERNATIONAL_LEAGUES
from prometheus.utils import get_engine

WEIGHTS_PATH = Path(__file__).with_name("form_weights.json")
ELO_SCALE = 400 / math.log(10)
# Tuned in the backtest (see docs/steering/work_log.md); shrinkage barely matters.
HALF_LIFE = 20
CARRY = 0.5
PRIOR_GAMES = 5


def load_form_games(before=None):
    """Per team-game GLORY stats for every league, oldest first."""
    condition = "m.date < :before" if before is not None else "TRUE"
    stmt = f"""
    SELECT st.*, m.date, m.year, m.league, m.teamname, m.result
    FROM match_glory_stats st
    JOIN matches m ON st.gameid = m.gameid AND st.teamid = m.teamid
    WHERE {condition}
    ORDER BY m.date, m.gameid, m.teamid
    """
    params = {"before": str(before)[:10]} if before is not None else {}
    return pd.read_sql(text(stmt), get_engine(), params=params)


def opponent_adjust(games, features=GLORY_FEATURES, elos=None):
    """Restate each game's stats against an average opponent, by pre-game Elo.

    For each season, `feature ~ own_elo + opponent_elo` is fit on every earlier
    season's games (the first season uses its own), and the opponent term is
    removed relative to the average opponent. Games without Elo are left as they are.

    Args:
        games: `load_form_games` rows.
        elos: `elo.get_pregame_elos` output; read when None.
    """
    if elos is None:
        elos = get_pregame_elos("game_length")
    games = games.merge(elos, on=["gameid", "teamid"], how="left")
    rated = games[["elo", "opp_elo"]].notna().all(axis=1)
    years = sorted(games["year"].unique())
    adjusted = games[features].copy()
    for year in years:
        rows = games["year"] == year
        train = rated & ((games["year"] < year) if year != years[0] else rows)
        offset = (games.loc[rows, "opp_elo"] - games.loc[train, "opp_elo"].mean()).fillna(0)
        for feature in features:
            fit = train & games[feature].notna()
            coef = LinearRegression().fit(games.loc[fit, ["elo", "opp_elo"]], games.loc[fit, feature]).coef_[1]
            adjusted.loc[rows, feature] = games.loc[rows, feature] - coef * offset
    games[features] = adjusted
    return games.drop(columns=["elo", "opp_elo"])


def _season_priors(games, features):
    """The average team going into each day: that season's mean of games on earlier
    days (every league), or the previous season's mean on a season's first day."""
    by_day = games.groupby(["year", "date"])[features].agg(["sum", "count"])
    sums = by_day.xs("sum", axis=1, level=1).groupby(level="year").cumsum()
    counts = by_day.xs("count", axis=1, level=1).groupby(level="year").cumsum()
    running = sums.groupby(level="year").shift(1) / counts.groupby(level="year").shift(1)
    previous = games.groupby("year")[features].mean().shift(1).bfill()
    fallback = previous.reindex(running.index.get_level_values("year")).set_axis(running.index)
    return running.fillna(fallback)


def form_states(games, features=GLORY_FEATURES, half_life=HALF_LIFE, carry=CARRY, prior_games=PRIOR_GAMES):
    """Each team's Form state before and after every game.

    Args:
        games: Opponent-adjusted `load_form_games` rows, oldest first.
    Returns:
        DataFrame aligned with `games`: gameid, teamid, teamname, league, year, date,
        home (the domestic league it has played most this season so far; its last
        season's home before its first domestic game), `pre_<feature>` and `post_<feature>`
        state columns, and `form_games` (effective games behind the pre-game state).
    """
    decay = 0.5 ** (1 / half_life)
    priors = _season_priors(games, features)
    prior_rows = priors.reindex(pd.MultiIndex.from_arrays([games["year"], games["date"]])).to_numpy()
    values = games[features].to_numpy(dtype=float)
    # A missing stat counts as an average game for that stat.
    values = np.where(np.isnan(values), prior_rows, values)
    teams = games["teamid"].to_numpy()
    years = games["year"].to_numpy()
    leagues = games["league"].to_numpy()
    domestic = ~games["league"].isin(INTERNATIONAL_LEAGUES).to_numpy()

    sums, weights, last_year = {}, {}, {}
    league_games, home_of = {}, {}
    pre = np.empty_like(values)
    post = np.empty_like(values)
    seen = np.empty(len(games))
    home = np.empty(len(games), dtype=object)
    for i in range(len(games)):
        team = teams[i]
        if team not in sums:
            sums[team] = np.zeros(len(features))
            weights[team] = 0.0
        elif last_year[team] != years[i]:
            sums[team] = sums[team] * carry
            weights[team] *= carry
            league_games[team] = {}
        last_year[team] = years[i]
        # Home league: the domestic league it has played most this season, so a
        # winter cup or an international event doesn't change it.
        if domestic[i]:
            counts = league_games.setdefault(team, {})
            counts[leagues[i]] = counts.get(leagues[i], 0) + 1
            home_of[team] = max(counts, key=counts.get)
        home[i] = home_of.get(team, leagues[i])
        pre[i] = (sums[team] + prior_games * prior_rows[i]) / (weights[team] + prior_games)
        seen[i] = weights[team]
        sums[team] = decay * sums[team] + values[i]
        weights[team] = decay * weights[team] + 1.0
        post[i] = (sums[team] + prior_games * prior_rows[i]) / (weights[team] + prior_games)

    out = games[["gameid", "teamid", "teamname", "league", "year", "date"]].reset_index(drop=True)
    out["home"] = home
    out["form_games"] = seen
    out = pd.concat(
        [
            out,
            pd.DataFrame(pre, columns=[f"pre_{f}" for f in features]),
            pd.DataFrame(post, columns=[f"post_{f}" for f in features]),
        ],
        axis=1,
    )
    return out


def fit_form_weights(gaps, won):
    """Logistic weights (log-odds per unit of stat gap) for blue-minus-red state gaps."""
    x = np.asarray(gaps, dtype=float)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=1e6, max_iter=1000).fit(x / scale, np.asarray(won, dtype=int))
    return model.coef_[0] / scale


def scores(states, weights, prefix="pre_"):
    """Log-odds strength of each state row: its stats times the Form weights."""
    cols = [f"{prefix}{f}" for f in weights]
    return states[cols].to_numpy(dtype=float) @ np.array(list(weights.values()), dtype=float)


def league_relative(states, score):
    """Score minus the average pre-game score of the same home league this season.

    The average runs over every pre-game state in that league and season up to and
    including the game's day (pre-game states are known before the games).
    """
    frame = states[["home", "year", "date"]].assign(score=score)
    day = frame.groupby(["home", "year", "date"])["score"].agg(["sum", "count"])
    running = day.groupby(level=["home", "year"]).cumsum()
    mean = (running["sum"] / running["count"]).rename("league_mean")
    return score - frame.join(mean, on=["home", "year", "date"])["league_mean"].to_numpy()


def load_weights(path=WEIGHTS_PATH):
    """The tracked Form weights and the hyperparameters they were fit with."""
    return json.loads(Path(path).read_text())


def save_weights(weights, path=WEIGHTS_PATH):
    data = {
        "half_life": HALF_LIFE,
        "carry": CARRY,
        "prior_games": PRIOR_GAMES,
        "weights": {f: round(float(w), 6) for f, w in weights.items()},
    }
    Path(path).write_text(json.dumps(data, indent=2) + "\n")
