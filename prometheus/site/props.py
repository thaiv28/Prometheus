"""The Props page: projections for every starter in the coming major and
international matches, the pick'em apps' lines beside them, and how saved calls
on those lines settled."""

import datetime
import json
import os

import numpy as np
import pandas as pd

from prometheus import props, props_live
from prometheus.site import config as site_config
from prometheus.site.config import PROPS, ROLE_ORDER
from prometheus.site.render import env, slugify, write

APPS = (("underdog", "Underdog"), ("prizepicks", "PrizePicks"), ("pick6", "Pick6"))
STATS = (("kills", "Kills"), ("assists", "Assists"), ("deaths", "Deaths"), ("cs", "CS"))
ROLE_NAMES = {
    "top": "Top",
    "jng": "Jungle",
    "mid": "Mid",
    "bot": "Bot",
    "sup": "Support",
}
RECENT_MAPS = 10


def default_maps(best_of):
    """The maps a line usually counts: three of a Bo5, two of a Bo3, one of a Bo1."""
    return {5: 3, 3: 2}.get(best_of, 1)


def _load_calls(path):
    try:
        with open(path) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def recent_means(games, n=RECENT_MAPS):
    """Each player's mean of every stat over their last `n` maps."""
    last = games.sort_values("date").groupby("playerid").tail(n)
    return last.groupby("playerid")[list(props.STATS)].mean()


def _pct(p):
    return int(min(99, max(1, round(100 * p))))


def line_cell(line):
    """One app's line as a register cell."""
    over = line["p_over"] / max(line["p_over"] + line["p_under"], 1e-9)
    cell = {
        "line": f"{line['line']:g}",
        "over": _pct(over),
        "side": line.get("side"),
        "one_sided": line.get("under_mult") is None or pd.isna(line.get("under_mult")),
    }
    side = line.get("side")
    if side:
        mult = line.get(f"{side}_mult") or 1.0
        cell["break_even"] = _pct(props_live.BREAK_EVEN / mult)
        cell["p_side"] = _pct(line["p_side"])
        cell["clears"] = bool(line["edge"] > 0)
    if line.get("over_prob") is not None and not pd.isna(line.get("over_prob")):
        cell["app_over"] = _pct(float(line["over_prob"]))
    return cell


def match_view(fixture, rows, priced, recent, team_slugs, player_slugs):
    """One match: its caption fields and, per stat, both teams' starters."""
    start = fixture["start"]
    p_series = fixture.get("p_series")
    maps = default_maps(fixture["best_of"])
    lines = {}
    if not priced.empty:
        mine = priced[priced["match_id"] == fixture["match_id"]]
        # PrizePicks' standard line (both sides offered) before its demon and goblin lines.
        mine = mine.assign(
            _alt=mine["side"].isna() | mine["under_mult"].isna()
        ).sort_values("_alt", kind="mergesort")
        for line in mine.to_dict("records"):
            # One line per player, stat and app: the standard line where several.
            lines.setdefault((line["playerid"], line["stat"], line["source"]), line)
            maps = props_live._maps(line["maps"]) or maps
    teams = []
    for team in (fixture["team1"], fixture["team2"]):
        mine = rows[rows["teamname"] == team]
        mine = mine.assign(order=mine["position"].map(ROLE_ORDER.index)).sort_values(
            "order"
        )
        teams.append(
            {
                "name": team,
                "slug": slugify(team) if slugify(team) in team_slugs else None,
                "players": mine,
            }
        )
    stats = []
    for stat, label in STATS:
        stat_teams = []
        for t in teams:
            players = []
            for r in t["players"].to_dict("records"):
                dist = props_live.distribution(
                    fixture["model"],
                    r,
                    stat,
                    fixture["best_of"],
                    min(maps, fixture["best_of"]),
                )
                s = props_live.summary(dist)
                avg = (
                    recent.loc[r["playerid"], stat] * maps
                    if r["playerid"] in recent.index
                    else None
                )
                cells = {}
                for app, _ in APPS:
                    line = lines.get((r["playerid"], stat, app))
                    if line is not None:
                        cells[app] = line_cell(line)
                players.append(
                    {
                        "role": ROLE_NAMES.get(r["position"], r["position"]),
                        "name": r["playername"],
                        "slug": player_slugs.get(r["playerid"]),
                        "median": s["median"],
                        "p10": s["p10"],
                        "p90": s["p90"],
                        "recent": None if avg is None or np.isnan(avg) else avg,
                        "lines": cells,
                    }
                )
            stat_teams.append(
                {"name": t["name"], "slug": t["slug"], "players": players}
            )
        stats.append(
            {
                "key": stat,
                "label": label,
                "teams": stat_teams,
                "n_lines": sum(
                    len(p["lines"]) for t in stat_teams for p in t["players"]
                ),
            }
        )
    return {
        "id": fixture["match_id"],
        "start": start.strftime("%Y-%m-%dT%H:%MZ"),
        "day": f"{start.strftime('%A')} {start.day} {start.strftime('%B')}",
        "time": start.strftime("%H:%M"),
        "league": fixture["league"],
        "event": fixture.get("event") or "",
        "best_of": fixture["best_of"],
        "maps": maps,
        "team1": teams[0]["name"],
        "team2": teams[1]["name"],
        "slug1": teams[0]["slug"],
        "slug2": teams[1]["slug"],
        "pct1": None if p_series is None else _pct(p_series),
        "stats": stats,
        "n_lines": sum(s["n_lines"] for s in stats),
    }


def scorecard_rows(settled):
    """The record per app and in all: settled calls, our sides' hit rate against
    the break-even, and log loss (ours and, on Underdog, Underdog's)."""
    rows = []
    groups = [
        (label, settled[settled["source"] == app] if not settled.empty else settled)
        for app, label in APPS
    ]
    groups.append(("All", settled))
    for label, part in groups:
        card = props_live.scorecard(part) if not part.empty else {"n": 0}
        rows.append({"label": label, **card})
    return rows


def build_props(games, prediction_log, latest_elos, team_slugs, player_slugs, now=None):
    """Project the coming matches, price the newest lines, save the calls and
    settle the old ones. Returns the page's view."""
    now = now or datetime.datetime.now(datetime.UTC)
    now = pd.Timestamp(now)
    # Every rated match is a candidate; the page keeps the major leagues and
    # international events, and any other match the apps post lines for.
    candidates = props_live.fixtures_from_log(prediction_log, now, leagues=None)
    lines = props_live.load_lines(site_config.PROP_LINES)
    index = props_live.player_index(games, now)
    current = props_live.latest_lines(lines, now) if not lines.empty else lines
    matched = (
        props_live.match_lines(current, index, candidates)
        if not current.empty
        else current
    )
    with_lines = set(matched["match_id"].dropna()) if not matched.empty else set()
    fixtures = [
        f
        for f in candidates
        if f["league"] in props_live.FIXTURE_LEAGUES or f["match_id"] in with_lines
    ]
    for f, e in zip(fixtures, _entries(prediction_log, fixtures), strict=True):
        f["p_series"] = e.get("p_series")
    elos = dict(zip(latest_elos["teamname"], latest_elos["elo"], strict=False))
    model, rows = props_live.project_fixtures(games, fixtures, elos)
    priced = pd.DataFrame()
    if not matched.empty and not rows.empty:
        priced = props_live.price_lines(model, matched, rows, fixtures)
    calls = _load_calls(site_config.PROP_CALLS)
    if not priced.empty:
        props_live.update_calls(calls, priced, fixtures, now)
        os.makedirs(os.path.dirname(site_config.PROP_CALLS) or ".", exist_ok=True)
        with open(site_config.PROP_CALLS, "w") as f:
            json.dump(calls, f, indent=1)
    settled = props_live.settle_lines(calls, games, now) if calls else pd.DataFrame()
    recent = recent_means(games)
    matches = []
    for f in fixtures:
        f["model"] = model
        mine = rows[rows["match_id"] == f["match_id"]] if not rows.empty else rows
        if mine.empty:
            continue
        matches.append(match_view(f, mine, priced, recent, team_slugs, player_slugs))
    reads = (
        lines["read_at"] if not lines.empty else pd.Series(dtype="datetime64[ns, UTC]")
    )
    return {
        "matches": matches,
        "lines_total": int(sum(m["n_lines"] for m in matches)),
        "lines_since": None if reads.empty else reads.min().strftime("%Y-%m-%d"),
        "lines_read": None if reads.empty else reads.max().strftime("%Y-%m-%dT%H:%MZ"),
        "scorecard": scorecard_rows(settled),
        "settled": 0
        if settled.empty
        else int(settled["result"].isin(["over", "under"]).sum()),
        "apps": [{"key": k, "label": label} for k, label in APPS],
        "stats": [{"key": k, "label": label} for k, label in STATS],
        "break_even": _pct(props_live.BREAK_EVEN),
    }


def _entries(log, fixtures):
    by_id = {e["match_id"]: e for e in props_live.log_entries(log)}
    return [by_id[f["match_id"]] for f in fixtures]


def render_props(view):
    write(
        os.path.join(site_config.OUTPUT_DIR, "props.html"),
        env.get_template("props.html.j2").render(
            page_key="props", root_path="", metric=PROPS, view=view
        ),
    )
