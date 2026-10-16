import datetime
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "live_wake", Path(__file__).resolve().parents[2] / "scripts" / "live_wake.py"
)
live_wake = importlib.util.module_from_spec(spec)
spec.loader.exec_module(live_wake)

NOW = datetime.datetime(2026, 10, 16, 17, 20, tzinfo=datetime.UTC)


def match(start, league="Worlds", winner=None):
    return {
        "start": start,
        "league": league,
        "winner": winner,
        "team1": "A",
        "team2": "B",
    }


def test_wakes_for_a_broadcast_match_starting_soon_or_still_on():
    soon = match("2026-10-16T18:00Z")
    on = match("2026-10-16T15:00Z")
    assert live_wake.due([soon, on], NOW) == [soon, on]


def test_ignores_far_off_finished_and_unbroadcast_matches():
    far = match("2026-10-16T20:00Z")
    done = match("2026-10-16T16:00Z", winner=1)
    small = match("2026-10-16T18:00Z", league="LFL")
    old = match("2026-10-16T11:00Z")
    assert live_wake.due([far, done, small, old], NOW) == []
