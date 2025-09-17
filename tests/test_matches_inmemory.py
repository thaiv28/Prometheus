import pytest
from unittest.mock import patch
import pandas as pd
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float

from prometheus.matches import _get_engine_and_tables, _build_select_stmt, _retrieve_dataframe_from_table

def setup_inmemory_db():
    engine = create_engine('sqlite:///:memory:')
    metadata = MetaData()
    stat_table = Table('match_lore_stats', metadata,
        Column('gameid', String, primary_key=True),
        Column('teamid', String),
        Column('feature1', Float),
    )
    match_raw_stats = Table('match_raw_stats', metadata,
        Column('gameid', String, primary_key=True),
        Column('teamid', String),
        Column('teamname', String),
        Column('league', String),
        Column('year', Integer),
    )
    metadata.create_all(engine)
    # Insert test data
    with engine.begin() as conn:
        conn.execute(stat_table.insert(), [
            {'gameid': 'g1', 'teamid': 't1', 'feature1': 1.0},
            {'gameid': 'g2', 'teamid': 't2', 'feature1': 2.0},
        ])
        conn.execute(match_raw_stats.insert(), [
            {'gameid': 'g1', 'teamid': 't1', 'teamname': 'A', 'league': 'LCK', 'year': 2022},
            {'gameid': 'g2', 'teamid': 't2', 'teamname': 'B', 'league': 'LPL', 'year': 2022},
        ])
        
    return engine, stat_table, match_raw_stats

@pytest.fixture
def inmemory_tables():
    return setup_inmemory_db()

@patch('prometheus.matches._get_engine_and_tables')
def test_retrieve_dataframe_from_table_inmemory(mock_get_engine_and_tables, inmemory_tables):
    engine, stat_table, match_raw_stats = inmemory_tables
    mock_get_engine_and_tables.return_value = (engine, stat_table, match_raw_stats)
    
    filters = {'league': 'LCK', 'year': 2022}
    df, _ = _retrieve_dataframe_from_table('match_lore_stats', filters)
    
    assert not df.empty
    assert df['teamname'].iloc[0] == 'A'
    assert df['feature1'].iloc[0] == 1.0
