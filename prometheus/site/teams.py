"""Team pages: rows, rosters, the team index."""

import json
import os

import pandas as pd

from prometheus.site import config as site_config
from prometheus.site.config import ACTIVE_WINDOW, ROLE_ORDER, ROSTER_EXTRAS
from prometheus.site.render import _slugify, _write, env


def _team_pages(
    glory_df,
    forge_seasons,
    forge_now,
    elo_history,
    latest_elos,
    glory_qualified,
    rosters=None,
):
    """Return {slug: context} for every team with GLORY data or Elo history.

    Each season carries GLORY (every team-season with a game) and FORGE at the
    end of that year. `forge_now` gives the current FORGE.
    """

    # Rank of each qualified team-season within its year, for team pages.
    q = glory_qualified[["teamname", "year", "score"]].copy()
    q["year_rank"] = (
        q.groupby("year")["score"].rank(ascending=False, method="min").astype(int)
    )
    q["field"] = q.groupby("year")["score"].transform("size").astype(int)
    year_rank = {
        (t, int(y)): (int(r), int(f))
        for t, y, r, f in q[["teamname", "year", "year_rank", "field"]].itertuples(
            index=False
        )
    }

    key = ["teamname", "year"]
    seasons = (
        glory_df[["teamname", "year", "league", "score"]]
        .rename(columns={"score": "glory"})
        .merge(forge_seasons[key + ["forge"]].drop_duplicates(key), on=key, how="left")
    )
    forge_current = forge_now.drop_duplicates("teamname").set_index("teamname")["forge"]

    latest = latest_elos.set_index("teamname")
    pages = {}
    teams = sorted(set(seasons["teamname"]) | set(elo_history["teamname"]))
    seasons_by_team = dict(tuple(seasons.groupby("teamname")))
    elo_by_team = dict(tuple(elo_history.groupby("teamname")))
    value = lambda v, digits: None if pd.isna(v) else round(float(v), digits)

    for team in teams:
        slug = _slugify(team)
        series = []
        if team in seasons_by_team:
            for row in seasons_by_team[team].sort_values("year").itertuples():
                year = int(row.year)
                series.append(
                    {
                        "year": year,
                        "league": row.league,
                        "glory": value(row.glory, 2),
                        "forge": None
                        if pd.isna(row.forge)
                        else round(float(row.forge)),
                        "year_rank": year_rank.get((team, year), (None, None))[0],
                        "field": year_rank.get((team, year), (None, None))[1],
                    }
                )
        elo_series = []
        if team in elo_by_team:
            elo_series = [
                {"date": str(d)[:10], "elo": round(float(v), 1)}
                for d, v in zip(
                    elo_by_team[team]["date"], elo_by_team[team]["post_match_elo"]
                )
            ]
        current = latest.loc[team] if team in latest.index else None
        if isinstance(current, pd.DataFrame):  # duplicate team names across ids
            current = current.iloc[0]
        elo_summary = None
        if elo_series:
            peak = max(elo_series, key=lambda d: d["elo"])
            low = min(elo_series, key=lambda d: d["elo"])
            elo_summary = {
                "games": len(elo_series),
                "peak": peak,
                "low": low,
                "first": elo_series[0],
                "last": elo_series[-1],
            }
        ranked = [s for s in series if s["glory"] is not None]
        best = max(ranked, key=lambda s: s["glory"]) if ranked else None
        leagues = sorted({s["league"] for s in series})
        pages[slug] = {
            "teamname": team,
            "slug": slug,
            "series": series,
            "elo_series": elo_series,
            "elo_summary": elo_summary,
            "best": best,
            "current_elo": None if current is None else round(float(current["elo"])),
            "current_forge": round(float(forge_current[team]))
            if team in forge_current.index
            else None,
            "current_league": None if current is None else current["league"],
            "leagues": leagues or ([current["league"]] if current is not None else []),
            "roster": (rosters or {}).get(team),
        }
    return pages


def team_rosters(history, player_slugs, player_elos):
    """Each team's last lineup and its starters by season and role, keyed by team name.

    Args:
        history: `elo.get_player_history` rows (gameid, date, year, teamname,
            position, playerid, playername).
        player_slugs: playerid -> page slug, for players with a page.
        player_elos: playerid -> current player Elo.
    Returns:
        {teamname: {"last": {"date", "active", "players": [...]}, "seasons": [{"year", "roles": [...]}]}}.
        A player entry has name, slug (or None), role and games; in "last" also elo.
        Seasons are newest first; each role lists players by games for the team that
        year, the main starter first.
    """
    role_rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    newest = pd.to_datetime(history["date"]).max()
    rosters = {}

    def elo_of(pid):
        elo = player_elos.get(pid)
        return None if pd.isna(elo) else round(float(elo))

    last_game = history.drop_duplicates("teamname", keep="last")[
        ["teamname", "gameid", "date"]
    ]
    last = history.merge(last_game, on=["teamname", "gameid", "date"])
    # Teams in order of first appearance, each lineup in role order.
    last = last.assign(
        team_order=last.groupby("teamname", sort=False).ngroup(),
        role_order=last["position"].map(role_rank),
    ).sort_values(["team_order", "role_order"], kind="stable")
    for r in last.itertuples(index=False):
        roster = rosters.get(r.teamname)
        if roster is None:
            roster = rosters[r.teamname] = {
                "last": {
                    "date": r.date[:10],
                    "active": bool(pd.to_datetime(r.date) >= newest - ACTIVE_WINDOW),
                    "players": [],
                },
                "seasons": [],
            }
        roster["last"]["players"].append(
            {
                "name": r.playername,
                "slug": player_slugs.get(r.playerid),
                "role": r.position,
                "elo": elo_of(r.playerid),
            }
        )

    group = ["teamname", "year", "position"]
    counts = (
        history.groupby(group + ["playerid"])
        .agg(games=("gameid", "size"), name=("playername", "last"))
        .reset_index()
        .sort_values(
            ["teamname", "year", "position", "games"],
            ascending=[True, False, True, False],
            kind="mergesort",
        )
    )
    counts["more"] = (
        counts.groupby(group)["games"].transform("size") - 1 - ROSTER_EXTRAS
    )
    counts["rank"] = counts.groupby(group).cumcount()
    seasons = {}
    for r in counts[counts["rank"] <= ROSTER_EXTRAS].itertuples(index=False):
        roles = seasons.get((r.teamname, r.year))
        if roles is None:
            roles = seasons[(r.teamname, r.year)] = {
                role: {"role": role, "players": [], "more": 0} for role in ROLE_ORDER
            }
        if r.position in roles:
            roles[r.position]["players"].append(
                {
                    "name": r.name,
                    "slug": player_slugs.get(r.playerid),
                    "games": int(r.games),
                }
            )
            roles[r.position]["more"] = max(0, int(r.more))
    for (team, year), roles in seasons.items():
        rosters[team]["seasons"].append(
            {"year": int(year), "roles": list(roles.values())}
        )
    for roster in rosters.values():
        roster["seasons"].sort(key=lambda s: s["year"], reverse=True)
    return rosters


def write_team_index(pages):
    """teams.json for the header search: name, slug, league and last game.

    Ordered major-league teams first, then by last game, newest first; the search
    keeps this order among equally good matches.
    """
    teams = [
        {
            "n": p["teamname"],
            "s": p["slug"],
            "l": p["current_league"] or (p["leagues"][-1] if p["leagues"] else ""),
            "d": p["elo_summary"]["last"]["date"]
            if p["elo_summary"]
            else str(p["series"][-1]["year"]),
        }
        for p in pages.values()
    ]
    majors = set(env.globals["major_leagues"])
    teams.sort(key=lambda t: t["d"], reverse=True)
    teams.sort(key=lambda t: t["l"] not in majors)
    with open(os.path.join(site_config.OUTPUT_DIR, "teams.json"), "w") as f:
        f.write(json.dumps(teams, ensure_ascii=False, separators=(",", ":")))


def render_team_pages(pages):
    template = env.get_template("team.html.j2")
    for page in pages.values():
        _write(
            os.path.join(site_config.OUTPUT_DIR, "teams", f"{page['slug']}.html"),
            template.render(page_key="team", root_path="../", **page),
        )
