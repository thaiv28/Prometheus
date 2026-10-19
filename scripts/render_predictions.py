"""Render predictions between builds, using the live site's build artifacts."""

import argparse
import datetime
import json
import tempfile
import urllib.request
from pathlib import Path

from prometheus import markets, schedule
from prometheus.site.predictions import render_from_log

SITE = "https://prometheus.thaiv.dev/"


def run(log_path, out_dir, summary_path=None, now=None):
    """Fetch all dependencies before rendering; a failed fetch writes nothing."""
    try:
        artifacts = {}
        for name in ("teams.json", "series-links.json", "backtest.json"):
            request = urllib.request.Request(
                SITE + name, headers={"User-Agent": markets.USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=30) as response:
                artifacts[name] = json.load(response)
        slugs = {team["n"]: team["s"] for team in artifacts["teams.json"]}
        coverage = None
        if summary_path and Path(summary_path).exists():
            summary = json.loads(Path(summary_path).read_text())
            coverage = {key: summary[key] for key in ("matched", "matches")}
        with tempfile.TemporaryDirectory() as staging:
            render_from_log(
                schedule.load_log(log_path),
                artifacts["backtest.json"],
                set(slugs.values()),
                artifacts["series-links.json"],
                coverage,
                now or datetime.datetime.now(datetime.UTC),
                staging,
            )
            for source in Path(staging).rglob("*.html"):
                target = Path(out_dir) / source.relative_to(staging)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(source.read_bytes())
    except Exception as exc:
        print(f"Predictions not rendered ({exc}); keeping published pages.")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    args = parser.parse_args()
    run(args.log, args.out, args.summary)


if __name__ == "__main__":
    main()
