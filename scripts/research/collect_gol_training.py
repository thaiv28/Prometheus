"""Resumable public gol.gg dataset acquisition; excludes LPL and viewed 2026."""

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import shutil
import urllib.error
import urllib.parse
from collections import deque
from pathlib import Path
from types import SimpleNamespace

import audit_gol_coverage as audit
import pandas as pd
import pilot_gol as pilot


class CollectionStopped(Exception):
    pass


class BudgetCache(pilot.Cache):
    def __init__(self, directory, fetch, limit, delay):
        self.limit = limit
        super().__init__(directory, fetch=fetch, delay=delay)

    def read(self, name, url, robots=False):
        if (
            not (self.directory / name).exists()
            and self.fetch
            and self.requests >= self.limit
        ):
            raise CollectionStopped("request_budget_reached")
        try:
            return super().read(name, url, robots=robots)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 429):
                raise CollectionStopped(
                    f"http_{error.code}; Retry-After={error.headers.get('Retry-After', 'unspecified')}"
                ) from error
            raise


def file_hash(path):
    with Path(path).open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def atomic_json(path, value):
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps(value, indent=2) + "\n")
    temp.replace(path)


def maps(html, first_id):
    """Read explicit series navigation, never synthesize consecutive IDs."""
    pilot.metadata(html, first_id)
    result = {}
    for a in pilot.Document(html).root.all("a"):
        label = re.fullmatch(r"Game\s+(\d+)", a.value())
        link = re.search(r"/game/stats/(\d+)/page-game/", a.attrs.get("href", ""))
        if label and link:
            number, game = int(label[1]), int(link[1])
            if number in result and result[number] != game:
                raise ValueError("Conflicting map navigation")
            result[number] = game
    if (
        not result
        or result.get(1) != first_id
        or len(set(result.values())) != len(result)
    ):
        raise ValueError("Missing/invalid explicit map navigation")
    if sorted(result) != list(range(1, len(result) + 1)):
        raise ValueError("Incomplete map numbering")
    return [
        {"gol_id": game, "expected_map": number}
        for number, game in sorted(result.items())
    ]


def interleave(groups):
    groups = [deque(g) for g in groups]
    while any(groups):
        for group in groups:
            if group:
                yield group.popleft()


def training_frame(candidates):
    if candidates.empty:
        return candidates
    meta = pd.read_sql(
        "SELECT m.gameid, m.side, m.date, m.league, m.teamname, m.result, e.pre_match_elo FROM matches m JOIN game_length_elo e ON e.gameid=m.gameid AND e.teamid=m.teamid",
        pilot.get_engine(),
    )
    blue, red = meta[meta.side.eq("Blue")].copy(), meta[meta.side.eq("Red")].copy()
    blue = blue.rename(
        columns={
            "gameid": "oe_gameid",
            "result": "blue_won",
            "teamname": "blue_team",
            "pre_match_elo": "blue_elo",
        }
    ).drop(columns="side")
    red = red.rename(
        columns={
            "gameid": "oe_gameid",
            "teamname": "red_team",
            "pre_match_elo": "red_elo",
        }
    )[["oe_gameid", "red_team", "red_elo"]]
    result = candidates.merge(
        blue, on="oe_gameid", how="left", validate="many_to_one"
    ).merge(red, on="oe_gameid", how="left", validate="many_to_one")
    result["date"] = pd.to_datetime(result.date, utc=True)
    result["year"] = result.date.dt.year
    result = result[
        result.year.between(2022, 2025)
        & result.blue_elo.map(math.isfinite)
        & result.red_elo.map(math.isfinite)
    ].copy()
    result["gold_gap"] = result.blue_gold - result.red_gold
    result["elo_gap"] = result.blue_elo - result.red_elo
    for kind in pilot.OBJECTIVES:
        result[f"{kind}_gap"] = result[f"blue_{kind}"] - result[f"red_{kind}"]
    if result.duplicated(["oe_gameid", "minute"]).any():
        raise ValueError("Duplicate OE game/checkpoint in training dataset")
    return result.sort_values(["date", "oe_gameid", "minute"])


def export(args, samples, progress):
    atomic_json(args.artifacts / "samples.json", samples)
    frames, manifest = pilot.run(
        SimpleNamespace(
            artifacts=args.artifacts,
            fetch=False,
            samples=args.artifacts / "samples.json",
            out=args.artifacts / "detail_report.md",
        ),
        sample_limit=len(samples),
    )
    # Check the map identity against the series link before allowing training rows.
    identities = frames["games"]
    wrong = set()
    if not identities.empty:
        for row in identities.to_dict("records"):
            if row.get("map_number") != row.get("expected_map"):
                wrong.add(row["gol_id"])
    candidates = frames["training_candidates"]
    if not candidates.empty:
        candidates = candidates[~candidates.gol_id.isin(wrong)]
    dataset = training_frame(candidates)
    dataset.to_csv(args.artifacts / "training_dataset.csv", index=False)
    progress.update(
        parsed_games=len(samples),
        ready_games=int(dataset.oe_gameid.nunique()) if not dataset.empty else 0,
        training_rows=len(dataset),
        map_identity_failures=sorted(wrong),
    )
    listing_sources = []
    for stratum in [s for s in audit.STRATA if s["league"] != "LPL"]:
        name = stratum["tournament"]
        filename = "listing-" + hashlib.sha256(name.encode()).hexdigest()[:12] + ".html"
        path = args.artifacts / "html" / filename
        if path.exists():
            listing_sources.append(
                {
                    "tournament": name,
                    "cache_file": filename,
                    "sha256": hashlib.sha256(path.read_text().encode()).hexdigest(),
                }
            )
    manifest.update(
        listing_sources=listing_sources,
        purpose="partial historical acquisition dataset; no model training; LPL excluded by user",
        collection=progress,
        collector_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        database_sha256=file_hash("db/prometheus.db"),
        feature_policy="gold + stored chronologically replay-verified pre-match Elo + cumulative past objective counts; blue_won is target; final totals are validation-only",
    )
    atomic_json(args.artifacts / "manifest.json", manifest)
    atomic_json(args.artifacts / "progress.json", progress)
    coverage = (
        identities.groupby(["league", "year", "status"], dropna=False)
        .size()
        .reset_index(name="games")
        if not identities.empty
        else pd.DataFrame()
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        f"""# gol.gg training-data collection

Status: {progress["stop_reason"]}. New HTTP requests this batch: {progress["requests_this_run"]}. {len(samples)} downloaded maps, {progress["ready_games"]} verified games, {len(dataset)} training rows at 10/15/20 minutes. Discovery/download errors recorded: {len(progress["discovery_errors"])}. LPL excluded as requested. 2026 excluded. This is a partial acquisition dataset, not a fitted model or a complete season corpus.

## Download inventory

{audit.markdown(coverage)}

## Dataset and validation

`data/gol_training/training_dataset.csv` contains verified gold snapshots, stored pre-match Elo, strictly past objective counts/gaps and winner labels, with OE/gol.gg IDs, dates, league and map/series provenance in the accompanying games/samples files. Checkpoints must match OE gold exactly and have no objective at the exact second boundary. Final counts validate extraction and are absent from predictor columns. Explicit series links discover every map; IDs are never guessed. Map numbers are checked against those links. Missing data, unknown icons, unmatched rosters and failed totals remain outside the training dataset. Team/player identities and winner/date/league columns are metadata or labels, not proposed numeric predictors.

All raw pages and hashes are retained. Games/events/validation/gold_comparison/checkpoints/training_candidates CSVs and detail_report.md preserve exclusions. Per-event discovery errors and the precise stop reason live in progress.json. Stored Elo was verified against chronological replay in the earlier experiment; source DB hash is recorded. No DB writes, model fitting, or forecast changes.

## Resume

`.venv/bin/python scripts/research/collect_gol_training.py --fetch --max-requests 300 --delay 2` resumes from cached pages. Default is offline. Public requests are serial, at least two seconds apart, with a per-run request budget. Stop on 401/403/429 or a transport/DNS error and preserve progress; honor Retry-After before a later invocation, no automatic retries, concurrency, alternate identity or bypass. Order interleaves the 16 audited non-LPL event strata, so a partial run reaches multiple leagues/years. Additional splits/playoffs/MSI are future acquisition work. The default corpus covers the audit's selected spring/Worlds events and later maps, not every 2022–2025 event.

Before fitting objective models, spot-check timeline timestamps and inspect coverage/exclusions. Use chronological splits and identical game cohorts for gold+Elo versus gold+Elo+objectives; this collection does not establish predictive improvement.
"""
    )


def seed_cache(html):
    for source in (Path("data/gol_coverage/html"), Path("data/gol_pilot/html")):
        for p in source.glob("*"):
            if p.is_file() and not (html / p.name).exists():
                shutil.copyfile(p, html / p.name)


def run(args):
    if args.max_requests < 0 or args.delay < 2:
        raise ValueError("Nonnegative request budget and delay >=2 required")
    html = args.artifacts / "html"
    html.mkdir(parents=True, exist_ok=True)
    seed_cache(html)
    progress = {
        "started_at_utc": dt.datetime.now(dt.UTC).isoformat(),
        "stop_reason": "in_progress",
        "requests_this_run": 0,
        "discovery_errors": [],
        "series_completed": 0,
    }
    sample_path = args.artifacts / "samples.json"
    samples = json.loads(sample_path.read_text()) if sample_path.exists() else []
    seen = {sample["gol_id"] for sample in samples}
    if len(seen) != len(samples):
        raise ValueError("Duplicate IDs in saved sample inventory")
    groups = []
    cache = None
    try:
        cache = BudgetCache(html, args.fetch, args.max_requests, args.delay)
        for stratum in [s for s in audit.STRATA if s["league"] != "LPL"]:
            name = stratum["tournament"]
            filename = (
                "listing-" + hashlib.sha256(name.encode()).hexdigest()[:12] + ".html"
            )
            url = (
                "https://gol.gg/tournament/tournament-matchlist/"
                + urllib.parse.quote(name, safe="")
                + "/"
            )
            try:
                entries = audit.listing(cache.read(filename, url), name)
                # Stable ordering independent of results or whether histories exist.
                groups.append(
                    [
                        {**stratum, **e}
                        for e in audit.select(entries, name, count=len(entries))
                    ]
                )
            except (ValueError, FileNotFoundError, urllib.error.URLError) as error:
                progress["discovery_errors"].append(
                    {"tournament": name, "error": str(error)}
                )
                if isinstance(error, urllib.error.URLError) and not isinstance(
                    error, urllib.error.HTTPError
                ):
                    raise CollectionStopped(f"network_error: {error}") from error
        progress["listed_series"] = sum(len(g) for g in groups)
        for series in interleave(groups):
            first = series["gol_id"]
            try:
                body = cache.read(
                    f"{first}-game.html",
                    f"https://gol.gg/game/stats/{first}/page-game/",
                )
                discovered = maps(body, first)
                for entry in discovered:
                    game = entry["gol_id"]
                    if game in seen:
                        continue
                    for page in ("game", "timeline"):
                        cache.read(
                            f"{game}-{page}.html",
                            f"https://gol.gg/game/stats/{game}/page-{page}/",
                        )
                    samples.append(
                        {
                            **series,
                            **entry,
                            "series_first_id": first,
                            "sample": series["tournament"],
                        }
                    )
                    seen.add(game)
                    progress["requests_this_run"] = cache.requests
                    atomic_json(args.artifacts / "samples.json", samples)
                    atomic_json(args.artifacts / "progress.json", progress)
                    print(
                        f"Downloaded {len(samples)} maps; {cache.requests} new requests; {series['league']} {series['year']} map {entry['expected_map']}",
                        flush=True,
                    )
                progress["series_completed"] += 1
            except (ValueError, FileNotFoundError, urllib.error.URLError) as error:
                progress["discovery_errors"].append(
                    {"series_first_id": first, "error": str(error)}
                )
                if isinstance(error, urllib.error.URLError) and not isinstance(
                    error, urllib.error.HTTPError
                ):
                    raise CollectionStopped(f"network_error: {error}") from error
        progress["stop_reason"] = (
            "selected_events_download_complete"
            if not progress["discovery_errors"]
            else "completed_with_discovery_gaps"
        )
    except CollectionStopped as error:
        progress["stop_reason"] = str(error)
    except (TimeoutError, ConnectionError) as error:
        progress["stop_reason"] = f"network_error: {type(error).__name__}: {error}"
        progress["discovery_errors"].append(
            {"exception_type": type(error).__name__, "error": str(error)}
        )
    except KeyboardInterrupt:
        progress["stop_reason"] = "interrupted"
    finally:
        progress["requests_this_run"] = cache.requests if cache is not None else 0
        export(args, samples, progress)
    print(
        f"Saved {progress['training_rows']} rows from {progress['ready_games']} games; {progress['stop_reason']}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--max-requests", type=int, default=300)
    parser.add_argument("--delay", type=float, default=2)
    parser.add_argument("--artifacts", type=Path, default=Path("data/gol_training"))
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/gol_training_report.md")
    )
    run(parser.parse_args())
