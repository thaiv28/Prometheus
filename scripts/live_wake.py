"""Start the live worker when a match is about to begin (the hourly prices job).

The worker (deploy/live/) powers itself off after 90 minutes with nothing live;
this starts it again from the prediction log's schedule: any match lolesports.com
broadcasts that starts within `--lead` minutes, or started within `--since`
minutes and has no result yet. Starting a running instance changes nothing.

    uv run python scripts/live_wake.py --dry-run
    LIVE_WORKER_INSTANCE_ID=i-... uv run python scripts/live_wake.py
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Event leagues (schedule.EVENT_LEAGUES codes) that lolesports.com's live feed carries.
LIVE_LEAGUES = {
    "Worlds",
    "MSI",
    "FST",
    "LCK",
    "LPL",
    "LEC",
    "LCS",
    "CBLOL",
    "LCP",
    "VCS",
    "EM",
    "LCKC",
}


def due(matches, now, lead=75, since=240):
    """Matches that should have the worker on at `now` (an aware datetime)."""
    out = []
    for m in matches:
        if m.get("league") not in LIVE_LEAGUES or m.get("winner") is not None:
            continue
        try:
            start = datetime.datetime.strptime(m["start"], "%Y-%m-%dT%H:%MZ").replace(
                tzinfo=datetime.UTC
            )
        except (KeyError, TypeError, ValueError):
            continue
        minutes = (start - now).total_seconds() / 60
        if -since <= minutes <= lead:
            out.append(m)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=ROOT / "data" / "predictions.json")
    parser.add_argument("--lead", type=int, default=75, help="minutes before a start")
    parser.add_argument("--since", type=int, default=240, help="minutes after a start")
    parser.add_argument(
        "--instance-id", default=os.environ.get("LIVE_WORKER_INSTANCE_ID")
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not args.log.exists():
        print(f"No prediction log at {args.log}; nothing to wake for.")
        return 0
    matches = json.loads(args.log.read_text())["matches"]
    now = datetime.datetime.now(datetime.UTC)
    found = due(matches, now, args.lead, args.since)
    for m in found:
        print(f"{m['start']} {m.get('league')}: {m.get('team1')} v {m.get('team2')}")
    if not found:
        print("No live-feed match due; the worker stays as it is.")
        return 0
    if args.dry_run or not args.instance_id:
        print("Dry run or no LIVE_WORKER_INSTANCE_ID: not starting the worker.")
        return 0
    subprocess.run(
        ["aws", "ec2", "start-instances", "--instance-ids", args.instance_id],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    print(f"Started (or kept on) {args.instance_id}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
