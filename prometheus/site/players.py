"""Player pages and the player registers (Player Elo, AURA)."""

import json
import os

import pandas as pd

from prometheus.site import config as site_config
from prometheus.site.config import (
    ACTIVE_WINDOW,
    PLAYER_PAGE_WINDOW,
    PLAYER_SEASON_GAMES,
)
from prometheus.site.render import env, slugify, write
from prometheus.types import INTERNATIONAL_LEAGUES


def aura_rows_and_seasons(seasons, slugs):
    """AURA register rows (qualified player-seasons of listed players) and each listed player's seasons.

    `seasons` is `aura.season_aura` output; `slugs` maps playerid to page slug.
    Returns (rows, {slug: [season, ...] newest first}).
    """
    listed = seasons[seasons["playerid"].isin(slugs.index)].assign(
        slug=lambda d: d["playerid"].map(slugs)
    )
    listed = listed.assign(
        aura=listed["aura"].round(2), role_z=listed["role_z"].round(2)
    )
    qualified = listed[listed["qualified"]]
    cols = [
        "slug",
        "playername",
        "position",
        "teamname",
        "league",
        "year",
        "games",
        "aura",
        "role_z",
    ]
    rows = qualified[cols].to_dict(orient="records")
    by_player = {}
    for r in listed.sort_values(
        ["year", "games"], ascending=[False, False]
    ).itertuples():
        by_player.setdefault(r.slug, []).append(
            {
                "year": int(r.year),
                "teamname": r.teamname,
                "team_slug": slugify(r.teamname),
                "league": r.league,
                "position": r.position,
                "games": int(r.games),
                "aura": float(r.aura),
                "role_rank": int(r.role_rank) if r.qualified else None,
                "role_count": int(r.role_count) if r.qualified else None,
            }
        )
    return rows, by_player


def _player_slugs(players):
    """Unique page slugs: the name, then name and last team, then a number."""
    base = players["playername"].map(slugify)
    shared = base.duplicated(keep=False)
    slug = base.where(~shared, base + "-" + players["teamname"].map(slugify))
    order = players.assign(slug=slug).sort_values("playerid")
    order["n"] = order.groupby("slug").cumcount()
    order.loc[order["n"] > 0, "slug"] = (
        order["slug"] + "-" + (order["n"] + 1).astype(str)
    )
    return order["slug"].reindex(players.index)


def player_pages_and_rows(history, latest, seasons):
    """Player Elo register rows and one page context per listed player.

    Listed players: ever in a major league or at an international event, or active
    within PLAYER_PAGE_WINDOW. The register has their current ratings ("now" rows,
    active within ACTIVE_WINDOW, every league) and, to keep the page light, their
    major-league seasons with PLAYER_SEASON_GAMES or more games.
    """
    newest = pd.to_datetime(latest["latest_date"]).max()
    big_stage = set(env.globals["major_leagues"]) | set(INTERNATIONAL_LEAGUES)
    on_big_stage = set(history.loc[history["league"].isin(big_stage), "playerid"])
    latest = latest[~latest["playerid"].str.startswith("dup:")]
    listed = latest[
        latest["playerid"].isin(on_big_stage)
        | (pd.to_datetime(latest["latest_date"]) >= newest - PLAYER_PAGE_WINDOW)
    ].copy()
    listed["slug"] = _player_slugs(listed)
    slugs = listed.set_index("playerid")["slug"]

    def rows(df, is_now):
        df = df.assign(
            slug=df["playerid"].map(slugs),
            elo=df["elo"].round(),
            now=is_now,
            active=True,
        )
        if is_now:
            df["active"] = pd.to_datetime(df["latest_date"]) >= newest - ACTIVE_WINDOW
            df["year"] = pd.to_datetime(df["latest_date"]).dt.year
        cols = [
            "slug",
            "playername",
            "position",
            "teamname",
            "league",
            "elo",
            "year",
            "latest_date",
            "now",
            "active",
        ]
        return df[cols].to_dict(orient="records")

    season_rows = seasons[
        seasons["playerid"].isin(slugs.index)
        & (seasons["games"] >= PLAYER_SEASON_GAMES)
        & seasons["league"].isin(env.globals["major_leagues"])
    ]
    register = rows(listed, True) + rows(season_rows, False)

    pages = {}
    infos = listed.drop_duplicates("playerid").set_index("playerid")
    listed_history = history[history["playerid"].isin(slugs.index)]
    # A stint is a run of consecutive games for one team. History is in date order,
    # so group each player's games together (keeping their order) before marking runs.
    by_player = listed_history.sort_values("playerid", kind="stable")
    by_player["stint"] = (
        (by_player["playerid"] != by_player["playerid"].shift())
        | (by_player["teamid"] != by_player["teamid"].shift())
    ).cumsum()
    # Each stint's last game (not "last" aggregation, which skips nulls).
    stint_rows = (
        by_player.drop_duplicates("stint", keep="last")
        .set_index("stint")[
            ["playerid", "teamname", "home_league", "league", "date", "elo"]
        ]
        .rename(columns={"date": "last"})
    )
    stint_rows["first"] = by_player.drop_duplicates("stint").set_index("stint")["date"]
    stint_rows["games"] = by_player.groupby("stint").size()
    # The stint's most common role, ties to the first alphabetically (as Series.mode).
    roles = by_player.groupby(["stint", "position"]).size().rename("n").reset_index()
    roles = roles.sort_values(
        ["stint", "n", "position"], ascending=[True, False, True], kind="stable"
    )
    stint_rows["position"] = roles.drop_duplicates("stint").set_index("stint")[
        "position"
    ]
    stints_by_player = {}
    for r in stint_rows.itertuples():
        stints_by_player.setdefault(r.playerid, []).append(
            {
                "teamname": r.teamname,
                "team_slug": slugify(r.teamname),
                "league": r.home_league or r.league,
                "position": r.position,
                "first": r.first[:10],
                "last": r.last[:10],
                "games": int(r.games),
                "elo": round(float(r.elo)),
            }
        )
    for pid, games in listed_history.groupby("playerid", sort=False):
        info = infos.loc[pid]
        series = [
            {"date": d[:10], "elo": round(float(e), 1)}
            for d, e in zip(games["date"], games["elo"])
        ]
        peak = max(series, key=lambda d: d["elo"])
        low = min(series, key=lambda d: d["elo"])
        stints = stints_by_player[pid]
        names = [
            n
            for n in dict.fromkeys(games["playername"][::-1])
            if n != info["playername"]
        ]
        pages[info["slug"]] = {
            "playername": info["playername"],
            "slug": info["slug"],
            "position": info["position"],
            "teamname": info["teamname"],
            "team_slug": slugify(info["teamname"]),
            "home_league": info["league"],
            "current_elo": round(float(info["elo"])),
            "active": bool(
                pd.to_datetime(info["latest_date"]) >= newest - ACTIVE_WINDOW
            ),
            "aliases": names,
            "elo_series": series,
            "elo_summary": {
                "games": len(series),
                "peak": peak,
                "low": low,
                "first": series[0],
                "last": series[-1],
            },
            "stints": stints[::-1],
        }
    return register, pages, listed


def render_player_pages(pages):
    template = env.get_template("player.html.j2")
    for page in pages.values():
        write(
            os.path.join(site_config.OUTPUT_DIR, "players", f"{page['slug']}.html"),
            template.render(page_key="player", root_path="../", **page),
        )


def write_player_index(listed):
    """players.json for the header search: name, slug, role, team, league, last game."""
    majors = set(env.globals["major_leagues"])
    players = [
        {
            "n": r.playername,
            "s": r.slug,
            "r": r.position,
            "t": r.teamname,
            "l": r.league,
            "d": r.latest_date,
        }
        for r in listed.sort_values("latest_date", ascending=False).itertuples()
    ]
    players.sort(key=lambda p: p["l"] not in majors)
    with open(os.path.join(site_config.OUTPUT_DIR, "players.json"), "w") as f:
        f.write(json.dumps(players, ensure_ascii=False, separators=(",", ":")))
