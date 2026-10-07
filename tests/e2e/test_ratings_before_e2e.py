"""The one-read rating lookups give exactly what the per-day queries give."""

import datetime

import numpy as np
import pandas as pd
import pytest

from prometheus import elo, schedule, utils
from prometheus.form import form_states, load_form_games, opponent_adjust

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def days():
    """A day before any game, then game days and days after a game day, spread
    evenly over the data (a fixed number, so the full DB in CI stays quick: each
    old per-day query takes about a second there)."""
    dates = pd.read_sql(
        "SELECT DISTINCT DATE(date) AS day FROM matches", utils.get_engine()
    )
    game_days = sorted(datetime.date.fromisoformat(d) for d in dates["day"])
    picks = [game_days[i] for i in np.linspace(0, len(game_days) - 1, 8, dtype=int)]
    after = [d + datetime.timedelta(days=1) for d in picks[1::2]]
    return [game_days[0] - datetime.timedelta(days=30), *picks, *after]


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
