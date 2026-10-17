"""Dependency-free inference for the separate full-timeline research model."""

import math
import sqlite3
from pathlib import Path

from .feed import timestamp

# The model the live service calls with (and `scripts/evaluate_live.py` scores).
MODEL_PATH = Path(__file__).with_name("time_model_v1.json")
FEATURES = ["gold_k", "gold_fraction", "elo_hundred", "time", "gold_time", "elo_time"]


def features(clock_seconds, blue_gold, red_gold, blue_elo, red_elo):
    values = [clock_seconds, blue_gold, red_gold, blue_elo, red_elo]
    if not all(type(v) in {int, float} and math.isfinite(v) for v in values):
        raise ValueError("finite clock/gold/Elo required")
    if clock_seconds < 0 or min(blue_gold, red_gold) <= 0:
        raise ValueError("nonnegative clock and positive actual gold required")
    gold = (blue_gold - red_gold) / 1000
    elo = (blue_elo - red_elo) / 100
    t = clock_seconds / 1200
    return [
        gold,
        (blue_gold - red_gold) / (blue_gold + red_gold),
        elo,
        t,
        gold * t,
        elo * t,
    ]


def predict(model, clock_seconds, blue_gold, red_gold, blue_elo, red_elo):
    if model.get("schema") != "time_gold_elo_v1" or model.get("features") != FEATURES:
        raise ValueError("unsupported time-aware model contract")
    low, high = model["supported_seconds"]
    if not low <= clock_seconds <= high:
        raise ValueError("outside measured model time range")
    x = features(clock_seconds, blue_gold, red_gold, blue_elo, red_elo)
    mean, scale, coef = model["mean"], model["scale"], model["coef"]
    if (
        len(mean) != 6
        or len(scale) != 6
        or len(coef) != 6
        or not all(v > 0 and math.isfinite(v) for v in scale)
    ):
        raise ValueError("invalid numeric model parameters")
    z = model["intercept"] + sum(
        (v - m) / s * c for v, m, s, c in zip(x, mean, scale, coef)
    )
    z = model["calibration_slope"] * z + model["calibration_intercept"]
    if not math.isfinite(z):
        raise ValueError("nonfinite model logit")
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


"""Research win-chance calls at every published frame from the full-timeline model.

Elapsed game time is estimated from the feed's own source timestamps: zero at the
first frame where both teams hold exactly the starting 2,500 gold, minus
stretches where combined gold stops rising (passive income never stops in play,
so a flat total means a pause). This is an estimate, not a verified game clock.
"""


START_GOLD = 2500
# Passive gold starts about a minute in; before this a flat total is normal.
PAUSE_CHECK_AFTER = 120
# A flat combined total for at least this long counts as paused.
PAUSE_SECONDS = 15
BY = "Timeline gold + dated Elo (research)"


def elapsed_seconds(frames, start=None):
    """Estimated elapsed seconds per frame (None before a known start).

    `start` is the source time of the first 2,500/2,500 frame when it was found
    in the feed's history (late join); otherwise the first such frame seen.
    """
    out, paused = [], 0.0
    start = timestamp(start) if start else None
    flat_since, last_total, last_t = None, None, None
    for frame in frames:
        t = timestamp(frame["source_at"])
        golds = [team.get("gold") for team in frame["teams"]]
        if start is not None and t < start:
            out.append(None)
            continue
        if start is None:
            if golds == [START_GOLD, START_GOLD]:
                start = t
            else:
                out.append(None)
                continue
        if None in golds or (last_t is not None and t < last_t):
            out.append(None)
            continue
        total = sum(golds)
        if total != last_total:
            if flat_since is not None and last_t is not None:
                flat = (last_t - flat_since).total_seconds()
                if flat >= PAUSE_SECONDS and (
                    (flat_since - start).total_seconds() - paused >= PAUSE_CHECK_AFTER
                ):
                    paused += flat
            flat_since, last_total = t, total
        last_t = t
        raw = (t - start).total_seconds() - paused
        flat = (t - flat_since).total_seconds()
        if flat >= PAUSE_SECONDS and raw - flat >= PAUSE_CHECK_AFTER:
            raw -= flat  # still paused: hold the clock
        out.append(max(0.0, raw))
    return out


def latest_elo(db_path, team_name, before):
    """Latest Prometheus game-length Elo for an exact team name before a time."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        row = conn.execute(
            "SELECT m.date, e.post_match_elo FROM matches m JOIN game_length_elo e"
            " ON e.gameid=m.gameid AND e.teamid=m.teamid"
            " WHERE m.teamname=? AND m.date<? ORDER BY m.date DESC LIMIT 1",
            (team_name, before.strftime("%Y-%m-%d %H:%M:%S")),
        ).fetchone()
    if row is None:
        raise ValueError(f"no Prometheus Elo for {team_name}")
    return {"elo": row[1], "as_of": row[0]}


def timeline_calls(page, model, ratings, start=None):
    """Pregame and per-minute calls for teams[0]; ratings in match-team order.

    Also sets each frame's `clock_estimate` (seconds, or None).
    """
    game = page.get("game")
    if not game or game.get("blue") not in (0, 1):
        return None, []
    blue = game["blue"]

    def first(p_blue):
        return p_blue if blue == 0 else 1 - p_blue

    elo = [ratings[blue]["elo"], ratings[1 - blue]["elo"]]
    pregame = first(predict(model, 0, START_GOLD, START_GOLD, *elo))
    calls = []
    frames = game["frames"]
    for frame, seconds in zip(frames, elapsed_seconds(frames, start)):
        frame["clock_estimate"] = None if seconds is None else round(seconds, 1)
        if seconds is None or seconds > model["supported_seconds"][1]:
            continue
        gold = [frame["teams"][blue]["gold"], frame["teams"][1 - blue]["gold"]]
        if None in gold or min(gold) <= 0:
            continue
        call = {
            "minute": round(seconds / 60, 1),
            "p": first(predict(model, seconds, *gold, *elo)),
            "by": BY,
            "at": frame["at"],
        }
        # One call per estimated minute keeps the chart readable; the newest wins.
        if calls and int(calls[-1]["minute"]) == int(call["minute"]):
            calls[-1] = call
        else:
            calls.append(call)
    return pregame, calls
