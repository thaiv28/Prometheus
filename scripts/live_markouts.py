"""Offline candidate markouts from `scripts/live_data.py pull` (data/live/).

These are quote-mid minus original ask, not fills, realized P&L or fee-adjusted
returns. Pre-match fills are out of scope: their ledger is private. No AWS or
network access. Use the first saved quote at or after each horizon; print its
age beyond the horizon so sparse observations remain visible. Missing quotes
stay blank, with available-observation counts in the summary.
"""

import argparse
import bisect
import csv
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = (30, 60, 120)


def timestamp(value):
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def markouts(root):
    rows = []
    for path in sorted(Path(root).glob("*/*/trading/candidate.json")):
        candidate = json.loads(path.read_text())
        game = path.parent.parent
        bo1 = candidate["event_ticker"].startswith("KXLOLGAME-")
        quotes_path = (
            game.parent / "series_quotes.jsonl" if bo1 else game / "quotes.jsonl"
        )
        quotes = (
            [json.loads(line) for line in quotes_path.read_text().splitlines() if line]
            if quotes_path.exists()
            else []
        )
        quotes = sorted(quotes, key=lambda q: timestamp(q["at"]))
        times = [timestamp(q["at"]) for q in quotes]
        side = candidate["teams"].index(candidate["backed_team"])
        row = {
            "candidate": str(path.relative_to(root)),
            "alert_at": candidate["alert_at"],
            "backed_team": candidate["backed_team"],
            "event_ticker": candidate["event_ticker"],
            "map_number": candidate["map_number"],
            "delivered": (path.parent / "delivered").exists(),
        }
        for horizon in HORIZONS:
            target = timestamp(candidate["alert_at"]) + dt.timedelta(seconds=horizon)
            i = bisect.bisect_left(times, target)
            value = delay = None
            if i < len(quotes):
                q = quotes[i]
                mid = (float(q["bid"]) + float(q["ask"])) / 2
                value = (mid if side == 0 else 1 - mid) - float(
                    candidate["original_ask"]
                )
                delay = (times[i] - target).total_seconds()
            row[f"markout_{horizon}"] = value
            row[f"quote_delay_{horizon}"] = delay
        rows.append(row)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT / "data/live")
    args = parser.parse_args(argv)
    rows = markouts(args.root)
    if rows:
        writer = csv.DictWriter(sys.stdout, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Candidates: {len(rows)}")
    for horizon in HORIZONS:
        values = [
            r[f"markout_{horizon}"] for r in rows if r[f"markout_{horizon}"] is not None
        ]
        mean = f"{sum(values) / len(values):+.6f}" if values else ""
        print(f"{horizon}s: n={len(values)}, mean markout={mean}")


if __name__ == "__main__":
    main()
