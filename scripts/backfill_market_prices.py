"""Backfill Kalshi's last price before the start on logged matches that never got one.

The build and the hourly job read Kalshi's prices only for matches that haven't
started, so matches played before prices were logged (2026-10-06) have none.
This gives each started match in the log the market's last two-sided hourly
quote before its start, from Kalshi's price history (the backtest's cache in
`data/markets/`, fetched where missing), the same figure a live read would have
frozen, and the price 12 hours before (`market_12h`, what the page's paper
bets buy at). Entries get `backfilled`. A one-off: run it on the log, then put
the log back where CI keeps it.

    uv run python scripts/backfill_market_prices.py --log data/predictions.json [--refresh] [--dry-run]
"""

import argparse
import datetime
import time
from pathlib import Path

from evaluate_markets import (
    CACHE,
    _ts,
    cached_candles,
    fetch_candles,
    fetch_markets,
    historical_cutoff,
)
from update_prices import team_matcher

from prometheus import markets, schedule


def last_book(candles, ts):
    """(bid, ask, end time) of the last hourly candle that ended by `ts` with a
    two-sided quote within `MAX_SPREAD`, or None."""
    best = None
    for c in candles:
        if c["end_period_ts"] > ts:
            break
        bid = markets._dollars(c.get("yes_bid"), "close")
        ask = markets._dollars(c.get("yes_ask"), "close")
        mid, spread = markets.mid(bid, ask)
        if mid is not None and spread <= markets.MAX_SPREAD:
            best = (bid, ask, c["end_period_ts"])
    return best


def last_quote(candles, ts):
    """(mid, spread, end time) from `last_book`, or None."""
    book = last_book(candles, ts)
    if book is None:
        return None
    bid, ask, end = book
    mid, spread = markets.mid(bid, ask)
    return mid, spread, end


def price_history(cutoff, pause=0.1):
    """(`price_at`, `bet_at`) for `markets.backfill_prices`, from hourly
    candlesticks, fetching (one request at a time) contracts not yet cached.

    `price_at`: the mean of team1's mid and one minus the opponent's, each the
    last before the start. `bet_at`: the same `BET_LEAD` before the start, with
    what a contract on each team cost then (the cheaper of its ask and one minus
    the opponent's bid, as `markets.buy_costs`)."""

    def candles_for(m, at):
        """The market's hourly candles through `at`. The backtest's cache stops an
        hour after Kalshi's scheduled start, which for a day-only market is
        midnight Eastern; when the match (the log's start) comes later, the
        history is fetched again through it, so the last quote is the real one."""
        candles = cached_candles(m["ticker"])
        trading = _ts(m["close"]) > _ts(at) - 3600
        short = (
            candles is not None
            and trading
            and (not candles or candles[-1]["end_period_ts"] < _ts(at) - 3600)
        )
        if candles is None or short:
            if short:
                (CACHE / "candles" / f"{m['ticker']}.json").unlink()
            candles = fetch_candles(
                markets.SERIES,
                m["ticker"],
                _ts(m["open"]),
                max(_ts(m["start"]), _ts(at)) + 3600,
                historical=m["close"] < cutoff,
            )
            time.sleep(pause)
        return candles

    def books(row, team1, at):
        """[(is team1's contract, bid, ask, end)] at `at`."""
        out = []
        for m in row["markets"]:
            book = last_book(candles_for(m, at), _ts(at))
            if book is not None:
                out.append((m["side"] == team1, *book))
        return out

    def when(ends):
        return datetime.datetime.fromtimestamp(max(ends), datetime.timezone.utc)

    def price_at(row, team1, start):
        quotes = books(row, team1, start)
        if not quotes:
            return None
        chances = [(b + a) / 2 if mine else 1 - (b + a) / 2 for mine, b, a, _ in quotes]
        spreads = [a - b for _, b, a, _ in quotes]
        return (
            sum(chances) / len(chances),
            sum(spreads) / len(spreads),
            when([q[3] for q in quotes]),
        )

    def bet_at(row, team1, start):
        quotes = books(row, team1, start - markets.BET_LEAD)
        if not quotes:
            return None
        chances = [(b + a) / 2 if mine else 1 - (b + a) / 2 for mine, b, a, _ in quotes]
        costs = [None, None]
        for mine, bid, ask, _ in quotes:
            own, other = (0, 1) if mine else (1, 0)
            for side, cost in ((own, ask), (other, round(1 - bid, 4))):
                costs[side] = cost if costs[side] is None else min(costs[side], cost)
        return (
            sum(chances) / len(chances),
            costs[0],
            costs[1],
            when([q[3] for q in quotes]),
        )

    return price_at, bet_at


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--log",
        default="data/predictions.json",
        help="The prediction log to backfill in place",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Refetch Kalshi's market lists (needed for recent matches)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count what would be priced; don't write the log",
    )
    args = parser.parse_args()

    path = Path(args.log)
    log = schedule.load_log(path)
    now = datetime.datetime.now(datetime.timezone.utc)
    first = min(e["start"] for e in log.values())[:10]
    since = datetime.date.fromisoformat(first) - datetime.timedelta(days=1)
    rows = [
        r
        for r in markets.events(fetch_markets(markets.SERIES, args.refresh))
        if r["start"].date() >= since
    ]
    price_at, bet_at = price_history(historical_cutoff())
    priced = markets.backfill_prices(
        log, rows, team_matcher(log), price_at, now, bet_at
    )
    started = [
        e
        for e in log.values()
        if e.get("matched") and e["start"] <= now.strftime("%Y-%m-%dT%H:%MZ")
    ]
    with_price = sum(1 for e in started if e.get("market"))
    with_early = sum(1 for e in started if e.get("market_12h"))
    print(
        f"{priced} matches backfilled; of {len(started)} started rated matches, {with_price} have a price "
        f"before the start and {with_early} one {markets.BET_LEAD.seconds // 3600} hours before."
    )
    if not args.dry_run:
        schedule.save_log(log, path)
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
