"""Fixture groups shared by notifications and forecast reporting."""

from prometheus import regional_calibration
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

MAJORS = {league.value for league in ALL_MAJOR_LEAGUES}
GROUPS = (
    ("major-domestic", "Major domestic"),
    ("major-international", "Major vs major international"),
    ("minor-domestic", "Minor domestic"),
    ("mixed-international", "Major vs minor international"),
    ("minor-international", "Minor vs minor international"),
    ("other-cross-league", "Other cross-league"),
)


def international(entry):
    """Event scope, including two teams from the same home pool."""
    return regional_calibration.eligible(
        entry.get("league"), entry.get("event", ""), entry.get("start")
    )


def classify(entry):
    """Group by home pools and event scope, independently of forecast method."""
    homes = entry.get("home1"), entry.get("home2")
    if not all(homes) or any(home in INTERNATIONAL_LEAGUES for home in homes):
        return None
    major_count = sum(home in MAJORS for home in homes)
    if homes[0] == homes[1]:
        return "major-domestic" if major_count else "minor-domestic"
    if not international(entry):
        return "other-cross-league"
    return {
        2: "major-international",
        1: "mixed-international",
        0: "minor-international",
    }[major_count]
