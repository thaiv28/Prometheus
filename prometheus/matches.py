import pandas as pd
from collections.abc import Iterable
from enum import Enum

from prometheus import utils

from . import DB_PATH


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

    df = get_matches_frame(stat_table_name, filters)
    
    # Define potential grouping columns and filter to ones that exist in the DataFrame
    potential_group_cols = ["teamname", "year", "league"]
    group_cols = [col for col in potential_group_cols if col in df.columns]

    min_matches_df = df.groupby(group_cols).filter(lambda x: len(x) >= minimum_matches)
    averages_df = min_matches_df.groupby(group_cols).mean(numeric_only=True).reset_index()
    
    return averages_df


def get_matches_frame(stat_table_name, filters=None):
    """
    Reads from the given stat_table_name, joins with match_raw_stats, applies filters, and returns a pandas DataFrame.
    Args:
        stat_table_name (str): Name of the stats table (e.g., 'match_lore_stats').
        filters (dict, optional): Dictionary of filters, e.g. {'league': 'LPL', 'year': 2018}
    Returns:
        pd.DataFrame: Resulting DataFrame
    """
    condition = "TRUE"
    for filter_key, filter_value in filters.items():
        if filter_value is None:
            continue
        if isinstance(filter_value, str):
            filter_value = f"('{filter_value}')"
        elif isinstance(filter_value, Iterable):
            if isinstance(filter_value[0], Enum):
                filter_value = f"({', '.join(repr(v.value) for v in filter_value)})"
            else:
                filter_value = f"({', '.join(repr(v) for v in filter_value)})"
                
        match filter_key:
            case "leagues":
                condition += f" AND m.league IN {filter_value}"
            case "years":
                condition += f" AND m.year IN {filter_value} "
                
    stmt = f"""
    SELECT st.*, m.year, m.split, m.league, m.teamname, m.side, m.gamelength, m.result
    FROM {stat_table_name} st
    JOIN MATCHES m
        ON st.gameid = m.gameid AND st.teamid = m.teamid
    WHERE {condition};
    """
    
    engine = utils.get_engine()
    df = pd.read_sql(stmt, engine)
    return df
