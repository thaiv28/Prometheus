from unittest.mock import patch

from sqlalchemy import create_engine, text

from prometheus.elo import get_latest_elos, get_season_elos


def _engine():
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE matches (gameid TEXT, teamid TEXT, teamname TEXT, league TEXT, date TEXT)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE game_length_elo (gameid TEXT, teamid TEXT, pre_match_elo REAL,"
                " post_match_elo REAL, elo_change REAL, home_league TEXT, league_offset REAL,"
                " main_elo REAL)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE game_length_elo_league_offsets"
                " (gameid TEXT, date TEXT, league TEXT, league_offset REAL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO matches VALUES"
                " ('g1', 't1', 'T1', 'LCK', '2024-08-01'),"
                " ('g2', 't1', 'T1', 'Worlds', '2024-11-02'),"
                " ('g3', 't2', 'Samsung White', 'Worlds', '2014-10-19'),"
                " ('g4', 't3', 'Gen.G', 'LCK', '2024-08-15'),"
                " ('g0', 't3', 'Gen.G', 'LCK', '2023-05-01'),"
                " ('g6', 't4', 'DRX', 'LCK', '2024-07-01'),"
                " ('g7', 't4', 'DRX', 'KeSPA Cup', '2024-08-20')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO game_length_elo VALUES"
                " ('g1', 't1', 1600, 1610, 10, 'LCK', 100, NULL),"
                " ('g2', 't1', 1610, 1625, 15, 'LCK', 104, NULL),"
                " ('g3', 't2', 1500, 1520, 20, NULL, 0, NULL),"
                " ('g4', 't3', 1590, 1580, -10, 'LCK', 100, NULL),"
                " ('g0', 't3', 1540, 1550, 10, 'LCK', 90, NULL),"
                " ('g6', 't4', 1700, 1710, 10, 'LCK', 100, 1710),"
                # An academy lineup under DRX's name at the KeSPA Cup: the team row
                # rates that lineup; main_elo keeps the main roster's rating.
                " ('g7', 't4', 1400, 1395, -5, 'LCK', 100, 1710)"
            )
        )
        # T1's Worlds games moved LCK's offset from 100 to 104, then 106.
        conn.execute(
            text(
                "INSERT INTO game_length_elo_league_offsets VALUES"
                " ('g9', '2023-10-01', 'LCK', 95),"
                " ('g2', '2024-11-02', 'LCK', 104),"
                " ('g5', '2024-11-09', 'LCK', 106)"
            )
        )
    return engine


@patch("prometheus.elo.get_engine")
def test_latest_elo_uses_home_league_after_international_event(mock_get_engine):
    mock_get_engine.return_value = _engine()

    df = get_latest_elos("game_length").set_index("teamname")

    # Rating comes from the latest game (Worlds) plus the league's offset change
    # since, the league from the home league.
    assert df.loc["T1", "elo"] == 1627
    assert df.loc["T1", "league"] == "LCK"
    # A team only ever seen at an international event keeps that label.
    assert df.loc["Samsung White", "league"] == "Worlds"


@patch("prometheus.elo.get_engine")
def test_latest_elo_includes_league_offset_changes_since_last_game(mock_get_engine):
    mock_get_engine.return_value = _engine()

    df = get_latest_elos("game_length").set_index("teamname")
    # Gen.G stayed home; LCK's offset rose from 100 to 106 after its last game.
    assert df.loc["Gen.G", "elo"] == 1586

    import datetime

    df = get_latest_elos("game_length", date=datetime.date(2024, 11, 5)).set_index(
        "teamname"
    )
    # As of Nov 5 only the first offset change (to 104) had happened.
    assert df.loc["Gen.G", "elo"] == 1584


@patch("prometheus.elo.get_engine")
def test_season_elos_are_ratings_at_the_end_of_each_year(mock_get_engine):
    mock_get_engine.return_value = _engine()

    df = get_season_elos("game_length").set_index(["teamname", "year"])

    # 2023: Gen.G's last game left it at 1550 with LCK at 90; LCK ended 2023 at 95.
    assert df.loc[("Gen.G", 2023), "elo"] == 1555
    # 2024: LCK ended the year at 106.
    assert df.loc[("Gen.G", 2024), "elo"] == 1586
    assert df.loc[("T1", 2024), "elo"] == 1627
    # The league is the domestic league played that year, not Worlds.
    assert df.loc[("T1", 2024), "league"] == "LCK"
    assert df.loc[("Samsung White", 2014), "league"] == "Worlds"


@patch("prometheus.elo.get_engine")
def test_latest_elo_rates_the_main_roster_after_a_cup(mock_get_engine):
    mock_get_engine.return_value = _engine()

    df = get_latest_elos("game_length").set_index("teamname")
    # Last game was an academy lineup at the KeSPA Cup: the league stays LCK and the
    # rating is the main roster's (1710) plus LCK's offset change since (100 -> 106).
    assert df.loc["DRX", "league"] == "LCK"
    assert df.loc["DRX", "elo"] == 1716
