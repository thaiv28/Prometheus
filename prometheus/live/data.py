"""Load saved live maps for tests and backtests.

Each finished map's page file (`<match>/pages/map<n>.json` after
`scripts/live_data.py pull`, or `output/live/<match>/map<n>.json` from a local
run) holds every frame received, our calls, Kalshi's quotes, FORGE before the
map and the winner. Team columns are in the match's fixed order: `_0` is the
first team (whose chance every `p` is), `_1` the second; `blue` says which one
played blue.

    from prometheus.live.data import load_maps
    maps = load_maps()                       # every map under data/live
    frames = pd.concat(m.frames.assign(match=m.match_id, map=m.number) for m in maps)
"""

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
STATS = ("gold", "kills", "towers", "dragons", "barons", "inhibitors")


@dataclass
class LiveMap:
    match_id: str
    number: int
    game_id: str
    teams: list[str]
    blue: int | None
    winner: int | None
    pregame: dict
    series: dict
    frames: pd.DataFrame
    calls: pd.DataFrame
    market: pd.DataFrame
    path: Path = field(repr=False)


def map_files(*roots):
    """Saved finished-map files under the given roots (default: data/live)."""
    roots = roots or (ROOT / "data" / "live",)
    files = []
    for root in roots:
        root = Path(root)
        files += root.glob("*/pages/map*.json")
        files += root.glob("*/map*.json")
    return sorted(set(files))


def _times(df, *columns):
    for c in columns:
        if c in df:
            df[c] = pd.to_datetime(df[c], utc=True, format="ISO8601")
    return df


def load_map(path):
    """One finished map's file as tables."""
    path = Path(path)
    page = json.loads(path.read_text())
    match, game = page["match"], page["game"]
    rows = []
    for f in game.get("frames") or []:
        row = {
            "at": f.get("at"),
            "source_at": f.get("source_at"),
            "clock_estimate": f.get("clock_estimate"),
        }
        for i, team in enumerate(f.get("teams") or []):
            for stat in STATS:
                row[f"{stat}_{i}"] = team.get(stat)
        rows.append(row)
    frames = _times(pd.DataFrame(rows), "at", "source_at")
    if {"gold_0", "gold_1"} <= set(frames):
        frames["gold_lead"] = frames["gold_0"] - frames["gold_1"]
    calls = _times(pd.DataFrame(game.get("calls") or []), "at")
    market = _times(pd.DataFrame(game.get("market") or []), "at")
    if not market.empty:
        market["mid"] = (market["bid"] + market["ask"]) / 2
    return LiveMap(
        match_id=match["id"],
        number=game["number"],
        game_id=game.get("id"),
        teams=[t["name"] for t in match["teams"]],
        blue=game.get("blue"),
        winner=game.get("winner"),
        pregame=game.get("pregame") or {},
        series=match.get("series") or {},
        frames=frames,
        calls=calls,
        market=market,
        path=path,
    )


def load_maps(*roots):
    """Every saved finished map, oldest match first."""
    return [load_map(p) for p in map_files(*roots)]
