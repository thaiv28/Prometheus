"""Kalshi map-winner (KXLOLMAP) contracts and top-of-book quotes for live games.

A contract matches a game only on its rules text: the exact two team names, the
map number and the match's scheduled US Eastern date. Several matching events
for one map are ambiguous and give no contract. Quotes are for YES on the
match's first team: bid is the best YES bid, ask is 1 minus the best NO bid.
"""

import re
from datetime import datetime
from zoneinfo import ZoneInfo

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
        pair = {rule["team1"].strip(), rule["team2"].strip()}
        if not any(a in pair for a in first) or not any(b in pair for b in second):
            continue
        if rule["side"].strip() in first:
            hits.setdefault(market["event_ticker"], []).append(market["ticker"])
    if len(hits) != 1:
        return None
    (tickers,) = hits.values()
    return tickers[0] if len(tickers) == 1 else None


def quote(book, at):
    """{at, bid, ask} for YES from an orderbook response, or None if one-sided."""
    levels = book.get("orderbook_fp") or {}
    yes = [float(p) for p, size in levels.get("yes_dollars") or [] if float(size) > 0]
    no = [float(p) for p, size in levels.get("no_dollars") or [] if float(size) > 0]
    if not yes or not no:
        return None
    return {"at": at, "bid": round(max(yes), 4), "ask": round(1 - max(no), 4)}
