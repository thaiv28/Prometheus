"""Backfill Kalshi's last price before the start on logged matches that never got one.

The build and the hourly job read Kalshi's prices only for matches that haven't
started, so matches played before prices were logged (2026-10-06) have none.
This gives each started match in the log the market's last two-sided hourly
quote before its start, from Kalshi's price history (the backtest's cache in
`data/markets/`, fetched where missing), the same figure a live read would have
frozen. Entries get `market.backfilled`. A one-off: run it on the log, then put
the log back where CI keeps it.

    uv run python scripts/backfill_market_prices.py --log data/predictions.json [--refresh] [--dry-run]
"""

import argparse
import datetime
import time
from pathlib import Path

from evaluate_markets import _ts, cached_candles, fetch_candles, fetch_markets, historical_cutoff
from update_prices import team_matcher

from prometheus import markets, schedule


def last_quote(candles, ts):
    """(mid, spread, end time) of the last hourly candle that ended by `ts` with a
    two-sided quote within `MAX_SPREAD`, or None."""
    best = None
    for c in candles:
        if c["end_period_ts"] > ts:
            break
        bid = markets._dollars(c.get("yes_bid"), "close")
        ask = markets._dollars(c.get("yes_ask"), "close")
        mid, spread = markets.mid(bid, ask)
        if mid is not None and spread <= markets.MAX_SPREAD:
            best = (mid, spread, c["end_period_ts"])
    return best


def price_history(cutoff, pause=0.1):
    """`price_at` for `markets.backfill_prices`: the mean of team1's quote and one
    minus the opponent's, each the last before the start, fetching candlesticks
    (one request at a time) for contracts not yet cached."""

    def price_at(row, team1, start):
        chances, spreads, times = [], [], []
        for m in row["markets"]:
            candles = cached_candles(m["ticker"])
            if candles is None:
                candles = fetch_candles(
                    markets.SERIES,
                    m["ticker"],
                    _ts(m["open"]),
                    _ts(max(m["start"], start)) + 3600,
                    historical=m["close"] < cutoff,
                )
                time.sleep(pause)
            quote = last_quote(candles, _ts(start))
            if quote is None:
                continue
            mid, spread, end = quote
            chances.append(mid if m["side"] == team1 else 1 - mid)
            spreads.append(spread)
            times.append(end)
        if not chances:
            return None
        at = datetime.datetime.fromtimestamp(max(times), datetime.timezone.utc)
        return sum(chances) / len(chances), sum(spreads) / len(spreads), at

    return price_at


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--log", default="data/predictions.json", help="The prediction log to backfill in place")
    parser.add_argument("--refresh", action="store_true", help="Refetch Kalshi's market lists (needed for recent matches)")
    parser.add_argument("--dry-run", action="store_true", help="Count what would be priced; don't write the log")
    args = parser.parse_args()

    path = Path(args.log)
    log = schedule.load_log(path)
    now = datetime.datetime.now(datetime.timezone.utc)
    first = min(e["start"] for e in log.values())[:10]
    since = datetime.date.fromisoformat(first) - datetime.timedelta(days=1)
    rows = [r for r in markets.events(fetch_markets(markets.SERIES, args.refresh)) if r["start"].date() >= since]
    priced = markets.backfill_prices(log, rows, team_matcher(log), price_history(historical_cutoff()), now)
    started = [e for e in log.values() if e.get("matched") and e["start"] <= now.strftime("%Y-%m-%dT%H:%MZ")]
    with_price = sum(1 for e in started if e.get("market"))
    print(f"{priced} matches backfilled; {with_price} of {len(started)} started rated matches now have a price.")
    if not args.dry_run:
        schedule.save_log(log, path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
