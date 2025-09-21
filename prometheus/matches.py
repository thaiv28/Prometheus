import pandas as pd
from sqlalchemy import create_engine, Table, MetaData, select, and_

from . import DB_PATH


def _get_engine_and_tables(stat_table_name, db_path=DB_PATH):
    engine = create_engine(f"sqlite:///{db_path}")
    metadata = MetaData()
    stat_table = Table(stat_table_name, metadata, autoload_with=engine)
    match_raw_stats = Table("match_raw_stats", metadata, autoload_with=engine)
    return engine, stat_table, match_raw_stats


def _build_select_stmt(stat_table, match_raw_stats, filters):
    column_table_map = {col: stat_table for col in stat_table.columns.keys()}
    column_table_map.update(
        {col: match_raw_stats for col in match_raw_stats.columns.keys()}
    )
    sql_filters = []
    if filters:
        for key, val in filters.items():
            if val is None:
                continue
            table = column_table_map.get(key)
            if table is None:
                continue

            col = getattr(table.c, key)
            if isinstance(val, list):
                sql_filters.append(col.in_(val))
            else:
                sql_filters.append(col == val)

    join_condition = (stat_table.c.gameid == match_raw_stats.c.gameid) & (
        stat_table.c.teamid == match_raw_stats.c.teamid
    )
    stmt = select("*").select_from(stat_table.join(match_raw_stats, join_condition))
    if sql_filters:
        stmt = stmt.where(and_(*sql_filters))
    return stmt


def _retrieve_dataframe_from_table(stat_table_name, filters=None, db_path=DB_PATH):
    engine, stat_table, match_raw_stats = _get_engine_and_tables(
        stat_table_name, db_path
    )
    stmt = _build_select_stmt(stat_table, match_raw_stats, filters)

    df = pd.read_sql(stmt, engine)
    if df.empty:
        raise ValueError("No data found for given criteria.")

    df = df.loc[:, ~df.columns.duplicated()]
    return df, stat_table


def get_team_averages_frame(stat_table_name, minimum_matches=0, filters=None):
    """
    Reads from the given stat_table_name, joins with match_raw_stats, applies filters, and returns a pandas DataFrame
    with one row per team, containing the team's averages for all feature columns in the stat table.
    Args:
        stat_table_name (str): Name of the stats table (e.g., 'match_lore_stats').
        filters (dict, optional): Dictionary of filters, e.g. {'league': 'LPL', 'year': 2018, 'teamid': 'SKT'}
    Returns:
        pd.DataFrame: DataFrame with one row per team, columns are teamid and averages for each feature.
    """

    df, stat_table = _retrieve_dataframe_from_table(stat_table_name, filters)

    # Define potential grouping columns and filter to ones that exist in the DataFrame
    potential_group_cols = ["teamname", "year", "league"]
    group_cols = [col for col in potential_group_cols if col in df.columns]

    if minimum_matches and minimum_matches > 0:
        # keep groups with at least `minimum_matches` unique games
        mask = df.groupby(group_cols)["gameid"].transform("nunique") >= minimum_matches
        df = df[mask].copy()

    # Only include numeric columns for averaging
    features = [
        col
        for col in stat_table.columns.keys()
        if col not in ["teamid", "gameid", "teamname"]
    ]
    df = df.groupby(group_cols)[features].mean().reset_index()
    return df


def get_matches_frame(stat_table_name, filters=None):
    """
    Reads from the given stat_table_name, joins with match_raw_stats, applies filters, and returns a pandas DataFrame.
    Args:
        stat_table_name (str): Name of the stats table (e.g., 'match_lore_stats').
        filters (dict, optional): Dictionary of filters, e.g. {'league': 'LPL', 'year': 2018}
    Returns:
        pd.DataFrame: Resulting DataFrame
    """
    df, _ = _retrieve_dataframe_from_table(stat_table_name, filters)
    return df
