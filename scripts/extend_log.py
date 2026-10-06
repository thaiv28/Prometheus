"""Extend the prediction log back in time with calls rebuilt for matches already played.

A new log starts with a 30-day rebuild (`build_predictions`). This adds every
match from `--since` up to the log's first one, the same way: each call comes
from the ratings as they stood the day before the match (games before it only),
marked `reconstructed`, with its result. Entries already in the log are never
touched. The schedule is fetched from Leaguepedia a month at a time and cached
(`--schedule-cache`), so a rerun doesn't fetch again. Needs the built DB.

    uv run python scripts/extend_log.py --log data/predictions.json --since 2026-01-01

Then price the new entries with `scripts/backfill_market_prices.py`.
"""

import argparse
import datetime
from pathlib import Path

import pandas as pd

from prometheus import schedule
from prometheus.form import form_states, load_form_games, opponent_adjust


def fetch_months(since, until, cache):
    """Leaguepedia's schedule from `since` up to `until` (dates), a month per
    query, read from and saved to the `cache` pickle."""
    if cache and Path(cache).exists():
        return pd.read_pickle(cache)
    parts, start = [], since
    while start < until:
        end = min(
            (start.replace(day=1) + datetime.timedelta(days=32)).replace(day=1), until
        )
        print(f"Fetching {start} to {end}")
        parts.append(schedule.fetch_schedule(start, end))
        start = end
    frame = pd.concat(parts, ignore_index=True).drop_duplicates("match_id")
    if cache:
        frame.to_pickle(cache)
    return frame


def extend(log, sched, states, now):
    """Add a rebuilt call for every match in `sched` that has started and isn't
    in `log`, in place. Returns the number added."""
    sched = sched[(sched["start"] <= pd.Timestamp(now)) & ~sched["match_id"].isin(log)]
    if sched.empty:
        return 0
    ratings = schedule.current_ratings(states)
    match_team = schedule.TeamMatcher(ratings.reset_index())
    predictions = schedule.predict(sched, ratings, match_team)
    cache = {}

    def reconstruct(row):
        day = row["start"].date()
        if day not in cache:
            print(f"  ratings before {day}")
            cache[day] = schedule.ratings_before(states, day)
        rec = schedule.predict(pd.DataFrame([row]), cache[day], match_team)[0]
        return {
            **rec,
            "predicted": None,
            "data_through": str(day - datetime.timedelta(days=1)),
        }

    before = len(log)
    data_through = str(pd.to_datetime(states["date"]).max())[:10]
    schedule.update_log(log, sched, predictions, now, data_through, reconstruct)
    return len(log) - before


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--log",
        default="data/predictions.json",
        help="The prediction log to extend in place",
    )
    parser.add_argument(
        "--since", default="2026-01-01", help="First day to add (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--schedule-cache", help="Pickle to keep the fetched schedule in"
    )
    args = parser.parse_args()

    path = Path(args.log)
    log = schedule.load_log(path)
    now = datetime.datetime.now(datetime.timezone.utc)
    since = datetime.date.fromisoformat(args.since)
    until = (
        datetime.date.fromisoformat(min(e["start"] for e in log.values())[:10])
        if log
        else now.date()
    )
    sched = fetch_months(since, until, args.schedule_cache)
    print(f"{len(sched)} scheduled matches from {since} to {until}")
    states = form_states(opponent_adjust(load_form_games()))
    added = extend(log, sched, states, now)
    rated = sum(1 for e in log.values() if e.get("matched"))
    print(f"Added {added} matches; the log now holds {len(log)} ({rated} rated).")
    schedule.save_log(log, path)
    print(f"Wrote {path}")


if __name__ == "__main__":
    main()
