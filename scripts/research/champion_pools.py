"""champion_pools.py: how many champions a team's starters play, before every game.

A player's pool before a game is the champions they played in pro games over the
`WINDOW_DAYS` before it. Its depth is the effective number of champions, exp of
the entropy of their picks: a player who split ten games evenly over five
champions has depth 5, one who played the same champion ten times has depth 1.
Experience is the number of games in the window. A team's values average its
starters', from those with at least one game in the window, and are left empty
when fewer than `MIN_PLAYERS` have one.
"""

import math
from collections import Counter

import numpy as np
import pandas as pd

from prometheus.utils import get_engine

WINDOW_DAYS = 180
MIN_PLAYERS = 4


def load_player_picks():
    """Every player-game with a champion, oldest first: gameid, teamid, playerid, champion, when."""
    stmt = """
    SELECT p.gameid, p.teamid, p.playerid, p.champion, m.date
    FROM player_stats p
    JOIN (SELECT DISTINCT gameid, date FROM matches) m ON m.gameid = p.gameid
    WHERE p.playerid IS NOT NULL AND p.champion IS NOT NULL AND p.champion != ''
    """
    picks = pd.read_sql(stmt, get_engine())
    picks["when"] = pd.to_datetime(picks["date"])
    return picks.sort_values(["when", "gameid"], kind="mergesort").reset_index(
        drop=True
    )


def player_pools(picks, window_days=WINDOW_DAYS):
    """Each player-game's pre-game pool: `depth` and `games` over the window before it.

    Games at the same moment as this one (or later) don't count. Rows with no game
    in the window get depth NaN and games 0.
    """
    window = pd.Timedelta(days=window_days)
    depth = np.full(len(picks), np.nan)
    games = np.zeros(len(picks), dtype=int)
    for _, rows in picks.groupby("playerid", sort=False):
        idx = rows.index.to_numpy()
        when = rows["when"].to_numpy()
        champs = rows["champion"].to_numpy()
        counts = Counter()
        # sum of c * log(c) over the window's champion counts, kept as the window moves
        c_log_c = 0.0
        start = end = 0  # window is rows [start, end)
        for i in range(len(idx)):
            # add every game strictly before this one
            while end < len(idx) and when[end] < when[i]:
                c = counts[champs[end]]
                c_log_c += (c + 1) * math.log(c + 1) - (c * math.log(c) if c else 0.0)
                counts[champs[end]] = c + 1
                end += 1
            # drop games older than the window
            while start < end and when[start] < when[i] - window:
                c = counts[champs[start]]
                c_log_c -= c * math.log(c) - (
                    (c - 1) * math.log(c - 1) if c > 1 else 0.0
                )
                counts[champs[start]] = c - 1
                start += 1
            n = end - start
            games[idx[i]] = n
            if n:
                depth[idx[i]] = math.exp(math.log(n) - c_log_c / n)
    return picks.assign(depth=depth, games=games)


def team_pools(picks=None, window_days=WINDOW_DAYS):
    """Per (gameid, teamid): the starters' mean pre-game `depth` and `experience`
    (games in the window), NaN when fewer than `MIN_PLAYERS` starters have a pool."""
    if picks is None:
        picks = load_player_picks()
    pools = player_pools(picks, window_days)
    has = pools[pools["games"] > 0]
    team = has.groupby(["gameid", "teamid"]).agg(
        depth=("depth", "mean"), experience=("games", "mean"), players=("depth", "size")
    )
    team.loc[team["players"] < MIN_PLAYERS, ["depth", "experience"]] = np.nan
    return team.drop(columns="players")
