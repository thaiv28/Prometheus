import pytest
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, Float


@pytest.fixture
def inmemory_engine():
    return setup_inmemory_db()


def setup_inmemory_db():
    engine = create_engine("sqlite:///:memory:")
    metadata = MetaData()
    stat_table = Table(
        "match_glory_stats",
        metadata,
        Column("gameid", String, primary_key=True),
        Column("teamid", String),
        Column("gpm", Float),
        Column("dragon_per_10", Float),
    )
    matches = Table(
        "matches",
        metadata,
        Column("gameid", String, primary_key=True),
        Column("year", Integer),
        Column("split", String),
        Column("league", String),
        Column("teamid", String),
        Column("teamname", String),
        Column("side", String),
        Column("gamelength", Float),
        Column("result", Float),
    )
    metadata.create_all(engine)
    # Insert more robust test data
    with engine.begin() as conn:
        conn.execute(
            stat_table.insert(),
            [
                # 2022
                {
                    "gameid": "g1",
                    "teamid": "t1",
                    "gpm": 100.0,
                    "dragon_per_10": 200.0,
                },  # A
                {
                    "gameid": "g2",
                    "teamid": "t2",
                    "gpm": 200.0,
                    "dragon_per_10": 400.0,
                },  # B (strongest)
                {
                    "gameid": "g3",
                    "teamid": "t3",
                    "gpm": 10.0,
                    "dragon_per_10": 20.0,
                },  # C (weakest)
                {
                    "gameid": "g4",
                    "teamid": "t4",
                    "gpm": 50.0,
                    "dragon_per_10": 100.0,
                },  # D
                # 2023. values are 1/10th of 2022 to mimic meta changes. however, team B is still strongest
                # with a greater margin than in 2022
                {
                    "gameid": "g5",
                    "teamid": "t1",
                    "gpm": 10.0,
                    "dragon_per_10": 20.0,
                },  # A
                {
                    "gameid": "g6",
                    "teamid": "t2",
                    "gpm": 20.0,
                    "dragon_per_10": 40.0,
                },  # B (strongest)
                {
                    "gameid": "g7",
                    "teamid": "t3",
                    "gpm": 1.0,
                    "dragon_per_10": 2.0,
                },  # C (weakest)
                {
                    "gameid": "g8",
                    "teamid": "t4",
                    "gpm": 5.0,
                    "dragon_per_10": 10.0,
                },  # D
            ],
        )
        conn.execute(
            matches.insert(),
            [
                {
                    "gameid": "g1",
                    "year": 2022,
                    "split": "Spring",
                    "league": "LCK",
                    "teamid": "t1",
                    "teamname": "A",
                    "side": "Blue",
                    "gamelength": 35.0,
                    "result": 1.0,
                },
                {
                    "gameid": "g2",
                    "year": 2022,
                    "split": "Spring",
                    "league": "LPL",
                    "teamid": "t2",
                    "teamname": "B",
                    "side": "Red",
                    "gamelength": 32.5,
                    "result": 1.0,
                },
                {
                    "gameid": "g3",
                    "year": 2022,
                    "split": "Spring",
                    "league": "LEC",
                    "teamid": "t3",
                    "teamname": "C",
                    "side": "Blue",
                    "gamelength": 30.0,
                    "result": 0.0,
                },
                {
                    "gameid": "g4",
                    "year": 2022,
                    "split": "Spring",
                    "league": "LCS",
                    "teamid": "t4",
                    "teamname": "D",
                    "side": "Red",
                    "gamelength": 33.0,
                    "result": 0.0,
                },
                {
                    "gameid": "g5",
                    "year": 2023,
                    "split": "Summer",
                    "league": "LCK",
                    "teamid": "t1",
                    "teamname": "A",
                    "side": "Blue",
                    "gamelength": 36.0,
                    "result": 1.0,
                },
                {
                    "gameid": "g6",
                    "year": 2023,
                    "split": "Summer",
                    "league": "LPL",
                    "teamid": "t2",
                    "teamname": "B",
                    "side": "Red",
                    "gamelength": 34.5,
                    "result": 1.0,
                },
                {
                    "gameid": "g7",
                    "year": 2023,
                    "split": "Summer",
                    "league": "LEC",
                    "teamid": "t3",
                    "teamname": "C",
                    "side": "Blue",
                    "gamelength": 31.0,
                    "result": 0.0,
                },
                {
                    "gameid": "g8",
                    "year": 2023,
                    "split": "Summer",
                    "league": "LCS",
                    "teamid": "t4",
                    "teamname": "D",
                    "side": "Red",
                    "gamelength": 32.0,
                    "result": 0.0,
                },
            ],
        )
    return engine
