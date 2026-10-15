"""Frozen regional forecast calibration; never changes Elo's rating state.

Only international fixtures are eligible. The artifact is fitted offline on
completed earlier events; snapshots freeze coefficients through an event. Runtime
only reads JSON. Event titles and known historical windows exclude qualifiers.
"""

import datetime as dt
import json
import math
import os
from functools import lru_cache
from pathlib import Path

from prometheus.types import INTERNATIONAL_LEAGUES

PATH = Path(__file__).with_name("regional_calibration.json")
VERSION = "regional-v1"
ALIASES = (
    ("world star challengers invitational", "WSCI"),
    ("demacia cup global invitational", "DCGI"),
    ("mid-season invitational", "MSI"),
    ("esports world cup", "EWC"),
    ("first stand", "FST"),
    ("world championship", "Worlds"),
    ("worlds", "Worlds"),
)


def day(value=None):
    if value is None:
        return dt.datetime.now(dt.UTC).date().isoformat()
    if isinstance(value, dt.datetime):
        value = value.astimezone(dt.UTC) if value.tzinfo else value
        return value.date().isoformat()
    if isinstance(value, dt.date):
        return value.isoformat()
    return str(value)[:10]


def event_code(event=None, title=""):
    if any(x in str(title).lower() for x in ("qualifier", "regional finals")):
        return None
    if event in INTERNATIONAL_LEAGUES or event == "international":
        return event
    text = str(title or event or "").lower()
    return next((code for name, code in ALIASES if name in text), None)


@lru_cache(maxsize=1)
def load():
    data = json.loads(PATH.read_text())
    if data.get("version") != VERSION:
        raise ValueError("Unsupported regional calibration artifact")
    previous = ""
    for model in data["snapshots"]:
        if model["available_from"] <= previous:
            raise ValueError(
                "Regional calibration snapshots must be ordered and unique"
            )
        if (
            model["trained_through"]
            and model["trained_through"] >= model["available_from"]
        ):
            raise ValueError("Regional calibration uses future training data")
        values = [model["slope"], *model["effects"].values()]
        if model["slope"] <= 0 or not all(math.isfinite(x) for x in values):
            raise ValueError("Invalid regional calibration coefficients")
        previous = model["available_from"]
    return data


def eligible(event=None, title="", event_day=None):
    code = event_code(event, title)
    if code is None:
        return False
    when = day(event_day)
    window = load().get("event_windows", {}).get(f"{code}-{when[:4]}")
    return window is None or window[0] <= when <= window[1]


def snapshot(at=None, event=None, event_day=None):
    when = day(at)
    played = day(event_day or at)
    code = event_code(event)
    snapshots = load()["snapshots"]
    # Freeze a known tournament's model; never admit a coefficient before its
    # final training day, including calls made the evening before event entry.
    for tournament in load()["events"]:
        if (
            tournament["event"] == code
            and tournament["start"] <= played <= tournament["end"]
        ):
            identifier = tournament["model"]
            if identifier and identifier <= when:
                return next(m for m in snapshots if m["available_from"] == identifier)
            if identifier is None:
                return None
            break
    return next((m for m in reversed(snapshots) if m["available_from"] <= when), None)


def probability(
    base, elo_gap, home1, home2, *, at=None, event=None, title="", event_day=None
):
    if os.environ.get("REGIONAL_CALIBRATION", "1") == "0":
        return base
    if (
        not home1
        or not home2
        or home1 in INTERNATIONAL_LEAGUES
        or home2 in INTERNATIONAL_LEAGUES
    ):
        return base
    if home1 == home2 or not eligible(event, title, event_day or at):
        return base
    code = event_code(event, title)
    model = snapshot(at, code, event_day)
    if model is None:
        return base
    logit = (
        model["slope"] * float(elo_gap)
        + model["effects"].get(home1, 0.0)
        - model["effects"].get(home2, 0.0)
    )
    return (
        1 / (1 + math.exp(-logit))
        if logit >= 0
        else math.exp(logit) / (1 + math.exp(logit))
    )


def apply_frame(
    frame, probabilities, gap="elo_live", homes=("blue_league", "red_league")
):
    """Apply exactly the production forecast to native benchmark probabilities."""
    import numpy as np

    out = np.asarray(probabilities).copy()
    if not all(c in frame for c in ("date", "league", gap, *homes)):
        return out
    mask = frame["league"].isin(INTERNATIONAL_LEAGUES) & (
        frame[homes[0]] != frame[homes[1]]
    )
    for i in np.flatnonzero(mask.to_numpy()):
        row = frame.iloc[i]
        out[i] = probability(
            out[i],
            row[gap],
            row[homes[0]],
            row[homes[1]],
            at=row["date"],
            event=row["league"],
            event_day=row["date"],
        )
    return out
