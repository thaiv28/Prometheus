"""Write a synthetic live feed (live/index.json and one file per match) for previews.

The live collector (in the lol-live repo) will write the real file; until then
this script produces the same shape from a made-up game, labelled as a demo on
the page. See "Live page state" in docs/steering/tech.md for the format.

    uv run python scripts/live_demo.py --minute 24             # one snapshot
    uv run python scripts/live_demo.py --minute 3 --follow     # keep the games going
    uv run python scripts/live_demo.py --matches 1             # only one match
    uv run python scripts/live_demo.py --status idle           # no game on

Then serve output/ (python -m http.server -d output 8000) and open
predictions.html (every match) or watch.html. Every time is real wall-clock time: a game at
--minute 24 started 24 minutes ago (divided by --speed). The other matches run a
few minutes ahead or behind the first.
"""

import argparse
import datetime
import json
import math
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "live"
SCHEMA = 1
FRAME_SECONDS = 10  # the feed's cadence, in game seconds
QUOTE_SECONDS = 15
CHECKPOINTS = (10, 15, 20)
GAME_MINUTES = 40
# The demo's matches: (minutes relative to --minute, spec). Team names are
# Oracle's Elixir names, so they link to team pages.
MATCHES = [
    (
        0,
        {
            "id": "lcs-tl-fly",
            "league": "LCS",
            "event": "LCS Championship",
            "best_of": 5,
            "teams": [
                {"name": "Team Liquid", "code": "TL"},
                {"name": "FlyQuest", "code": "FLY"},
            ],
            "score": [1, 0],
            "number": 2,
            "blue": 1,
            "pregame": 0.58,
            "series": 0.71,
            "seed": 7,
        },
    ),
    (
        -6,
        {
            "id": "lck-t1-gen",
            "league": "LCK",
            "event": "LCK Regional Finals",
            "best_of": 5,
            "teams": [{"name": "T1", "code": "T1"}, {"name": "Gen.G", "code": "GEN"}],
            "score": [1, 1],
            "number": 3,
            "blue": 0,
            "pregame": 0.44,
            "series": 0.41,
            "seed": 11,
        },
    ),
    (
        9,
        {
            "id": "lpl-blg-jdg",
            "league": "LPL",
            "event": "LPL Regional Finals",
            "best_of": 5,
            "teams": [
                {"name": "Bilibili Gaming", "code": "BLG"},
                {"name": "JD Gaming", "code": "JDG"},
            ],
            "score": [0, 0],
            "number": 1,
            "blue": 0,
            "pregame": 0.62,
            "series": 0.7,
            "seed": 3,
        },
    ),
    (
        -15,
        {
            "id": "lec-g2-fnc",
            "league": "LEC",
            "event": "LEC Season Finals",
            "best_of": 5,
            "teams": [
                {"name": "G2 Esports", "code": "G2"},
                {"name": "Fnatic", "code": "FNC"},
            ],
            "score": [2, 1],
            "number": 4,
            "blue": 1,
            "pregame": 0.66,
            "series": 0.83,
            "seed": 5,
        },
    ),
]


def iso(t):
    return (
        datetime.datetime.fromtimestamp(t, datetime.UTC)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def chance(gold_gap, minute, pregame):
    """A made-up live chance: the pre-game edge plus a gold lead worth more later."""
    logit = math.log(pregame / (1 - pregame)) + gold_gap / (
        1500 + 9000 / max(minute, 1)
    )
    return 1 / (1 + math.exp(-logit))


def simulate(game_seconds, seed):
    """Totals every FRAME_SECONDS of game time up to game_seconds."""
    rng = random.Random(seed)
    totals = [
        {
            "gold": 2500,
            "kills": 0,
            "towers": 0,
            "dragons": 0,
            "barons": 0,
            "inhibitors": 0,
        },
        {
            "gold": 2500,
            "kills": 0,
            "towers": 0,
            "dragons": 0,
            "barons": 0,
            "inhibitors": 0,
        },
    ]
    frames = []
    edge = 0.0
    for s in range(0, int(game_seconds) + 1, FRAME_SECONDS):
        if s:
            edge = 0.97 * edge + rng.gauss(0.04, 0.3)
            share = 1 / (1 + math.exp(-edge))
            income = 2 * (20 + s / 90) * FRAME_SECONDS
            totals[0]["gold"] += round(
                income * (0.92 + 0.16 * share) + rng.gauss(0, 25)
            )
            totals[1]["gold"] += round(
                income * (1.08 - 0.16 * share) + rng.gauss(0, 25)
            )
            if rng.random() < 0.055 + s / 40000:
                totals[0 if rng.random() < share else 1]["kills"] += 1
            if s > 300 and s % 300 == 0:
                totals[0 if rng.random() < share else 1]["dragons"] += 1
            if s > 840 and rng.random() < 0.03:
                totals[0 if rng.random() < share else 1]["towers"] += 1
            if s > 1200 and s % 420 == 0:
                totals[0 if rng.random() < share else 1]["barons"] += 1
        frames.append({"clock": s, "teams": [dict(t) for t in totals]})
    return frames


def match_state(spec, minute, args, now):
    """One match's file: the format the watch page reads (see tech.md)."""
    pre = spec["pregame"]
    started = now - minute * 60 / args.speed
    game_seconds = (now - started) * args.speed
    frames = simulate(game_seconds, spec["seed"])
    at = lambda clock: started + clock / args.speed
    for f in frames:
        f["at"] = iso(at(f["clock"]))
    calls = []
    for checkpoint in CHECKPOINTS:
        if checkpoint * 60 <= game_seconds:
            f = frames[checkpoint * 60 // FRAME_SECONDS]
            gap = f["teams"][0]["gold"] - f["teams"][1]["gold"]
            calls.append(
                {
                    "minute": checkpoint,
                    "p": round(chance(gap, checkpoint, pre), 3),
                    "by": "gold and Elo",
                    "at": iso(at(checkpoint * 60) + 2),
                }
            )
    rng = random.Random(spec["seed"] + 1)
    market = []
    for s in range(0, int(game_seconds) + 1, QUOTE_SECONDS):
        f = frames[min(s // FRAME_SECONDS, len(frames) - 1)]
        gap = f["teams"][0]["gold"] - f["teams"][1]["gold"]
        mid = min(0.97, max(0.03, chance(gap, s / 60, pre) + rng.gauss(0, 0.015)))
        spread = 0.02 + 0.01 * rng.random()
        market.append(
            {
                "at": iso(at(s) + 1),
                "bid": round(mid - spread / 2, 2),
                "ask": round(mid + spread / 2, 2),
            }
        )
    if args.no_clock:
        for f in frames:
            f["clock"] = None
    return {
        "schema": SCHEMA,
        "published_at": iso(now),
        "status": args.status,
        "note": "Demo feed: made-up games, not real matches.",
        "match": {
            "id": spec["id"],
            "league": spec["league"],
            "event": spec["event"],
            "best_of": spec["best_of"],
            "teams": spec["teams"],
            "score": spec["score"],
            "series": {
                "ours": spec["series"],
                "by": "FORGE",
                "kalshi": {
                    "at": iso(now - 20),
                    "bid": spec["series"] - 0.05,
                    "ask": spec["series"] - 0.01,
                },
                "kalshi_url": "https://kalshi.com/markets/kxlolgame/league-of-legends-game",
            },
        },
        "game": {
            "number": spec["number"],
            "id": f"{spec['id']}-{spec['number']}",
            "blue": spec["blue"],
            "pregame": {
                "p": pre,
                "by": "FORGE",
                "market": {
                    "at": iso(started - 60),
                    "bid": round(pre - 0.03, 2),
                    "ask": round(pre, 2),
                },
            },
            "calls": calls,
            "frames": frames,
            "market": market,
            "market_url": "https://kalshi.com/markets/kxlolmap",
            "winner": None,
            "ended_at": None,
        },
    }


def summary(state, url):
    """A match's entry in live/index.json: its latest numbers, no history."""
    match, game = state["match"], state["game"]
    last = game["frames"][-1] if game["frames"] else {}
    return {
        **{k: match[k] for k in ("id", "league", "event", "best_of", "teams", "score")},
        "url": url,
        "status": state["status"],
        "game": {
            "number": game["number"],
            "blue": game["blue"],
            "clock": last.get("clock"),
            "at": last.get("at"),
            "pregame": {k: game["pregame"][k] for k in ("p", "by")},
            "call": game["calls"][-1] if game["calls"] else None,
            "market": game["market"][-1] if game["market"] else None,
            "teams": last.get("teams"),
            "winner": game["winner"],
            "ended_at": game["ended_at"],
        },
    }


def feed(args, now):
    """{relative path: payload}: the index and each match's file."""
    if args.status in ("idle", "unavailable"):
        return {
            "index.json": {
                "schema": SCHEMA,
                "published_at": iso(now),
                "note": None,
                "matches": [],
            }
        }
    files, entries = {}, []
    for offset, spec in MATCHES[: args.matches]:
        # Games run to GAME_MINUTES, then a new one starts, so --follow can run all day.
        state = match_state(
            spec, max(0.5, (args.minute + offset) % GAME_MINUTES), args, now
        )
        name = f"{spec['id']}.json"
        files[name] = state
        entries.append(summary(state, f"live/{name}"))
    files["index.json"] = {
        "schema": SCHEMA,
        "published_at": iso(now),
        "note": "Demo feed: made-up games, not real matches.",
        "matches": entries,
    }
    return files


def write(files, out):
    out.mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        tmp = out / f"{name}.tmp"
        tmp.write_text(json.dumps(payload, separators=(",", ":")))
        tmp.replace(out / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--minute", type=float, default=24, help="the first game's minutes played now"
    )
    parser.add_argument(
        "--matches",
        type=int,
        default=len(MATCHES),
        help=f"how many matches (1–{len(MATCHES)})",
    )
    parser.add_argument(
        "--speed", type=float, default=1.0, help="game seconds per real second"
    )
    parser.add_argument(
        "--status",
        default="live",
        choices=["live", "paused", "between_games", "idle", "unavailable"],
    )
    parser.add_argument(
        "--no-clock", action="store_true", help="frames without a game clock"
    )
    parser.add_argument(
        "--follow", action="store_true", help="rewrite every 2 s until stopped"
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=OUT,
        help="directory for index.json and the match files",
    )
    args = parser.parse_args()
    now = time.time()
    if not args.follow:
        write(feed(args, now), args.out)
        print(f"Wrote {args.out}/index.json")
        return
    first = now
    base = args.minute
    while True:
        now = time.time()
        args.minute = base + (now - first) * args.speed / 60
        write(feed(args, now), args.out)
        time.sleep(2)


if __name__ == "__main__":
    main()
