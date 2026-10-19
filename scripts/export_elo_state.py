"""Export resumable Elo and name indexes for the database-free hourly refresh."""

import argparse
import datetime
import gzip
import json
import time
from pathlib import Path

import pandas as pd

from prometheus.elo import load_elo_games, load_rosters, replay_state
from prometheus.schedule import fold
from prometheus.utils import get_engine


def build():
    games = load_elo_games()
    state = replay_state(games, load_rosters())
    teams = pd.read_sql(
        "SELECT teamname, teamid, date, gameid FROM matches ORDER BY date, gameid",
        get_engine(),
    )
    players = pd.read_sql(
        "SELECT p.playername, p.playerid, m.date, m.gameid FROM match_players p JOIN matches m ON p.gameid=m.gameid AND p.teamid=m.teamid ORDER BY m.date, m.gameid",
        get_engine(),
    )
    latest = players.drop_duplicates("playerid", keep="last").copy()
    latest["folded"] = latest.playername.map(fold)
    recent = latest[
        pd.to_datetime(latest.date)
        >= pd.to_datetime(games.date).max() - pd.Timedelta(days=730)
    ]
    unique = recent[~recent.folded.duplicated(keep=False)]
    names = dict(zip(latest.playerid, latest.folded))
    rosters = {
        team: {names[p]: p for p in roster if p in names}
        for team, roster in state.last_roster.items()
    }
    data_through = pd.to_datetime(games.date).max()
    recent_games = games[
        pd.to_datetime(games.date) >= data_through - pd.Timedelta(days=3)
    ]
    return {
        "schema": 1,
        "generated_at": datetime.datetime.now(datetime.UTC).isoformat(),
        "data_through": data_through.isoformat(),
        "recent_games": [
            [
                *sorted((row.teamid, row.opponent_teamid)),
                pd.Timestamp(row.date).isoformat(),
            ]
            for row in recent_games.itertuples(index=False)
        ],
        "state": state.to_dict(),
        "teams": dict(zip(teams.teamname, teams.teamid)),
        "rosters": rosters,
        "players": dict(zip(unique.folded, unique.playerid)),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    started = time.monotonic()
    payload = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(args.out, "wt") as stream:
        json.dump(payload, stream, separators=(",", ":"))
    print(
        f"Elo state: {len(payload['teams'])} teams, {len(payload['players'])} players, {args.out.stat().st_size:,} bytes, {time.monotonic() - started:.2f}s"
    )


if __name__ == "__main__":
    main()
