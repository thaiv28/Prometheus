"""Find a game's start in the Riot window feed by binary search over its history.

The start is the first frame where both teams hold the starting 2,500 gold
(loading frames before it are zero or absent). Before the start no window has
such a frame; after it every window does, so the search is monotone. About ten
requests from a 90-minute range reach the feed's 10-second query resolution.
"""

from datetime import timedelta

from .feed import timestamp

START_GOLD = 2500
STEP = 10  # the feed's startingTime resolution, seconds


def floor_step(t):
    t = t.replace(microsecond=0)
    return t - timedelta(seconds=t.second % STEP)


def started(frames):
    return any(
        f["blueTeam"]["totalGold"] >= START_GOLD
        and f["redTeam"]["totalGold"] >= START_GOLD
        for f in frames
    )


def find_start(fetch, now, lookback=5400, lag=60):
    """`fetch(t)` returns window frames from t ([] for no content) or raises.

    Returns the source timestamp string of the first 2,500/2,500 frame, or None
    when the start is older than `lookback` or no exact starting frame is seen.
    """
    lo = floor_step(now - timedelta(seconds=lookback))
    hi = floor_step(now - timedelta(seconds=lag))
    hi_frames = fetch(hi)
    if not started(hi_frames) or started(fetch(lo)):
        return None
    while (hi - lo).total_seconds() > STEP:
        mid = floor_step(lo + (hi - lo) / 2)
        if mid <= lo:
            break
        frames = fetch(mid)
        if started(frames):
            hi, hi_frames = mid, frames
        else:
            lo = mid
    for f in sorted(hi_frames, key=lambda f: timestamp(f["rfc460Timestamp"])):
        gold = (f["blueTeam"]["totalGold"], f["redTeam"]["totalGold"])
        if min(gold) >= START_GOLD:
            return f["rfc460Timestamp"] if gold == (START_GOLD, START_GOLD) else None
    return None
