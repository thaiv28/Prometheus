"""Enrich a COPY of the pinned live data with API drafts and prior-day histories.

Bounded historical feed requests require --fetch; no retries. Existing data pin
and shared source files are never modified. Availability uses the first returned
historical frame, not a measured live receipt; the result remains retrospective.
"""

import argparse
import gzip
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from prometheus import DB_PATH
from prometheus.live import draft
from prometheus.live.draft_export import History
from prometheus.live.service import fetch_json


def compact(history, roster, names):
    """Only the exact lookup rows this map needs; the same runtime resolver runs in CI."""
    out = {k: history[k] for k in ("schema", "as_of", "data_through", "champions")}
    out["teams"] = {n: history["teams"].get(n, {}) for n in names}
    ids = {p["player"] for side in roster for p in side.values()}
    out["players"] = {
        name: values
        for name, values in history.get("players", {}).items()
        if ids.intersection(values)
    }
    wanted = {"experience": set(), "meta": set(), "matchup": set(), "synergy": set()}
    from itertools import combinations

    for side, opp in zip(roster, reversed(roster)):
        tokens = []
        for role in draft.ROLES:
            p, c = side[role]["player"], side[role]["champion"]
            wanted["experience"].add(draft.key(p, c))
            wanted["meta"].add(draft.key(role, c))
            wanted["matchup"].add(draft.key(role, c, opp[role]["champion"]))
            tokens.append(f"{role}:{c}")
        wanted["synergy"].update(
            draft.pair_key(a, b) for a, b in combinations(tokens, 2)
        )
    for name, keys in wanted.items():
        out[name] = {k: history[name][k] for k in keys if k in history[name]}
    return out


def fetch_observation(m, cache, fetch):
    path = cache / f"{m['game']}.json"
    if path.exists():
        return json.loads(path.read_text())
    if not fetch:
        return None
    start = datetime.fromisoformat(m["start"].replace("Z", "+00:00"))
    start = start.replace(microsecond=0, second=start.second // 10 * 10)
    url = f"https://feed.lolesports.com/livestats/v1/window/{m['game']}?" + urlencode(
        {"startingTime": start.strftime("%Y-%m-%dT%H:%M:%SZ")}
    )
    request_dir = cache / "requests" / f"{m['game']}-{time.time_ns()}"
    record, payload = fetch_json(url, request_dir)
    if not payload or not payload.get("frames"):
        return None
    meta = payload.get("gameMetadata", {})
    sides = [meta.get(f"{s}TeamMetadata", {}) for s in ("blue", "red")]
    sample = payload["frames"][-1]
    observation = {
        "at": sample["rfc460Timestamp"],
        "source_at": sample["rfc460Timestamp"],
        "teams": [s.get("participantMetadata") for s in sides],
        "riot_team_ids": [s.get("esportsTeamId") for s in sides],
        "provenance": {
            "availability": "historical-window-proxy",
            "fetched_at": record["received_at_utc"],
            "response_sha256": record["sha256"],
        },
    }
    path.write_text(json.dumps(observation) + "\n")
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data", type=Path, default=ROOT / "data/live_bench/live_maps.json.gz"
    )
    parser.add_argument(
        "--games",
        type=Path,
        required=True,
        help="frozen draft_v2 player_feats_games.pkl with earlier-only production calls",
    )
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--cache", type=Path, default=ROOT / "data/research/draft_api")
    parser.add_argument(
        "--timelines", type=Path, default=ROOT / "data/feed_timelines/games"
    )
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="maximum maps to inspect, oldest first; never silently fetch the full corpus",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.limit <= 2000 or args.out.resolve() == args.data.resolve():
        parser.error("limit must be 1..2000 and output must differ from pinned input")
    args.cache.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.data, "rt") as f:
        data = json.load(f)
    games = pd.read_pickle(args.games)
    games["date"] = pd.to_datetime(games.date)
    counts = Counter()
    history = History(args.db)
    selected = sorted(data["maps"], key=lambda m: m["start"])[: args.limit]
    day, snapshot = None, None
    try:
        for m in selected:
            counts["inspected"] += 1
            obs = fetch_observation(m, args.cache, args.fetch)
            if obs is None:
                counts["no_api_metadata"] += 1
                continue
            if m["start"][:10] != day:
                day = m["start"][:10]
                snapshot = history.before(day).snapshot()
            at = pd.Timestamp(m["start"]).tz_localize(None)
            hits = games[
                (games.date - at).abs().le(pd.Timedelta(minutes=10))
                & games.blue.eq(m["teams"][m["blue"]])
                & games.red.eq(m["teams"][1 - m["blue"]])
            ]
            timeline_path = args.timelines / f"{m['game']}.json"
            source = (
                json.loads(timeline_path.read_text()) if timeline_path.exists() else {}
            )
            source_ids = {t["id"] for t in source.get("teams", [])}
            if (
                len(hits) != 1
                or source.get("blue_id") != obs["riot_team_ids"][0]
                or source_ids != set(obs["riot_team_ids"])
            ):
                counts["identity_or_oe_join_failed"] += 1
                continue
            codes = {t["id"]: t.get("code") for t in source.get("teams", [])}
            obs["team_codes"] = [codes.get(i) for i in obs["riot_team_ids"]]
            names = [m["teams"][m["blue"]], m["teams"][1 - m["blue"]]]
            try:
                roster = draft.resolve(obs, snapshot, names)
            except ValueError as error:
                counts[str(error)] += 1
                continue
            m["draft_history"] = compact(snapshot, roster, names)
            m["draft_observations"] = [obs]
            p = float(hits.iloc[0].p_forge)
            m["forge_p"] = p if m["blue"] == 0 else 1 - p
            counts["ready"] += 1
            print(f"{counts['inspected']}: {m['game']} ready", flush=True)
    finally:
        history.close()
    data["draft_enrichment"] = {
        "counts": dict(counts),
        "source": str(args.data),
        "availability": "historical-window-proxy; no measured receipt timing",
        "built": datetime.now(UTC).isoformat(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt") as f:
        json.dump(data, f, separators=(",", ":"))
    print(json.dumps(data["draft_enrichment"], indent=2))


if __name__ == "__main__":
    main()
