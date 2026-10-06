"""Small cached gol.gg historical objective-timeline pilot, separate from training.

Run offline: .venv/bin/python scripts/pilot_gol.py
Fetch bounded public sample: .venv/bin/python scripts/pilot_gol.py --fetch
"""

import argparse
from collections import Counter
from dataclasses import dataclass, field
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser

import pandas as pd
from sqlalchemy import text

from prometheus.utils import get_engine

SAMPLES = [
    (37756, "LCK 2022"),
    (35845, "LCK 2022; Elder"),
    (46778, "LEC 2023"),
    (53542, "Worlds 2023; Elder"),
    (62081, "LCK 2024"),
    (53778, "LPL 2024"),
    (69531, "LTA North 2025"),
    (64875, "First Stand 2025"),
]
MINUTES = (10, 15, 20)
USER_AGENT = "Prometheus historical-data pilot (small cached research sample)"
OBJECTIVES = ("tower", "dragon", "elder", "baron", "herald", "voidgrubs", "atakhan")
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}


@dataclass
class Node:
    tag: str
    attrs: dict = field(default_factory=dict)
    children: list = field(default_factory=list)
    parent: object = None

    def all(self, tag=None, css=None):
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (
                    css is None or css in child.attrs.get("class", "").split()
                ):
                    yield child
                yield from child.all(tag, css)

    def value(self):
        return " ".join(
            c.value() if isinstance(c, Node) else c for c in self.children
        ).strip()


class Document(HTMLParser):
    """Minimal inert HTML tree: scripts are strings, never executed."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node("document")
        self.current = self.root
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), parent=self.current)
        self.current.children.append(node)
        if tag not in VOID_TAGS:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID_TAGS:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        node = self.current
        while node.parent is not None:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def one(nodes):
    nodes = list(nodes)
    if not nodes:
        raise ValueError("Required page element is absent")
    return nodes[0]


def seconds(clock):
    if not re.fullmatch(r"\d{1,3}:[0-5]\d", clock.strip()):
        raise ValueError(f"Invalid clock {clock!r}")
    minute, second = map(int, clock.split(":"))
    return minute * 60 + second


def image_name(image):
    return image.attrs.get("src", "").split("/")[-1].split("?")[0].lower()


def metadata(html, game_id):
    root = Document(html).root
    title = one(root.all("title")).value()
    if "Page not found" in html or " vs " not in title:
        raise ValueError("Unavailable/non-game page (including soft 404)")
    headings = [h.value() for h in root.all("h1")]
    duration = next(
        (seconds(h) for h in headings if re.fullmatch(r"\d{1,3}:[0-5]\d", h)), None
    )
    date = re.search(
        r"\b(20\d{2}-\d{2}-\d{2})\b", " ".join(n.value() for n in root.all("div"))
    )
    game_number = re.search(r"\bgame (\d+)\b", title, re.I)
    if duration is None or date is None or game_number is None:
        raise ValueError("Missing duration/date/map number")
    info = {
        "gol_id": game_id,
        "date": date.group(1),
        "gamelength": duration,
        "map_number": int(game_number.group(1)),
        "title": title,
    }
    for side in ("blue", "red"):
        header = one(root.all(css=f"{side}-line-header"))
        info[f"{side}_team"] = one(header.all("a")).value()
        info[f"{side}_won"] = int(bool(re.search(r"\bWIN\b", header.value())))
        region = header.parent.parent
        for span in region.all("span", css="score-box"):
            image = one(span.all("img"))
            label = image.attrs.get("alt", "")
            key = {
                "Kills": "kills",
                "Towers": "tower",
                "Dragons": "dragon",
                "Nashor": "baron",
                "Team Gold": "gold",
            }.get(label)
            number = re.search(r"\d+(?:\.\d+)?", span.value())
            if key and number:
                value = float(number.group())
                info[f"{side}_final_{key}"] = (
                    int(value * 1000) if key == "gold" else int(value)
                )
        if any(
            f"{side}_final_{key}" not in info for key in ("tower", "dragon", "baron")
        ):
            raise ValueError("Missing objective summary count")
    if info["blue_team"] == info["red_team"] or info["blue_won"] + info["red_won"] != 1:
        raise ValueError("Invalid side identities/results")
    return root, info


def action_kind(icon, action_text):
    if action_text.strip() == "PLATE":
        return "plate", ""
    fixed = {
        "tower-icon.png": "tower",
        "nashor-icon.png": "baron",
        "herald-icon.png": "herald",
        "rift-herald-icon.png": "herald",
        "voidgrubs-icon.png": "voidgrubs",
        "atakhan-icon.png": "atakhan",
        "atakhan.png": "atakhan",
        "kill-icon.png": "kill",
        "inhibitor-icon.png": "inhibitor",
        "inhib-icon.png": "inhibitor",
        "nexus-icon.png": "nexus",
    }
    if icon in fixed:
        return fixed[icon], ""
    if icon in ("elder-dragon.png", "elder-icon.png"):
        return "elder", "elder"
    if icon == "fire-dragon.png":
        return "dragon", "infernal"
    dragon = re.fullmatch(
        r"(cloud|ocean|mountain|infernal|hextech|chemtech)-dragon\.png", icon
    )
    if dragon:
        return "dragon", dragon.group(1)
    return "unknown", icon or action_text


def parse_timeline(html, game_id):
    root, info = metadata(html, game_id)
    tables = list(root.all("table", css="timeline"))
    if not tables:
        raise ValueError("No event timeline; never interpret missing data as zero")
    events, seen = [], set()
    for index, row in enumerate(tables[0].all("tr")):
        cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
        if not cells:
            continue
        if len(cells) != 7:
            raise ValueError("Unexpected timeline column layout")
        clock = cells[0].value()
        stamp = seconds(clock)
        side_icon = image_name(one(cells[1].all("img")))
        side = {"blueside-icon.png": "blue", "redside-icon.png": "red"}.get(side_icon)
        if not side or stamp > info["gamelength"]:
            raise ValueError("Unknown side or event after game end")
        icons = list(cells[4].all("img"))
        kind, detail = action_kind(
            image_name(icons[0]) if icons else "", cells[4].value()
        )
        identity = re.search(r"ShowPoint\((\d+)\)", row.attrs.get("onmouseover", ""))
        event_id = identity.group(1) if identity else f"row-{index}"
        if event_id in seen:
            raise ValueError("Duplicate source event ID")
        seen.add(event_id)
        events.append(
            {
                "gol_id": game_id,
                "event_id": event_id,
                "seconds": stamp,
                "clock": clock,
                "side": side,
                "team": info[f"{side}_team"],
                "kind": kind,
                "detail": detail,
                "player": cells[2].value(),
                "target": cells[6].value(),
                "icon": image_name(icons[0]) if icons else "",
            }
        )
    if not events or any(
        a["seconds"] > b["seconds"] for a, b in zip(events, events[1:])
    ):
        raise ValueError("Empty or unordered timeline")
    checks = []
    for side in ("blue", "red"):
        counts = Counter(e["kind"] for e in events if e["side"] == side)
        for objective in ("tower", "dragon", "baron"):
            actual = counts[objective] + (
                counts["elder"] if objective == "dragon" else 0
            )
            checks.append(
                {
                    "gol_id": game_id,
                    "side": side,
                    "objective": objective,
                    "observed": actual,
                    "expected": info[f"{side}_final_{objective}"],
                    "matches": actual == info[f"{side}_final_{objective}"],
                }
            )
    info["unknown_events"] = sum(e["kind"] == "unknown" for e in events)
    info["timeline_valid"] = (
        all(c["matches"] for c in checks) and info["unknown_events"] == 0
    )
    return info, events, checks


def parse_gold(html):
    """Read numeric graph arrays without JS execution; ambiguous duplicate minutes skipped."""
    match = re.search(r"var\s+golddatas\s*=\s*\{(.*?)\n\s*\};", html, re.S)
    if not match:
        return {}, "missing_gold_graph"
    block = match.group(1)
    labels = re.search(r"labels:\s*\[([^]]*)\]", block)
    series = re.findall(
        r'label:\s*[\'"]([^\'"]+)[\'"].*?data:\s*\[([^]]*)\].*?borderColor:\s*[\'"]rgba\(([^)]*)\)',
        block,
        re.S,
    )
    if labels is None or len(series) != 10:
        return {}, "unsupported_gold_graph"
    clocks = [int(x) for x in re.findall(r'[\'"](\d+)[\'"]', labels.group(1))]
    values = []
    for i, (role, numbers, color) in enumerate(series):
        if role != ("TOP", "JGL", "MID", "BOT", "SPT")[i % 5]:
            return {}, "unexpected_role_order"
        colors = list(map(int, color.split(",")[:3]))
        if (i < 5 and colors[2] <= colors[0]) or (i >= 5 and colors[0] <= colors[2]):
            return {}, "unexpected_side_colors"
        if not re.fullmatch(r"[\s\d.,]+", numbers):
            return {}, "nonnumeric_gold_graph"
        nums = [float(v) for v in numbers.split(",") if v.strip()]
        if len(nums) != len(clocks) or not all(v >= 0 for v in nums):
            return {}, "invalid_gold_arrays"
        values.append(nums)
    gold = {}
    for minute in MINUTES:
        if clocks.count(minute) == 1:
            i = clocks.index(minute)
            gold[minute] = {
                "blue_gold": sum(v[i] for v in values[:5]),
                "red_gold": sum(v[i] for v in values[5:]),
            }
    return gold, "ok"


def roster(html):
    root = Document(html).root
    result = {}
    tables = list(root.all("table", css="playersInfosLine"))
    if len(tables) != 2:
        return result
    for side, table in zip(("blue", "red"), tables):
        players = []
        for row in table.all("tr"):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag == "td"]
            if not cells:
                continue
            links = [
                a
                for a in cells[0].all("a")
                if "/players/player-stats/" in a.attrs.get("href", "")
            ]
            if links:
                champs = [
                    img.attrs.get("alt", "")
                    for img in cells[0].all("img")
                    if "champions_icon/" in img.attrs.get("src", "")
                ]
                players.append(
                    {
                        "player": links[0].value(),
                        "champion": champs[0] if champs else "",
                    }
                )
        if len(players) == 5:
            result[side] = players
    return result


def fold(name):
    name = "".join(
        c for c in unicodedata.normalize("NFKD", name).casefold() if c.isalnum()
    )
    return {
        "gengesports": "geng",
        "bnkfearx": "fearx",
        "dwgkia": "dpluskia",
        "madlionskoi": "madlions",
        "teamliquidhonda": "teamliquid",
        "brokenbiade": "brokenblade",
        # Observed source rebrands; joins still require date, duration, sides and full rosters.
        "counterlogicgaming": "clg",
        "hanjinbrion": "brion",
        "freditbrion": "brion",
        "kwangdongfreecs": "dnsoopers",
        "dnfreecs": "dnsoopers",
    }.get(name, name)


def match_oe(info, players, matches):
    day = pd.Timestamp(info["date"], tz="UTC")
    candidates = matches[
        matches.side.eq("Blue")
        & matches.date.between(
            day - pd.Timedelta(days=1), day + pd.Timedelta(days=2), inclusive="left"
        )
        & matches.gamelength.sub(info["gamelength"]).abs().le(1)
        & matches.result.eq(info["blue_won"])
        & matches.teamname.map(fold).eq(fold(info["blue_team"]))
    ]
    accepted = []
    for game in candidates.gameid:
        pair = matches[matches.gameid.eq(game)]
        red = pair[pair.side.eq("Red")]
        if (
            len(pair) != 2
            or len(red) != 1
            or fold(red.iloc[0].teamname) != fold(info["red_team"])
            or red.iloc[0].result != info["red_won"]
        ):
            continue
        rows = pd.read_sql(
            text(
                "SELECT m.side, p.playername FROM match_players p JOIN matches m ON m.gameid=p.gameid AND m.teamid=p.teamid WHERE p.gameid=:game"
            ),
            get_engine(),
            params={"game": game},
        )
        if set(players) != {"blue", "red"} or not all(
            sorted(fold(p["player"]) for p in players[side])
            == sorted(rows[rows.side.eq(side.title())].playername.map(fold))
            for side in ("blue", "red")
        ):
            continue
        accepted.append(game)
    if len(accepted) != 1:
        return None, "unmatched" if not accepted else "ambiguous"
    return accepted[0], "matched_date_duration_sides_result_rosters"


def checkpoint_rows(info, events, gold):
    if not info["timeline_valid"]:
        return []
    rows = []
    for minute in MINUTES:
        if info["gamelength"] <= minute * 60:
            continue
        row = {
            "gol_id": info["gol_id"],
            "minute": minute,
            "objective_boundary_events": sum(
                e["kind"] in OBJECTIVES and e["seconds"] == minute * 60 for e in events
            ),
        }
        for side in ("blue", "red"):
            counts = Counter(
                e["kind"]
                for e in events
                if e["side"] == side and e["seconds"] < minute * 60
            )
            for kind in OBJECTIVES:
                row[f"{side}_{kind}"] = counts[kind]
        row.update(gold.get(minute, {}))
        rows.append(row)
    return rows


class Cache:
    def __init__(self, directory, fetch=False, delay=1.0):
        self.directory, self.fetch, self.delay = directory, fetch, max(1.0, delay)
        directory.mkdir(parents=True, exist_ok=True)
        self.last_request = 0.0
        self.requests = 0
        self.robot = urllib.robotparser.RobotFileParser()
        self.robot.parse(
            self.read(
                "robots.txt", "https://gol.gg/robots.txt", robots=True
            ).splitlines()
        )

    def read(self, name, url, robots=False):
        path = self.directory / name
        if path.exists():
            return path.read_text()
        if not self.fetch:
            raise FileNotFoundError(
                f"Missing cached {name}; run --fetch for the bounded sample"
            )
        if not robots and not self.robot.can_fetch(USER_AGENT, url):
            raise PermissionError(f"robots.txt disallows {url}")
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        self.requests += 1
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=25) as response:
            if urllib.parse.urlparse(response.url).hostname != "gol.gg":
                raise ValueError("Unexpected redirect domain")
            data = response.read().decode("utf-8")
        path.write_text(data)
        return data


def run(args, *, sample_limit=12, cache=None):
    cache = (
        cache if cache is not None else Cache(args.artifacts / "html", fetch=args.fetch)
    )
    matches = pd.read_sql(
        "SELECT gameid, date, teamname, side, gamelength, result, league FROM matches",
        get_engine(),
    )
    matches["date"] = pd.to_datetime(matches.date, utc=True)
    inventory, event_rows, check_rows, snapshots, comparisons, sources = (
        [],
        [],
        [],
        [],
        [],
        [],
    )
    samples = (
        json.loads(args.samples.read_text())
        if args.samples
        else [{"gol_id": game, "sample": label} for game, label in SAMPLES]
    )
    if len(samples) > sample_limit or any(
        not isinstance(s["gol_id"], int) or s["gol_id"] <= 0 for s in samples
    ):
        raise ValueError(
            f"Sample limited to {sample_limit} explicitly supplied positive integer game IDs"
        )
    for sample in samples:
        game = sample["gol_id"]
        print(f'gol.gg {game}: {sample.get("sample", "custom")}', flush=True)
        record = {**sample, "status": "pending"}
        try:
            pages = {}
            for page in ("timeline", "game"):
                url = f"https://gol.gg/game/stats/{game}/page-{page}/"
                body = cache.read(f"{game}-{page}.html", url)
                pages[page] = body
                sources.append(
                    {
                        "gol_id": game,
                        "page": page,
                        "url": url,
                        "sha256": hashlib.sha256(body.encode()).hexdigest(),
                    }
                )
            _, summary_info = metadata(pages["game"], game)
            record.update(summary_info)
            record["gold_status"] = parse_gold(pages["timeline"])[1]
            info, events, checks = parse_timeline(pages["timeline"], game)
            _, main_info = metadata(pages["game"], game)
            if any(
                info[k] != main_info[k]
                for k in (
                    "date",
                    "gamelength",
                    "blue_team",
                    "red_team",
                    "blue_won",
                    "red_won",
                    "map_number",
                )
            ):
                raise ValueError("Summary and timeline identities disagree")
            gold, gold_status = parse_gold(pages["timeline"])
            players = roster(pages["game"])
            oe_game, match_status = match_oe(info, players, matches)
            record.update(
                {
                    **info,
                    "oe_gameid": oe_game,
                    "match_status": match_status,
                    "gold_status": gold_status,
                    "events": len(events),
                    "status": (
                        "valid" if info["timeline_valid"] else "rejected_timeline"
                    ),
                }
            )
            event_rows.extend(events)
            check_rows.extend(checks)
            rows = checkpoint_rows(info, events, gold)
            for row in rows:
                row["oe_gameid"] = oe_game
                row["matched"] = oe_game is not None
                row["gold_verified"] = False
                if oe_game and row["minute"] in gold:
                    minute = row["minute"]
                    oe = pd.read_sql(
                        text(
                            f"SELECT m.side, SUM(p.goldat{minute}) AS gold, COUNT(p.goldat{minute}) AS players FROM player_stats p JOIN matches m ON m.gameid=p.gameid AND m.teamid=p.teamid WHERE p.gameid=:game GROUP BY m.side"
                        ),
                        get_engine(),
                        params={"game": oe_game},
                    )
                    for side in ("blue", "red"):
                        team = oe[oe.side.eq(side.title())]
                        if len(team) == 1 and team.iloc[0].players == 5:
                            comparisons.append(
                                {
                                    "gol_id": game,
                                    "oe_gameid": oe_game,
                                    "minute": minute,
                                    "side": side,
                                    "gol_gold": row[f"{side}_gold"],
                                    "oe_gold": float(team.iloc[0].gold),
                                    "difference": row[f"{side}_gold"]
                                    - float(team.iloc[0].gold),
                                }
                            )
                verified = [
                    c
                    for c in comparisons
                    if c["gol_id"] == game and c["minute"] == row["minute"]
                ]
                row["gold_verified"] = len(verified) == 2 and all(
                    c["difference"] == 0 for c in verified
                )
                row["training_ready"] = (
                    row["matched"]
                    and row["gold_verified"]
                    and row["objective_boundary_events"] == 0
                )
            snapshots.extend(rows)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 429):
                raise RuntimeError(
                    f"Access/rate-limit response {error.code}; stopped requests, no bypass"
                ) from error
            record.update(status="fetch_error", error=str(error))
        except (ValueError, FileNotFoundError, urllib.error.URLError) as error:
            record.update(status="unavailable", error=str(error))
        inventory.append(record)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    frames = {
        "games": pd.DataFrame(inventory),
        "events": pd.DataFrame(event_rows),
        "validation": pd.DataFrame(check_rows),
        "checkpoints": pd.DataFrame(snapshots),
        "gold_comparison": pd.DataFrame(comparisons),
    }
    frames["training_candidates"] = (
        frames["checkpoints"][frames["checkpoints"].training_ready]
        if not frames["checkpoints"].empty
        else pd.DataFrame()
    )
    for name, frame in frames.items():
        frame.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest = {
        "processed_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "purposive coverage/parser pilot; no model training",
        "samples": samples,
        "source_pages": sources,
        "network_requests_this_run": cache.requests,
        "parser_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "checkpoints": MINUTES,
        "timestamp_boundary": "strictly before checkpoint; second-precision boundary events flagged and excluded from training-ready set; games must last strictly beyond it",
        "notes": "Elder separate from elemental dragon features; summary dragon total includes Elder. Missing timelines never become zero. Gold graph minute labels need validation against OE; duplicate minute labels skipped.",
    }
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(frames, manifest))
    print(f"Wrote {args.out} and {args.artifacts}; {cache.requests} new requests")
    return frames, manifest


def report(frames, manifest):
    def table(frame):
        if frame.empty:
            return "(No rows.)"
        rows = [
            [str(v).replace("|", "\\|").replace("\n", " ") for v in row]
            for row in frame.fillna("").itertuples(index=False, name=None)
        ]
        return "\n".join(
            [
                "| " + " | ".join(map(str, frame.columns)) + " |",
                "| " + " | ".join(["---"] * len(frame.columns)) + " |",
            ]
            + ["| " + " | ".join(row) + " |" for row in rows]
        )

    games = frames["games"]
    columns = [
        c
        for c in (
            "gol_id",
            "sample",
            "date",
            "blue_team",
            "red_team",
            "status",
            "timeline_valid",
            "unknown_events",
            "match_status",
            "gold_status",
            "oe_gameid",
            "error",
        )
        if c in games
    ]
    valid = games.get("timeline_valid", pd.Series(False, index=games.index)).eq(True)
    matches = (
        games.get("match_status", pd.Series("", index=games.index))
        .fillna("")
        .str.startswith("matched")
    )
    checked = frames["gold_comparison"]
    gold_error = checked.difference.abs().max() if not checked.empty else None
    finding = f"{int(valid.sum())}/{len(games)} sampled games have validated timelines; {int((valid & matches).sum())} match OE. {len(frames['validation'])} tower/dragon/Baron total checks and {len(checked)} gold cross-checks were recorded."
    if gold_error is not None:
        finding += f" Maximum absolute gold difference from OE: {gold_error:g}."
    finding += f" Exported {len(frames['training_candidates'])} matched checkpoint candidates. This is a feasibility result, not representative coverage or a model benchmark."
    return "\n".join(
        [
            "# gol.gg historical objective pilot",
            "",
            "Small purposively selected sample across 2022–2025, not a representative coverage estimate. Public HTML only; no documented API used, no OCR, browser automation or model training. Raw source HTML and hashes are cached in gitignored data/gol_pilot/.",
            "",
            "## Finding",
            "",
            finding,
            "",
            "## Method",
            "",
            "Parse timeline HTML using event columns and icon filenames: action, taking side, game-clock seconds, player and target. Read team identities from blue/red headers rather than title ordering. Plates and inhibitors are separate from towers; Elder is separate from elemental dragons, but included when validating the displayed final dragon total. Unknown actions, malformed/empty timelines, duplicate IDs, unordered or post-end events are rejected. Reconstructed tower/dragon/Baron totals must match both side summaries before checkpoint export. End-game totals are validation targets, never predictor inputs.",
            "",
            "Match OE conservatively by blue/red team names, nearby calendar date, duration within one second, winner and all five starter names on each side. Ambiguous or missing matches are retained as unmatched; no fuzzy guesses. Map number is recorded but OE lacks a directly comparable map number, so duration/rosters distinguish games. Gold graph role arrays are parsed as inert numeric data with checked role order and side colors. Export only unique 10/15/20-minute labels; skip duplicate final-minute labels rather than infer their timestamp. Compare graph gold with OE snapshots where present. Objective checkpoints use events strictly before the minute and exclude ended games. Events exactly at a checkpoint have only second precision, so affected rows are flagged and excluded from the training-ready set. Training-ready rows also require an unambiguous OE match and both sides’ gold agreeing exactly with OE.",
            "",
            "## Game inventory",
            "",
            table(games[columns]),
            "",
            "## Final-total validation",
            "",
            table(frames["validation"]),
            "",
            "## Gold cross-check against OE",
            "",
            table(frames["gold_comparison"]),
            "",
            "## Limits and next decision",
            "",
            "A passed totals check supports parser consistency but does not independently prove every event timestamp. Audit a sample against the rendered timeline and assess representative league/year coverage before bulk acquisition. Missing histories and unsupported icons remain explicit failures. Dragon soul, buff expiration and patch-specific objective rules are not inferred yet. Keep OE gold for training until graph timestamps agree; this pilot creates candidate objective features only, with no forecast adoption. Historical features added now need development testing before another evaluation; the 2026 data has already been viewed.",
            "",
            "## Reproduction",
            "",
            "`.venv/bin/python scripts/pilot_gol.py` reprocesses the cached default sample offline. Add `--fetch` to obtain uncached pages; requests are sequential, at least one second apart, follow robots.txt and stop on authentication/rate-limit responses. `--samples PATH` accepts a JSON array of gol_id/sample objects, bounded to 12 games. Outputs games/events/validation/checkpoints/gold_comparison/training_candidates CSVs plus manifest. No DB or published metric changes.",
            "",
            f'New HTTP requests in this run: {manifest["network_requests_this_run"]}.',
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--samples", type=Path)
    parser.add_argument("--artifacts", type=Path, default=Path("data/gol_pilot"))
    parser.add_argument("--out", type=Path, default=Path("docs/gol_pilot_report.md"))
    run(parser.parse_args())


if __name__ == "__main__":
    main()
