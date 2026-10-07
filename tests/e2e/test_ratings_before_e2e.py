"""The one-read rating lookups give exactly what the per-day queries give."""

import datetime

import pandas as pd
import pytest

from prometheus import elo, schedule, utils
from prometheus.form import form_states, load_form_games, opponent_adjust

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def days():
    """Every game day, the day after each, and one before any game."""
    dates = pd.read_sql(
        "SELECT DISTINCT DATE(date) AS day FROM matches", utils.get_engine()
    )
    game_days = sorted(datetime.date.fromisoformat(d) for d in dates["day"])
    after = [d + datetime.timedelta(days=1) for d in game_days]
    return [game_days[0] - datetime.timedelta(days=30), *game_days[::5], *after[::7]]


def _by_team(frame):
    return frame.sort_values(["teamname", "latest_date"]).reset_index(drop=True)


def test_latest_elos_matches_get_latest_elos_on_every_cutoff(days):
    latest = elo.LatestElos("game_length")
    for day in [None, *days]:
        expected = elo.get_latest_elos("game_length", day)
        got = latest(day)
        if expected.empty:
            assert got.empty
            continue
        pd.testing.assert_frame_equal(
            _by_team(got), _by_team(expected), check_exact=True
        )
        assert got["elo"].tolist() == expected["elo"].tolist()  # same order (elo desc)


def test_ratings_before_class_matches_the_function(days):
    states = form_states(opponent_adjust(load_form_games()))
    before = schedule.RatingsBefore(states)
    for day in days[1:]:
        expected = schedule.ratings_before(states, day)
        # An empty SQL result has untyped columns; values are compared either way.
        pd.testing.assert_frame_equal(
            before(day), expected, check_exact=True, check_dtype=not expected.empty
        )
    assert len(before) == len(set(days[1:]))
