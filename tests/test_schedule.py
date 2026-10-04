"""Unit tests for prometheus.schedule: name matching, odds, league labels, the
prediction log and the scorecard. No network and no database."""

import datetime
import math

import pandas as pd
import pytest

from prometheus import schedule
from prometheus.forge import CROSS_REGION_ELO_WEIGHT, ELO_WEIGHT

UTC = datetime.timezone.utc


def test_fold_and_strip_disambiguation():
    assert schedule.fold("Barça eSports") == "barca esports"
    assert schedule.fold("Movistar KOI Fénix!") == "movistar koi fenix"
    assert schedule.strip_disambiguation("LYON (2024 American Team)") == "LYON"
    assert schedule.strip_disambiguation("Gen.G") == "Gen.G"


def test_team_matcher_prefers_alias_exact_folded_then_stripped_and_newest():
    teams = pd.DataFrame(
        {
            "teamname": ["LYON", "Lyon", "Ninjas in Pyjamas", "Gen.G"],
            "latest_date": ["2026-09-01", "2019-01-01", "2026-09-06", "2026-09-13"],
        }
    )
    match = schedule.TeamMatcher(teams, aliases={"Ninjas in Pyjamas.CN": "Ninjas in Pyjamas"})
    assert match("Gen.G") == "Gen.G"
    assert match("gen g") == "Gen.G"
    # Two teams fold to "lyon": the one that played most recently wins.
    assert match("LYON (2024 American Team)") == "LYON"
    assert match("Ninjas in Pyjamas.CN") == "Ninjas in Pyjamas"
    assert match("Unknown Squad") is None
    assert match("TBD") is None
    assert match(None) is None


def test_series_probability():
    assert schedule.series_probability(0.6, 1) == pytest.approx(0.6)
    assert schedule.series_probability(0.6, 3) == pytest.approx(0.6**2 * (3 - 2 * 0.6))
    assert schedule.series_probability(0.6, 5) == pytest.approx(0.6**3 * (10 - 15 * 0.6 + 6 * 0.6**2))
    for bo in (1, 3, 5):
        assert schedule.series_probability(0.5, bo) == pytest.approx(0.5)
    # A favourite is a bigger favourite over more games.
    assert schedule.series_probability(0.6, 5) > schedule.series_probability(0.6, 3) > 0.6


def test_game_probability_picks_the_method_by_league():
    lck_a = {"league": "LCK", "elo": 1800, "forge": 1900}
    lck_b = {"league": "LCK", "elo": 1800, "forge": 1800}
    lec = {"league": "LEC", "elo": 1700, "forge": 2000}
    em_a = {"league": "EM", "elo": 1600, "forge": 1650}
    em_b = {"league": "EM", "elo": 1500, "forge": 1500}

    p, method = schedule.game_probability(lck_a, lck_b)
    assert method == "forge"
    assert p == pytest.approx(1 / (1 + math.exp(-ELO_WEIGHT * 100)))

    p, method = schedule.game_probability(lck_b, lec)
    assert method == "elo-cross"  # FORGE ratings don't compare across leagues
    assert p == pytest.approx(1 / (1 + math.exp(-CROSS_REGION_ELO_WEIGHT * 100)))

    p, method = schedule.game_probability(em_a, em_b)
    assert method == "elo"  # FORGE isn't validated outside the major leagues
    assert p == pytest.approx(1 / (1 + 10 ** (-100 / 400)))


@pytest.mark.parametrize(
    "event_league, page, homes, expected",
    [
        ("World Championship", "LPL/2026 Season/Regional Finals", ("LPL", "LPL"), "LPL"),
        ("World Championship", "2026 Season World Championship/Main Event", ("LCK", "LPL"), "Worlds"),
        ("World Championship", "2026 Season World Championship/Main Event", ("LCK", "LCK"), "Worlds"),
        ("League of Legends Championship Series", "LCS/2027 Season/Promotion", ("NACL", "WSCI"), "LCS"),
        ("EMEA Masters", "EMEA Masters/2026 Season", ("LFL", "LES"), "EM"),
        ("League of Legends Championship Series", "LCS/2026 Season/Summer Playoffs", ("LCS", "LCS"), "LCS"),
        ("EMEA Masters", "EMEA Masters/2026 Season", ("EM", "EM"), "EM"),
        ("Some Cup", "Some Cup", ("LFL", "EM"), "Intl"),
        ("Some Cup", "Some Cup", (None, "EM"), "EM"),
        ("Some Cup", "Some Cup", (None, None), "Other"),
    ],
)
def test_event_league(event_league, page, homes, expected):
    row = {"event_league": event_league, "overview_page": page}
    assert schedule.event_league(row, *homes) == expected


def _schedule(rows):
    base = {"best_of": 1, "winner": None, "score1": None, "score2": None, "event": "Cup",
            "event_league": "LoL Champions Korea", "overview_page": "LCK/2026"}
    return schedule.parse_schedule([{**base, **r} for r in rows])


def _ratings():
    return pd.DataFrame(
        {"teamname": ["T1", "Gen.G"], "league": ["LCK", "LCK"], "elo": [1800.0, 1900.0],
         "form": [0.0, 0.0], "forge": [1800.0, 1900.0], "latest_date": ["2026-09-01"] * 2}
    ).set_index("teamname")


def test_parse_schedule_types_and_predict():
    df = _schedule([
        {"match_id": "m1", "start": "2026-10-04 08:00:00", "team1": "T1", "team2": "Gen.G", "best_of": "5"},
        {"match_id": "m2", "start": "2026-10-04 10:00:00", "team1": "T1", "team2": "TBD"},
    ])
    assert df["best_of"].tolist() == [5, 1]
    assert str(df["start"].dt.tz) == "UTC"
    ratings = _ratings()
    preds = schedule.predict(df, ratings, schedule.TeamMatcher(ratings.reset_index(), aliases={}))
    assert preds[0]["matched"] and preds[0]["method"] == "forge" and preds[0]["league"] == "LCK"
    assert preds[0]["p_game"] < 0.5 and preds[0]["p_series"] < preds[0]["p_game"]
    assert preds[0]["start"] == "2026-10-04T08:00Z"
    assert not preds[1]["matched"] and "p_game" not in preds[1]


def _pred(mid, start, p=0.6, matched=True):
    return {"match_id": mid, "start": start, "team1": "A", "team2": "B", "ours1": "A", "ours2": "B",
            "best_of": 3, "league": "LCK", "matched": matched, "p_game": p, "p_series": p, "method": "forge"}


def test_update_log_refreshes_until_start_then_freezes_and_adds_results():
    log = {}
    sched = _schedule([{"match_id": "m1", "start": "2026-10-04 08:00:00", "team1": "A", "team2": "B"}])
    day_before = datetime.datetime(2026, 10, 3, 10, tzinfo=UTC)
    schedule.update_log(log, sched, [_pred("m1", "2026-10-04T08:00Z", 0.6)], day_before, "2026-10-02")
    assert log["m1"]["p_game"] == 0.6 and not log["m1"]["reconstructed"]
    assert log["m1"]["data_through"] == "2026-10-02"

    # Same day, newer ratings, still before the start: the call is refreshed.
    morning = datetime.datetime(2026, 10, 4, 6, tzinfo=UTC)
    schedule.update_log(log, sched, [_pred("m1", "2026-10-04T08:00Z", 0.7)], morning, "2026-10-03")
    assert log["m1"]["p_game"] == 0.7

    # After the start the call is frozen; the result is filled in.
    done = _schedule([{"match_id": "m1", "start": "2026-10-04 08:00:00", "team1": "A", "team2": "B",
                       "winner": "2", "score1": "1", "score2": "2"}])
    later = datetime.datetime(2026, 10, 5, 10, tzinfo=UTC)
    schedule.update_log(log, done, [_pred("m1", "2026-10-04T08:00Z", 0.2)], later, "2026-10-04",
                        reconstruct=lambda row: pytest.fail("a saved call must not be rebuilt"))
    assert log["m1"]["p_game"] == 0.7
    assert (log["m1"]["winner"], log["m1"]["score1"], log["m1"]["score2"]) == (2, 1, 2)


def test_update_log_reconstructs_matches_already_played():
    log = {}
    sched = _schedule([{"match_id": "old", "start": "2026-09-20 08:00:00", "team1": "A", "team2": "B", "winner": "1"}])
    now = datetime.datetime(2026, 10, 3, tzinfo=UTC)
    schedule.update_log(log, sched, [_pred("old", "2026-09-20T08:00Z", 0.9)], now, "2026-10-02",
                        reconstruct=lambda row: {**_pred("old", "2026-09-20T08:00Z", 0.55), "predicted": None})
    assert log["old"]["reconstructed"] and log["old"]["p_game"] == 0.55 and log["old"]["winner"] == 1


def test_save_and_load_log_round_trip(tmp_path):
    path = tmp_path / "nested" / "log.json"
    log = {"b": _pred("b", "2026-10-05T08:00Z"), "a": _pred("a", "2026-10-04T08:00Z")}
    schedule.save_log(log, path)
    assert schedule.load_log(path) == log
    assert schedule.load_log(tmp_path / "missing.json") == {}


def test_scorecard_counts_series_games_and_log_loss():
    entries = [
        {**_pred("a", "s", 0.6), "winner": 1, "score1": 2, "score2": 1, "reconstructed": False},
        {**_pred("b", "s", 0.6), "winner": 2, "score1": 0, "score2": 2, "reconstructed": True},
        {**_pred("c", "s", 0.6), "reconstructed": False},  # no result yet
        {**_pred("d", "s", 0.6, matched=False), "winner": 1},
    ]
    saved, rebuilt, total = schedule.scorecard(entries)
    assert (saved["series"], saved["right"], saved["games"], saved["games_right"]) == (1, 1, 3, 2)
    assert saved["log_loss"] == pytest.approx(-(2 * math.log(0.6) + math.log(0.4)) / 3)
    assert (rebuilt["series"], rebuilt["right"], rebuilt["games"], rebuilt["games_right"]) == (1, 0, 2, 0)
    assert total["series"] == 2 and total["series_pct"] == pytest.approx(50)
    assert schedule.scorecard([])[2]["log_loss"] is None


def test_is_major():
    assert schedule.is_major({"league": "LCK", "home1": "LCK", "home2": "LCK"})
    assert schedule.is_major({"league": "Worlds", "home1": "LCK", "home2": "LEC"})
    assert not schedule.is_major({"league": "EM", "home1": "EM", "home2": "EM"})
    # An LCS promotion series between two challenger teams isn't a major-league match.
    assert not schedule.is_major({"league": "LCS", "home1": "NACL", "home2": "NACL"})
