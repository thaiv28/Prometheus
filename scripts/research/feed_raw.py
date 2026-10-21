"""
feed_raw.py: past maps' raw Riot live-stats window and details responses.

Saves both endpoints unchanged, including participant fields, one sample a minute
from start through finish in `data/feed_raw/games/<game id>.json.gz`:

    {"game_id", "match_id", "league", "number", "teams", "blue_id", "start",
     "start_source": "feed_timelines" or "searched", "first": initial window,
     "samples": [{"t", "window": full payload, "details": full payload}], "error"}

Uses `data/feed_timelines/schedule.json` and saved map starts when available;
otherwise searches the feed for the start. An unfinished map gets one extra
sample 30 seconds after its last sample. Atomic gzip files make runs resumable;
existing maps, including those with errors, are skipped.

    uv run python scripts/research/feed_raw.py collect
    uv run python scripts/research/feed_raw.py status
    COLLECTOR=scripts/research/feed_raw.py bash scripts/research/feed_timelines_collect.sh data/feed_raw 8

Requests use feed_timelines.get unchanged. Refusals (403, 429) and server errors
stop with exit 3; no answer (offline, asleep) exits 4 for the wrapper to resume.
Successful runs exit 0. Saved maps survive either failure.
"""

import argparse
import gzip
import json
import os
import random
import sys
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from feed_timelines import (
    MAX_MINUTES,
    SEED,
    STEP,
    WINDOW,
    Refused,
    Unreachable,
    find_start,
    get,
    when,
)

DETAILS = "https://feed.lolesports.com/livestats/v1/details/{}"
OUT = ROOT / "data" / "feed_raw"
TIMELINES = ROOT / "data" / "feed_timelines"


def fetch(url_template, game_id, at=None):
    query = ""
    if at is not None:
        at = at.replace(microsecond=0) - timedelta(seconds=at.second % 10)
        query = "?" + urlencode({"startingTime": at.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return get(url_template.format(game_id) + query)


def known_start(game_id, timelines):
    path = timelines / "games" / f"{game_id}.json"
    if path.exists():
        saved = json.loads(path.read_text())
        if saved.get("start") is not None:
            return when({"rfc460Timestamp": saved["start"]}), saved["blue_id"]
    return None, None


def collect_game(game, timelines):
    game_id = game["game_id"]
    first = fetch(WINDOW, game_id)
    start, blue_id = known_start(game_id, timelines)
    start_source = "feed_timelines"
    if start is None:
        start, blue_id = find_start(game_id)
        start_source = "searched"
    result = dict(
        game,
        blue_id=blue_id,
        start=start.isoformat() if start is not None else None,
        start_source=start_source,
        first=first,
        samples=[],
        error="no start",
    )
    if start is None:
        return result
    samples = result["samples"]
    finished = False
    for k in range(MAX_MINUTES + 1):
        t = start + timedelta(seconds=k * STEP)
        w = fetch(WINDOW, game_id, t)
        if not w or not w.get("frames"):
            break
        d = fetch(DETAILS, game_id, t)
        samples.append({"t": t.isoformat(), "window": w, "details": d})
        if w["frames"][-1]["gameState"] == "finished":
            finished = True
            break
    if not finished and samples:
        t2 = when({"rfc460Timestamp": samples[-1]["t"]}) + timedelta(seconds=30)
        w = fetch(WINDOW, game_id, t2)
        d = fetch(DETAILS, game_id, t2)
        samples.append({"t": t2.isoformat(), "window": w, "details": d})
        frames = (w or {}).get("frames") or []
        finished = bool(frames and frames[-1]["gameState"] == "finished")
    result["error"] = None if finished else "no finished frame"
    return result


def collect(out, timelines, limit=None, shard=(0, 1), split=(0, 1)):
    saved = json.loads((timelines / "schedule.json").read_text())
    games = sorted(
        (g for m in saved.values() for g in m["games"]), key=lambda g: g["game_id"]
    )
    random.Random(SEED).shuffle(games)
    games = games[shard[0] :: shard[1]]
    games = [
        g for g in games if not (out / "games" / f"{g['game_id']}.json.gz").exists()
    ]
    games = games[split[0] :: split[1]]
    (out / "games").mkdir(parents=True, exist_ok=True)
    done = 0
    for g in games:
        path = out / "games" / f"{g['game_id']}.json.gz"
        if path.exists():
            continue
        result = collect_game(g, timelines)
        temp = path.with_name(path.name + ".tmp")
        temp.write_bytes(
            gzip.compress(json.dumps(result, separators=(",", ":")).encode())
        )
        os.replace(temp, path)
        done += 1
        print(
            f"{saved[g['match_id']]['start'][:10]} {g['league']} map {g['number']}: "
            f"{len(result['samples'])} samples {result['error'] or ''}",
            flush=True,
        )
        if limit and done >= limit:
            break
    return done


def status(out, timelines):
    saved = json.loads((timelines / "schedule.json").read_text())
    total = sum(len(m["games"]) for m in saved.values())
    files = list((out / "games").glob("*.json.gz"))
    ok = 0
    for path in files:
        with gzip.open(path, "rt") as stream:
            ok += json.load(stream)["error"] is None
    size = sum(path.stat().st_size for path in files) / 1_000_000
    print(f"{len(files):,} of {total:,} maps collected, {ok:,} complete, {size:.1f} MB")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("collect", "status"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--timelines", type=Path, default=TIMELINES)
    parser.add_argument("--limit", type=int, help="maps to collect this run")
    parser.add_argument(
        "--shard", default="0/1", help="i/n: this run's share of the maps"
    )
    parser.add_argument(
        "--split",
        default="0/1",
        help="j/m: this run's part of the shard's missing maps",
    )
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "collect":
            i, n = (int(x) for x in args.shard.split("/"))
            j, m = (int(x) for x in args.split.split("/"))
            collect(args.out, args.timelines, args.limit, (i, n), (j, m))
        status(args.out, args.timelines)
    except Refused as error:
        print(f"Stopped: {error}. Saved maps are kept; run again later.")
        return 3
    except Unreachable as error:
        print(f"Unreachable: {error}. Saved maps are kept.")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
