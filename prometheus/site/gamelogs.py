"""Game logs on team and player pages."""

import json
import os
import shutil

from prometheus import aura, gamelog
from prometheus.site import config as site_config
from prometheus.site.render import env


def game_log_context(kind, log, slug):
    """A page's game log: its newest series embedded, the rest written to games/<kind>s/<slug>.json.

    Returns the template's `games` context, or None for an empty log.
    """
    series = log["series"]
    if not series:
        return None
    people = "players" if kind == "team" else "teams"
    data = {
        "kind": kind,
        people: log[people],
        "series": series[: site_config.GAME_LOG_SERIES],
        "years": gamelog.year_records(series),
    }
    if len(series) > site_config.GAME_LOG_SERIES:
        path = os.path.join(site_config.OUTPUT_DIR, "games", f"{kind}s", f"{slug}.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(
                json.dumps(
                    {people: log[people], "series": series},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
            )
        data["src"] = f"../games/{kind}s/{slug}.json"
    return {
        "data": data,
        "series": len(series),
        "games": sum(len(s["g"]) for s in series),
        "shown": min(len(series), site_config.GAME_LOG_SERIES),
        "since": series[-1]["d"][:4],
        "years": [y[0] for y in data["years"]],
    }


def add_game_logs(
    team_pages,
    player_pages,
    states,
    prediction_log,
    player_slugs,
    aura_games,
    tables=None,
):
    """Attach a game log to every team and player page (as `games`).

    `player_slugs` maps playerid to page slug; `aura_games` is `aura.get_aura`
    output, whose major-league games give the per-game AURA on player logs.
    `tables` is the build's shared `PlayerTables`.
    """
    shutil.rmtree(os.path.join(site_config.OUTPUT_DIR, "games"), ignore_errors=True)
    games = gamelog.add_series(gamelog.add_calls(gamelog.load_team_games(), states))
    players = gamelog.load_player_games(tables)
    prices = gamelog.load_prices(site_config.MARKET_PRICES, prediction_log)
    heads = gamelog.series_heads(games, gamelog.PriceBook(prices))
    teams = gamelog.team_logs(games, players, heads, player_slugs)
    for page in team_pages.values():
        log = teams.get(page["teamname"])
        page["games"] = game_log_context("team", log, page["slug"]) if log else None
    majors = aura_games[aura_games["league"].isin(env.globals["major_leagues"])].dropna(
        subset=["aura"]
    )
    aura_by_game = dict(
        zip(zip(majors["gameid"], majors["playerid"]), majors["aura"] * aura.POINTS)
    )
    for slug, log in gamelog.player_logs(
        games, players, heads, player_slugs, aura_by_game
    ).items():
        if slug in player_pages:
            player_pages[slug]["games"] = game_log_context("player", log, slug)
    priced = sum(1 for log in teams.values() for s in log["series"] if "k" in s)
    print(
        f"Game logs: {len(heads):,} team-series, {priced:,} with a Kalshi price ({len(prices):,} prices on file)"
    )
