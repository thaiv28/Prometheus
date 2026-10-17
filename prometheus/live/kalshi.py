"""Kalshi map-winner (KXLOLMAP) contracts and top-of-book quotes for live games.

A contract matches a game only on its rules text: the two team names (exact, or
through the market benchmark's `MARKET_ALIASES`, Kalshi's name -> ours), the map
number and the match's scheduled US Eastern date. Several matching events
for one map are ambiguous and give no contract. Quotes are for YES on the
match's first team: bid is the best YES bid, ask is 1 minus the best NO bid.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..markets import MARKET_ALIASES

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXLOLMAP"  # one map's winner
MATCH_SERIES = "KXLOLGAME"  # the series winner
MARKET_URL = "https://kalshi.com/markets/kxlolmap"
MATCH_URL = "https://kalshi.com/markets/kxlolgame"
RULES = re.compile(
    r"If (?P<side>.+?) wins (?:game (?P<map>\d+) in )?the (?P<event>.+?): "
    r"(?P<team1>.+?) vs\. (?P<team2>.+?) League of Legends match originally "
    r"scheduled for (?P<day>\w+ \d{1,2}, \d{4})"
)


def names(team):
    return {team["name"], team.get("riot_name"), team.get("code")} - {None}


def known(name, team_names):
    """Whether Kalshi's `name` is one of a team's names, directly or by alias."""
    name = name.strip()
    return name in team_names or MARKET_ALIASES.get(name) in team_names


def scheduled_day(start_time):
    """Event start as Kalshi writes it: 'Oct 15, 2026' in US Eastern time."""
    t = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    t = t.astimezone(ZoneInfo("America/New_York"))
    return f"{t.strftime('%b')} {t.day}, {t.year}"


def contract(markets, mapping, game_number, start_time):
    """Ticker for YES on mapping team 0 winning this map (or, with game_number
    None, the series), or None."""
    first, second = (names(t) for t in mapping["teams"])
    day = scheduled_day(start_time)
    hits = {}
    for market in markets:
        rule = RULES.match(market.get("rules_primary", ""))
        number = int(rule["map"]) if rule and rule["map"] else None
        if not rule or number != game_number or rule["day"] != day:
            continue
        pair = (rule["team1"], rule["team2"])
        if not any(known(n, first) for n in pair) or not any(
            known(n, second) for n in pair
        ):
            continue
        if known(rule["side"], first):
            hits.setdefault(market["event_ticker"], []).append(market["ticker"])
    if len(hits) != 1:
        return None
    (tickers,) = hits.values()
    return tickers[0] if len(tickers) == 1 else None


DEPTH = 5  # price levels kept a side


def book_levels(book, depth=DEPTH):
    """The best `depth` levels of each side as [[price, size], ...], best first:
    `yes` bids, and `no` bids (1 - price is the cost of YES there)."""
    levels = book.get("orderbook_fp") or {}
    out = {}
    for side in ("yes", "no"):
        rows = [
            [float(p), float(size)]
            for p, size in levels.get(f"{side}_dollars") or []
            if float(size) > 0
        ]
        out[side] = sorted(rows, key=lambda r: -r[0])[:depth]
    return out


def quote(book, at):
    """{at, bid, ask} for YES from an orderbook response, or None if one-sided."""
    levels = book.get("orderbook_fp") or {}
    yes = [float(p) for p, size in levels.get("yes_dollars") or [] if float(size) > 0]
    no = [float(p) for p, size in levels.get("no_dollars") or [] if float(size) > 0]
    if not yes or not no:
        return None
    return {"at": at, "bid": round(max(yes), 4), "ask": round(1 - max(no), 4)}
