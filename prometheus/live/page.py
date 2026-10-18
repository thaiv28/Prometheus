"""Live page files: one match's schema-1 page from its collector, and the index.

Builds each match's `live/<match>.json` (actual Riot stats, timeline-model calls,
nullable fields kept null) from the collector's read-only SQLite journal.
"""

import json
import math
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from datetime import timedelta
from pathlib import Path

from .feed import integer, timestamp
from .requests import utc_now
from .timeline import timeline_calls


def first_team_probability(blue_probability, blue_index):
    """Orient a future model's blue-win probability to the fixed match order."""
    if blue_probability is None:
        return None
    if type(blue_index) is not int or blue_index not in (0, 1):
        raise ValueError("blue index must be 0 or 1")
    if (
        isinstance(blue_probability, bool)
        or not isinstance(blue_probability, (int, float))
        or not math.isfinite(blue_probability)
        or not 0 <= blue_probability <= 1
    ):
        raise ValueError("probability must be finite and in [0,1]")
    return blue_probability if blue_index == 0 else 1 - blue_probability


def validate_mapping(mapping, catalog):
    if (
        not isinstance(mapping, dict)
        or not isinstance(catalog, list)
        or any(
            not isinstance(entry, dict) or not isinstance(entry.get("n"), str)
            for entry in catalog
        )
    ):
        raise ValueError("mapping object and Prometheus team catalog list required")
    if mapping.get("schema") != 1:
        raise ValueError("unsupported mapping schema")
    for key in ("match_id", "competition", "league", "event"):
        if not isinstance(mapping.get(key), str) or not mapping[key]:
            raise ValueError(f"mapping requires {key}")
    teams = mapping.get("teams")
    if not isinstance(teams, list) or len(teams) != 2:
        raise ValueError("mapping requires two ordered teams")
    names = {entry["n"] for entry in catalog}
    for team in teams:
        if (
            not isinstance(team, dict)
            or not isinstance(team.get("riot_team_id"), str)
            or not team["riot_team_id"]
            or team.get("name") not in names
        ):
            raise ValueError("each Riot team ID needs an exact Prometheus catalog name")
    if (
        len({t["riot_team_id"] for t in teams}) != 2
        or len({t["name"] for t in teams}) != 2
    ):
        raise ValueError("mapped identities must differ")
    best_of = mapping.get("best_of")
    if type(best_of) is not int or best_of < 1 or best_of % 2 != 1:
        raise ValueError("best_of must be a positive odd integer")
    games = mapping.get("games")
    if (
        not isinstance(games, dict)
        or not games
        or any(
            not isinstance(k, str)
            or not k
            or type(v) is not int
            or not 1 <= v <= best_of
            for k, v in games.items()
        )
        or len(set(games.values())) != len(games)
    ):
        raise ValueError("games must map unique IDs to distinct map numbers")
    score = mapping.get("score")
    if score is not None and (
        not isinstance(score, list)
        or len(score) != 2
        or any(integer(n) is None or n > best_of // 2 + 1 for n in score)
        or sum(score) > best_of
    ):
        raise ValueError("score must be null or two valid series scores")
    return mapping


def read_collector(directory):
    """One consistent read transaction, including journal rows for this session."""
    database = Path(directory).resolve() / "collector.sqlite3"
    with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        stored = db.execute("SELECT body FROM state WHERE id=1").fetchone()
        if stored is None:
            raise ValueError("collector has no committed state")
        state = json.loads(stored[0])
        if state.get("version") != 1:
            raise ValueError("unsupported collector state version")
        if state.get("mode") not in {
            "simulated_replay",
            "recorded_replay",
            "network_probe",
        }:
            raise ValueError("unsupported collector mode")
        selection = state.get("selection")
        rows = []
        if selection:
            for (result,) in db.execute("SELECT result FROM journal ORDER BY sequence"):
                rows.extend(
                    row
                    for row in json.loads(result).get("rows", [])
                    if row.get("session") == selection["session"]
                    and row.get("status") == "research_candidate"
                )
        db.rollback()
    return state, rows


def unavailable(at, reason):
    return {
        "schema": 1,
        "published_at": at,
        "status": "unavailable",
        "note": reason,
        "match": None,
        "game": None,
        "live_state_verified": False,
    }


def build_state(state, rows, mapping, at, preview=False):
    now = timestamp(at)
    selection = state.get("selection")
    quality = {
        "mode": state["mode"],
        "collector_as_of": state.get("as_of"),
        "research_preview": preview,
        "live_state_verified": False,
    }
    if selection is None:
        return {
            "schema": 1,
            "published_at": at,
            "status": "idle",
            "note": "No selected map.",
            "match": None,
            "game": None,
            "quality": quality,
            "live_state_verified": False,
        }
    if (
        selection["match_id"] != mapping["match_id"]
        or selection["competition"] != mapping["competition"]
    ):
        raise ValueError("mapping does not match selected competition/match")
    ids = [t["riot_team_id"] for t in mapping["teams"]]
    if (
        set(ids) != {selection["blue_id"], selection["red_id"]}
        or selection["game_id"] not in mapping["games"]
    ):
        raise ValueError("selected teams/game missing from explicit mapping")
    blue_index = ids.index(selection["blue_id"])
    frames = []
    seen = set()
    for row in rows:
        if (
            row["session"] != selection["session"]
            or row["match_id"] != selection["match_id"]
            or row["game_id"] != selection["game_id"]
            or row["status"] != "research_candidate"
        ):
            raise ValueError("journal candidate does not belong to selected map")
        receipt = (
            row.get("simulated_received_at_utc")
            if state["mode"] == "simulated_replay"
            else row.get("received_at_utc")
        )
        if not receipt or timestamp(receipt) > now:
            continue
        source = timestamp(row["source_timestamp"])
        if source > timestamp(receipt):
            raise ValueError("candidate source timestamp is after receipt")
        if row["source_timestamp"] in seen:
            continue
        seen.add(row["source_timestamp"])
        sides = row["teams"]
        if (
            sides["blue"]["team_id"] != selection["blue_id"]
            or sides["red"]["team_id"] != selection["red_id"]
        ):
            raise ValueError("candidate side identities differ from selection")
        totals = []
        for team_id in ids:
            side = sides["blue"] if team_id == selection["blue_id"] else sides["red"]
            dragons = side.get("dragons")
            totals.append(
                {
                    "gold": side.get("totalGold"),
                    "kills": side.get("totalKills"),
                    "towers": side.get("towers"),
                    "dragons": len(dragons) if isinstance(dragons, list) else None,
                    "barons": side.get("barons"),
                    "inhibitors": side.get("inhibitors"),
                }
            )
        frames.append(
            {
                "at": receipt,
                "clock": None,
                "teams": totals,
                "source_at": row["source_timestamp"],
                "actual_received_at": row.get("received_at_utc"),
                "dragon_types": [
                    sides["blue" if i == blue_index else "red"].get("dragons")
                    for i in (0, 1)
                ],
                "live_state_verified": False,
            }
        )
    frames.sort(key=lambda f: timestamp(f["at"]))
    reason = None
    last = state.get("last_good")
    age = (now - timestamp(last["source_timestamp"])).total_seconds() if last else None
    quality.update(
        source_age_seconds=age,
        expires_at_utc=(
            (
                timestamp(last["source_timestamp"])
                + timedelta(seconds=selection["max_age_seconds"])
            ).isoformat()
            if last
            else None
        ),
        session=selection["session"],
        objective_semantics="source counters; not model approved",
        elapsed_clock_verified=False,
    )
    if state.get("as_of") and timestamp(state["as_of"]) > now:
        reason = "Collector state is ahead of exporter time."
    elif not preview:
        reason = "Live verification pending; collector research observations are unavailable for live display."
    elif state.get("unavailable_reason"):
        reason = "Research feed unavailable: " + state["unavailable_reason"]
    elif not last or not frames:
        reason = "No usable observation for the selected map."
    elif age is None or age < 0 or age > selection["max_age_seconds"]:
        reason = "Research observations are stale or have invalid source timing."
    finished = bool(state.get("window") and state["window"]["finished"])
    return {
        "schema": 1,
        "published_at": at,
        "status": "unavailable" if reason else "between_games" if finished else "live",
        "note": reason
        or "RESEARCH PREVIEW — unverified game state; no model calls or market quotes.",
        "match": {
            "id": mapping["match_id"],
            "league": mapping["league"],
            "event": mapping["event"],
            "best_of": mapping["best_of"],
            "teams": [{"name": t["name"]} for t in mapping["teams"]],
            "score": mapping.get("score"),
            "series": {"ours": None, "by": None, "kalshi": None, "kalshi_url": None},
        },
        "game": {
            "id": selection["game_id"],
            "number": mapping["games"][selection["game_id"]],
            "blue": blue_index,
            "pregame": {"p": None, "by": None, "market": None},
            "calls": [],
            "frames": frames,
            "market": [],
            "market_url": None,
            "winner": None,
            "ended_at": None,
        },
        "quality": quality,
        "live_state_verified": False,
    }


def write_atomic(path, payload):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(payload, stream, allow_nan=False)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def summary(page):
    match, game = page["match"], page["game"]
    last = game["frames"][-1] if game and game["frames"] else {}
    return {
        **{k: match[k] for k in ("id", "league", "event", "best_of", "teams", "score")},
        "start": match.get("start"),
        "url": f"live/{match['id']}.json",
        "status": page["status"],
        "game": None
        if game is None
        else {
            "number": game["number"],
            "blue": game["blue"],
            "clock": last.get("clock"),
            "clock_estimate": last.get("clock_estimate"),
            "at": last.get("at"),
            "pregame": game["pregame"],
            "call": game["calls"][-1] if game["calls"] else None,
            "market": game["market"][-1] if game.get("market") else None,
            "teams": last.get("teams"),
            "winner": None,
            "ended_at": None,
        },
    }


def attach_timeline(page, model, ratings, start=None, shift=0.0):
    """Estimated-clock research calls after any reviewed checkpoint calls."""
    pregame, calls = timeline_calls(page, model, ratings, start, shift)
    if pregame is None:
        return
    game = page["game"]
    game["pregame"] = {"p": pregame, "by": "Dated Elo (research)", "market": None}
    game["calls"] = sorted(game["calls"] + calls, key=lambda c: c["at"])
    page["quality"]["timeline_model"] = {
        "schema": model.get("schema"),
        "version": model.get("version"),
        "clock": "estimated from source time since 2,500/2,500 gold, pauses removed",
        "start": start,
        "series_shift": shift,
        "ratings": [
            {"name": t["name"], "elo": r["elo"], "as_of": r["as_of"]}
            for t, r in zip(page["match"]["teams"], ratings)
        ],
    }


def build_page(collector, mapping, catalog, at, timeline=None):
    """One match's schema-1 page; raises when it cannot be built."""
    validate_mapping(mapping, catalog)
    if not re.fullmatch(r"[\w-]+", mapping["match_id"]):
        raise ValueError("unsafe match file name")
    state, rows = read_collector(collector)
    page = build_state(state, rows, mapping, at, preview=True)
    page["quality"]["ordered_team_ids"] = [t["riot_team_id"] for t in mapping["teams"]]
    page["match"]["teams"] = [
        {"name": t["name"], "code": t.get("code", t["name"])} for t in mapping["teams"]
    ]
    if timeline:
        attach_timeline(page, *timeline)
    if page["status"] == "live":
        page["note"] = "Research preview."
    return page


def publish(collector, mapping, catalog, destination, at=None, timeline=None):
    """Match first, index last; empty index on failure so old evidence isn't relabelled."""
    at = at or utc_now()
    destination = Path(destination)
    if destination.resolve().is_relative_to(Path(collector).resolve()):
        raise ValueError("page output must be outside collector")
    index = {"schema": 1, "published_at": at, "matches": [], "note": None}
    try:
        page = build_page(collector, mapping, catalog, at, timeline)
        index["note"] = page["note"]
        write_atomic(destination / f"{mapping['match_id']}.json", page)
        if page["status"] not in {"unavailable", "idle"}:
            index["matches"] = [summary(page)]
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error) as error:
        index["note"] = "Feed unavailable: " + str(error)
    write_atomic(destination / "index.json", index)
    return index
