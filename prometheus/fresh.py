"""Resume published Elo with results that Oracle's Elixir has not ingested yet.

Leaguepedia scoreboards and worker maps supply players and duration; schedule
maps fill gaps with last-known rosters and a neutral 30-minute duration. Only Elo changes: Form stays
frozen, and future calls retain their Oracle's Elixir data date for alerts.
"""

import datetime
import json
import time
from collections import namedtuple
from pathlib import Path

import pandas as pd

from prometheus import schedule
from prometheus.elo import EloState, calculate_game_length_elo_change
from prometheus.types import INTERNATIONAL_LEAGUES

# The live worker's league labels that differ from ours (`live.service.LEAGUES`).
WORKER_LEAGUES = {"WLDs": "Worlds", "LTA N": "LCS"}

COLUMNS = [
    "game_key",
    "start",
    "team1",
    "team2",
    "winner",
    "gamelength",
    "players1",
    "players2",
    "event_league",
    "event",
    "game_number",
    "league",
    "source",
]


def _quote(value):
    return "'" + str(value).replace("\\", "\\\\").replace("'", "\\'") + "'"


def _pages(params, sleep):
    rows, offset = [], 0
    while True:
        page = schedule._get(
            {
                "action": "cargoquery",
                "format": "json",
                "limit": schedule.PAGE_SIZE,
                "offset": offset,
                **params,
            },
            sleep=sleep,
        )
        rows.extend(page)
        if len(page) < schedule.PAGE_SIZE:
            return rows
        offset += schedule.PAGE_SIZE
        sleep(5)


def fetch_recent_games(since, sleep=time.sleep):
    """Fetch finished scoreboard and schedule maps since a UTC timestamp."""
    since = pd.Timestamp(since).strftime("%Y-%m-%d %H:%M:%S")
    scoreboard = _pages(
        {
            "tables": "ScoreboardGames=SG, Tournaments=T",
            "join_on": "SG.OverviewPage=T.OverviewPage",
            "fields": "SG.GameId=game_key, SG.MatchId=match_id, SG.DateTime_UTC=start, SG.Team1=team1, SG.Team2=team2, SG.WinTeam=win_team, SG.Gamelength_Number=gamelength, SG.N_GameInMatch=game_number, T.League=event_league, T.Name=event",
            "where": f"SG.DateTime_UTC >= {_quote(since)}",
            "order_by": "SG.DateTime_UTC, SG.GameId",
        },
        sleep,
    )
    ids = list(dict.fromkeys(row["game_key"] for row in scoreboard))
    players = {}
    for offset in range(0, len(ids), 50):
        batch = ",".join(_quote(key) for key in ids[offset : offset + 50])
        rows = _pages(
            {
                "tables": "ScoreboardPlayers=SP",
                "fields": "SP.Link=player, SP.Team=team, SP.GameId=game_key",
                "where": f"SP.GameId IN ({batch})",
                "order_by": "SP.GameId, SP.Team, SP.Link",
            },
            sleep,
        )
        for row in rows:
            players.setdefault((row["game_key"], row["team"]), []).append(row["player"])
    fallback = _pages(
        {
            "tables": "MatchScheduleGame=MSG, MatchSchedule=MS, Tournaments=T",
            "join_on": "MSG.MatchId=MS.MatchId, MS.OverviewPage=T.OverviewPage",
            "fields": "MSG.GameId=game_key, MSG.MatchId=match_id, MS.DateTime_UTC=start, MSG.Blue=team1, MSG.Red=team2, MSG.Winner=winner, MSG.N_GameInMatch=game_number, T.League=event_league, T.Name=event",
            "where": f"MS.DateTime_UTC >= {_quote(since)} AND MSG.Winner IS NOT NULL",
            "order_by": "MS.DateTime_UTC, MSG.MatchId, MSG.N_GameInMatch",
        },
        sleep,
    )
    out = []
    for row in scoreboard:
        winner = (
            1
            if row.get("win_team") == row.get("team1")
            else 2
            if row.get("win_team") == row.get("team2")
            else None
        )
        if not row.get("win_team") or winner is None:
            continue
        length = pd.to_numeric(row.get("gamelength"), errors="coerce")
        out.append(
            {
                **row,
                "winner": winner,
                "source": "scoreboard",
                "league": None,
                "gamelength": length * 60,
                "players1": tuple(players.get((row["game_key"], row["team1"]), []))
                or None,
                "players2": tuple(players.get((row["game_key"], row["team2"]), []))
                or None,
            }
        )
    for row in fallback:
        if row["game_key"] in ids or str(row.get("winner")) not in ("1", "2"):
            continue
        out.append(
            {
                **row,
                "winner": int(row["winner"]),
                "source": "schedule",
                "league": None,
                "gamelength": float("nan"),
                "players1": None,
                "players2": None,
            }
        )
    frame = pd.DataFrame(out, columns=[*COLUMNS, "match_id"])
    frame["game_number"] = pd.to_numeric(frame.game_number, errors="coerce")
    frame["start"] = pd.to_datetime(frame.start, utc=True).dt.tz_localize(None)
    return frame.sort_values(["start", "match_id", "game_number"], kind="stable")[
        COLUMNS
    ].reset_index(drop=True)


def worker_games(directory, since):
    """Read compact finished-map records uploaded by the live worker."""
    out = []
    since = pd.Timestamp(since).tz_localize(None)
    for path in sorted(Path(directory).glob("*/maps.json")):
        for row in json.loads(path.read_text()).values():
            teams = row.get("teams") or []
            date = row.get("ended_at") or row.get("started_at")
            if (
                row.get("winner") not in (0, 1)
                or len(teams) != 2
                or not all(teams)
                or not date
            ):
                continue
            if pd.Timestamp(date).tz_localize(None) < since:
                continue
            length = pd.to_numeric(row.get("duration_seconds"), errors="coerce")
            start = row.get("started_at")
            if not start:
                start = (
                    pd.Timestamp(date) - pd.Timedelta(seconds=length)
                    if pd.notna(length)
                    else date
                )
            players = row.get("players") or [None, None]
            out.append(
                {
                    "game_key": f"riot:{row['game_id']}",
                    "start": pd.Timestamp(start).tz_localize(None),
                    "team1": teams[0],
                    "team2": teams[1],
                    "winner": row["winner"] + 1,
                    "gamelength": length,
                    "players1": tuple(players[0]) if players[0] else None,
                    "players2": tuple(players[1]) if players[1] else None,
                    "game_number": row["number"],
                    "league": worker_league(row.get("league")),
                    "event": row.get("event"),
                    "event_league": None,
                    "source": "worker",
                }
            )
    return pd.DataFrame(out, columns=COLUMNS)


def worker_league(label):
    """Our code for an international event the worker labels; None otherwise, so a
    domestic game takes the teams' home league as Leaguepedia rows do."""
    league = WORKER_LEAGUES.get(label, label)
    return league if league in INTERNATIONAL_LEAGUES else None


def _aliases():
    return (
        json.loads(schedule.ALIASES_PATH.read_text())
        if schedule.ALIASES_PATH.exists()
        else {}
    )


def refreshed_ratings(
    inputs, state_payload, games, aliases=None, *, return_state=False
):
    """Return published ratings shifted by newly replayed Elo, with an audit."""
    ratings = pd.DataFrame.from_dict(inputs, orient="index").rename_axis("teamname")
    matcher = schedule.TeamMatcher(
        ratings.reset_index(), _aliases() if aliases is None else aliases
    )
    state = EloState.from_dict(state_payload["state"], calculate_game_length_elo_change)
    teams = state_payload["teams"]
    before = {name: state.team_rating(team) for name, team in teams.items()}
    recent = sorted(
        (low, high, pd.Timestamp(date))
        for low, high, date in state_payload["recent_games"]
    )
    used = set()
    stale_before = pd.Timestamp(state_payload["data_through"]) - pd.Timedelta(hours=6)
    summary = {
        "deltas": {},
        "applied": 0,
        "known": 0,
        "stale_skipped": 0,
        "unmatched": [],
        "results_through": None,
        "applied_by_team": {},
        "applied_by_source": {},
    }
    unmatched = set()
    Game = namedtuple("Game", "gameid teamid opponent_teamid gamelength result date")
    candidates = []
    priority = {"scoreboard": 0, "worker": 1, "schedule": 2}
    ordered = games.assign(
        _priority=games.get("source", pd.Series("schedule", index=games.index))
        .map(priority)
        .fillna(2)
    )
    for game in (
        ordered.sort_values("_priority", kind="stable")
        .drop(columns="_priority")
        .itertuples(index=False)
    ):
        names = [matcher(game.team1), matcher(game.team2)]
        for raw, name in zip((game.team1, game.team2), names):
            if name is None or name not in teams:
                unmatched.add(raw)
        if (
            any(name is None or name not in teams for name in names)
            or names[0] == names[1]
        ):
            continue
        pair = tuple(sorted(names))
        number = getattr(game, "game_number", None)
        if any(
            pair == old_pair
            and (pd.isna(number) or pd.isna(old_number) or number == old_number)
            and abs(game.start - old.start) <= pd.Timedelta(hours=3)
            # Legacy inputs without source labels retain their original replay behavior.
            and (hasattr(game, "source") or hasattr(old, "source"))
            for old, _, old_pair, old_number in candidates
        ):
            continue
        candidates.append((game, names, pair, number))
    for game, names, _, _ in sorted(candidates, key=lambda item: item[0].start):
        ids = [teams[name] for name in names]
        pair = tuple(sorted(ids))
        match = next(
            (
                i
                for i, (low, high, date) in enumerate(recent)
                if i not in used
                and (low, high) == pair
                and abs(date - game.start) <= pd.Timedelta(hours=3)
            ),
            None,
        )
        if match is not None:
            used.add(match)
            summary["known"] += 1
            continue
        if game.start < stale_before:
            summary["known"] += 1
            summary["stale_skipped"] += 1
            continue
        homes = [state.home.get(team) for team in ids]
        league = getattr(game, "league", None)
        if pd.isna(league):
            league = schedule.EVENT_LEAGUES.get(game.event_league) or homes[0]
        for side, team in enumerate(ids, 1):
            links = getattr(game, f"players{side}")
            if links:
                local = state_payload["rosters"].get(team, {})
                roster = tuple(
                    local.get(schedule.fold(link))
                    or state_payload["players"].get(schedule.fold(link))
                    or f"lp:{schedule.fold(link)}"
                    for link in links
                )
                state.rosters[game.game_key, team] = roster
        length = 1800 if pd.isna(game.gamelength) else game.gamelength
        state.play(
            Game(game.game_key, *ids, length, int(game.winner == 1), game.start),
            league,
            game.start,
        )
        summary["applied"] += 1
        source = getattr(game, "source", "schedule")
        counts = summary["applied_by_source"]
        counts[source] = counts.get(source, 0) + 1
        summary["results_through"] = game.start.strftime("%Y-%m-%dT%H:%MZ")
        for name in names:
            counts = summary["applied_by_team"]
            counts[name] = counts.get(name, 0) + 1
    for name, team in teams.items():
        after = state.team_rating(team)
        if name in ratings.index and before[name] is not None and after is not None:
            delta = after - before[name]
            if delta:
                summary["deltas"][name] = delta
            ratings.loc[name, "elo"] += delta
            ratings.loc[name, "forge"] += delta
    summary["unmatched"] = sorted(unmatched)
    return (ratings, summary, state) if return_state else (ratings, summary)


def site_overlay(state_payload, state_after, summary, player_slugs, now):
    """Build-relative rating deltas, including league-wide player offset moves."""
    before = EloState.from_dict(
        state_payload["state"], calculate_game_length_elo_change
    )
    players = {}
    if summary["applied"]:
        for player in state_after.own:
            old = before.player_rating(player)
            slug = player_slugs.get(player)
            if old is not None and slug:
                delta = state_after.player_rating(player) - old
                if abs(delta) >= 0.05:
                    players[slug] = round(delta, 1)
    return {
        "base": state_payload["data_through"],
        "at": now.strftime("%Y-%m-%dT%H:%MZ"),
        "results_through": summary["results_through"],
        "teams": {
            name: round(delta, 1)
            for name, delta in summary["deltas"].items()
            if abs(delta) >= 0.05
        }
        if summary["applied"]
        else {},
        "players": players,
    }


def refresh_log(
    log,
    now,
    inputs,
    state_payload,
    fetch=fetch_recent_games,
    fetch_schedule=schedule.fetch_schedule,
    worker_maps=None,
    site_out=None,
    player_slugs=None,
):
    """Refresh only unstarted calls and settle schedule results, preserving OE dates."""
    since = pd.Timestamp(state_payload["data_through"]).date() - datetime.timedelta(
        days=1
    )
    worker = (
        worker_games(worker_maps, since)
        if worker_maps and Path(worker_maps).exists()
        else pd.DataFrame(columns=COLUMNS)
    )
    try:
        games = fetch(since=since)
    except Exception:
        if worker.empty:
            raise
        games = pd.DataFrame(columns=COLUMNS)
    if not worker.empty:
        games = (
            pd.concat([games, worker], ignore_index=True) if not games.empty else worker
        )
    aliases = _aliases()
    ratings, summary, state_after = refreshed_ratings(
        inputs["teams"], state_payload, games, aliases, return_state=True
    )
    sched = fetch_schedule(
        now.date() - datetime.timedelta(days=1), now.date() + datetime.timedelta(days=8)
    )
    predictions = schedule.predict(
        sched, ratings, schedule.TeamMatcher(ratings.reset_index(), aliases), at=now
    )
    for pred in predictions:
        if pred["matched"]:
            count = sum(
                summary["applied_by_team"].get(pred[f"ours{i}"], 0) for i in (1, 2)
            )
            if count:
                pred.update(
                    provisional_games=count, results_through=summary["results_through"]
                )
    old = {key: entry.get("p_game") for key, entry in log.items()}
    schedule.update_log(
        log,
        sched,
        predictions,
        now,
        data_through=inputs["data_through"][:10],
        reconstruct=None,
    )
    if site_out is not None:
        path = Path(site_out)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                site_overlay(
                    state_payload, state_after, summary, player_slugs or {}, now
                )
            )
        )
    return {
        **summary,
        "matches": len(predictions),
        "matched": sum(p["matched"] for p in predictions),
        "calls_changed": sum(
            e.get("matched", False) and e.get("p_game") != old.get(key)
            for key, e in log.items()
        ),
    }
