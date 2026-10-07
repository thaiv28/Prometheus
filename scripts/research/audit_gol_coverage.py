"""Bounded, reproducible tournament-stratified gol.gg coverage audit (offline default)."""

import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace
import urllib.error
import urllib.parse

import pandas as pd

import pilot_gol as pilot

SEED = 42
PER_TOURNAMENT = 3
STRATA = [
    {"league": league, "year": year, "tournament": name}
    for year in range(2022, 2026)
    for league, name in (
        ("LCK", f"LCK Spring {year}" if year < 2025 else "LCK 2025 Rounds 1-2"),
        ("LPL", f"LPL Spring {year}" if year < 2025 else "LPL 2025 Split 2"),
        (
            "LEC",
            (
                f"LEC Spring {year}"
                if year == 2022
                else (
                    f"LEC Spring Season {year}"
                    if year < 2025
                    else "LEC 2025 Spring Season"
                )
            ),
        ),
        ("LCS", f"LCS Spring {year}" if year < 2025 else "LTA North 2025 Split 2"),
        (
            "Worlds",
            (
                "World Championship 2022"
                if year == 2022
                else (
                    f"Worlds Main Event {year}"
                    if year < 2025
                    else "Worlds 2025 Main Event"
                )
            ),
        ),
    )
]


def listing(html, tournament):
    """Extract dated series entries, never infer maps by consecutive numeric IDs."""
    root = pilot.Document(html).root
    tables = [
        t
        for t in root.all("table", css="table_list")
        if f"{tournament} results" in t.value()
    ]
    if len(tables) != 1:
        raise ValueError("Missing/ambiguous tournament results table")
    entries = {}
    for row in tables[0].all("tr"):
        links = [
            (
                a,
                re.search(
                    r"/game/stats/(\d+)/page-(summary|game)/", a.attrs.get("href", "")
                ),
            )
            for a in row.all("a")
        ]
        links = [(a, m) for a, m in links if m]
        if not links:
            continue
        dates = re.findall(r"\b\d{4}-\d{2}-\d{2}\b", row.value())
        if len(links) != 1 or len(dates) != 1:
            raise ValueError("Ambiguous tournament row")
        dt.date.fromisoformat(dates[0])
        a, m = links[0]
        game = int(m.group(1))
        entry = {
            "gol_id": game,
            "listing_date": dates[0],
            "listing_pair": a.value(),
            "listing_route": m.group(2),
        }
        if game in entries and entries[game] != entry:
            raise ValueError("Conflicting duplicate series entry")
        entries[game] = entry
    if not entries:
        raise ValueError("Empty tournament listing; never count as zero coverage")
    return list(entries.values())


def select(entries, tournament, count=PER_TOURNAMENT):
    """Uniform hash ranking, independent of input order and page availability."""

    def rank(row):
        value = f"{SEED}|{tournament}|{row['gol_id']}".encode()
        return hashlib.sha256(value).hexdigest(), row["gol_id"]

    return sorted(entries, key=rank)[:count]


def summarize(inventory, games, checkpoints):
    rows = []
    for item in inventory:
        tournament = item["tournament"]
        group = games[games.tournament.eq(tournament)] if not games.empty else games
        snaps = (
            checkpoints[checkpoints.gol_id.isin(group.gol_id)]
            if not checkpoints.empty
            else checkpoints
        )
        valid = group.get("timeline_valid", pd.Series(False, index=group.index)).eq(
            True
        )
        matched = (
            group.get("match_status", pd.Series("", index=group.index))
            .fillna("")
            .str.startswith("matched")
        )
        row = {
            **item,
            "sampled": len(group),
            "valid_timelines": int(valid.sum()),
            "oe_matched": int(matched.sum()),
            "gold_graphs": int(
                group.get("gold_status", pd.Series("", index=group.index))
                .eq("ok")
                .sum()
            ),
        }
        for minute in pilot.MINUTES:
            eligible = int(
                pd.to_numeric(
                    group.get("gamelength", pd.Series(float("nan"), index=group.index)),
                    errors="coerce",
                )
                .gt(minute * 60)
                .sum()
            )
            subset = snaps[snaps.minute.eq(minute)] if not snaps.empty else snaps
            row[f"known_eligible_{minute}m"] = eligible
            row[f"ready_{minute}m"] = (
                int(subset.training_ready.eq(True).sum()) if not subset.empty else 0
            )
        rows.append(row)
    return pd.DataFrame(rows)


def markdown(frame):
    if frame.empty:
        return "(No rows.)"
    lines = [
        "| " + " | ".join(frame.columns) + " |",
        "| " + " | ".join(["---"] * len(frame.columns)) + " |",
    ]
    for row in frame.fillna("").itertuples(index=False, name=None):
        lines.append(
            "| "
            + " | ".join(str(v).replace("|", "\\|").replace("\n", " ") for v in row)
            + " |"
        )
    return "\n".join(lines)


def report(coverage, games, frames, manifest):
    cols = [
        "league",
        "year",
        "listing_status",
        "listed_series",
        "sampled",
        "valid_timelines",
        "oe_matched",
        "gold_graphs",
        "ready_10m",
        "ready_15m",
        "ready_20m",
    ]
    failures = (
        games[
            ~games.status.eq("valid")
            | ~games.match_status.fillna("").str.startswith("matched")
        ]
        if "match_status" in games
        else games
    )
    failcols = [
        c
        for c in ("league", "year", "gol_id", "status", "match_status", "error")
        if c in failures
    ]
    totals = frames["validation"]
    gold = frames["gold_comparison"]
    checks = (
        f"{len(totals)} final objective-total checks; {len(gold)} OE gold comparisons"
    )
    if not gold.empty:
        checks += f"; {int(gold.difference.eq(0).sum())} exact gold agreements"
    league_totals = (
        coverage.groupby("league", sort=False)[
            ["sampled", "valid_timelines", "oe_matched", "gold_graphs"]
        ]
        .sum()
        .reset_index()
    )
    snapshots = frames["checkpoints"]
    excluded = (
        snapshots[~snapshots.training_ready.eq(True)]
        if not snapshots.empty
        else snapshots
    )
    excluded_columns = [
        c
        for c in (
            "gol_id",
            "minute",
            "matched",
            "gold_verified",
            "objective_boundary_events",
        )
        if c in excluded
    ]
    return f"""# gol.gg historical coverage audit

{len(games)} sampled series entries across {len(coverage)} fixed tournament strata (2022–2025). {int(coverage.valid_timelines.sum())} validated timelines, {int(coverage.oe_matched.sum())} OE matches, {len(frames['training_candidates'])} training-ready 10/15/20-minute rows. {checks}.

## League summary

{markdown(league_totals)}

LPL missing histories remain a separate acquisition gap. For any usable timeline without an OE match, inspect team/player aliases and roster identity before relaxing the join. Verified rows can still be excluded at exact objective boundaries; the table below makes those exclusions explicit.

## Sample and denominators

One explicitly named event per league/year: domestic spring (LCK rounds 1–2, LPL split 2 and LTA North split 2 in 2025) and Worlds main event. Public match-list pages enumerate series, not all maps. Select three series entries per event by SHA-256 ranking with seed 42, then inspect the linked first map; a single-game entry is its sole map. This selection is fixed before fetching timelines, independent of wins or data availability. Failed listings and sampled games remain in the inventory; no replacements. Rates describe sampled first maps in these events, not all maps, splits, leagues, or years. Three per event is a screening sample with substantial uncertainty; no population-wide percentage is claimed.

`listed_series` counts unique dated entries on each selected tournament listing. `sampled` includes unavailable/rejected games. `known_eligible` in coverage.csv counts sampled games with readable duration strictly beyond the checkpoint; unreadable duration remains unknown, not eligible or ineligible. `ready` requires valid objective totals, an unambiguous OE match, exact gold agreement for both sides, and no second-precision objective boundary event. End-game counts are validation targets only. The original purposive pilot is excluded from this audit's sampling denominator.

## Tournament coverage

{markdown(coverage[cols])}

## Failures and unmatched games

{markdown(failures[failcols])}

## Checkpoint exclusions

{markdown(excluded[excluded_columns])}

All sampled game identities, validation results and source hashes are available under gitignored data/gol_coverage/. Detail report: data/gol_coverage/detail_report.md. A valid timeline with a missing graph or failed gold check can still have zero training-ready rows. Missing timelines are never interpreted as zero objectives. Soul and remaining buff duration are not reconstructed. Totals validate parser consistency, not independently every timestamp.

## Reproduction and next decision

Run `.venv/bin/python scripts/research/audit_gol_coverage.py` to reprocess cached listings/pages without network. Add `--fetch` to fetch only missing public pages (20 listings, at most 60 games / 120 game pages, plus robots.txt; serial requests at least one second apart). Stop on 401/403/429; no retries or bypass. Preserve manifest/sample JSON, raw HTML and hashes. No DB writes or model fitting.

Next expand reliable event strata to additional splits and all map numbers, and investigate explicit parser/matching failures before collecting a training corpus. Do not drop poorly covered regions silently. Use chronological same-game gold+Elo versus gold+Elo+objectives comparisons only after acquisition passes a separate dataset-quality gate. 2026 has already been viewed and is excluded here.

HTTP requests this run: {manifest['network_requests_this_run']}. Selection seed: {SEED}.
"""


def run(args):
    cache = pilot.Cache(args.artifacts / "html", fetch=args.fetch)
    inventory, selected, sources = [], [], []
    for stratum in STRATA:
        name = stratum["tournament"]
        url = (
            "https://gol.gg/tournament/tournament-matchlist/"
            + urllib.parse.quote(name, safe="")
            + "/"
        )
        filename = "listing-" + hashlib.sha256(name.encode()).hexdigest()[:12] + ".html"
        record = {
            **stratum,
            "listing_url": url,
            "listing_status": "pending",
            "listed_series": None,
        }
        print(f"Listing {name}", flush=True)
        try:
            body = cache.read(filename, url)
            sources.append(
                {
                    "url": url,
                    "cache_file": filename,
                    "sha256": hashlib.sha256(body.encode()).hexdigest(),
                }
            )
            entries = listing(body, name)
            record.update(listing_status="ok", listed_series=len(entries))
            for entry in select(entries, name):
                selected.append({**stratum, **entry, "sample": name})
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 429):
                raise RuntimeError(
                    f"Access/rate-limit response {error.code}; stopped, no bypass"
                ) from error
            record.update(listing_status="unavailable", listing_error=str(error))
        except (ValueError, FileNotFoundError, urllib.error.URLError) as error:
            record.update(listing_status="unavailable", listing_error=str(error))
        inventory.append(record)
    if len({s["gol_id"] for s in selected}) != len(selected):
        raise ValueError("Overlapping tournament samples; audit stopped")
    sample_path = args.artifacts / "samples.json"
    sample_path.write_text(json.dumps(selected, indent=2) + "\n")
    frames, detail = pilot.run(
        SimpleNamespace(
            artifacts=args.artifacts,
            fetch=args.fetch,
            samples=sample_path,
            out=args.artifacts / "detail_report.md",
        ),
        sample_limit=60,
        cache=cache,
    )
    coverage = summarize(inventory, frames["games"], frames["checkpoints"])
    coverage.to_csv(args.artifacts / "coverage.csv", index=False)
    manifest = {
        **detail,
        "purpose": "fixed tournament-stratified first-map coverage screening; no model training",
        "selection_seed": SEED,
        "per_tournament": PER_TOURNAMENT,
        "strata": inventory,
        "listing_sources": sources,
        "network_requests_this_run": cache.requests,
        "audit_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(coverage, frames["games"], frames, manifest))
    print(
        f"Wrote {args.out}; {len(selected)} sampled entries, {manifest['network_requests_this_run']} requests",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--artifacts", type=Path, default=Path("data/gol_coverage"))
    parser.add_argument("--out", type=Path, default=Path("docs/research/gol_coverage_report.md"))
    run(parser.parse_args())
