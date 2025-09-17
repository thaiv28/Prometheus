import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float


@pytest.fixture
def inmemory_tables():
    return setup_inmemory_db()


def setup_inmemory_db():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stat_table = Table(
        "match_lore_stats",
        metadata,
        Column("gameid", String, primary_key=True),
        Column("teamid", String),
        Column("gpm", Float),
        Column("dragon_per_10", Float),
    )
    match_raw_stats = Table(
        "match_raw_stats",
        metadata,
        Column("gameid", String, primary_key=True),
        Column("teamid", String),
        Column("result", Float),
        Column("teamname", String),
        Column("league", String),
        Column("year", Integer),
    )
    metadata.create_all(engine)
    # Insert more robust test data
    with engine.begin() as conn:
        conn.execute(
            stat_table.insert(),
            [
                {
                    "gameid": "g1",
                    "teamid": "t1",
                    "gpm": 1800,
                    "dragon_per_10": 0.3,
                },  # A
                {
                    "gameid": "g2",
                    "teamid": "t2",
                    "gpm": 2000,
                    "dragon_per_10": 0.5,
                },  # B (strongest)
                {
                    "gameid": "g3",
                    "teamid": "t3",
                    "gpm": 1600,
                    "dragon_per_10": 0.1,
                },  # C (weakest)
                {
                    "gameid": "g4",
                    "teamid": "t4",
                    "gpm": 1700,
                    "dragon_per_10": 0.2,
                },  # D
                {
                    "gameid": "g5",
                    "teamid": "t1",
                    "gpm": 1850,
                    "dragon_per_10": 0.35,
                },  # A
                {
                    "gameid": "g6",
                    "teamid": "t2",
                    "gpm": 2100,
                    "dragon_per_10": 0.6,
                },  # B (strongest)
                {
                    "gameid": "g7",
                    "teamid": "t3",
                    "gpm": 1650,
                    "dragon_per_10": 0.15,
                },  # C (weakest)
                {
                    "gameid": "g8",
                    "teamid": "t4",
                    "gpm": 1750,
                    "dragon_per_10": 0.25,
                },  # D
            ],
        )
        conn.execute(
            match_raw_stats.insert(),
            [
                {
                    "gameid": "g1",
                    "teamid": "t1",
                    "teamname": "A",
                    "league": "LCK",
                    "year": 2022,
                    "result": 1.0,
                },
                {
                    "gameid": "g2",
                    "teamid": "t2",
                    "teamname": "B",
                    "league": "LPL",
                    "year": 2022,
                    "result": 1.0,
                },
                {
                    "gameid": "g3",
                    "teamid": "t3",
                    "teamname": "C",
                    "league": "LEC",
                    "year": 2022,
                    "result": 0.0,
                },
                {
                    "gameid": "g4",
                    "teamid": "t4",
                    "teamname": "D",
                    "league": "LCS",
                    "year": 2022,
                    "result": 1.0,
                },
                {
                    "gameid": "g5",
                    "teamid": "t1",
                    "teamname": "A",
                    "league": "LCK",
                    "year": 2023,
                    "result": 0.0,
                },
                {
                    "gameid": "g6",
                    "teamid": "t2",
                    "teamname": "B",
                    "league": "LPL",
                    "year": 2023,
                    "result": 1.0,
                },
                {
                    "gameid": "g7",
                    "teamid": "t3",
                    "teamname": "C",
                    "league": "LEC",
                    "year": 2023,
                    "result": 0.0,
                },
                {
                    "gameid": "g8",
                    "teamid": "t4",
                    "teamname": "D",
                    "league": "LCS",
                    "year": 2023,
                    "result": 0.0,
                },
            ],
        )
    return engine, stat_table, match_raw_stats
