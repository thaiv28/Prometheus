from unittest.mock import patch

from sqlalchemy import create_engine, text

from prometheus.elo import get_latest_elos


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
                "CREATE TABLE game_length_elo (gameid TEXT, teamid TEXT, pre_match_elo REAL, post_match_elo REAL, elo_change REAL)"
            )
        )
        conn.execute(
            text(
                "INSERT INTO matches VALUES"
                " ('g1', 't1', 'T1', 'LCK', '2024-08-01'),"
                " ('g2', 't1', 'T1', 'Worlds', '2024-11-02'),"
                " ('g3', 't2', 'Samsung White', 'Worlds', '2014-10-19')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO game_length_elo VALUES"
                " ('g1', 't1', 1600, 1610, 10),"
                " ('g2', 't1', 1610, 1625, 15),"
                " ('g3', 't2', 1500, 1520, 20)"
            )
        )
    return engine


@patch("prometheus.elo.get_engine")
def test_latest_elo_uses_home_league_after_international_event(mock_get_engine):
    mock_get_engine.return_value = _engine()

    df = get_latest_elos("game_length").set_index("teamname")

    # Rating comes from the latest game (Worlds), the league from the home league.
    assert df.loc["T1", "elo"] == 1625
    assert df.loc["T1", "league"] == "LCK"
    # A team only ever seen at an international event keeps that label.
    assert df.loc["Samsung White", "league"] == "Worlds"
