"""Paired same-day Elo freshness diagnostic; no model fitting or CI work.

Rebuild settled logged calls at day start, then shift Elo/FORGE by only the
Oracle's Elixir games at least an hour before each series on that UTC day,
excluding its own matchup within 12 hours. Form stays frozen.
"""

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus import form, schedule
from prometheus.elo import (
    EloState,
    calculate_game_length_elo_change,
    load_elo_games,
    load_rosters,
)
from prometheus.evaluation import paired_bootstrap
from prometheus.utils import get_engine


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, default=Path("data/predictions.json"))
    args = parser.parse_args()
    started = time.monotonic()
    entries = schedule.load_log(args.log)
    series = [
        e for e in entries.values() if e.get("matched") and e.get("winner") in (1, 2)
    ]
    series.sort(key=lambda e: e["start"])
    games = load_elo_games()
    games["date"] = pd.to_datetime(games.date)
    # Resolve names using each name's latest game at the relevant cutoff.
    names = pd.read_sql(
        "SELECT teamname, teamid, date, gameid FROM matches ORDER BY date, gameid",
        get_engine(),
    )
    names["date"] = pd.to_datetime(names.date)
    name_rows = list(names.itertuples(index=False))
    name_index, by_name = 0, {}
    before = schedule.RatingsBefore(form.load_states())
    state = EloState(calculate_game_length_elo_change, rosters=load_rosters())
    game_rows = list(games.itertuples(index=False))
    cursor = 0
    day = None
    day_ratings = {}
    out = []
    own_excluded = 0
    for entry in series:
        start = pd.Timestamp(entry["start"]).tz_localize(None)
        if day != start.date():
            boundary = start.normalize()
            while cursor < len(game_rows) and game_rows[cursor].date < boundary:
                row = game_rows[cursor]
                state.play(row, row.league, row.date)
                cursor += 1
            day_ratings = {team: state.team_rating(team) for team in state.main_roster}
            day_state = state.to_dict()
            day = start.date()
        while name_index < len(name_rows) and name_rows[name_index].date < start:
            row = name_rows[name_index]
            by_name[row.teamname] = row.teamid
            name_index += 1
        ratings = before(day)
        teams = [entry.get("ours1"), entry.get("ours2")]
        if any(t not in ratings.index or t not in by_name for t in teams):
            continue
        a, b = (ratings.loc[t].copy() for t in teams)

        def chance(a, b, start=start, entry=entry):
            p, _ = schedule.game_probability(
                a,
                b,
                at=start,
                event=entry.get("league"),
                title=entry.get("event", ""),
                event_day=start,
            )
            return schedule.series_probability(
                p, int(entry["best_of"]), schedule.series_rho(a.league, b.league)
            )

        p_a = chance(a, b)
        pair = {by_name[name] for name in teams}
        refreshed = EloState.from_dict(day_state, calculate_game_length_elo_change)
        refreshed.rosters = state.rosters
        for row in game_rows[cursor:]:
            if row.date > start - pd.Timedelta(minutes=60):
                break
            own = {row.teamid, row.opponent_teamid} == pair and abs(
                row.date - start
            ) <= pd.Timedelta(hours=12)
            if own:
                own_excluded += 1
                continue
            refreshed.play(row, row.league, row.date)
        deltas = []
        for name, rating in zip(teams, (a, b)):
            team = by_name[name]
            base = day_ratings.get(team)
            current = refreshed.team_rating(team)
            delta = current - base if base is not None and current is not None else 0.0
            deltas.append(delta)
            rating["elo"] += delta
            rating["forge"] += delta
        out.append(
            (
                float(entry["winner"] == 1),
                p_a,
                chance(a, b),
                any(d != 0 for d in deltas),
            )
        )
    frame = pd.DataFrame(out, columns=["won", "a", "b", "changed"])
    print(f"series own games excluded={own_excluded}")
    print(f"n={len(frame)}, series with any change={int(frame.changed.sum())}")
    for label, rows in [("overall", frame), ("changed", frame[frame.changed])]:
        if rows.empty:
            print(f"{label}: n=0")
            continue

        def loss(p, rows=rows):
            p = np.clip(p.to_numpy(), 1e-6, 1 - 1e-6)
            y = rows.won.to_numpy()
            return -(y * np.log(p) + (1 - y) * np.log(1 - p))

        mean, lo, hi = paired_bootstrap(loss(rows.b), loss(rows.a))
        print(
            f"{label}: n={len(rows)}, paired log loss B-A={mean:+.6f} ({lo:+.6f}, {hi:+.6f})"
        )
    print(f"{time.monotonic() - started:.2f}s; research only, Form frozen")


if __name__ == "__main__":
    main()
