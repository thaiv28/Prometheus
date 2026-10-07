"""The player tables, each read once and shared by AURA, player Elo history and game logs.

SQLite has no index for the joins between `player_stats`, `match_players`,
`matches` and the player Elo table, so joining them in SQL is slow. Reading each
table's columns once and merging in pandas is several times faster, and the site
build passes one `PlayerTables` to `aura.load_aura_games`,
`elo.get_player_history` and `gamelog.load_player_games` so no table is read twice.
"""

from functools import cached_property

import pandas as pd

from prometheus.utils import get_engine


class PlayerTables:
    """The player tables, each read on first use.

    Args:
        method: player Elo method (`elo.ELO_METHODS`), naming `<method>_player_elo`.
        stats, minutes: lane gaps to read from `player_stats`, as
            `<stat>_<minute>` = `<stat>at<minute> - opp_<stat>at<minute>`.
    """

    def __init__(self, method="game_length", stats=(), minutes=()):
        self.method = method
        self.gaps = [f"{s}_{m}" for m in minutes for s in stats]
        self._gap_sql = "".join(
            f", {s}at{m} - opp_{s}at{m} AS {s}_{m}" for m in minutes for s in stats
        )

    @cached_property
    def roster(self):
        """match_players: gameid, teamid, position, playerid, playername."""
        return pd.read_sql(
            "SELECT gameid, teamid, position, playerid, playername FROM match_players",
            get_engine(),
        )

    @cached_property
    def stats(self):
        """player_stats: gameid, teamid, position, champion and the lane gaps."""
        return pd.read_sql(
            f"SELECT gameid, teamid, position, champion{self._gap_sql} FROM player_stats",
            get_engine(),
        )

    @cached_property
    def elo(self):
        """Player Elo per game: gameid, teamid, playerid, elo_pre, elo, home_league, league_offset."""
        from prometheus.elo import _players_table

        return pd.read_sql(
            f"""SELECT gameid, teamid, playerid, pre_match_elo AS elo_pre,
                       post_match_elo AS elo, home_league, league_offset
                FROM {_players_table(self.method)}""",
            get_engine(),
        )

    @cached_property
    def matches(self):
        """matches: gameid, teamid, date, year, league, teamname, side, result."""
        return pd.read_sql(
            "SELECT gameid, teamid, date, year, league, teamname, side, result FROM matches",
            get_engine(),
        )
