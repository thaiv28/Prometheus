"""Finished live maps, kept small for the live results pages.

A finished map's page file (`<match>/pages/map<n>.json` in the backup bucket,
about 3 MB: every frame received) is cut to what the results figure draws:
our calls, Kalshi's middle price and the gold lead, each at seconds of game
time on the watch page's axis (`live_state.js` `axis`), so the figure reads the
same as Figure 1 there. Team order is the match's fixed order: every `p` and
price is the first team's chance, the gold lead is first team minus second.

    python -m prometheus.live.archive data/live/<match>/pages/map2.json out.json

A map the service tracked without Kalshi (the contract wasn't found, or quotes
started after the map began) gets Kalshi's minute prices for the map contract
from its public candlesticks (`backfill`; `--offline` skips it), marked
`market_backfilled` (the line) and `pregame.backfilled` (the pre-map price).

`scripts/live_archive.sh` makes one `map<n>.min.json` beside each page file in
the bucket (again when `SCHEMA` moves) and restores them (with each match's
`results.json`) for the build.
"""

import json
import sys
from datetime import UTC, datetime, timedelta
from itertools import pairwise
from pathlib import Path

from .. import markets
from .kalshi import MATCH_SERIES, SERIES, contract

SCHEMA = 2  # 2: Kalshi backfilled from candlesticks

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


def _contract_markets(start, get):
    """Every map and series market closing within two weeks after `start`."""
    out = []
    for series in (SERIES, MATCH_SERIES):
        cursor = None
        while True:
            query = {
                "series_ticker": series,
                "min_close_ts": int(start.timestamp()),
                "max_close_ts": int((start + timedelta(days=14)).timestamp()),
                "limit": 1000,
            }
            if cursor:
                query["cursor"] = cursor
            page = get("/markets", **query)
            out += [dict(m, _series=series) for m in page.get("markets", [])]
            cursor = page.get("cursor")
            if not cursor or not page.get("markets"):
                break
    return out


def _dollars(block):
    try:
        return float((block or {})["close_dollars"])
    except (KeyError, TypeError, ValueError):
        return None


def backfill(page, get=markets.get):
    """`page` with Kalshi's minute prices where the service recorded none: the
    map contract (the series one for a deciding map, which has no map market)
    for the match's first team, from its candlesticks; the last minute before
    the map's first frame is the pre-map price. Unchanged when nothing is found."""
    match, game = page["match"], page["game"]
    frames = sorted(game.get("frames") or [], key=lambda f: f.get("at") or "")
    pre = game.get("pregame") or {}
    if not frames or (game.get("market") and pre.get("market")):
        return page
    start = datetime.fromisoformat(frames[0]["at"].replace("Z", "+00:00"))
    end = datetime.fromisoformat(
        (game.get("ended_at") or frames[-1]["at"]).replace("Z", "+00:00")
    )
    mapping = {
        "teams": [{"name": t["name"], "code": t.get("code")} for t in match["teams"]]
    }
    found = _contract_markets(start - timedelta(hours=12), get)
    ticker = series = None
    # Kalshi dates a match by its scheduled day (US Eastern); a map can start
    # hours after it, past midnight.
    for day in (start, start - timedelta(hours=6)):
        stamp = day.astimezone(UTC).isoformat()
        for number, kind in ((game["number"], SERIES), (None, MATCH_SERIES)):
            if number is None and game["number"] != match.get("best_of"):
                continue
            pool = [m for m in found if m["_series"] == kind]
            ticker = contract(pool, mapping, number, stamp)
            if ticker:
                series = kind
                break
        if ticker:
            break
    if not ticker:
        return page
    candles = get(
        f"/series/{series}/markets/{ticker}/candlesticks",
        start_ts=int((start - timedelta(minutes=30)).timestamp()),
        end_ts=int(end.timestamp()) + 60,
        period_interval=1,
    ).get("candlesticks", [])
    quotes = []
    for c in candles:
        bid, ask = _dollars(c.get("yes_bid")), _dollars(c.get("yes_ask"))
        if bid is None or ask is None:
            continue
        at = datetime.fromtimestamp(c["end_period_ts"], UTC).isoformat()
        quotes.append({"at": at, "bid": bid, "ask": ask})
    before = [q for q in quotes if q["at"] < frames[0]["at"]]
    during = [q for q in quotes if q["at"] >= frames[0]["at"]]
    game = dict(game)
    if not game.get("market") and during:
        game["market"] = during
        game["market_backfilled"] = True
    if not pre.get("market") and before:
        game["pregame"] = dict(pre, market=before[-1], backfilled=True)
    return dict(page, game=game)


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
        "schema": SCHEMA,
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
            "backfilled": bool(pre.get("backfilled")),
        },
        "calls": calls,
        "market": market,
        "market_backfilled": bool(game.get("market_backfilled")),
        "gold": gold,
    }


def main(argv=None):
    args = argv or sys.argv[1:]
    source, out = [a for a in args if not a.startswith("--")][:2]
    page = json.loads(Path(source).read_text())
    if "--offline" not in args:
        try:
            page = backfill(page)
        except (OSError, ValueError, KeyError) as error:
            print(f"Kalshi backfill skipped: {error}", file=sys.stderr)
    data = compact(page)
    Path(out).write_text(json.dumps(data, separators=(",", ":")) + "\n")


if __name__ == "__main__":
    main()
