"""AURA (Attributable Utility via Role Analytics): each player's share of a game.

A win-probability model reads the game at a snapshot minute from the five lanes:
each starter's gold, XP, CS, kills, deaths and assists minus their lane
opponent's. It is a logistic regression with one weight per role and stat, so the
blue side's log-odds of winning is an intercept plus a sum of five lane terms. A
player's snapshot score is their lane's term: how much their lane moved the
team's odds, in log-odds. The five terms plus the intercept are the team's
log-odds, and a player's term is exactly minus their lane opponent's.

A player's AURA for a game is their 15-minute term plus a quarter of their
*team-centred* change to 25 minutes (20 when the game ended first): their own
term's change from 15 to 25 minus the average change of their four teammates.
The 15-minute snapshot is the base because later snapshots mostly restate how the
whole team is doing (a 25-minute term correlates 0.56 with the teammates' in the
same game, against 0.21 at 15). Taking out the teammates' average keeps the part
of the later game that is the player's own; it adds up to zero over a team, so a
team's total AURA is its 15-minute total. The quarter was fixed before a held-out
test (weights from earlier years only), where this beat the 15-minute term alone
on following a player to a new team. See `docs/aura_report.md`.

The weights are fit per year on every league's games (the game changes from patch
to patch), like GLORY's; `earlier_only=True` fits each year on every earlier year
instead, for held-out tests.

AURA is research: nothing on the site uses it yet.
"""

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from prometheus.utils import get_engine

MINUTES = (10, 15, 20, 25)
MINUTE = 15
# The later snapshot whose team-centred change is added, and its fallback for
# games that ended first.
LATE_MINUTES = (25, 20)
LATE_WEIGHT = 0.25
# With `earlier_only`, a year is scored only when earlier years hold this many games.
MIN_TRAIN_GAMES = 1000
STATS = ("gold", "xp", "cs", "kills", "deaths", "assists")
ROLES = ("top", "jng", "mid", "bot", "sup")
# Ridge strength on standardized lane gaps; with thousands of games a year it
# barely matters, but it keeps a thin early year from extreme weights.
C = 1.0


def load_aura_games(minutes=MINUTES):
    """One row per starter per game, with lane gaps `<stat>_<minute>` (own minus lane opponent).

    Only team-games with all five starters' snapshots are kept. A gap is NULL when
    the game ended before that minute. `playerid` comes from `match_players`, the
    same id player Elo uses.
    """
    gaps = ", ".join(f"p.{s}at{m} - p.opp_{s}at{m} AS {s}_{m}" for m in minutes for s in STATS)
    stmt = f"""
    SELECT p.gameid, p.teamid, p.position, mp.playerid, mp.playername, p.champion,
           m.date, m.year, m.league, m.teamname, m.side, m.result, {gaps}
    FROM player_stats p
    JOIN match_players mp ON mp.gameid = p.gameid AND mp.teamid = p.teamid AND mp.position = p.position
    JOIN matches m ON m.gameid = p.gameid AND m.teamid = p.teamid
    ORDER BY m.date, p.gameid, p.teamid, p.position
    """
    players = pd.read_sql(stmt, get_engine())
    full = players.groupby(["gameid", "teamid"])["position"].transform("size") == len(ROLES)
    players = players[full]
    both = players.groupby("gameid")["teamid"].transform("nunique") == 2
    return players[both].reset_index(drop=True)


def lane_columns():
    """Game-frame columns, role-major: `top_gold`, `top_xp`, ..., `sup_assists`."""
    return [f"{r}_{s}" for r in ROLES for s in STATS]


def game_frame(players, minute=MINUTE):
    """One row per game from the blue side: `year`, `won` and the blue lanes' gaps.

    Games that ended before `minute` are left out.
    """
    blue = players[players["side"] == "Blue"]
    wide = blue.pivot(index="gameid", columns="position", values=[f"{s}_{minute}" for s in STATS])
    wide.columns = [f"{role}_{col.rsplit('_', 1)[0]}" for col, role in wide.columns]
    info = blue.groupby("gameid")[["year", "result"]].first().rename(columns={"result": "won"})
    games = info.join(wide[lane_columns()], how="inner").dropna()
    games["won"] = games["won"].astype(int)
    return games


def fit_aura_weights(games):
    """Logistic weights per role on a `game_frame`.

    Returns (intercept, weights): `weights` maps each role to log-odds per unit
    of each stat's gap, in `STATS` order. The intercept is the blue side's edge.
    """
    cols = lane_columns()
    x = games[cols].to_numpy(dtype=float)
    scale = x.std(axis=0)
    scale[scale == 0] = 1.0
    model = LogisticRegression(C=C, max_iter=2000).fit(x / scale, games["won"])
    coef = model.coef_[0] / scale
    weights = {r: coef[i * len(STATS) : (i + 1) * len(STATS)] for i, r in enumerate(ROLES)}
    return float(model.intercept_[0]), weights


def win_probability(games, intercept, weights):
    """Blue's chance of winning each `game_frame` row."""
    logit = intercept + sum(
        games[[f"{r}_{s}" for s in STATS]].to_numpy(dtype=float) @ weights[r] for r in ROLES
    )
    return 1 / (1 + np.exp(-logit))


def player_scores(players, weights, minute=MINUTE):
    """Each player-game's AURA: their lane's log-odds term under `weights`."""
    out = pd.Series(np.nan, index=players.index)
    for role in ROLES:
        rows = players["position"] == role
        gaps = players.loc[rows, [f"{s}_{minute}" for s in STATS]].to_numpy(dtype=float)
        out[rows] = gaps @ weights[role]
    return out


def _weights_by_year(games, earlier_only=False):
    """(year, weights) for each year: fit on that year, or on every earlier year."""
    for year in sorted(games["year"].unique()):
        train = games[games["year"] < year] if earlier_only else games[games["year"] == year]
        if earlier_only and len(train) < MIN_TRAIN_GAMES:
            continue
        yield year, fit_aura_weights(train)[1]


def snapshot_scores(players, minute=MINUTE, earlier_only=False):
    """Each player-game's lane term at `minute`; NaN when the game ended first or the year wasn't fit."""
    out = pd.Series(np.nan, index=players.index)
    for year, weights in _weights_by_year(game_frame(players, minute), earlier_only):
        rows = players["year"] == year
        out[rows] = player_scores(players[rows], weights, minute)
    return out


def team_centred(change, players):
    """Each player's value minus the average of their teammates' in the same game."""
    team = change.groupby([players["gameid"], players["teamid"]]).transform("sum")
    return change - (team - change) / (len(ROLES) - 1)


def get_aura(players=None, earlier_only=False):
    """Every player-game with its AURA: the 15-minute term plus `LATE_WEIGHT` of the team-centred change.

    Returns `players` (read when None) with `aura` and `aura_late` (the
    team-centred change; 0 when the game ended before every late snapshot).
    """
    if players is None:
        players = load_aura_games()
    players = players.copy()
    early = snapshot_scores(players, MINUTE, earlier_only)
    late = pd.Series(np.nan, index=players.index)
    for minute in LATE_MINUTES:
        late = late.fillna(snapshot_scores(players, minute, earlier_only))
    players["aura_late"] = team_centred((late - early).fillna(0.0), players)
    players["aura"] = early + LATE_WEIGHT * players["aura_late"]
    return players


# Season AURA is shown in win-chance points per game: log-odds times the logistic
# curve's slope at an even game (0.25), times 100.
POINTS = 25
# A season AURA needs about 22 games to be more signal than noise (split-half
# reliability 0.59 at 31 games a half); the register lists seasons with this many.
SEASON_GAMES = 20


def season_aura(scored, leagues, min_games=SEASON_GAMES):
    """AURA per player-season and role, in `leagues` (the major leagues).

    `scored` is `get_aura` output. One row per (playerid, year, position) with the
    player's last name that season, the team and league they played most for,
    `games`, `aura` (mean per game, in win-chance points), and, for seasons with
    `min_games` or more, `role_z` (standard deviations above the average such
    season in that role and year), `role_rank` and `role_count`; those are NaN for
    shorter seasons, which are flagged `qualified=False`.
    """
    games = scored[scored["league"].isin(leagues)].dropna(subset=["aura"])
    key = ["playerid", "year", "position"]

    def most(col):
        """The value of `col` with the most games in each player-season."""
        counts = games.groupby(key + [col]).size().reset_index(name="n").sort_values("n")
        return counts.drop_duplicates(key, keep="last").set_index(key)[col]

    seasons = games.groupby(key).agg(
        playername=("playername", "last"), games=("aura", "size"), aura=("aura", "mean")
    )
    seasons["teamname"] = most("teamname")
    seasons["league"] = most("league")
    seasons = seasons.reset_index()
    seasons["aura"] *= POINTS
    seasons["qualified"] = seasons["games"] >= min_games
    q = seasons[seasons["qualified"]]
    by = q.groupby(["year", "position"])["aura"]
    seasons.loc[q.index, "role_z"] = (q["aura"] - by.transform("mean")) / by.transform("std")
    seasons.loc[q.index, "role_rank"] = by.rank(ascending=False, method="min")
    seasons.loc[q.index, "role_count"] = by.transform("size")
    return seasons
