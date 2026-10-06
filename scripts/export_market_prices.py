"""
export_market_prices.py: Kalshi's last price before every settled series, for the game logs.

Reads the match table `scripts/evaluate_markets.py` saves (`data/markets/frames.pkl`)
and writes `data/market_prices.json`: one row per series between two teams we
rate, with our team names, the scheduled start, team 1's chance at the last
hour before the start, and Kalshi's event ticker. The build reads it (with the
prices in the prediction log) to show Kalshi's price on team and player pages.

CI restores it from the data-backup bucket; after refreshing it locally, copy it
back (see docs/steering/deployment.md).

Usage:
    uv run python scripts/evaluate_markets.py      # refreshes frames.pkl (slow)
    uv run python scripts/export_market_prices.py [--frames data/markets/frames.pkl] [--out data/market_prices.json]
"""

import argparse
import json
from pathlib import Path

import pandas as pd


def market_prices(series_frame):
    """Rows for `data/market_prices.json` from evaluate_markets' series table."""
    rows = series_frame.dropna(subset=["market_close"])
    return [
        {
            "t1": r.ours1,
            "t2": r.ours2,
            "start": pd.Timestamp(r.start).strftime("%Y-%m-%dT%H:%MZ"),
            "p1": round(float(r.market_close), 4),
            "ticker": r.event_ticker,
        }
        for r in rows.sort_values("start").itertuples()
    ]


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--frames", default="data/markets/frames.pkl")
    parser.add_argument("--out", default="data/market_prices.json")
    args = parser.parse_args()
    series_frame = pd.read_pickle(args.frames)[0]
    prices = market_prices(series_frame)
    Path(args.out).write_text(
        json.dumps(prices, ensure_ascii=False, separators=(",", ":"))
    )
    print(f"{len(prices)} series prices written to {args.out}")


if __name__ == "__main__":
    main()
