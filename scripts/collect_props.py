"""
collect_props.py: Append the pick'em apps' current LoL player prop lines (Underdog,
DraftKings Pick6, PrizePicks) to a JSON-lines log, one row per line per read.

Run it on a schedule (every hour or two) to build the line history that
`evaluate_props.py` will need; nothing reads the log yet. See
`prometheus/prop_lines.py` for what each source gives.

Usage:
    uv run python scripts/collect_props.py [--log data/prop_lines.jsonl] [--sources underdog pick6]
"""

import argparse
import os

from prometheus import prop_lines


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="data/prop_lines.jsonl")
    parser.add_argument("--sources", nargs="+", default=list(prop_lines.SOURCES))
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.log) or ".", exist_ok=True)
    for source, n in prop_lines.collect(args.log, args.sources).items():
        print(f"{source}: {n}")


if __name__ == "__main__":
    main()
