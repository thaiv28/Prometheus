import pytest

from prometheus.forecast_groups import classify


@pytest.mark.parametrize(
    "home1,home2,league,event,expected",
    [
        ("LCK", "LCK", "Worlds", "Worlds", "major-domestic"),
        ("LPL", "LCK", "Worlds", "Worlds", "major-international"),
        ("LFL", "LFL", "LFL", "Summer", "minor-domestic"),
        ("LPL", "VCS", "Worlds", "Worlds", "mixed-international"),
        ("LFL", "VCS", "Worlds", "Worlds", "minor-international"),
        ("LFL", "PRM", "EM", "EMEA Masters", "other-cross-league"),
        ("LCK", "LCK CL", "LCK", "Regional Cup", "other-cross-league"),
        ("LPL", "LCK", "Worlds", "Worlds Qualifier", "other-cross-league"),
        ("LCK", None, "Worlds", "Worlds", None),
        ("LCK", "Worlds", "Worlds", "Worlds", None),
    ],
)
def test_groups_follow_home_pools_and_actual_event(
    home1, home2, league, event, expected
):
    assert (
        classify(
            {
                "home1": home1,
                "home2": home2,
                "league": league,
                "event": event,
                "start": "2026-10-15T10:00Z",
            }
        )
        == expected
    )
