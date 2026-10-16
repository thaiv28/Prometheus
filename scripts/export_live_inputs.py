"""Export the ratings the live worker needs, so it never loads the database.

For every team: FORGE's rating fields (as `schedule.current_ratings` gives them,
the input to `game_probability`) and the latest game-length Elo the in-game
model was trained on (`game_length_elo.post_match_elo`). The publish build
uploads the file to the artifacts bucket; `deploy/live/refresh.sh` fetches it.

    uv run python scripts/export_live_inputs.py --out data/live_inputs.json
"""

import argparse
import datetime
import json
import math
import sqlite3
from pathlib import Path

from prometheus import DB_PATH
from prometheus.form import load_states
from prometheus.schedule import current_ratings

FIELDS = ("league", "elo", "form", "forge", "has_form")


def model_elos(db_path):
    """{team name: (latest post-match game-length Elo, its game's date)}."""
    with sqlite3.connect(f"file:{db_path}?mode=ro", uri=True) as conn:
        rows = conn.execute(
            "SELECT m.teamname, e.post_match_elo, m.date FROM matches m"
            " JOIN game_length_elo e ON e.gameid = m.gameid AND e.teamid = m.teamid"
            " ORDER BY m.date"
        ).fetchall()
    return {name: (elo, date) for name, elo, date in rows}


def plain(value):
    if isinstance(value, bool):
        return value
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def build(db_path):
    ratings = current_ratings(load_states())
    elos = model_elos(db_path)
    teams = {}
    for name, row in ratings.iterrows():
        team = {k: plain(row[k]) for k in FIELDS}
        team["latest_date"] = str(row["latest_date"])
        if name in elos:
            team["model_elo"], team["model_elo_as_of"] = elos[name]
        teams[name] = team
    return {
        "schema": 1,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "data_through": max(str(t["latest_date"]) for t in teams.values()),
        "teams": teams,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path(DB_PATH))
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    data = build(args.db)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"{len(data['teams']):,} teams through {data['data_through']} -> {args.out}")


if __name__ == "__main__":
    main()
