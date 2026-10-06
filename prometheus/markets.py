"""Kalshi's prediction-market prices for pro League of Legends matches.

Kalshi lists a yes/no contract per team for nearly every pro series (series
`KXLOLGAME`; single maps are `KXLOLMAP`), usually from about a day before the
match. A contract's price is the market's chance in dollars, with no bookmaker
margin, only the bid-ask spread. Market data is public (no key), but Kalshi's
API refuses browsers from other sites, so the site shows prices as of each build.

Each build takes the open markets once, matches them to the prediction log by
team names and start time, and stores the market's chance on every match that
hasn't started (`attach_prices`). Like our call, it is frozen at the start.
`scripts/evaluate_markets.py` uses the same parsing to score past calls.
"""

import datetime
import http.client
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

API = "https://api.elections.kalshi.com/trade-api/v2"
USER_AGENT = "Prometheus/1.0 (https://prometheus.thaiv.dev; https://github.com/thaiv28/Prometheus)"
SERIES, MAP = "KXLOLGAME", "KXLOLMAP"
# A match's page on Kalshi's site: this prefix plus the event ticker in lower case.
EVENT_URL = "https://kalshi.com/markets/kxlolgame/league-of-legends-game/"
# Quotes with a wider bid-ask spread are too thin to call a price.
MAX_SPREAD = 0.10
# Kalshi's start time and Leaguepedia's can disagree (a moved match, a day-only
# start); a market matches a logged match between the same teams this close.
MATCH_WINDOW = datetime.timedelta(hours=18)
# The paper bets on the Predictions page buy at the last price read at least this
# long before the start, as the backtest's betting section does.
BET_LEAD = datetime.timedelta(hours=12)
EASTERN = ZoneInfo("America/New_York")

# "If T1 wins the LCK 2026: T1 vs. Gen.G League of Legends match originally
# scheduled for Aug 3, 2026 at 2:00 PM EDT, ..." (some give only the day) and, for
# maps, "If T1 wins map 1 in the LCK 2026: ...". Event names can hold a colon.
RULES = re.compile(
    r"^If (?P<side>.+?) wins (?:map (?P<map>\d+) in )?the (?P<event>.+): (?P<team1>.+?) vs\.? (?P<team2>.+?) "
    r"League of Legends match originally scheduled for (?P<day>\w{3} \d{1,2}, \d{4})(?: at (?P<time>\d{1,2}:\d{2} [AP]M) E[DS]T)?"
)

# Kalshi names that don't fold to an Oracle's Elixir name, often from before a
# rebrand. Grown by hand from the unmatched names `evaluate_markets.py` prints.
MARKET_ALIASES = {
    "DN Freecs": "DN SOOPers",
    "DRX": "Kiwoom DRX",
    "DRX Challengers": "Kiwoom DRX Challengers",
    "Nongshim Red Force": "Nongshim RedForce",
    "OKSavingsBank BRION": "HANJIN BRION",
    "OKSavingsBank BRION Challengers": "HANJIN BRION Challengers",
    "T1 Academy": "T1 Esports Academy",
    "NRG Esports": "NRG",
    "FURIA Esports": "FURIA",
    "Leviatan Esports": "Leviatan",
    "INTZ e-Sports": "INTZ",
    "UCAM Esports Club": "UCAM Esports",
    "CyberCore Esports": "SN CyberCore Esports",
    "Lyon Gaming Academy": "LYON Academy",
    "Rising Bees": "Vitality Rising Bees",
    "The Otter Side": "Otter Side",
    "Skillcamp Esport": "Skillcamp",
    "The Secret Club Esport": "The Secret Club",
    "MAGAZA": "Magaza Esports",
    "PCIFIC": "PCIFIC Esports",
    "Senshi Esports Club": "Senshi eSports",
    "MVK Academy": "MVK Esports Academy",
}


def event_url(ticker):
    """Kalshi's page for a series market's event (where its odds are traded)."""
    return EVENT_URL + ticker.lower()


# ---------------------------------------------------------------- fetching


def get(path, sleep=time.sleep, **query):
    """GET one API path as JSON, waiting out rate limits and dropped connections."""
    url = f"{API}{path}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for wait in (1, 2, 5, 10, 20, 30, 60, None):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            if err.code != 429 or wait is None:
                raise
            print(f"  rate-limited; waiting {wait}s")
            sleep(wait)
        except (urllib.error.URLError, http.client.HTTPException, OSError):
            if wait is None:
                raise
            sleep(wait)


def fetch_open_markets(series=SERIES, sleep=time.sleep):
    """Every open (tradable) market in a series, from Kalshi's live endpoint."""
    markets, cursor = [], None
    while True:
        query = {"series_ticker": series, "status": "open", "limit": 1000}
        if cursor:
            query["cursor"] = cursor
        page = get("/markets", sleep=sleep, **query)
        markets += page.get("markets", [])
        cursor = page.get("cursor")
        if not cursor or not page.get("markets"):
            return markets


# ---------------------------------------------------------------- parsing


def parse_market(m, settled=True):
    """The fields we use from one market, or None when its rules don't parse or,
    with `settled`, it didn't settle yes/no (postponed and cancelled matches
    settle at a price)."""
    rules = RULES.match(m.get("rules_primary", ""))
    if not rules or (settled and m.get("result") not in ("yes", "no")):
        return None
    # Some markets give only the day; their start is taken as midnight Eastern, so
    # a "close" quote comes before any game that day could have begun.
    when = datetime.datetime.strptime(
        f"{rules['day']} {rules['time'] or '12:00 AM'}", "%b %d, %Y %I:%M %p"
    ).replace(tzinfo=EASTERN)
    return {
        "ticker": m["ticker"],
        "event_ticker": m["event_ticker"],
        "event": rules["event"],
        "team1": rules["team1"].strip(),
        "team2": rules["team2"].strip(),
        "side": rules["side"].strip(),
        "map": int(rules["map"]) if rules["map"] else None,
        "start": when.astimezone(datetime.timezone.utc),
        "timed": rules["time"] is not None,
        "open": m["open_time"],
        "close": m["close_time"],
        "won": m.get("result") == "yes",
        "volume": float(m.get("volume_fp") or m.get("volume") or 0),
        "bid": _dollars(m, "yes_bid"),
        "ask": _dollars(m, "yes_ask"),
    }


def _dollars(block, key):
    """A price in dollars; live and historical data name fields differently
    (`close_dollars` / `close`, `yes_bid_dollars` / `yes_bid`)."""
    if not block:
        return None
    value = block.get(f"{key}_dollars", block.get(key))
    return None if value is None else float(value)


def mid(bid, ask):
    """(mid, spread) for a two-sided quote, or (None, None)."""
    if bid is not None and ask is not None and 0 < bid <= ask < 1:
        return (bid + ask) / 2, ask - bid
    return None, None


def book_at(candles, ts):
    """(bid, ask) for "yes" from the last hourly candle that ended by `ts` with a
    two-sided quote, or (None, None)."""
    best = (None, None)
    for c in candles:
        if c["end_period_ts"] > ts:
            break
        bid, ask = _dollars(c.get("yes_bid"), "close"), _dollars(
            c.get("yes_ask"), "close"
        )
        if mid(bid, ask)[0] is not None:
            best = (bid, ask)
    return best


def quote_at(candles, ts):
    """(mid, spread) from the last hourly candle that ended by `ts` with a
    two-sided quote, or (None, None)."""
    return mid(*book_at(candles, ts))


def events(markets, settled=True):
    """Markets grouped by event: one row per match (or per map) with its markets
    and, when settled, team1's result."""
    rows = {}
    for m in filter(None, (parse_market(m, settled) for m in markets)):
        row = rows.setdefault(
            m["event_ticker"],
            {
                k: m[k]
                for k in (
                    "event_ticker",
                    "event",
                    "team1",
                    "team2",
                    "map",
                    "start",
                    "timed",
                )
            },
        )
        row.setdefault("markets", []).append(m)
        if m["side"] == m["team1"]:
            row["won1"] = m["won"]
        elif m["side"] == m["team2"]:
            row["won1"] = not m["won"]
        row["volume"] = row.get("volume", 0) + m["volume"]
    return [r for r in rows.values() if not settled or "won1" in r]


def chance_now(row, team1):
    """(chance `team1` wins, spread) from an event's current quotes: the mean of
    team1's mid and one minus the opponent's, over quotes within `MAX_SPREAD`."""
    chances, spreads = [], []
    for m in row["markets"]:
        p, spread = mid(m["bid"], m["ask"])
        if p is None or spread > MAX_SPREAD:
            continue
        chances.append(p if m["side"] == team1 else 1 - p)
        spreads.append(spread)
    if not chances:
        return None, None
    return sum(chances) / len(chances), sum(spreads) / len(spreads)


def buy_costs(row, team1):
    """(cost of a team-1 contract, cost of a team-2 contract) for a market order
    now: the cheaper of a team's "yes" ask and one minus the opponent's "yes" bid,
    over quotes within `MAX_SPREAD`. None for a side with no usable quote."""
    best = [None, None]
    for m in row["markets"]:
        if mid(m["bid"], m["ask"])[0] is None or m["ask"] - m["bid"] > MAX_SPREAD:
            continue
        mine, other = (0, 1) if m["side"] == team1 else (1, 0)
        for side, cost in ((mine, m["ask"]), (other, 1 - m["bid"])):
            best[side] = cost if best[side] is None else min(best[side], cost)
    return tuple(best)


def fee(price, stake, rate=0.07):
    """Kalshi's fee on one order of `stake` dollars at `price`:
    ceil(rate × contracts × P × (1 − P)) to the cent (7% for orders that take
    the book, 1.75% for resting orders)."""
    contracts = stake / price
    return math.ceil(round(rate * contracts * price * (1 - price) * 100, 6)) / 100


# ---------------------------------------------------------------- the log


def prices_file(log, now, days_back=2):
    """The site's `kalshi.json`: when prices were last read and, for every rated
    match with a price that starts after `now` − `days_back` days, team 1's and
    team 2's chance (whole numbers adding to 100, as the register shows them),
    when that price was read and the market's page. The fixture registers apply
    it in the browser, so prices refreshed between site builds show."""
    since = (now - datetime.timedelta(days=days_back)).strftime("%Y-%m-%dT%H:%MZ")
    out = {}
    for entry in log.values():
        market = entry.get("market")
        if not entry.get("matched") or not market or entry["start"] < since:
            continue
        p1 = min(99, max(1, round(market["p"] * 100)))
        out[entry["match_id"]] = {
            "p1": p1,
            "p2": 100 - p1,
            "at": market["at"],
            "url": event_url(market["ticker"]) if market.get("ticker") else None,
        }
    return {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "matches": out}


def published_log(log):
    """The site's `predictions.json`: every rated match in the log."""
    return {"matches": [e for e in log.values() if e.get("matched")]}


def _parse_start(value):
    return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%MZ").replace(
        tzinfo=datetime.timezone.utc
    )


def attach_prices(log, markets, match_team, now):
    """Store the market's chance on every logged match that hasn't started, in place.

    `markets` are Kalshi's open series markets; `match_team` resolves Kalshi team
    names to ours (`schedule.TeamMatcher` with `MARKET_ALIASES`). A logged match
    takes the market between the same two teams whose start is nearest within
    `MATCH_WINDOW`. The entry gets `market`: {"p": team1's chance, "spread",
    "ask1"/"ask2" (what a contract on each team costs now, `buy_costs`), "at"
    (when the price was read), "ticker"}. A match without a usable quote keeps
    the price it had. While the start is at least `BET_LEAD` away, the read is
    also kept as `market_12h` (with our call as `ours`), the price the page's
    paper bets buy at. Started matches are left alone, so the last price before
    the start stays. Returns the number of matches priced.
    """
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    by_pair = {}
    for row in events(markets, settled=False):
        if row["map"] is not None:
            continue
        ours = (match_team(row["team1"]), match_team(row["team2"]))
        if None in ours:
            continue
        by_pair.setdefault(frozenset(ours), []).append((row, ours))
    priced = 0
    for entry in log.values():
        if not entry.get("matched") or entry["start"] <= now_s:
            continue
        options = by_pair.get(frozenset((entry["ours1"], entry["ours2"])), [])
        start = _parse_start(entry["start"])
        near = [
            (abs(row["start"] - start), row, ours)
            for row, ours in options
            if abs(row["start"] - start) <= MATCH_WINDOW
        ]
        if not near:
            continue
        _, row, ours = min(near, key=lambda x: x[0])
        team1 = row["team1"] if ours[0] == entry["ours1"] else row["team2"]
        p, spread = chance_now(row, team1)
        if p is None:
            continue
        ask1, ask2 = buy_costs(row, team1)
        entry["market"] = {
            "p": round(p, 4),
            "spread": round(spread, 4),
            "ask1": ask1,
            "ask2": ask2,
            "at": now_s,
            "ticker": row["event_ticker"],
        }
        if start - now >= BET_LEAD:
            entry["market_12h"] = {
                "p": round(p, 4),
                "ask1": ask1,
                "ask2": ask2,
                "at": now_s,
                "ours": entry.get("p_series"),
            }
        priced += 1
    return priced


def backfill_prices(log, rows, match_team, price_at, now, bet_at=None):
    """Give started matches without a price the market's last price before their
    start, from Kalshi's price history, in place.

    `rows` are settled series events (`events`); `price_at(row, team1, start)`
    returns (team1's chance, spread, when it was read: a datetime before `start`)
    or None. Matching is as in `attach_prices`. The entry gets the same `market`
    a live read would have left, plus `"backfilled": True`. With `bet_at(row,
    team1, start)` (returning (team1's chance, ask1, ask2, when) `BET_LEAD`
    before the start, or None), a match without `market_12h` gets that too,
    with our call as `ours`. Returns the number of matches given either.
    """
    now_s = now.strftime("%Y-%m-%dT%H:%MZ")
    by_pair = {}
    for row in rows:
        if row["map"] is not None:
            continue
        ours = (match_team(row["team1"]), match_team(row["team2"]))
        if None not in ours:
            by_pair.setdefault(frozenset(ours), []).append((row, ours))
    priced = 0
    for entry in log.values():
        if not entry.get("matched") or entry["start"] > now_s:
            continue
        if entry.get("market") and (bet_at is None or entry.get("market_12h")):
            continue
        start = _parse_start(entry["start"])
        near = [
            (abs(row["start"] - start), row, ours)
            for row, ours in by_pair.get(
                frozenset((entry["ours1"], entry["ours2"])), []
            )
            if abs(row["start"] - start) <= MATCH_WINDOW
        ]
        if not near:
            continue
        _, row, ours = min(near, key=lambda x: x[0])
        team1 = row["team1"] if ours[0] == entry["ours1"] else row["team2"]
        done = False
        quote = None if entry.get("market") else price_at(row, team1, start)
        if quote is not None:
            p, spread, at = quote
            entry["market"] = {
                "p": round(p, 4),
                "spread": round(spread, 4),
                "at": at.strftime("%Y-%m-%dT%H:%MZ"),
                "ticker": row["event_ticker"],
                "backfilled": True,
            }
            done = True
        early = (
            None
            if bet_at is None or entry.get("market_12h")
            else bet_at(row, team1, start)
        )
        if early is not None:
            p, ask1, ask2, at = early
            entry["market_12h"] = {
                "p": round(p, 4),
                "ask1": ask1,
                "ask2": ask2,
                "at": at.strftime("%Y-%m-%dT%H:%MZ"),
                "ours": entry.get("p_series"),
                "backfilled": True,
            }
            done = True
        priced += done
    return priced
