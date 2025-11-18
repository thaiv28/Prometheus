"""Player-level data access utilities.

Contains helper functions originally defined in win_prediction.py for
retrieving per-player snapshot rows joined with match results.
"""

from typing import List

import pandas as pd
from sqlalchemy import MetaData, Table, create_engine, select, and_

from prometheus import DB_PATH


def _get_engine_and_tables(db_path: str = DB_PATH):
    engine = create_engine(f"sqlite:///{db_path}")
    metadata = MetaData()
    player_raw = Table("player_raw_stats", metadata, autoload_with=engine)
    match_raw = Table("match_stats", metadata, autoload_with=engine)
    return engine, player_raw, match_raw


def _build_player_match_query(
    player_raw: Table, match_raw: Table, years: List[int] | None
):
    join_cond = and_(
        player_raw.c.gameid == match_raw.c.gameid,
        player_raw.c.teamid == match_raw.c.teamid,
    )
    stmt = select(player_raw, match_raw.c.result).select_from(
        player_raw.join(match_raw, join_cond)
    )
    if years:
        stmt = stmt.where(match_raw.c.year.in_(years))
    return stmt


def _fetch_player_base_frame(
    years: List[int] | None = None, db_path: str = DB_PATH
) -> pd.DataFrame:
    """Return per-player snapshot row joined with match result.

    Raises ValueError if no rows match criteria.
    """
    engine, player_raw, match_raw = _get_engine_and_tables(db_path)
    stmt = _build_player_match_query(player_raw, match_raw, years)
    df = pd.read_sql(stmt, engine)
    if df.empty:
        raise ValueError("No player snapshot data found for the provided filters/years.")
    df = df.loc[:, ~df.columns.duplicated()]
    return df
