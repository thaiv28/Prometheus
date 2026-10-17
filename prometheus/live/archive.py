"""Finished live maps, kept small for the live results pages.

A finished map's page file (`<match>/pages/map<n>.json` in the backup bucket,
about 3 MB: every frame received) is cut to what the results figure draws:
our calls, Kalshi's middle price and the gold lead, each at seconds of game
time on the watch page's axis (`live_state.js` `axis`), so the figure reads the
same as Figure 1 there. Team order is the match's fixed order: every `p` and
price is the first team's chance, the gold lead is first team minus second.

    python -m prometheus.live.archive data/live/<match>/pages/map2.json out.json

`scripts/live_archive.sh` makes one `map<n>.min.json` beside each page file in
the bucket and restores them (with each match's `results.json`) for the build.
"""

import json
import sys
from datetime import datetime
from itertools import pairwise
from pathlib import Path

MAX_SPREAD = 0.1  # as live_state.js: a wider quote is too thin to call a price
GOLD_STEP = 30  # seconds of game time between kept gold readings


def _time(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except (AttributeError, ValueError):
        return None


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def axis(frames):
    """Seconds of game time for a wall-clock time, as live_state.js `axis` does:
    the game clock when every frame has one, else the estimated clock, else time
    since the first frame. Between two frames a time maps linearly."""
    for key in ("clock", "clock_estimate"):
        pts = [(_time(f.get("at")), _num(f.get(key))) for f in frames]
        pts = [p for p in pts if p[0] is not None]
        if pts and all(c is not None for _, c in pts):
            break
    else:
        t0 = _time(frames[0].get("at")) if frames else None
        return lambda t: None if t0 is None or t is None else max(0.0, t - t0)

    def x(t):
        if t is None:
            return None
        if t <= pts[0][0]:
            return max(0.0, pts[0][1] - (pts[0][0] - t))
        for (ta, ca), (tb, cb) in pairwise(pts):
            if t <= tb:
                return ca + (cb - ca) * (t - ta) / (tb - ta) if tb > ta else cb
        return pts[-1][1] + (t - pts[-1][0])

    return x


def _mid(q):
    bid, ask = _num(q.get("bid")), _num(q.get("ask"))
    if bid is None or ask is None or ask < bid or ask - bid > MAX_SPREAD:
        return None
    return round((bid + ask) / 2, 3)


def compact(page):
    """One finished map's page file as the results page needs it."""
    match, game = page["match"], page["game"]
    frames = sorted(game.get("frames") or [], key=lambda f: f.get("at") or "")
    x = axis(frames)
    length = x(_time(frames[-1]["at"])) if frames else None

    calls = []
    for c in sorted(game.get("calls") or [], key=lambda c: c.get("at") or ""):
        s, p = x(_time(c.get("at"))), _num(c.get("p"))
        if s is not None and p is not None:
            calls.append([round(s), round(p, 3)])

    market, last = [], object()
    for q in sorted(game.get("market") or [], key=lambda q: q.get("at") or ""):
        s, mid = x(_time(q.get("at"))), _mid(q)
        if s is None or mid == last:
            continue  # keep only changes: a step line needs nothing between
        market.append([round(s), mid])
        last = mid

    gold, next_s = [], 0
    for f in frames:
        s = x(_time(f.get("at")))
        teams = f.get("teams") or []
        golds = [_num((t or {}).get("gold")) for t in teams[:2]]
        if s is None or len(golds) < 2 or None in golds or s < next_s:
            continue
        gold.append([round(s), golds[0] - golds[1]])
        next_s = s + GOLD_STEP

    pre = game.get("pregame") or {}
    pre_market = pre.get("market")
    return {
        "schema": 1,
        "match": {
            "id": match["id"],
            "league": match.get("league"),
            "event": match.get("event"),
            "best_of": match.get("best_of"),
            "teams": [t["name"] for t in match["teams"]],
        },
        "number": game["number"],
        "blue": game.get("blue"),
        "winner": game.get("winner"),
        "start_at": frames[0]["at"] if frames else None,
        "ended_at": game.get("ended_at"),
        "length": round(length) if length is not None else None,
        "pregame": {
            "p": _num(pre.get("p")),
            "by": pre.get("by"),
            "market": _mid(pre_market) if pre_market else None,
        },
        "calls": calls,
        "market": market,
        "gold": gold,
    }


def main(argv=None):
    source, out = (argv or sys.argv[1:])[:2]
    data = compact(json.loads(Path(source).read_text()))
    Path(out).write_text(json.dumps(data, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
