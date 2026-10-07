"""The `before` filter keeps games strictly before the cutoff date, wherever it is read."""

import pandas as pd
import pytest

from prometheus import utils
from prometheus.form import load_form_games
from prometheus.matches import get_matches_frame
from prometheus.ranking import get_glory_ranking
from prometheus.season import load_season_games
from prometheus.types import ALL_MAJOR_LEAGUES

YEAR = 2022


@pytest.fixture(scope="module")
def games():
    """Every team-game of YEAR with its date."""
    return pd.read_sql(
        f"SELECT gameid, teamid, teamname, league, date FROM matches WHERE year = {YEAR}",
        utils.get_engine(),
    )


@pytest.fixture(scope="module")
def cutoff(games):
    """A mid-season day with a game on it, as 'YYYY-MM-DD'."""
    days = sorted(games["date"].str[:10].unique())
    return days[len(days) // 2]


def _expected(games, cutoff):
    day = games["date"].str[:10]
    earlier = set(games.loc[day < cutoff, "gameid"])
    on_or_after = set(games.loc[day >= cutoff, "gameid"])
    # The cutoff day has a game, so "on the cutoff" is tested, not only "after".
    assert earlier and set(games.loc[day == cutoff, "gameid"])
    return earlier, on_or_after


def test_matches_frame_before(games, cutoff):
    earlier, on_or_after = _expected(games, cutoff)
    df = get_matches_frame("match_glory_stats", {"years": [YEAR], "before": cutoff})
    assert set(df["gameid"]) == earlier
    assert not set(df["gameid"]) & on_or_after


def test_matches_frame_before_takes_a_timestamp(games, cutoff):
    # A datetime cuts at the start of its day, like the date string.
    stamp = pd.Timestamp(cutoff) + pd.Timedelta(hours=18)
    df = get_matches_frame("match_glory_stats", {"years": [YEAR], "before": stamp})
    assert set(df["gameid"]) == _expected(games, cutoff)[0]


@pytest.mark.parametrize(
    "load",
    [
        load_form_games,
        lambda before=None: load_season_games(years=[YEAR], before=before),
    ],
    ids=["form", "season"],
)
def test_form_and_season_games_before(load, games, cutoff):
    _, on_or_after = _expected(games, cutoff)
    everything = load()
    filtered = load(before=cutoff)
    # Exactly the games the loader returns without a cutoff, less those on or after it.
    kept = everything.loc[everything["date"].str[:10] < cutoff, "gameid"]
    assert set(filtered["gameid"]) == set(kept)
    assert not set(filtered["gameid"]) & on_or_after
    assert set(everything["gameid"]) & on_or_after


def test_glory_ranking_before(games, cutoff, using_fixture_db):
    earlier, _ = _expected(games, cutoff)
    ranking = get_glory_ranking(
        league=ALL_MAJOR_LEAGUES, year=YEAR, minimum_matches=0, before=cutoff
    )
    majors = games[games["league"].isin(ALL_MAJOR_LEAGUES)]
    teams_before = set(majors.loc[majors["gameid"].isin(earlier), "teamname"])
    assert set(ranking["teamname"]) == teams_before
    if using_fixture_db:
        # In the sample some teams' first game comes after the cutoff.
        assert teams_before < set(majors["teamname"])
