"""Live publisher: every lolesports game in progress onto the live pages.

Each minute one getLive request lists games in progress; each tracked game's
window feed is read every 10 seconds into its own collector. Pages carry actual
Riot stats, FORGE before the map and the series, timeline-model calls with an
estimated clock, and Kalshi's map and series quotes. Errors stop that game (no
retries); 401/403/429 from Riot stops the service, from Kalshi only its quotes.

    uv run python -m prometheus.live.service --fetch                     # local
    uv run python -m prometheus.live.service --fetch --s3 s3://<bucket>/current/live
"""

import argparse
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import tempfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import urlencode

from .. import DB_PATH
from ..alert_contract import fold
from .collector import Collector
from .feed import timestamp
from .kalshi import (
    KALSHI,
    MARKET_URL,
    MATCH_SERIES,
    MATCH_URL,
    SERIES,
    book_levels,
    contract,
    quote,
)
from .notify import dispatch_prices, upload_maps
from .page import build_page, summary, write_atomic
from .requests import SITE_API_HOST, probe, utc_now
from .series import map_prior, map_shift, series_chance
from .start import find_start
from .timeline import MODEL_PATH, latest_elo, timeline_calls

GETSCHEDULE = f"https://{SITE_API_HOST}/persisted/gw/getSchedule?hl=en-US"
GETLIVE = f"https://{SITE_API_HOST}/persisted/gw/getLive?hl=en-US"
WINDOW = "https://feed.lolesports.com/livestats/v1/window/{}?{}"
# Riot league slug -> Prometheus league name (picks the page's default stream).
LEAGUES = {
    "worlds": "WLDs",
    "msi": "MSI",
    "first_stand": "FST",
    "lck": "LCK",
    "lpl": "LPL",
    "lec": "LEC",
    "lcs": "LCS",
    "lta_n": "LTA N",
    "lta_s": "LTA S",
    "lcp": "LCP",
    "cblol-brazil": "CBLOL",
}
# Trailing words Riot adds to some teams' names (folded).
ORG_SUFFIX = re.compile(r"( (e ?sports|gaming))+$")
QUERY_LAG = 30  # initial lag; back off when Riot holds a feed back longer
LOG_FILE = None
FEED_PHASE = 0.5  # seconds after a 10 s boundary to poll the feed
FRESH = 60  # seconds a match file stays in the index without a new write
# Exit status after Riot refused access or rate-limited us: the systemd unit
# doesn't restart on it (no retrying into a block).
REFUSED = 3
# Exit status after --idle-exit minutes with no live game: the unit backs up the
# evidence and powers the worker off until the schedule starts it again.
IDLE = 4
RESTART_FOR_UPDATE = 5
RESTART_FLAG = Path(os.environ.get("APP_ROOT", "/srv/prometheus-live")) / "restart"
QUOTE_INTERVAL = 2  # seconds; independent of the Riot feed cadence
SERIES_SHOWN = 30  # minutes a decided series stays on the live pages
# A recorded map length outside this range (seconds) is dropped as implausible.
MAP_SECONDS = (15 * 60, 75 * 60)


class Stop(Exception):
    """Access refused or rate limited: stop all requests."""


def log(event, **fields):
    line = json.dumps(dict(at=utc_now(), event=event, **fields))
    print(line, flush=True)
    if LOG_FILE is not None and event != "cycle":
        with LOG_FILE.open("a") as file:
            file.write(line + "\n")


class TooRecent(ValueError):
    """Riot has not released this feed window yet."""


class FeedLag:
    def __init__(self):
        self.lags = {}
        self.successes = {}

    def lag(self, game_id):
        return self.lags.get(game_id, QUERY_LAG)

    def change(self, game_id, lag):
        self.successes[game_id] = 0
        if lag != self.lag(game_id):
            self.lags[game_id] = lag
            log("feed_lag", game=game_id, lag=lag)

    def too_recent(self, game_id):
        self.change(game_id, min(600, self.lag(game_id) * 2))

    def ok(self, game_id):
        self.successes[game_id] = self.successes.get(game_id, 0) + 1
        if self.successes[game_id] >= 30 and self.lag(game_id) > QUERY_LAG:
            self.change(game_id, max(QUERY_LAG, self.lag(game_id) // 2))


FEED_LAG = FeedLag()


def expire_failed(failed, failed_at, now):
    for gid in list(failed):
        if now - failed_at[gid] >= 300:
            del failed[gid]
            del failed_at[gid]


def fetch_json(url, out):
    """One request; None on 204; TooRecent on 400; Stop on 401/403/429."""
    record = probe(url, out)[0]
    status = record.get("http_status")
    if status in {401, 403, 429}:
        raise Stop(f"HTTP {status} from {url}")
    if status == 400:
        raise TooRecent(f"HTTP {status} {record.get('error', '')}".strip())
    if status == 204:
        return record, None
    if status != 200 or record.get("parse_error"):
        raise ValueError(f"HTTP {status} {record.get('error', '')}".strip())
    return record, json.loads((out / record["raw_file"]).read_bytes())


def resolve_team(team, catalog, aliases):
    names = {t["n"] for t in catalog}
    if team.get("id") in aliases:
        return aliases[team["id"]]
    if team.get("name") in names:
        return team["name"]
    slugs = [t["n"] for t in catalog if team.get("slug") and t.get("s") == team["slug"]]
    if len(slugs) == 1:
        return slugs[0]
    # Riot's spelling of a catalog name: "Dplus KIA", "LOS" (LØS), "Gen.G Esports".
    for key in (fold, lambda name: ORG_SUFFIX.sub("", fold(name))):
        matches = {t["n"] for t in catalog if key(t["n"]) == key(team.get("name", ""))}
        if len(matches) == 1:
            return matches.pop()
    return None


def live_events(payload):
    for event in payload["data"]["schedule"].get("events") or []:
        match = event.get("match")
        if event.get("state") == "inProgress" and match and len(match["teams"]) == 2:
            yield event


def feed_sides(game, out):
    """`game` with its sides as Riot's feed has them; None until the feed has it.

    getLive can still list the previous map's sides when a map starts (KC v MVK
    map 3, FURIA v C9 maps 2 and 3, 2026-10-16). The collector refuses every frame
    whose teams aren't on the selected sides, so a map selected that way shows no
    stats, never finishes and leaves no snapshot.
    """
    try:
        query = datetime.now(UTC).replace(microsecond=0) - timedelta(
            seconds=FEED_LAG.lag(game["id"])
        )
        query -= timedelta(seconds=query.second % 10)
        _, payload = fetch_json(
            WINDOW.format(
                game["id"],
                urlencode({"startingTime": query.strftime("%Y-%m-%dT%H:%M:%SZ")}),
            ),
            out,
        )
    except TooRecent:
        FEED_LAG.too_recent(game["id"])
        return None
    except ValueError as error:
        FEED_LAG.successes[game["id"]] = 0
        log("sides_failed", game=game["id"], reason=str(error))
        return None
    if payload is not None:
        FEED_LAG.ok(game["id"])
    metadata = (payload or {}).get("gameMetadata") or {}
    ids = {
        side: (metadata.get(f"{side}TeamMetadata") or {}).get("esportsTeamId")
        for side in ("blue", "red")
    }
    if None in ids.values():
        return None
    by_id = {team_id: side for side, team_id in ids.items()}
    if set(by_id) != {t["id"] for t in game["teams"]}:
        raise ValueError(f"feed teams {sorted(by_id)} are not getLive's")
    return dict(game, teams=[dict(t, side=by_id[t["id"]]) for t in game["teams"]])


def pin_order(event, root):
    """`event` with its teams in the order first seen for the match.

    Team 0 is who every stored record is for (settled map winners, FORGE, the
    quotes, the score), and getLive can swap a match's teams between maps (FURIA
    v C9 2026-10-16: C9 first on map 1, FURIA from map 2).
    """
    teams = event["match"]["teams"]
    ids = [t["id"] for t in teams]
    path = root / event["id"] / "teams.json"
    if not path.exists():
        write_atomic(path, ids)
        return event
    saved = json.loads(path.read_text())
    if saved == ids or sorted(saved) != sorted(ids):
        return event
    teams = sorted(teams, key=lambda t: saved.index(t["id"]))
    return dict(event, match=dict(event["match"], teams=teams))


def mapping_for(event, catalog, aliases):
    match = event["match"]
    teams = []
    for team in match["teams"]:
        name = resolve_team(team, catalog, aliases)
        if name is None:
            raise ValueError(f"no Prometheus name for {team['name']} ({team['id']})")
        teams.append(
            {
                "riot_team_id": team["id"],
                "name": name,
                "code": team["code"],
                "riot_name": team.get("name"),
            }
        )
    league = event["league"]
    return {
        "schema": 1,
        "match_id": event["id"],
        "competition": league["slug"],
        "league": LEAGUES.get(league["slug"], league["name"]),
        "event": " ".join(filter(None, [league["name"], event.get("blockName")])),
        "best_of": match.get("strategy", {}).get("count"),
        "teams": teams,
        "games": {g["id"]: g["number"] for g in match["games"]},
        "score": mapping_score(event),
    }


def decided(match):
    """Whether a Riot match has a winner (getLive can list it for hours after)."""
    best_of = (match.get("strategy") or {}).get("count")
    return any(
        (t.get("result") or {}).get("outcome") in {"win", "loss"}
        or (
            best_of is not None
            and ((t.get("result") or {}).get("gameWins") or 0) >= best_of // 2 + 1
        )
        for t in match.get("teams") or []
    )


def waiting_pages(events, catalog, aliases, at, tracked=(), failed=()):
    """Due Riot fixtures while this worker is on; same IDs as getLive.

    Schedule teams have names/codes but no Riot IDs or map assignments. Keep
    those unknown, and never replace a tracked map (including between maps).
    """
    now = timestamp(at)
    pages = {}
    # A league plays one match at a time; a decided one stays tracked a while.
    tracked_leagues = {
        e.get("league", {}).get("slug")
        for e in events
        if ((e.get("match") or {}).get("id") or e.get("id")) in tracked
        and not decided(e.get("match") or {})
    }
    seen = set(tracked)
    # A failed/skipped active map is unavailable, never a pre-match fallback.
    # getSchedule lacks games, so exclude its duplicate using getLive first.
    seen.update(
        event.get("id") or (event.get("match") or {}).get("id")
        for event in events
        if any(
            g.get("state") == "inProgress" and g.get("id") in failed
            for g in (event.get("match") or {}).get("games", [])
        )
    )
    for event in events:
        match = event.get("match") or {}
        mid = match.get("id") or event.get("id")
        if (
            not mid
            or not re.fullmatch(r"[\w-]+", str(mid))
            or mid in seen
            or event.get("state") not in {"unstarted", "inProgress"}
        ):
            continue
        try:
            if decided(match) or event["league"]["slug"] in tracked_leagues:
                continue
            if (
                not -240 * 60
                <= (timestamp(event["startTime"]) - now).total_seconds()
                <= 75 * 60
            ):
                continue
            teams = [
                {
                    "name": resolve_team(t, catalog, aliases),
                    "code": t.get("code"),
                    "riot_name": t.get("name"),
                }
                for t in match["teams"]
            ]
            if (
                len(teams) != 2
                or any(not t["name"] for t in teams)
                or teams[0]["name"] == teams[1]["name"]
            ):
                continue
            league = event["league"]
            slug = league["slug"]
            if slug in pages and timestamp(event["startTime"]) >= timestamp(
                pages[slug]["match"]["start"]
            ):
                continue
            pages[slug] = {
                "schema": 1,
                "published_at": at,
                "status": "waiting",
                "note": None,
                "match": {
                    "id": mid,
                    "start": event["startTime"],
                    "league": LEAGUES.get(league["slug"], league["name"]),
                    "event": " ".join(
                        filter(None, [league["name"], event.get("blockName")])
                    ),
                    "best_of": match.get("strategy", {}).get("count"),
                    "teams": teams,
                    "score": None,
                    "series": {},
                    "maps": [],
                },
                "game": None,
                "live_state_verified": False,
            }
            seen.add(mid)
        except (ValueError, KeyError, TypeError):
            continue
    return list(pages.values())


def settle_map(ticker, number, results_path, out):
    """Record map `number`'s winner from its settled Kalshi contract (YES = team 0).

    Returns True once a result is known. Kalshi usually determines a map minutes
    before getLive's score moves.
    """
    results = json.loads(results_path.read_text()) if results_path.exists() else {}
    if str(number) in results:
        return True
    _, payload = fetch_json(f"{KALSHI}/markets/{ticker}", out)
    market = (payload or {}).get("market") or {}
    if market.get("status") not in {"determined", "settled", "finalized"}:
        return False
    if market.get("result") not in {"yes", "no"}:
        return False
    results[str(number)] = {
        "winner": 0 if market["result"] == "yes" else 1,
        "ticker": ticker,
        "source": "kalshi",
        "at": utc_now(),
    }
    write_atomic(results_path, results)
    log("settled", ticker=ticker, map=number, winner=results[str(number)]["winner"])
    return True


def record_map(game):
    """Save a settled map from normalized collector evidence, including on restart."""
    try:
        path = game.dir.parent / "maps.json"
        maps = json.loads(path.read_text()) if path.exists() else {}
        key = str(game.number)
        if key in maps:
            return
        result = json.loads((game.dir.parent / "results.json").read_text()).get(key)
        if not result or result.get("winner") not in (0, 1):
            return
        rows = []
        db_path = game.collector_dir / "collector.sqlite3"
        with tempfile.TemporaryDirectory() as temporary:
            archive_path = game.dir / "archive.tar.gz"
            if not db_path.exists() and archive_path.exists():
                with tarfile.open(archive_path) as archive:
                    member = archive.extractfile("collector/collector.sqlite3")
                    db_path = Path(temporary) / "collector.sqlite3"
                    db_path.write_bytes(member.read())
            if db_path.exists():
                with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as db:
                    for (body,) in db.execute(
                        "SELECT result FROM journal ORDER BY sequence"
                    ):
                        rows.extend(json.loads(body).get("rows", []))
        rows = sorted(
            (r for r in rows if r.get("source_timestamp")),
            key=lambda r: timestamp(r["source_timestamp"]),
        )
        start_path = game.dir / "start.json"
        start = json.loads(start_path.read_text()) if start_path.exists() else {}
        # Only find_start's search back to the first frame dates the game's start;
        # the first frame we saw is later when the worker joined mid-map.
        found = start.get("source_at") if not start.get("error") else None
        started = found or (rows[0]["source_timestamp"] if rows else None)
        ended = rows[-1]["source_timestamp"] if rows else result.get("at")
        duration = (
            (timestamp(ended) - timestamp(found)).total_seconds()
            if found and ended
            else None
        )
        if duration is not None and not MAP_SECONDS[0] <= duration <= MAP_SECONDS[1]:
            duration = None
        players = []
        sides = (rows[-1].get("teams") or {}).values() if rows else []
        for team in game.mapping["teams"]:
            side = next(
                (
                    s
                    for s in sides
                    if str(s.get("team_id")) == str(team["riot_team_id"])
                ),
                {},
            )
            names = []
            for participant in side.get("participant_metadata") or []:
                name = participant.get("summonerName", "").strip()
                code = team.get("code") or ""
                if " " in name:
                    name = name.split(" ", 1)[1]
                elif (
                    code
                    and name.lower().startswith(code.lower())
                    and len(name) > len(code)
                ):
                    name = name[len(code) :]
                if name:
                    names.append(name)
            players.append(names if len(names) == 5 else None)
        mapping = game.mapping
        maps[key] = {
            "match_id": mapping["match_id"],
            "league": mapping["league"],
            "event": mapping.get("event"),
            "best_of": mapping.get("best_of"),
            "number": game.number,
            "game_id": game.id,
            "teams": [t["name"] for t in mapping["teams"]],
            "winner": result["winner"],
            "started_at": started,
            "ended_at": ended,
            "duration_seconds": round(duration) if duration is not None else None,
            "players": players if any(players) else None,
            "recorded_at": utc_now(),
        }
        write_atomic(path, maps)
        page = (
            game.snapshot_path()
            if hasattr(game, "snapshot_path")
            else ROOT
            / "output"
            / "live"
            / mapping["match_id"]
            / f"map{game.number}.json"
        )
        upload_maps(game.dir.parent, mapping["match_id"], page)
        if page.exists():
            dispatch_prices(datetime.now(UTC))
    except Exception as error:
        log("record_map_failed", game=game.id, reason=str(error))


def patch_snapshot(path, results_path, names):
    """Add a settled winner to a finished map's saved page."""
    if not path.exists() or not results_path.exists():
        return
    page = json.loads(path.read_text())
    result = json.loads(results_path.read_text()).get(str(page["game"]["number"]))
    if not result or page["game"].get("winner") is not None:
        return
    game = page["game"]
    game["winner"] = result["winner"]
    game["ended_at"] = game["frames"][-1]["at"] if game["frames"] else result["at"]
    page["note"] = f"{names[result['winner']]} won map {game['number']}."
    write_atomic(path, page)


def mapping_score(event):
    return [(t.get("result") or {}).get("gameWins") for t in event["match"]["teams"]]


class Ratings:
    """Team ratings for FORGE and the in-game model.

    Production reads `live_inputs.json` (`scripts/export_live_inputs.py`, from
    the publish build); without it, local runs compute them from the database.
    Reloaded when the file changes, or every `REFRESH` seconds from the DB.
    """

    REFRESH = 6 * 3600

    def __init__(self, inputs=None, db=None):
        self.inputs, self.db = inputs, db
        self.teams, self.stamp = None, None
        self.draft = None

    def refresh_fresh(self, bucket):
        """Adopt a newer refresh only when it belongs to the current publish."""
        if not self.inputs or not bucket:
            return
        candidate = self.inputs.parent / "live_inputs_fresh.json.new"
        try:
            candidate.unlink(missing_ok=True)
            result = subprocess.run(
                [
                    "aws",
                    "s3",
                    "cp",
                    f"s3://{bucket}/prometheus/live-inputs/live_inputs_fresh.json",
                    str(candidate),
                    "--only-show-errors",
                ],
                timeout=30,
                check=False,
                capture_output=True,
            )
            if result.returncode:
                return
            payload = json.loads(candidate.read_text())
            current = json.loads(self.inputs.read_text())
            if (
                not isinstance(payload["teams"], dict)
                or not payload["data_through"]
                or payload["data_through"] != current["data_through"]
                or datetime.fromisoformat(payload["generated_at"])
                <= datetime.fromisoformat(current["generated_at"])
            ):
                return
            candidate.replace(self.inputs)
            self.stamp = None
            log("ratings_refreshed", results_through=payload.get("results_through"))
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            pass
        finally:
            try:
                candidate.unlink(missing_ok=True)
            except OSError:
                pass

    def _load(self):
        if self.inputs and self.inputs.exists():
            stamp = self.inputs.stat().st_mtime
            if stamp != self.stamp:
                payload = json.loads(self.inputs.read_text())
                self.teams = payload["teams"]
                self.draft = payload.get("draft")
                self.stamp = stamp
            return self.teams
        if not (self.db and Path(self.db).exists()):
            self.teams = {}  # no ratings: stats and Kalshi only
            return self.teams
        if self.teams is None or time.monotonic() - (self.stamp or 0) > self.REFRESH:
            from ..form import load_states
            from ..schedule import current_ratings

            frame = current_ratings(load_states())
            teams = {}
            for name, row in frame.iterrows():
                teams[name] = {
                    "league": row["league"],
                    "elo": float(row["elo"]),
                    "form": float(row["form"]),
                    "forge": float(row["forge"]),
                    "has_form": bool(row["has_form"]),
                    "latest_date": str(row["latest_date"]),
                }
            if self.db:
                for team in teams:
                    try:
                        found = latest_elo(self.db, team, datetime.now(UTC))
                    except ValueError:
                        continue
                    teams[team]["model_elo"] = found["elo"]
                    teams[team]["model_elo_as_of"] = found["as_of"]
            self.teams, self.stamp = teams, time.monotonic()
        return self.teams

    def draft_history(self):
        self._load()
        return self.draft

    def model_elo(self, name):
        """The game-length Elo the in-game model was trained on, with its date."""
        team = self._load().get(name) or {}
        if team.get("model_elo") is None:
            raise ValueError(f"no Prometheus Elo for {name}")
        return {"elo": team["model_elo"], "as_of": team["model_elo_as_of"]}

    def forge(self, mapping, start_time):
        """FORGE's pre-match call for mapping team 0, as `prometheus predict` makes it."""
        from ..schedule import game_probability, series_probability, series_rho

        teams = self._load()
        a, b = (teams[t["name"]] for t in mapping["teams"])
        start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        p, method = game_probability(
            a,
            b,
            event=mapping["league"],
            title=mapping["event"],
            at=datetime.now(UTC),
            event_day=start,
        )
        rho = series_rho(a["league"], b["league"])
        return {
            "p_game": p,
            "p_series": series_probability(p, mapping["best_of"], rho),
            "method": method,
            "rho": rho,
            "homes": [a["league"], b["league"]],
            "ratings_through": [a["latest_date"], b["latest_date"]],
            "computed_at": utc_now(),
        }


def forge_for(args, mapping, start_time):
    """FORGE's call for mapping team 0, cached per match; None on failure."""
    path = args.root / mapping["match_id"] / "forge.json"
    if path.exists():
        return json.loads(path.read_text())
    try:
        forge = args.ratings.forge(mapping, start_time)
    except (KeyError, ValueError, sqlite3.Error) as error:
        log("forge_failed", match=mapping["match_id"], reason=str(error)[:300])
        return None
    write_atomic(path, forge)
    log(
        "forge",
        match=mapping["match_id"],
        p_game=forge["p_game"],
        p_series=forge["p_series"],
    )
    return forge


def waiting_mapping(page):
    match = page["match"]
    return dict(
        match_id=match["id"],
        **{key: match[key] for key in ("league", "event", "best_of", "teams")},
    )


def fill_waiting(page, args, ticker=None):
    """Use the same FORGE cache and series quote history as the tracked map."""
    match = page["match"]
    forge = (
        forge_for(args, waiting_mapping(page), match["start"]) if args.forge else None
    )
    series = {}
    if forge:
        series = {
            "ours": series_chance(
                forge["p_game"], match["best_of"], forge["rho"], [0, 0], None
            ),
            "by": "FORGE",
            "kalshi": None,
            "kalshi_url": None,
        }
    if ticker:
        rows = Game.quotes(args.root / match["id"] / "series_quotes.jsonl")
        if rows:
            if not series:
                series = {"ours": None, "by": "FORGE"}
            series.update(kalshi=rows[-1], kalshi_url=MATCH_URL)
    match["series"] = series


def poll_waiting_quote(root, mid, ticker, out):
    """Append a public series book to the match's shared quote history."""
    _, book = fetch_json(f"{KALSHI}/markets/{ticker}/orderbook", out)
    q = quote(book or {}, utc_now())
    if q:
        path = root / mid / "series_quotes.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(dict(q, ticker=ticker, **book_levels(book))) + "\n")


def feed_slot(now, interval):
    """The feed window a poll at `now` (epoch seconds) reads.

    Windows start on 10 s boundaries 30 s back, so the newest frame is about
    20.6 s old just after a boundary and 29.6 s old just before the next
    (BLG v MKOI, 2026-10-23). Polling once per slot, FEED_PHASE after it opens,
    keeps it near the floor without extra requests.
    """
    return int((now - FEED_PHASE) // interval)


def next_feed_slot(now, interval):
    """Seconds until the next feed slot opens."""
    return (feed_slot(now, interval) + 1) * interval + FEED_PHASE - now


def without_recorded(pages, page_dir, cache):
    """Drop waiting pages whose match file already holds a recorded map.

    After a restart nothing is tracked, and getLive can list a decided series
    (or one between maps) as in progress: its waiting page would overwrite the
    last map's page. `cache` maps a path to (mtime, recorded).
    """
    kept = []
    for page in pages:
        path = page_dir / f"{page['match']['id']}.json"
        try:
            mtime = path.stat().st_mtime
        except FileNotFoundError:
            kept.append(page)
            continue
        if cache.get(path, (None,))[0] != mtime:
            try:
                saved = json.loads(path.read_text())
                recorded = bool((saved.get("game") or {}).get("frames"))
            except (ValueError, OSError):
                recorded = False
            cache[path] = (mtime, recorded)
        if not cache[path][1]:
            kept.append(page)
    return kept


def publish_s3(page_out, uri):
    """Mirror the live files to the site bucket; short-cached, removed when gone."""
    command = [
        "aws",
        "s3",
        "sync",
        str(page_out),
        uri,
        "--delete",
        "--only-show-errors",
        "--content-type",
        "application/json",
        "--cache-control",
        "max-age=1",
    ]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as error:
        log("s3_failed", reason=str(error)[:300])
        return
    if done.returncode:
        log("s3_failed", reason=done.stderr.strip()[:300])


class PreMaps:
    """Kalshi's book for maps getLive lists as in progress before the feed has
    them (the draft and the loading screen), until the map is tracked.

    Each poll appends {at, bid, ask, yes, no (top levels), ticker} to
    `<root>/<match>/<game>/pre_quotes.jsonl`; the first sighting is logged as
    `pre_map_seen` (when the draft was first seen live).
    """

    def __init__(self, root):
        self.root, self.maps, self.seq = root, {}, 0

    def seen(self, event, game, mapping):
        gid = game["id"]
        if gid in self.maps:
            return
        self.maps[gid] = {
            "dir": self.root / event["id"] / gid,
            "mapping": mapping,
            "number": game["number"],
            "start_time": event.get("startTime"),
            "ticker": None,
        }
        log("pre_map_seen", game=gid, match=event["id"], map=game["number"])

    def drop(self, gid):
        self.maps.pop(gid, None)

    def keep(self, match_ids):
        for gid in [
            g for g, m in self.maps.items() if m["mapping"]["match_id"] not in match_ids
        ]:
            self.drop(gid)

    def want_tickers(self):
        return any(m["ticker"] is None for m in self.maps.values())

    def match(self, markets):
        for gid, m in self.maps.items():
            if m["ticker"] is None and m["start_time"]:
                m["ticker"] = contract(
                    markets, m["mapping"], m["number"], m["start_time"]
                )
                if m["ticker"]:
                    log("pre_map_contract", game=gid, ticker=m["ticker"])

    def poll(self):
        for m in self.maps.values():
            if not m["ticker"]:
                continue
            self.seq += 1
            stamp = datetime.now(UTC).strftime("%H%M%S")
            out = m["dir"] / "prebook" / f"{self.seq:06d}_{stamp}"
            _, book = fetch_json(f"{KALSHI}/markets/{m['ticker']}/orderbook", out)
            q = quote(book or {}, utc_now())
            if q:
                m["dir"].mkdir(parents=True, exist_ok=True)
                with (m["dir"] / "pre_quotes.jsonl").open("a") as f:
                    row = dict(q, ticker=m["ticker"], **book_levels(book))
                    f.write(json.dumps(row) + "\n")


class Game:
    def __init__(
        self, root, mapping, game, model, ratings, start_time=None, adopt=None
    ):
        self.mapping, self.id = mapping, game["id"]
        self.number, self.start_time = game["number"], start_time
        self.feed_failures = 0
        self.latest_signal_book = None
        self.signal_skip = None
        self.ticker = self.series_ticker = self.forge = self.page_out = None
        self.dir = root / mapping["match_id"] / self.id
        self.dir.mkdir(parents=True, exist_ok=True)
        tickers = self.dir / "kalshi.json"
        if tickers.exists():
            saved = json.loads(tickers.read_text())
            self.ticker, self.series_ticker = saved.get("map"), saved.get("series")
        self.seq = (
            len(list((self.dir / "requests").glob("*")))
            if (self.dir / "requests").exists()
            else 0
        )
        sides = {t["side"]: t["id"] for t in game["teams"]}
        # An adopted game keeps another run's collector and session (its history).
        self.collector_dir, session = adopt or (self.dir / "collector", self.id)
        self.collector = Collector(self.collector_dir, "network_probe")
        # A resumed session keeps the sides it was selected with.
        saved = self.collector.state["used_sessions"].get(session)
        if saved:
            sides = {"blue": saved["blue_id"], "red": saved["red_id"]}
        self.collector.process(
            {
                "action": "select",
                "at": utc_now(),
                "session": session,
                "competition": mapping["competition"],
                "match_id": mapping["match_id"],
                "game_id": self.id,
                "blue_id": sides["blue"],
                "red_id": sides["red"],
                "max_age_seconds": 75,
            }
        )
        start_file = self.dir / "start.json"
        self.start = json.loads(start_file.read_text()) if start_file.exists() else None
        self.timeline = None
        # Pin history/model on the first complete draft; a restart reuses the packet.
        self.draft_history = (
            ratings.draft_history() if hasattr(ratings, "draft_history") else None
        )
        candidate = Path(__file__).with_name("time_model_draft_v2.json")
        self.draft_model = (
            json.loads(candidate.read_text())
            if self.draft_history and candidate.exists()
            else None
        )
        if self.draft_model and (
            not model or self.draft_model["fallback_model"] != model
        ):
            self.draft_model = None  # Candidate must be paired with its tested parent.
        self.draft_loaded_at = utc_now()
        self.draft_path = self.dir / "draft_context.json"
        self.draft_context = (
            json.loads(self.draft_path.read_text())
            if self.draft_path.exists()
            else None
        )
        if model:
            try:
                elos = [ratings.model_elo(t["name"]) for t in mapping["teams"]]
                self.timeline = (model, elos)
            except ValueError as error:
                log("no_model", game=self.id, reason=str(error))
        # A resumed collector may already hold the finished map.
        finished = self.collector.snapshot()["status"] == "finished"
        self.state = "finished" if finished else "waiting"

    @property
    def results_path(self):
        return self.dir.parent / "results.json"

    def results(self):
        """Settled map winners for this match: {map number: team index}."""
        if not self.results_path.exists():
            return {}
        return {int(k): v for k, v in json.loads(self.results_path.read_text()).items()}

    def settle(self):
        """Once the map is over, read its Kalshi contract's settled result.

        Kalshi's determination usually lands minutes before getLive's score.
        """
        ticker = self.ticker
        if not ticker and self.number == self.mapping.get("best_of"):
            ticker = self.series_ticker  # the deciding map is the series
        if self.state != "finished":
            return
        if self.number in self.results():
            record_map(self)
        elif ticker and settle_map(
            ticker, self.number, self.results_path, self.request_dir("settle")
        ):
            record_map(self)

    def save_tickers(self):
        write_atomic(
            self.dir / "kalshi.json", {"map": self.ticker, "series": self.series_ticker}
        )

    def score(self):
        """getLive's score plus settled maps it hasn't counted yet."""
        score = list(self.mapping.get("score") or [])
        if len(score) != 2 or None in score:
            return None
        for number, result in sorted(self.results().items()):
            if number > sum(score):
                score[result["winner"]] += 1
        return score

    def score_before(self, score):
        """The series score before this map, or None when it can't be told."""
        if not score:
            return None
        before = list(score)
        counted = sum(before) - (self.number - 1)
        if counted == 1:
            # getLive or a settlement already counts this map.
            winner = (self.results().get(self.number) or {}).get("winner")
            if winner not in (0, 1):
                return None
            before[winner] -= 1
        elif counted != 0:
            return None
        return before

    def request_dir(self, kind):
        self.seq += 1
        stamp = datetime.now(UTC).strftime("%H%M%S")
        return self.dir / "requests" / f"{self.seq:06d}_{stamp}_{kind}"

    def window(self, t):
        query = urlencode({"startingTime": t.strftime("%Y-%m-%dT%H:%M:%SZ")})
        out = self.request_dir("window")
        record, payload = fetch_json(WINDOW.format(self.id, query), out)
        return out, record, payload

    def find_start(self):
        def fetch(t):
            _, _, payload = self.window(t)
            return payload["frames"] if payload else []

        try:
            found, error = find_start(fetch, datetime.now(UTC)), None
        except ValueError as failure:
            # Fall back to the first starting-gold frame seen live.
            found, error = None, str(failure)
        self.start = {"source_at": found, "searched_at": utc_now(), "error": error}
        write_atomic(self.dir / "start.json", self.start)
        log("start", game=self.id, start=found)

    def poll(self):
        now = datetime.now(UTC)
        self.collector.process({"action": "tick", "at": now.isoformat()})
        query = now.replace(microsecond=0) - timedelta(seconds=FEED_LAG.lag(self.id))
        query -= timedelta(seconds=query.second % 10)
        try:
            out, record, payload = self.window(query)
        except TooRecent:
            FEED_LAG.too_recent(self.id)
            return
        except ValueError as error:
            FEED_LAG.successes[self.id] = 0
            self.feed_failures += 1
            log(
                "feed_failed", game=self.id, reason=str(error), count=self.feed_failures
            )
            if self.feed_failures >= 30:
                raise
            return
        self.feed_failures = 0
        if payload is not None:
            FEED_LAG.ok(self.id)
        if payload is None:
            return  # no content yet: draft or loading
        self.collector.process(
            {
                "action": "response",
                "at": record["received_at_utc"],
                "probe_dir": str(out.resolve()),
            }
        )
        self.state = "live"
        if self.start is None and any(
            f["blueTeam"]["totalGold"] > 0 for f in payload["frames"]
        ):
            self.find_start()
        if self.collector.snapshot()["status"] == "finished":
            self.state = "finished"

    def poll_quote(self, ticker, path):
        """One orderbook read for YES on team 0, appended to `path` when two-sided."""
        out = self.request_dir("book")
        record, book = fetch_json(f"{KALSHI}/markets/{ticker}/orderbook", out)
        q = quote(book or {}, utc_now())
        if ticker == self.ticker or (
            self.mapping["best_of"] == 1
            and not self.ticker
            and ticker == self.series_ticker
        ):
            self.latest_signal_book = None
            headers = record.get("headers") or {}
            # Trading also needs a current, uncached exchange response.
            if q and headers.get("Date") and float(headers.get("Age") or 0) == 0:
                import email.utils

                server = email.utils.parsedate_to_datetime(headers["Date"])
                if 0 <= (timestamp(q["at"]) - server).total_seconds() <= 3:
                    self.latest_signal_book = q
        if q:
            with path.open("a") as f:
                row = dict(q, ticker=ticker, **book_levels(book))
                f.write(json.dumps(row) + "\n")

    @staticmethod
    def quotes(path):
        if not path.exists():
            return []
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        return [{"at": r["at"], "bid": r["bid"], "ask": r["ask"]} for r in rows]

    @property
    def series_quotes_path(self):
        return self.dir.parent / "series_quotes.jsonl"

    def page(self, catalog, at, record=True):
        score = self.score()
        before = self.score_before(score)
        # Maps already played move this map's call as they move the series odds.
        shift = 0.0
        if self.forge and before:
            shift = map_shift(self.forge["p_game"], self.forge["rho"], *before)
        timeline = None
        if self.timeline:
            timeline = (*self.timeline, (self.start or {}).get("source_at"), shift)
        page = build_page(
            self.collector_dir, self.mapping, catalog, at, timeline=timeline
        )
        if self.state == "waiting" and page.get("game") and not page["game"]["frames"]:
            page.update(status="waiting", note=None)
        game = page.get("game")
        if game and self.timeline and self.draft_model and self.forge:
            from .draft import prepare

            game["start"] = (self.start or {}).get("source_at")
            packet = prepare(
                page,
                self.draft_history,
                self.draft_model,
                self.forge["p_game"],
                self.draft_context,
                not_before=self.draft_loaded_at,
            )
            if packet != self.draft_context:
                self.draft_context = packet
                write_atomic(self.draft_path, packet)
            _, shadow = timeline_calls(
                page,
                self.draft_model,
                self.timeline[1],
                (self.start or {}).get("source_at"),
                shift,
                draft=packet,
            )
            # Save privately with the journal; public calls remain the baseline.
            self.draft_shadow = {
                "context": packet,
                "call": shadow[-1] if shadow else None,
            }
        result = self.results().get(self.number)
        if score:
            page["match"]["score"] = score
        if game and self.state == "finished":
            # The match goes on: show the finished map and the score, not a blank page.
            page["status"] = "between_games"
            names = [t["name"] for t in self.mapping["teams"]]
            page["note"] = None
            if result:
                game["winner"] = result["winner"]
                game["ended_at"] = game["frames"][-1]["at"] if game["frames"] else at
                page["note"] = f"{names[result['winner']]} won map {self.number}."
            need = (self.mapping.get("best_of") or 1) // 2 + 1
            if score and max(score) >= need:
                # The series is over: say so, then leave the index after a while.
                won = 0 if score[0] > score[1] else 1
                page["note"] = f"{names[won]} won the series {max(score)}–{min(score)}."
                last = game["frames"][-1]["at"] if game["frames"] else None
                if last and timestamp(at) - timestamp(last) > timedelta(
                    minutes=SERIES_SHOWN
                ):
                    page["status"] = "idle"
        elif (
            game
            and self.state == "waiting"
            and page["status"] in {"unavailable", "idle"}
        ):
            page["status"] = "between_games"
            page["note"] = None
        if game and self.page_out:
            page["match"]["maps"] = self.maps()
        if game and self.forge and score:
            # FORGE is side-free; `forge` was computed for mapping team 0.
            p_map = self.forge["p_game"]
            if before:
                p_map = map_prior(p_map, self.forge["rho"], *before)
            game["pregame"] = dict(game["pregame"] or {}, p=p_map, by="FORGE")
            calls = game["calls"]
            live = (
                calls[-1]["p"]
                if calls and page["status"] in {"live", "paused"}
                else None
            )
            page["match"]["series"] = {
                "ours": series_chance(
                    self.forge["p_game"],
                    self.mapping["best_of"],
                    self.forge["rho"],
                    score,
                    live,
                ),
                "by": "Ours" if live is not None else "FORGE",
                "kalshi": (self.quotes(self.series_quotes_path) or [None])[-1],
                "kalshi_url": MATCH_URL if self.series_ticker else None,
            }
        page["match"]["start"] = self.start_time
        if record:
            self.journal(page)
        return self.add_quotes(page)

    def add_quotes(self, page):
        """Refresh prices on an existing page without replaying the game feed."""
        quotes = self.quotes(self.dir / "quotes.jsonl")
        series = page["match"].get("series")
        if series:
            series["kalshi"] = (self.quotes(self.series_quotes_path) or [None])[-1]
        url = MARKET_URL
        if not self.ticker and self.deciding(self.score()):
            # Kalshi lists no market for a deciding map: the series market is it.
            quotes, url = self.quotes(self.series_quotes_path), MATCH_URL
        if quotes and page.get("game"):
            game = page["game"]
            frames = game["frames"]
            # Before the map means before its start in the feed (the history
            # search); the first frame received is later when joining late.
            start = (self.start or {}).get("source_at") or (
                frames[0]["at"] if frames else None
            )
            start = timestamp(start) if start else None
            before = [q for q in quotes if start and timestamp(q["at"]) < start]
            game["market"] = [
                q for q in quotes if not start or timestamp(q["at"]) >= start
            ]
            game["market_url"] = url
            if before:
                game["pregame"] = dict(game["pregame"] or {}, market=before[-1])
        return page

    def deciding(self, score):
        """Whether this map decides the series (both teams one map from winning)."""
        best_of = self.mapping.get("best_of") or 1
        if self.number == best_of:
            return True  # the last map, even once the score counts it
        need = best_of // 2 + 1
        return bool(score) and score[0] == score[1] == need - 1

    def snapshot_path(self, number=None):
        match = self.mapping["match_id"]
        return self.page_out / match / f"map{number or self.number}.json"

    def maps(self):
        """Every map of the match the page can show: finished snapshots, then this one."""
        results = self.results()
        out = []
        for path in sorted(
            (self.page_out / self.mapping["match_id"]).glob("map*.json")
        ):
            number = int(path.stem[3:])
            if number != self.number:
                winner = (results.get(number) or {}).get("winner")
                if winner is None:
                    # A result settled in an earlier run is kept in the map's file.
                    try:
                        winner = json.loads(path.read_text())["game"].get("winner")
                    except (ValueError, KeyError, TypeError, OSError):
                        winner = None
                out.append(
                    {
                        "number": number,
                        "url": f"live/{self.mapping['match_id']}/{path.name}",
                        "winner": winner,
                    }
                )
        out.append(
            {"number": self.number, "url": None, "winner": None, "current": True}
        )
        return sorted(out, key=lambda m: m["number"])

    def write_snapshot(self, catalog):
        """A finished map's final page, kept for the series view."""
        page = self.page(catalog, utc_now(), record=False)
        page["final"] = True
        self.snapshot_path().parent.mkdir(parents=True, exist_ok=True)
        write_atomic(self.snapshot_path(), page)
        if not getattr(self, "_snapshot_notified", False):
            upload_maps(self.dir.parent, self.mapping["match_id"], self.snapshot_path())
            if self.number in self.results():
                dispatch_prices(datetime.now(UTC))
            self._snapshot_notified = True

    def journal(self, page):
        """Append each newly published call (map and series) as it was made."""
        game, series = page.get("game") or {}, page["match"].get("series") or {}
        calls = game.get("calls") or []
        row = {
            "map": self.number,
            "minute": calls[-1]["minute"] if calls else None,
            "p_map": calls[-1]["p"] if calls else None,
            "p_series": series.get("ours"),
            "draft_shadow": getattr(self, "draft_shadow", None),
            "score": self.mapping.get("score"),
            "status": page["status"],
        }
        if row != getattr(self, "_last_journal", None):
            self._last_journal = row
            with (self.dir.parent / "calls.jsonl").open("a") as f:
                f.write(json.dumps(dict(row, at=utc_now(), game=self.id)) + "\n")

    def close(self):
        """Release the writer; pack a finished game's evidence (~18x smaller)."""
        self.collector.close()
        if self.state != "finished":
            return
        parts = [
            self.dir / "requests",
            self.collector_dir,
            self.dir / "quotes.jsonl",
            self.draft_path,
        ]
        with tarfile.open(self.dir / "archive.tar.gz", "w:gz") as archive:
            for part in parts:
                if part.exists():
                    archive.add(part, arcname=part.name)
        for part in parts:
            if part.is_dir():
                shutil.rmtree(part, ignore_errors=True)
            else:
                part.unlink(missing_ok=True)
        log("archived", game=self.id)


def update_lifecycle(page_dir, events, catalog, aliases, at):
    """Persist provider-confirmed series state across empty indexes and shutdowns."""
    path = page_dir / "lifecycle.json"
    saved = json.loads(path.read_text()) if path.exists() else {"series": {}}
    before = json.dumps(saved, sort_keys=True)
    series = saved["series"]
    for event in events:
        if event.get("state") not in {"inProgress", "completed"}:
            continue
        match = event.get("match") or {}
        mid = match.get("id") or event.get("id")
        teams = [
            {"name": resolve_team(t, catalog, aliases), "code": t.get("code")}
            for t in match.get("teams", [])
        ]
        if not mid or len(teams) != 2 or any(not t["name"] for t in teams):
            continue
        start = event.get("startTime")
        if not start or timestamp(at) - timestamp(start) > timedelta(days=7):
            continue
        old = series.get(mid) or {}
        league = event.get("league") or {}
        score = [t.get("result", {}).get("gameWins") for t in match["teams"]]
        series[mid] = dict(
            old,
            id=mid,
            teams=teams,
            start=start,
            league=LEAGUES.get(league.get("slug"), league.get("name")),
            best_of=match.get("strategy", {}).get("count"),
            status="completed"
            if event["state"] == "completed" or old.get("status") == "completed"
            else "live",
            score=score if all(type(v) is int for v in score) else old.get("score"),
        )
        if old.get("status") == "completed" and event["state"] != "completed":
            series[mid] = old
        page_path = page_dir / f"{mid}.json"
        if page_path.exists():
            page = json.loads(page_path.read_text())
            if (page.get("game") or {}).get("frames"):
                series[mid].update(recorded=True, url=f"live/{mid}.json")
                if series[mid]["status"] == "completed":
                    complete_page(page_dir, page, series[mid])
    series = {
        k: v
        for k, v in series.items()
        if timestamp(at) - timestamp(v["start"]) <= timedelta(days=7)
    }
    body = {"series": series}
    if json.dumps(body, sort_keys=True) != before or not path.exists():
        write_atomic(path, body)
        return True
    return False


def complete_page(page_dir, page, row):
    """Use the provider's final series score, with each page's pinned team order."""
    names = [t["name"] for t in page["match"]["teams"]]
    incoming = [t["name"] for t in row["teams"]]
    score = row.get("score")
    need = (page["match"].get("best_of") or 1) // 2 + 1
    if set(names) != set(incoming) or not score or None in score or max(score) < need:
        return
    score = [score[incoming.index(name)] for name in names]
    previous = page["match"].get("score")
    game = page["game"]
    if game.get("winner") is None and previous and None not in previous:
        delta = [a - b for a, b in zip(score, previous)]
        if delta in ([1, 0], [0, 1]) and sum(score) == game["number"]:
            game["winner"] = delta.index(1)
    winner = 0 if score[0] > score[1] else 1
    note = f"{names[winner]} won the series {max(score)}–{min(score)}."
    if (
        page["match"].get("score") == score
        and page.get("note") == note
        and page.get("final")
        and page.get("status") == "between_games"
    ):
        return
    page["match"]["score"] = score
    page.update(status="between_games", note=note, final=True)
    game["ended_at"] = game.get("ended_at") or game["frames"][-1]["at"]
    write_atomic(page_dir / f"{row['id']}.json", page)
    snapshot = dict(page, final=True)
    write_atomic(page_dir / row["id"] / f"map{game['number']}.json", snapshot)


def update_observed(page_dir, games, at):
    """Attach watch links only for recorded maps; settle a known deciding win."""
    path = page_dir / "lifecycle.json"
    saved = json.loads(path.read_text()) if path.exists() else {"series": {}}
    before = json.dumps(saved, sort_keys=True)
    for game in games:
        mid = game.mapping["match_id"]
        row = saved["series"].get(mid)
        if row is None:
            continue
        row["url"] = f"live/{mid}.json"
        row["recorded"] = True
        if row.get("status") == "completed":
            continue
        score = game.score()
        names = [t["name"] for t in game.mapping["teams"]]
        if score and [t["name"] for t in row["teams"]] == names:
            row["score"] = score
            if max(score) >= (game.mapping.get("best_of") or 1) // 2 + 1:
                row["status"] = "completed"
    if before != json.dumps(saved, sort_keys=True):
        write_atomic(path, saved)


def write_index(page_dir, at):
    """Every fresh match file, including ones other publishers wrote."""
    matches = []
    for path in sorted(page_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        try:
            page = json.loads(path.read_text())
            age = (timestamp(at) - timestamp(page["published_at"])).total_seconds()
            if (
                age <= FRESH
                and page.get("match")
                and page["status"]
                not in {
                    "unavailable",
                    "idle",
                }
            ):
                matches.append(summary(page))
        except (ValueError, KeyError, TypeError, OSError):
            continue
    note = None if matches else "No live match."
    path = page_dir / "index.json"
    if not matches:
        # Nothing on, as before: leave the file (and the S3 mirror) untouched.
        try:
            if not json.loads(path.read_text())["matches"]:
                return 0, False
        except (ValueError, KeyError, TypeError, OSError):
            pass
    write_atomic(
        path, {"schema": 1, "published_at": at, "matches": matches, "note": note}
    )
    return len(matches), True


def run(args):
    catalog = json.loads(args.team_catalog.read_text())
    aliases = json.loads(args.aliases.read_text()) if args.aliases.exists() else {}
    model = json.loads(args.model.read_text()) if args.model else None
    skip = set(args.skip_game)
    adopt = {}
    for spec in args.adopt:
        gid, path, session = spec.split(":", 2)
        adopt[gid] = (Path(path), session)
    games, failed, last_discovery = {}, {}, 0.0
    failed_at = {}
    pre = PreMaps(args.root)
    signals = None
    if getattr(args, "live_map_signals", False):
        from .signals import Cli, Outbox, Signals

        outbox = None
        if args.signal_bucket:
            bridge = Cli(args.root / "signal-outbox")
            outbox = Outbox(bridge, bridge, args.signal_bucket, args.signal_queue)
        signals = Signals(fetch_json, outbox)
    events, last_active = None, time.monotonic()
    scheduled = []
    waiting_ids = set()
    waiting_tickers, waiting_discovered, waiting_polled = {}, {}, {}
    last_pending = []
    waiting_seq = 0
    feed_polled, recorded_cache = {}, {}
    kalshi = True
    last_ratings_refresh = float("-inf")
    try:
        while True:
            cycle = time.monotonic()
            if cycle - last_ratings_refresh >= 300:
                last_ratings_refresh = cycle
                if os.environ.get("ARTIFACTS_BUCKET") and args.ratings.inputs:
                    args.ratings.refresh_fresh(os.environ["ARTIFACTS_BUCKET"])
            lifecycle_changed = False
            if cycle - last_discovery >= args.discover_interval:
                last_discovery = cycle
                expire_failed(failed, failed_at, cycle)
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
                try:
                    _, payload = fetch_json(GETLIVE, args.root / "discovery" / stamp)
                except ValueError as error:
                    log("discovery_failed", reason=str(error))
                    payload = None
                events = (
                    [pin_order(e, args.root) for e in live_events(payload)]
                    if payload
                    else None
                )
                try:
                    _, schedule = fetch_json(
                        GETSCHEDULE, args.root / "schedule" / stamp
                    )
                    scheduled = schedule["data"]["schedule"].get("events") or []
                except (ValueError, KeyError, TypeError) as error:
                    scheduled = []
                    log("schedule_failed", reason=str(error))
                completed = {
                    e.get("id") or (e.get("match") or {}).get("id")
                    for e in scheduled
                    if e.get("state") == "completed"
                }
                if events is not None:
                    events = [e for e in events if e["id"] not in completed]
                if events is not None:
                    live_ids = {e["id"] for e in events}
                    for gid in [
                        k
                        for k, g in games.items()
                        if g.mapping["match_id"] not in live_ids
                    ]:
                        done = games.pop(gid)
                        if done.mapping["match_id"] in completed:
                            done.state = "finished"
                        if done.state == "finished":
                            if kalshi or done.number in done.results():
                                try:
                                    done.settle()
                                except Stop as error:
                                    kalshi = False
                                    log("kalshi_stopped", reason=str(error))
                                except ValueError as error:
                                    log("settle_failed", game=gid, reason=str(error))
                            done.write_snapshot(catalog)
                        done.close()
                        log("untracked", game=gid, reason="match no longer live")
                    pre.keep(live_ids)
                lifecycle_changed = update_lifecycle(
                    args.page_out,
                    scheduled + (events or []),
                    catalog,
                    aliases,
                    utc_now(),
                )
                for event in events or []:
                    for game in event["match"]["games"]:
                        gid = game["id"]
                        if (
                            game["state"] != "inProgress"
                            or gid in games
                            or gid in failed
                            or gid in skip
                        ):
                            continue
                        if any(
                            g.mapping["match_id"] == event["id"]
                            and g.number > game["number"]
                            for g in games.values()
                        ):
                            continue  # getLive relisting an earlier map as live
                        try:
                            mapping = mapping_for(event, catalog, aliases)
                            if gid not in adopt:
                                out = args.root / event["id"] / gid / "sides" / stamp
                                listed, game = game, feed_sides(game, out)
                                if game is None:
                                    # Draft or loading: read Kalshi's book meanwhile.
                                    pre.seen(event, listed, mapping)
                                    continue
                            # A new map replaces the match's earlier one.
                            for old in [
                                k
                                for k, g in games.items()
                                if g.mapping["match_id"] == event["id"]
                            ]:
                                previous = games.pop(old)
                                if previous.state == "finished":
                                    previous.write_snapshot(catalog)
                                previous.close()
                            games[gid] = Game(
                                args.root,
                                mapping,
                                game,
                                model,
                                args.ratings,
                                event.get("startTime"),
                                adopt.get(gid),
                            )
                            games[gid].page_out = args.page_out
                            pre.drop(gid)
                            log(
                                "tracking",
                                game=gid,
                                match=event["id"],
                                teams=[t["name"] for t in mapping["teams"]],
                                map=game["number"],
                            )
                        except (ValueError, KeyError, sqlite3.Error) as error:
                            failed[gid] = str(error)
                            failed_at[gid] = time.monotonic()
                            log("skipped", game=gid, reason=str(error))
                for event in events or []:
                    for game in event["match"]["games"]:
                        gid = game["id"]
                        local = args.root / event["id"] / gid / "collector"
                        has_data = gid in adopt or local.exists()
                        snap = args.page_out / event["id"] / f"map{game['number']}.json"
                        if (
                            game["state"] != "completed"
                            or gid in games
                            or not has_data
                            or snap.exists()
                        ):
                            continue
                        try:
                            mapping = mapping_for(event, catalog, aliases)
                            done = Game(
                                args.root,
                                mapping,
                                game,
                                model,
                                args.ratings,
                                event.get("startTime"),
                                adopt.get(gid),
                            )
                            done.page_out, done.state = args.page_out, "finished"
                            if args.forge:
                                done.forge = forge_for(args, mapping, done.start_time)
                            done.write_snapshot(catalog)
                            done.close()
                            log("snapshot", game=gid, map=game["number"])
                        except (ValueError, KeyError, OSError, sqlite3.Error) as error:
                            log("snapshot_failed", game=gid, reason=str(error))
                for event in events or []:
                    names = [t.get("name") for t in event["match"]["teams"]]
                    match_dir = args.root / event["id"]
                    for game in event["match"]["games"]:
                        tickers = match_dir / game["id"] / "kalshi.json"
                        snap = args.page_out / event["id"] / f"map{game['number']}.json"
                        results_path = match_dir / "results.json"
                        results = (
                            json.loads(results_path.read_text())
                            if results_path.exists()
                            else {}
                        )
                        known = str(game["number"]) in results
                        if game["id"] in games or (
                            not known and (not tickers.exists() or not kalshi)
                        ):
                            continue
                        saved = (
                            json.loads(tickers.read_text()) if tickers.exists() else {}
                        )
                        ticker = saved.get("map")
                        if not ticker and game["number"] == event["match"].get(
                            "strategy", {}
                        ).get("count"):
                            ticker = saved.get("series")  # the deciding map
                        try:
                            stamp_dir = (
                                match_dir / "settlements" / f"{stamp}_{game['number']}"
                            )
                            if known or (
                                ticker
                                and settle_map(
                                    ticker,
                                    game["number"],
                                    match_dir / "results.json",
                                    stamp_dir,
                                )
                            ):
                                try:
                                    mapping = mapping_for(event, catalog, aliases)
                                    names = [t["name"] for t in mapping["teams"]]
                                    record_map(
                                        SimpleNamespace(
                                            dir=match_dir / game["id"],
                                            collector_dir=match_dir
                                            / game["id"]
                                            / "collector",
                                            mapping=mapping,
                                            number=game["number"],
                                            id=game["id"],
                                        )
                                    )
                                except ValueError:
                                    pass
                                patch_snapshot(snap, match_dir / "results.json", names)
                        except Stop as error:
                            kalshi = False
                            log("kalshi_stopped", reason=str(error))
                        except ValueError as error:
                            log("settle_failed", game=game["id"], reason=str(error))
                for g in games.values():
                    for event in events or []:
                        if event["id"] == g.mapping["match_id"]:
                            g.mapping["score"] = mapping_score(event)
                    if g.forge is None and args.forge:
                        g.forge = forge_for(args, g.mapping, g.start_time)
                waiting_due = [
                    p
                    for p in last_pending
                    if p["match"]["id"]
                    not in {g.mapping["match_id"] for g in games.values()}
                    and not waiting_tickers.get(p["match"]["id"])
                    and cycle - waiting_discovered.get(p["match"]["id"], -float("inf"))
                    >= 300
                ]
                if kalshi and (
                    waiting_due
                    or any(
                        g.ticker is None or g.series_ticker is None
                        for g in games.values()
                    )
                    or pre.want_tickers()
                ):
                    try:
                        markets = []
                        for series in (SERIES, MATCH_SERIES):
                            _, payload = fetch_json(
                                f"{KALSHI}/markets?series_ticker={series}&status=open&limit=1000",
                                args.root / "kalshi" / f"{stamp}_{series}",
                            )
                            markets += (payload or {}).get("markets", [])
                        pre.match(markets)
                        for page in waiting_due:
                            mid = page["match"]["id"]
                            waiting_discovered[mid] = cycle
                            waiting_tickers[mid] = contract(
                                markets,
                                waiting_mapping(page),
                                None,
                                page["match"]["start"],
                            )
                            if waiting_tickers[mid]:
                                log(
                                    "kalshi_series_waiting",
                                    match=mid,
                                    ticker=waiting_tickers[mid],
                                )
                        for g in games.values():
                            if not g.start_time:
                                continue
                            if g.ticker is None:
                                g.ticker = contract(
                                    markets, g.mapping, g.number, g.start_time
                                )
                                if g.ticker:
                                    g.save_tickers()
                                    log("kalshi_contract", game=g.id, ticker=g.ticker)
                            if g.series_ticker is None:
                                g.series_ticker = contract(
                                    markets, g.mapping, None, g.start_time
                                )
                                if g.series_ticker:
                                    g.save_tickers()
                                    log(
                                        "kalshi_series",
                                        game=g.id,
                                        ticker=g.series_ticker,
                                    )
                        if signals:
                            for g in games.values():
                                signals.discover(g, markets)
                    except Stop as error:
                        kalshi = False
                        log("kalshi_stopped", reason=str(error))
                    except ValueError as error:
                        log("kalshi_discovery_failed", reason=str(error))
            if kalshi:
                try:
                    pre.poll()
                except Stop as error:
                    kalshi = False
                    log("kalshi_stopped", reason=str(error))
                except (ValueError, OSError) as error:
                    log("pre_quote_failed", reason=str(error))
            for gid, game in list(games.items()):
                if kalshi:
                    try:
                        # The map market stops with its map; the series one continues.
                        if game.ticker and game.state != "finished":
                            game.poll_quote(game.ticker, game.dir / "quotes.jsonl")
                        if game.series_ticker:
                            game.poll_quote(game.series_ticker, game.series_quotes_path)
                    except Stop as error:
                        kalshi = False
                        log("kalshi_stopped", reason=str(error))
                    except (ValueError, OSError) as error:
                        log("quote_failed", game=gid, reason=str(error))
                feed_due = feed_slot(time.time(), args.interval) != feed_polled.get(gid)
                if feed_due and (kalshi or game.number in game.results()):
                    try:
                        game.settle()
                    except Stop as error:
                        kalshi = False
                        log("kalshi_stopped", reason=str(error))
                    except (ValueError, OSError) as error:
                        log("settle_failed", game=gid, reason=str(error))
                try:
                    path = args.page_out / f"{game.mapping['match_id']}.json"
                    if feed_due or not path.exists():
                        feed_polled[gid] = feed_slot(time.time(), args.interval)
                        if game.state != "finished":
                            game.poll()
                        # Stamp after polling; receipts must not be in the future.
                        page = game.page(catalog, utc_now())
                    else:
                        page = game.add_quotes(json.loads(path.read_text()))
                        page["published_at"] = utc_now()
                    write_atomic(
                        args.page_out / f"{game.mapping['match_id']}.json", page
                    )
                    if game.state == "finished" and feed_due:
                        game.write_snapshot(catalog)
                    if signals and kalshi and game.state == "live":
                        try:
                            signals.poll(game, page, fresh_model=feed_due)
                        except Stop as error:
                            kalshi = False
                            log("kalshi_stopped", reason=str(error))
                        except (ValueError, OSError, subprocess.SubprocessError):
                            log("live_signal_unavailable", game=gid)
                except (
                    ValueError,
                    KeyError,
                    TypeError,
                    OSError,
                    sqlite3.Error,
                ) as error:
                    failed[gid] = str(error)
                    failed_at[gid] = time.monotonic()
                    games.pop(gid).close()
                    log("game_failed", game=gid, reason=str(error))
            update_observed(args.page_out, games.values(), utc_now())
            at = utc_now()
            tracked = {g.mapping["match_id"] for g in games.values()}
            pending = waiting_pages(
                scheduled + (events or []),
                catalog,
                aliases,
                at,
                tracked,
                set(failed) | skip,
            )
            pending = without_recorded(pending, args.page_out, recorded_cache)
            current_waiting = {p["match"]["id"] for p in pending}
            for mid in waiting_ids - current_waiting - tracked:
                (args.page_out / f"{mid}.json").unlink(missing_ok=True)
            for page in pending:
                mid = page["match"]["id"]
                ticker = waiting_tickers.get(mid) if kalshi else None
                try:
                    if (
                        ticker
                        and cycle - waiting_polled.get(mid, -float("inf"))
                        >= args.interval
                    ):
                        waiting_polled[mid] = cycle
                        waiting_seq += 1
                        out = (
                            args.root
                            / mid
                            / "waiting_book"
                            / f"{waiting_seq}_{datetime.now(UTC):%H%M%S}"
                        )
                        poll_waiting_quote(args.root, mid, ticker, out)
                except Stop as error:
                    kalshi = False
                    ticker = None
                    log("kalshi_stopped", reason=str(error))
                except (ValueError, OSError) as error:
                    log("waiting_quote_failed", match=mid, reason=str(error))
                try:
                    fill_waiting(page, args, ticker)
                except (ValueError, OSError) as error:
                    log("waiting_quote_failed", match=mid, reason=str(error))
                write_atomic(args.page_out / f"{mid}.json", page)
            for cache in (waiting_tickers, waiting_discovered, waiting_polled):
                for mid in set(cache) - current_waiting - tracked:
                    del cache[mid]
            last_pending = pending
            waiting_ids = current_waiting
            count, changed = write_index(args.page_out, utc_now())
            if args.s3 and (games or changed or lifecycle_changed):
                publish_s3(args.page_out, args.s3)
            log("cycle", tracked=len(games), published=count)
            if RESTART_FLAG.exists() and not any(
                game.state == "live" for game in games.values()
            ):
                log("restart_for_update")
                RESTART_FLAG.unlink()
                return RESTART_FOR_UPDATE
            # Activity is a map not yet over; getLive can list a decided match for hours.
            if pending or any(g.state != "finished" for g in games.values()):
                last_active = time.monotonic()
            elif (
                args.idle_exit and time.monotonic() - last_active > args.idle_exit * 60
            ):
                log("idle", minutes=args.idle_exit)
                return IDLE
            # Every 2 s while a map is tracked or in its draft (its book is read).
            interval = (
                QUOTE_INTERVAL if (games or pre.maps) and kalshi else args.interval
            )
            wait = interval - (time.monotonic() - cycle)
            if games:
                # Wake just after the feed's next window opens (see feed_slot).
                wait = min(wait, next_feed_slot(time.time(), args.interval))
            time.sleep(max(0, wait))
    except Stop as error:
        log("stopped", reason=str(error))
        return REFUSED
    finally:
        for game in games.values():
            game.close()
        write_atomic(
            args.page_out / "index.json",
            {
                "schema": 1,
                "published_at": utc_now(),
                "matches": [],
                "note": "Live service stopped.",
            },
        )
        if args.s3:
            publish_s3(args.page_out, args.s3)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def main():
    global LOG_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, default=ROOT / "data" / "live", help="Evidence directory"
    )
    parser.add_argument(
        "--page-out",
        type=Path,
        default=ROOT / "output" / "live",
        help="The site's live/ directory",
    )
    parser.add_argument(
        "--team-catalog", type=Path, default=ROOT / "output" / "teams.json"
    )
    parser.add_argument(
        "--aliases",
        type=Path,
        default=HERE / "team_aliases.json",
        help="Riot team ID -> Prometheus team name, for names that don't match",
    )
    parser.add_argument("--model", type=Path, default=MODEL_PATH)
    parser.add_argument(
        "--inputs",
        type=Path,
        default=ROOT / "data" / "live_inputs.json",
        help="Ratings from scripts/export_live_inputs.py; else read from --db",
    )
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--no-model", action="store_true", help="Stats only")
    parser.add_argument("--no-forge", action="store_true", help="No FORGE calls")
    parser.add_argument(
        "--s3", help="Also mirror the live files here, e.g. s3://<bucket>/current/live"
    )
    parser.add_argument(
        "--idle-exit",
        type=int,
        metavar="MINUTES",
        help="Exit (status 4) after this long with no live game",
    )
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--discover-interval", type=int, default=60)
    parser.add_argument("--skip-game", action="append", default=[])
    parser.add_argument(
        "--adopt",
        action="append",
        default=[],
        help="GAME_ID:COLLECTOR_DIR:SESSION — continue another run's collector",
    )
    parser.add_argument(
        "--live-map-signals",
        action="store_true",
        help="Record private 30s live-map candidates",
    )
    parser.add_argument(
        "--signal-bucket", help="Private signal bucket; requires --signal-queue"
    )
    parser.add_argument(
        "--signal-queue", help="Private SQS URL; requires --signal-bucket"
    )
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    LOG_FILE = args.root / "worker.jsonl"
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not args.fetch:
        parser.error("network requires --fetch")
    if args.interval not in (10, 20, 30) or args.discover_interval < 30:
        parser.error("interval 10, 20 or 30 s; discovery at least every 30 s")
    if bool(args.signal_bucket) != bool(args.signal_queue) or (
        args.signal_bucket and not args.live_map_signals
    ):
        parser.error(
            "Signal delivery requires --live-map-signals, --signal-bucket and --signal-queue together"
        )
    if args.no_model:
        args.model = None
    args.ratings = Ratings(args.inputs, args.db)
    args.forge = not args.no_forge
    args.page_out.mkdir(parents=True, exist_ok=True)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
