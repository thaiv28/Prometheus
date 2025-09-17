# Utility to get a pandas DataFrame from a stat table joined with match_raw_stats, with filters
import os
import pandas as pd
from sqlalchemy import create_engine, Table, MetaData, select, and_

from . import DB_PATH

def get_matches_frame(stat_table_name, filters=None):
	"""
	Reads from the given stat_table_name, joins with match_raw_stats, applies filters, and returns a pandas DataFrame.
	Args:
		stat_table_name (str): Name of the stats table (e.g., 'match_lore_stats').
		filters (dict, optional): Dictionary of filters, e.g. {'region': 'LPL', 'year': 2018}
	Returns:
		pd.DataFrame: Resulting DataFrame
	"""
	engine = create_engine(f'sqlite:///{DB_PATH}')
	metadata = MetaData()
	stat_table = Table(stat_table_name, metadata, autoload_with=engine)
	match_raw_stats = Table('match_raw_stats', metadata, autoload_with=engine)

	sql_filters = []
	if filters:
		if 'region' in filters:
			sql_filters.append(match_raw_stats.c.league == filters['region'])
		if 'year' in filters:
			sql_filters.append(match_raw_stats.c.year == filters['year'])

	join_condition = (stat_table.c.gameid == match_raw_stats.c.gameid) & (stat_table.c.teamid == match_raw_stats.c.teamid)
	stmt = select(
		stat_table,
		match_raw_stats.c.league,
		match_raw_stats.c.year
	).select_from(
		stat_table.join(match_raw_stats, join_condition)
	)
	if sql_filters:
		stmt = stmt.where(and_(*sql_filters))

	df = pd.read_sql(stmt, engine)
	return df
