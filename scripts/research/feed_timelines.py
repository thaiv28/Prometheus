"""
feed_timelines.py: past maps' gold timelines from Riot's live-stats feed.

The feed the live worker reads (`feed.lolesports.com/livestats/v1/window/<game>`)
still serves finished games: each request returns about ten seconds of frames
from `startingTime`. This samples one window a minute from each map's start (the
first frame with 2,500 gold a side, found in 10-second steps) to its end, and
saves each map's samples to `data/feed_timelines/games/<game id>.json`:

    {"game_id", "match_id", "league", "number", "teams": [{id, name, code, side}],
     "blue_id": the feed's blue team (getEventDetails' `side` is often wrong),
     "start": source time of the first 2,500/2,500 frame,
     "samples": [{"at", "state", "flat", "blue": {...}, "red": {...}}], "final": ...}

`flat` marks a sample whose ten seconds of frames kept the same combined gold
after two minutes (a pause). Team stats: gold, kills, towers, inhibitors,
barons, dragons. Results and Elo come later, from Oracle's Elixir
(`train_time_model_v2.py` joins by teams and start time).

    uv run python scripts/research/feed_timelines.py schedule   # matches since 2024
    uv run python scripts/research/feed_timelines.py collect    # resumable
    uv run python scripts/research/feed_timelines.py status

Requests are sequential with a pause between them and are never retried: any
refusal (403, 429) or server error stops the run (exit 3); finished maps are kept
and the next run continues from them. No answer at all (offline, asleep) exits 4;
`feed_timelines_collect.sh` reruns only that case, a minute later. The esports API key is the public one
lolesports.com sends (`prometheus.live.requests.SITE_API_KEY`).
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from prometheus.live.requests import SITE_API_KEY

OUT = ROOT / "data" / "feed_timelines"
API = "https://esports-api.lolesports.com/persisted/gw"
WINDOW = "https://feed.lolesports.com/livestats/v1/window/{}"
# Leagues Oracle's Elixir also covers (results and Elo come from it).
LEAGUES = {
    "worlds": "Worlds",
    "msi": "MSI",
    "first_stand": "FST",
    "ewc_lol": "EWC",
    "lck": "LCK",
    "lpl": "LPL",
    "lec": "LEC",
    "lcs": "LCS",
    "lta_n": "LTA N",
    "lta_s": "LTA S",
    "lta_cross": "LTA",
    "cblol-brazil": "CBLOL",
    "lcp": "LCP",
    "pcs": "PCS",
    "vcs": "VCS",
    "ljl-japan": "LJL",
}
SINCE = "2024-01-01"
STEP = 60  # seconds between samples
START_GOLD = 2500
PAUSE_AFTER = 120  # seconds; passive gold starts about a minute in
MAX_MINUTES = 80
PAUSE = 0.25  # seconds between one run's requests
SEED = 42


class Refused(Exception):
    """A refusal or server error: stop the run, keep what is saved."""


class Unreachable(Exception):
    """No answer at all (this machine offline or asleep): exit 4 so a wrapper may
    rerun later; never a reply from Riot."""


def get(url, key=False):
    """JSON payload, or None for 204 (no frames there)."""
    headers = {"User-Agent": "Prometheus research (feed_timelines.py)"}
    if key:
        headers["x-api-key"] = SITE_API_KEY
    time.sleep(PAUSE)
    try:
        with urlopen(Request(url, headers=headers), timeout=20) as response:
            if response.status == 204:
                return None
            return json.loads(response.read())
    except HTTPError as error:
        if error.code in (400, 404):
            return None
        raise Refused(f"{error.code} {url}") from error
    except (URLError, OSError, HTTPException) as error:
        raise Unreachable(f"{getattr(error, 'reason', error)} {url}") from error


def window(game_id, at=None):
    query = ""
    if at is not None:
        at = at.replace(microsecond=0) - timedelta(seconds=at.second % 10)
        query = "?" + urlencode({"startingTime": at.strftime("%Y-%m-%dT%H:%M:%SZ")})
    payload = get(WINDOW.format(game_id) + query)
    return (payload or {}).get("frames") or []


def when(frame):
    return datetime.fromisoformat(frame["rfc460Timestamp"].replace("Z", "+00:00"))


def team(side):
    return {
        "gold": side.get("totalGold"),
        "kills": side.get("totalKills"),
        "towers": side.get("towers"),
        "inhibitors": side.get("inhibitors"),
        "barons": side.get("barons"),
        "dragons": len(side.get("dragons") or []),
    }


def sample(frames, start):
    first, last = frames[0], frames[-1]
    totals = {f["blueTeam"]["totalGold"] + f["redTeam"]["totalGold"] for f in frames}
    flat = (
        len(frames) > 1
        and len(totals) == 1
        and (when(first) - start).total_seconds() > PAUSE_AFTER
        and (when(last) - when(first)).total_seconds() >= 5
    )
    return {
        "at": first["rfc460Timestamp"],
        "state": last["gameState"],
        "flat": flat,
        "blue": team(first["blueTeam"]),
        "red": team(first["redTeam"]),
    }


def find_start(game_id):
    """(start time of the first frame with 2,500 gold a side, the feed's blue team id).

    The feed's own team ids: getEventDetails' sides are often swapped."""
    payload = get(WINDOW.format(game_id)) or {}
    frames = payload.get("frames") or []
    meta = payload.get("gameMetadata") or {}
    blue_id = (meta.get("blueTeamMetadata") or {}).get("esportsTeamId")
    if not frames:
        return None, blue_id
    t = when(frames[0])
    for _ in range(30):  # five minutes of loading at most
        for f in frames:
            if (
                f["blueTeam"]["totalGold"] == START_GOLD
                and f["redTeam"]["totalGold"] == START_GOLD
            ):
                return when(f), blue_id
        t += timedelta(seconds=10)
        frames = window(game_id, t) or frames
    return None, blue_id


def collect_game(game):
    start, blue_id = find_start(game["game_id"])
    game = dict(game, blue_id=blue_id)
    if start is None:
        return dict(game, start=None, samples=[], final=None, error="no start")
    samples, final = [], None
    t = start
    for _ in range(MAX_MINUTES + 1):
        frames = window(game["game_id"], t)
        if not frames:
            break
        s = sample(frames, start)
        samples.append(s)
        if s["state"] == "finished":
            final = s
            break
        t += timedelta(seconds=STEP)
    if final is None and samples:
        # Look a little past the last sample for the finished frame.
        frames = window(game["game_id"], t + timedelta(seconds=30))
        if frames and frames[-1]["gameState"] == "finished":
            final = sample(frames, start)
    return dict(
        game,
        start=start.isoformat(),
        samples=samples,
        final=final,
        error=None if final else "no finished frame",
    )


def schedule(out):
    """Every completed match since SINCE in LEAGUES, with its games."""
    leagues = {
        lg["slug"]: lg["id"]
        for lg in get(f"{API}/getLeagues?hl=en-US", key=True)["data"]["leagues"]
    }
    path = out / "schedule.json"
    saved = json.loads(path.read_text()) if path.exists() else {}
    for slug, code in LEAGUES.items():
        if slug not in leagues:
            print(f"{slug}: not listed")
            continue
        token, events = None, []
        while True:
            query = {"hl": "en-US", "leagueId": leagues[slug]}
            if token:
                query["pageToken"] = token
            page = get(f"{API}/getSchedule?{urlencode(query)}", key=True)["data"][
                "schedule"
            ]
            events += page["events"]
            token = page["pages"].get("older")
            if not token or min(e["startTime"] for e in page["events"]) < SINCE:
                break
        matches = [
            e
            for e in events
            if e.get("type") == "match"
            and e.get("state") == "completed"
            and e["startTime"] >= SINCE
            and e.get("match", {}).get("id")
        ]
        for e in matches:
            match_id = e["match"]["id"]
            if match_id in saved:
                continue
            details = get(f"{API}/getEventDetails?hl=en-US&id={match_id}", key=True)
            if details is None:
                continue
            m = details["data"]["event"]["match"]
            names = {
                t["id"]: {"name": t["name"], "code": t.get("code")} for t in m["teams"]
            }
            saved[match_id] = {
                "league": code,
                "start": e["startTime"],
                "games": [
                    {
                        "game_id": g["id"],
                        "match_id": match_id,
                        "league": code,
                        "number": g["number"],
                        "teams": [
                            dict(names.get(t["id"], {}), id=t["id"], side=t["side"])
                            for t in g["teams"]
                        ],
                    }
                    for g in m["games"]
                    if g["state"] == "completed"
                ],
            }
        path.write_text(json.dumps(saved))
        print(f"{slug}: {len(matches)} matches")
    return saved


def collect(out, limit=None, shard=(0, 1)):
    """Maps in a fixed random order (a partial run still spans every year); `shard`
    (i, n) takes every n-th map so n runs can share the work."""
    saved = json.loads((out / "schedule.json").read_text())
    games = sorted(
        (g for m in saved.values() for g in m["games"]), key=lambda g: g["game_id"]
    )
    random.Random(SEED).shuffle(games)
    games = games[shard[0] :: shard[1]]
    (out / "games").mkdir(parents=True, exist_ok=True)
    done = 0
    for g in games:
        path = out / "games" / f"{g['game_id']}.json"
        if path.exists():
            continue
        result = collect_game(g)
        path.write_text(json.dumps(result))
        done += 1
        print(
            f"{saved[g['match_id']]['start'][:10]} {g['league']} map {g['number']}: "
            f"{len(result['samples'])} samples {result['error'] or ''}",
            flush=True,
        )
        if limit and done >= limit:
            break
    return done


def status(out):
    saved = json.loads((out / "schedule.json").read_text())
    total = sum(len(m["games"]) for m in saved.values())
    files = list((out / "games").glob("*.json")) if (out / "games").exists() else []
    ok = sum(1 for f in files if json.loads(f.read_text())["error"] is None)
    print(f"{len(files):,} of {total:,} maps collected, {ok:,} complete")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("schedule", "collect", "status"))
    parser.add_argument("--out", type=Path, default=OUT)
    parser.add_argument("--limit", type=int, help="maps to collect this run")
    parser.add_argument(
        "--shard", default="0/1", help="i/n: this run's share of the maps"
    )
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "schedule":
            schedule(args.out)
        elif args.command == "collect":
            i, n = (int(x) for x in args.shard.split("/"))
            collect(args.out, args.limit, (i, n))
        status(args.out)
    except Refused as error:
        print(f"Stopped: {error}. Saved maps are kept; run again later.")
        return 3
    except Unreachable as error:
        print(f"Unreachable: {error}. Saved maps are kept.")
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
