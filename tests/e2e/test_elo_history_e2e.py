"""Elo history's date cutoff is inclusive: every game on the day, none after."""

import datetime

import pandas as pd
import pytest

from prometheus import elo, utils

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def game_day():
    """The middle game day, as a date, and its team-games (dates carry a time of day)."""
    games = pd.read_sql(
        "SELECT m.teamname, m.date FROM game_length_elo e"
        " JOIN matches m ON e.gameid = m.gameid AND e.teamid = m.teamid",
        utils.get_engine(),
    )
    games["day"] = pd.to_datetime(games["date"]).dt.date
    days = sorted(games["day"].unique())
    day = days[len(days) // 2]
    return day, games


def test_history_cutoff_includes_every_game_on_the_day(game_day):
    day, games = game_day
    on_day = games[games["day"] == day]
    # Games later than midnight on the day, so a plain string comparison would drop them.
    assert (pd.to_datetime(on_day["date"]).dt.time > datetime.time(0)).any()

    history = elo.get_elo_history("game_length", date=day)

    assert len(history) == (games["day"] <= day).sum()
    assert pd.to_datetime(history["date"]).dt.date.max() == day


def test_history_cutoff_for_one_team(game_day):
    day, games = game_day
    team = games.loc[games["day"] == day, "teamname"].iloc[0]

    history = elo.get_elo_history("game_length", team=team, date=day)
    before = elo.get_elo_history(
        "game_length", team=team, date=day - datetime.timedelta(days=1)
    )

    mine = games[games["teamname"] == team]
    assert len(history) == (mine["day"] <= day).sum()
    assert len(before) == (mine["day"] < day).sum()
    assert len(history) > len(before)
