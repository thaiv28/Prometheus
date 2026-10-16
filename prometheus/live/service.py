"""Always-on live publisher: every lolesports game in progress onto the live pages.

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
import shutil
import sqlite3
import subprocess
import sys
import tarfile
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode

from .. import DB_PATH
from .collector import Collector
from .feed import timestamp
from .kalshi import (
    KALSHI,
    MARKET_URL,
    MATCH_SERIES,
    MATCH_URL,
    SERIES,
    contract,
    quote,
)
from .page import build_page, summary, write_atomic
from .requests import SITE_API_HOST, probe, utc_now
from .series import series_chance
from .start import find_start
from .timeline import latest_elo

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
QUERY_LAG = 30  # the feed rejects windows ending under 20 s ago (HTTP 400)
FRESH = 60  # seconds a match file stays in the index without a new write
# Exit status after Riot refused access or rate-limited us: the systemd unit
# doesn't restart on it (no retrying into a block).
REFUSED = 3


class Stop(Exception):
    """Access refused or rate limited: stop all requests."""


def log(event, **fields):
    print(json.dumps(dict(at=utc_now(), event=event, **fields)), flush=True)


def fetch_json(url, out):
    """One request; [] payload on 204; Stop on 403/429; ValueError otherwise."""
    record = probe(url, out)[0]
    status = record.get("http_status")
    if status in {401, 403, 429}:
        raise Stop(f"HTTP {status} from {url}")
    if status == 204:
        return record, None
    if status != 200 or record.get("parse_error"):
        raise ValueError(f"HTTP {status} {record.get('error', '')}".strip())
    return record, json.loads((out / record["raw_file"]).read_bytes())


def resolve_team(team, catalog, aliases):
    names = {t["n"] for t in catalog}
    if team["id"] in aliases:
        return aliases[team["id"]]
    if team.get("name") in names:
        return team["name"]
    slugs = [t["n"] for t in catalog if t.get("s") == team.get("slug")]
    return slugs[0] if len(slugs) == 1 else None


def live_events(payload):
    for event in payload["data"]["schedule"].get("events") or []:
        match = event.get("match")
        if event.get("state") == "inProgress" and match and len(match["teams"]) == 2:
            yield event


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


class Forge:
    """FORGE's pre-match calls, as `prometheus predict` makes them.

    Ratings come from every game in Prometheus's database (`current_ratings`),
    reloaded every `REFRESH` seconds so a rebuilt database reaches live calls.
    """

    REFRESH = 6 * 3600

    def __init__(self):
        self.ratings, self.loaded = None, 0.0

    def call(self, mapping, start_time):
        from ..form import load_states
        from ..schedule import (
            current_ratings,
            game_probability,
            series_probability,
            series_rho,
        )

        if self.ratings is None or time.monotonic() - self.loaded > self.REFRESH:
            self.ratings, self.loaded = current_ratings(load_states()), time.monotonic()
        a, b = (self.ratings.loc[t["name"]] for t in mapping["teams"])
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
            "ratings_through": [str(a["latest_date"]), str(b["latest_date"])],
            "computed_at": utc_now(),
        }


def forge_for(args, mapping, start_time):
    """FORGE's call for mapping team 0, cached per match; None on failure."""
    path = args.root / mapping["match_id"] / "forge.json"
    if path.exists():
        return json.loads(path.read_text())
    try:
        forge = args.forge.call(mapping, start_time)
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
        "max-age=2",
    ]
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=60)
    except (subprocess.SubprocessError, OSError) as error:
        log("s3_failed", reason=str(error)[:300])
        return
    if done.returncode:
        log("s3_failed", reason=done.stderr.strip()[:300])


class Game:
    def __init__(self, root, mapping, game, model, elo_db, start_time=None, adopt=None):
        self.mapping, self.id = mapping, game["id"]
        self.number, self.start_time = game["number"], start_time
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
        if model:
            try:
                now = datetime.now(UTC)
                ratings = [latest_elo(elo_db, t["name"], now) for t in mapping["teams"]]
                self.timeline = (model, ratings)
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
        if self.state != "finished" or not self.ticker or self.number in self.results():
            return
        settle_map(
            self.ticker, self.number, self.results_path, self.request_dir("settle")
        )

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
        query = now.replace(microsecond=0) - timedelta(seconds=QUERY_LAG)
        query -= timedelta(seconds=query.second % 10)
        out, record, payload = self.window(query)
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
        _, book = fetch_json(f"{KALSHI}/markets/{ticker}/orderbook", out)
        q = quote(book or {}, utc_now())
        if q:
            with path.open("a") as f:
                f.write(json.dumps(dict(q, ticker=ticker)) + "\n")

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
        timeline = None
        if self.timeline:
            timeline = (*self.timeline, (self.start or {}).get("source_at"))
        page = build_page(
            self.collector_dir, self.mapping, catalog, at, timeline=timeline
        )
        quotes = self.quotes(self.dir / "quotes.jsonl")
        game = page.get("game")
        score = self.score()
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
            game["pregame"] = dict(
                game["pregame"] or {}, p=self.forge["p_game"], by="FORGE"
            )
            calls = game["calls"]
            live = calls[-1]["p"] if calls and page["status"] == "live" else None
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
        if record:
            self.journal(page)
        url = MARKET_URL
        if not self.ticker and self.deciding(score):
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
        need = (self.mapping.get("best_of") or 1) // 2 + 1
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

    def journal(self, page):
        """Append each newly published call (map and series) as it was made."""
        game, series = page.get("game") or {}, page["match"].get("series") or {}
        calls = game.get("calls") or []
        row = {
            "map": self.number,
            "minute": calls[-1]["minute"] if calls else None,
            "p_map": calls[-1]["p"] if calls else None,
            "p_series": series.get("ours"),
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
                and page.get("game")
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
    write_atomic(
        page_dir / "index.json",
        {"schema": 1, "published_at": at, "matches": matches, "note": note},
    )
    return len(matches)


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
    kalshi = True
    try:
        while True:
            cycle = time.monotonic()
            if cycle - last_discovery >= args.discover_interval:
                last_discovery = cycle
                stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
                try:
                    _, payload = fetch_json(GETLIVE, args.root / "discovery" / stamp)
                except ValueError as error:
                    log("discovery_failed", reason=str(error))
                    payload = None
                events = list(live_events(payload)) if payload else None
                if events is not None:
                    live_ids = {e["id"] for e in events}
                    for gid in [
                        k
                        for k, g in games.items()
                        if g.mapping["match_id"] not in live_ids
                    ]:
                        games.pop(gid).close()
                        log("untracked", game=gid, reason="match no longer live")
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
                        try:
                            mapping = mapping_for(event, catalog, aliases)
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
                                args.elo_db,
                                event.get("startTime"),
                                adopt.get(gid),
                            )
                            games[gid].page_out = args.page_out
                            log(
                                "tracking",
                                game=gid,
                                match=event["id"],
                                teams=[t["name"] for t in mapping["teams"]],
                                map=game["number"],
                            )
                        except (ValueError, KeyError, sqlite3.Error) as error:
                            failed[gid] = str(error)
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
                                args.elo_db,
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
                        if game["id"] in games or not tickers.exists() or not kalshi:
                            continue
                        ticker = json.loads(tickers.read_text()).get("map")
                        try:
                            stamp_dir = (
                                match_dir / "settlements" / f"{stamp}_{game['number']}"
                            )
                            if ticker and settle_map(
                                ticker,
                                game["number"],
                                match_dir / "results.json",
                                stamp_dir,
                            ):
                                try:
                                    mapping = mapping_for(event, catalog, aliases)
                                    names = [t["name"] for t in mapping["teams"]]
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
                if kalshi and any(
                    g.ticker is None or g.series_ticker is None for g in games.values()
                ):
                    try:
                        markets = []
                        for series in (SERIES, MATCH_SERIES):
                            _, payload = fetch_json(
                                f"{KALSHI}/markets?series_ticker={series}&status=open&limit=1000",
                                args.root / "kalshi" / f"{stamp}_{series}",
                            )
                            markets += (payload or {}).get("markets", [])
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
                    except Stop as error:
                        kalshi = False
                        log("kalshi_stopped", reason=str(error))
                    except ValueError as error:
                        log("kalshi_discovery_failed", reason=str(error))
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
                if kalshi:
                    try:
                        game.settle()
                    except Stop as error:
                        kalshi = False
                        log("kalshi_stopped", reason=str(error))
                    except (ValueError, OSError) as error:
                        log("settle_failed", game=gid, reason=str(error))
                try:
                    if game.state != "finished":
                        game.poll()
                    # Stamp after polling so the newest receipt is not in the future.
                    page = game.page(catalog, utc_now())
                    write_atomic(
                        args.page_out / f"{game.mapping['match_id']}.json", page
                    )
                    if game.state == "finished":
                        game.write_snapshot(catalog)
                except (
                    ValueError,
                    KeyError,
                    TypeError,
                    OSError,
                    sqlite3.Error,
                ) as error:
                    failed[gid] = str(error)
                    games.pop(gid).close()
                    log("game_failed", game=gid, reason=str(error))
            count = write_index(args.page_out, utc_now())
            if args.s3:
                publish_s3(args.page_out, args.s3)
            log("cycle", tracked=len(games), published=count)
            time.sleep(max(0, args.interval - (time.monotonic() - cycle)))
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
    parser.add_argument("--model", type=Path, default=HERE / "time_model_v1.json")
    parser.add_argument("--elo-db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--no-model", action="store_true", help="Stats only")
    parser.add_argument("--no-forge", action="store_true", help="No FORGE calls")
    parser.add_argument(
        "--s3", help="Also mirror the live files here, e.g. s3://<bucket>/current/live"
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
    parser.add_argument("--fetch", action="store_true")
    args = parser.parse_args()
    if not args.fetch:
        parser.error("network requires --fetch")
    if not 10 <= args.interval <= 30 or args.discover_interval < 30:
        parser.error("interval 10..30 s; discovery at least every 30 s")
    if args.no_model:
        args.model = None
    args.forge = None if args.no_forge else Forge()
    args.page_out.mkdir(parents=True, exist_ok=True)
    sys.exit(run(args))


if __name__ == "__main__":
    main()
