"""Refresh future calls from published Elo state and recent Leaguepedia results."""

import argparse
import copy
import datetime
import gzip
import json
import os
import time
import urllib.request
from pathlib import Path

from prometheus import fresh, markets, schedule


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("data/predictions.json"))
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--worker-maps", type=Path)
    parser.add_argument("--live-out", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--site-out", type=Path)
    args = parser.parse_args()
    started = time.monotonic()
    if os.environ.get("REFRESH_CALLS") == "0":
        print("Fresh calls: disabled (REFRESH_CALLS=0)")
        return
    if not args.inputs.exists() or not args.state.exists():
        print("Fresh calls: missing input; leaving log unchanged")
        return
    try:
        inputs = json.loads(args.inputs.read_text())
        with gzip.open(args.state, "rt") as stream:
            state = json.load(stream)
        log = schedule.load_log(args.log)
        now = datetime.datetime.now(datetime.UTC)
        player_slugs = {}
        if args.site_out:
            try:
                request = urllib.request.Request(
                    "https://prometheus.thaiv.dev/player-slugs.json",
                    headers={"User-Agent": markets.USER_AGENT},
                )
                with urllib.request.urlopen(request, timeout=15) as response:
                    fetched_slugs = json.load(response)
                    if isinstance(fetched_slugs, dict):
                        player_slugs = fetched_slugs
            except Exception:
                pass
        summary = fresh.refresh_log(
            log,
            now,
            inputs,
            state,
            worker_maps=args.worker_maps,
            **(
                {"site_out": args.site_out, "player_slugs": player_slugs}
                if args.site_out
                else {}
            ),
        )
    except Exception as exc:
        print(
            f"Fresh calls: leaving log unchanged ({exc}); {time.monotonic() - started:.2f}s"
        )
        return
    schedule.save_log(log, args.log)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary))
    if args.live_out and summary["applied"]:
        payload = copy.deepcopy(inputs)
        for name, delta in summary["deltas"].items():
            for key in ("elo", "forge", "model_elo"):
                if key in payload["teams"][name]:
                    payload["teams"][name][key] += delta
        payload.update(
            generated_at=now.isoformat(), results_through=summary["results_through"]
        )
        args.live_out.parent.mkdir(parents=True, exist_ok=True)
        args.live_out.write_text(json.dumps(payload))
    print(
        f"Fresh calls: {json.dumps(summary, separators=(',', ':'))}; {time.monotonic() - started:.2f}s"
    )


if __name__ == "__main__":
    main()
