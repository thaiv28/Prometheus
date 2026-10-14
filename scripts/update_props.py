"""
update_props.py: The hourly props refresh, with no database. Prices the newest
pick'em lines (`data/prop_lines.jsonl`, appended by `collect_props.py`) against
the projections the last site build published (`props-dist.json`), saves our call
on each line until its start (`data/prop_calls.json`; this job is the only writer)
and writes `props-lines.json`, which the Props page applies over its built lines.

Usage:
    uv run python scripts/update_props.py --dist props-dist.json --out output-props
"""

import argparse
import datetime
import json
import os

import pandas as pd

from prometheus import props_live
from prometheus.site import props as site_props


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lines", default="data/prop_lines.jsonl")
    parser.add_argument("--calls", default="data/prop_calls.json")
    parser.add_argument("--dist", required=True, help="the build's props-dist.json")
    parser.add_argument("--out", required=True, help="folder for props-lines.json")
    args = parser.parse_args()

    if not os.path.exists(args.dist):
        print("No projections from a build yet; nothing to price.")
        return
    with open(args.dist) as f:
        table = json.load(f)
    now = pd.Timestamp(datetime.datetime.now(datetime.UTC))
    log = props_live.load_lines(args.lines)
    lines = props_live.latest_lines(log, now) if not log.empty else log
    priced, fixtures = props_live.price_from_table(lines, table)

    calls = {}
    if os.path.exists(args.calls):
        with open(args.calls) as f:
            calls = json.load(f)
    before = len(calls)
    if not priced.empty:
        props_live.update_calls(calls, priced, fixtures, now)
    os.makedirs(os.path.dirname(args.calls) or ".", exist_ok=True)
    with open(args.calls, "w") as f:
        json.dump(calls, f, indent=1)

    os.makedirs(args.out, exist_ok=True)
    reads = log["read_at"] if not log.empty else None
    with open(os.path.join(args.out, "props-lines.json"), "w") as f:
        json.dump(site_props.lines_payload(priced, reads), f, separators=(",", ":"))
    print(
        f"Priced {len(priced)} lines on {len(fixtures)} matches; "
        f"calls {before} -> {len(calls)}."
    )


if __name__ == "__main__":
    main()
