"""Prop projections for upcoming matches, the apps' lines matched to our players,
and settled lines scored.

- `fixtures_from_log`: upcoming major and international matches from the prediction
  log (teams, best-of, our map-win chance).
- `project_fixtures`: each team's last starting five, projected over the series with
  `props.py`'s model (states after every game played so far; our FORGE or Elo
  call as each map's win chance).
- `match_lines`: an app's line (a player name and a team label) to one of our
  players, by folded name among players active lately, preferring a player whose
  team matches the label; then to a fixture by team and start time.
- `price_lines`: P(over), P(under) and P(push) for each matched line over the maps
  it counts, and the edge: against the break-even of a standard two-pick entry
  paying 3× (adjusted by the side's multiplier), and against Underdog's implied
  probability where it gives one.
- `update_calls` / `settle_lines` / `scorecard`: our chances for each line are
  saved until its start (then frozen, as the prediction log does); once the series
  is in our games, each saved call's result from the totals over its counted maps
  (a void when the player played none of them), and how our sides did.

Settlement assumes "Maps 1-3" counts the maps actually played among the first
three (every map is guaranteed in a Bo5, the case for every LoL line seen so
far); each app's rule for a Bo3 that ends 2-0 hasn't been confirmed.
"""

import json
import math

import numpy as np
import pandas as pd

from prometheus import props
from prometheus.gamelog import SERIES_GAP
from prometheus.schedule import fold
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES

ACTIVE_DAYS = 180
FIXTURE_LEAGUES = tuple(lg.value for lg in ALL_MAJOR_LEAGUES) + tuple(
    INTERNATIONAL_LEAGUES
)
# A standard two-pick entry pays 3×: each pick must win 1/√3 of the time.
BREAK_EVEN = 1 / math.sqrt(3)
LINE_STATS = ("kills", "assists", "deaths", "cs", "fantasy")


def load_lines(path):
    """Every logged line read, as a frame (empty when there is no log)."""
    try:
        with open(path) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        rows = []
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame["read_at"] = pd.to_datetime(frame["read_at"], utc=True)
    frame["start"] = pd.to_datetime(frame["start"], utc=True, format="mixed")
    return frame


def latest_lines(lines, now=None):
    """The newest read of each line, for lines that hadn't started at `now`."""
    if lines.empty:
        return lines
    newest = lines.sort_values("read_at").groupby(["source", "line_id"]).tail(1)
    if now is not None:
        newest = newest[newest["start"] > now]
    return newest.reset_index(drop=True)


def closing_lines(lines):
    """Each line's last read before its start (its closing line)."""
    if lines.empty:
        return lines
    before = lines[lines["read_at"] <= lines["start"]]
    return (
        before.sort_values("read_at")
        .groupby(["source", "line_id"])
        .tail(1)
        .reset_index(drop=True)
    )


# ---------------------------------------------------------------- fixtures


def log_entries(log):
    """The prediction log's matches, from the file's shape ({"matches": [...]}) or
    the build's (match id -> entry)."""
    return (
        log["matches"] if isinstance(log.get("matches"), list) else list(log.values())
    )


def fixtures_from_log(log, now, days_ahead=7, leagues=FIXTURE_LEAGUES):
    """Matched, upcoming matches in the major leagues and international events."""
    out = []
    for e in log_entries(log):
        start = (
            pd.Timestamp(e["start"]).tz_convert("UTC")
            if pd.Timestamp(e["start"]).tzinfo
            else pd.Timestamp(e["start"], tz="UTC")
        )
        if not e.get("matched") or (
            leagues is not None and e.get("league") not in leagues
        ):
            continue
        if not (
            now - pd.Timedelta(hours=3) <= start <= now + pd.Timedelta(days=days_ahead)
        ):
            continue
        out.append(
            {
                "match_id": e["match_id"],
                "start": start,
                "team1": e["ours1"],
                "team2": e["ours2"],
                "best_of": int(e["best_of"]),
                "league": e["league"],
                "event": e.get("event"),
                "p_game": e.get("p_game"),
            }
        )
    return sorted(out, key=lambda f: f["start"])


def last_rosters(games):
    """Each team's starters in its newest game: teamname -> rows (teamid, position,
    playerid, playername)."""
    last = games.sort_values("date").groupby("teamname")["gameid"].last()
    rows = games[games["gameid"].isin(last.values)]
    rows = rows[rows["teamname"].map(last) == rows["gameid"]]
    return dict(list(rows.groupby("teamname")))


def _upcoming_rows(games, fixtures, elos):
    """One synthetic row per starter per fixture (stats unknown), placed after
    every game played so its states are the current ones."""
    rosters = last_rosters(games)
    rows = []
    for f in fixtures:
        sides = [
            (f["team1"], f["team2"], f["p_game"]),
            (f["team2"], f["team1"], None if f["p_game"] is None else 1 - f["p_game"]),
        ]
        if not all(t in rosters for t, _, _ in sides):
            continue
        team_ids = {t: rosters[t]["teamid"].iloc[0] for t, _, _ in sides}
        for team, opp, p in sides:
            for r in rosters[team].itertuples():
                rows.append(
                    {
                        "gameid": f"next:{f['match_id']}",
                        "teamid": team_ids[team],
                        "teamname": team,
                        "opp_teamid": team_ids[opp],
                        "opp_teamname": opp,
                        "position": r.position,
                        "playerid": r.playerid,
                        "playername": r.playername,
                        "league": f["league"],
                        "date": f["start"].tz_localize(None),
                        "year": f["start"].year,
                        "elo": elos.get(team),
                        "opp_elo": elos.get(opp),
                        "p_map": np.nan if p is None else p,
                        "match_id": f["match_id"],
                        "best_of": f["best_of"],
                    }
                )
    return pd.DataFrame(rows)


def project_fixtures(games, fixtures, elos, model=None):
    """Project every fixture's starters with the published model (or `model`).

    `games` is every game (`props.load_prop_games()`, or `games_from_tables` in
    the build): rare leagues' paces reach back years, so a shorter history moves
    projections by several percent. `elos` maps our team names to current Elo. Returns (model, rows): one row per
    starter per fixture with their states, the map-win chance and the per-map win
    and loss means of each stat.
    """
    model = model or props.load_model()
    upcoming = _upcoming_rows(games, fixtures, elos)
    played = games.copy()
    if not upcoming.empty:
        upcoming = upcoming.assign(
            **dict.fromkeys(
                props.STATS
                + ("gamelength", "result", "minutes", "team_kills", "team_deaths"),
                np.nan,
            )
        )
    frame = pd.concat([played, upcoming], ignore_index=True, sort=False)
    frame = frame.sort_values(
        ["date", "gameid", "teamid", "position"], kind="mergesort"
    ).reset_index(drop=True)
    states = props.add_stat_states(frame, model.settings)
    is_next = states["gameid"].astype(str).str.startswith("next:")
    rows = states[is_next].reset_index(drop=True)
    if rows.empty:
        return model, rows
    rows["p"] = model.win_chance(rows)
    for stat in props.STATS:
        rows[f"{stat}_win"], rows[f"{stat}_loss"] = model.means(rows, stat)
    fw, sw, fl, sl = model.fantasy(rows)
    (
        rows["fantasy_win"],
        rows["fantasy_sd_win"],
        rows["fantasy_loss"],
        rows["fantasy_sd_loss"],
    ) = fw, sw, fl, sl
    return model, rows


def _maps(span):
    """Maps counted by a line: "1-3" -> 3, "1-2" -> 2; None for single maps."""
    if not span or "-" not in str(span):
        return None
    lo, hi = (int(x) for x in str(span).split("-"))
    return hi if lo == 1 else None


def distribution(model, row, stat, best_of, maps):
    """A projected row's pmf (count stats) or normal parts (fantasy) over the
    first `maps` maps of a best-of-`best_of`."""
    frame = pd.DataFrame([row])
    p = np.array([row["p"]])
    if stat == "fantasy":
        return props.series_normal(
            np.array([row["fantasy_win"]]), np.array([row["fantasy_sd_win"]]),
            np.array([row["fantasy_loss"]]), np.array([row["fantasy_sd_loss"]]),
            p, best_of, maps,
        )  # fmt: skip
    win = props.nb_pmf(
        [row[f"{stat}_win"]], model.alphas(frame, stat, 1), props.SUPPORT[stat]
    )
    loss = props.nb_pmf(
        [row[f"{stat}_loss"]], model.alphas(frame, stat, 0), props.SUPPORT[stat]
    )
    return props.series_pmf(win, loss, p, best_of, maps)[0]


def summary(dist):
    """Mean, median and the 10th and 90th percentiles of a pmf or normal parts."""
    if isinstance(dist, list):
        grid = np.linspace(-50, 400, 4501)
        from scipy import stats as st

        cdf = sum(w[0] * st.norm.cdf((grid - m[0]) / s[0]) for w, m, s in dist)
        mean = float(sum(w[0] * m[0] for w, m, _ in dist))
        q = lambda x: float(grid[np.searchsorted(cdf, x)])
        return {"mean": mean, "median": q(0.5), "p10": q(0.1), "p90": q(0.9)}
    k = np.arange(len(dist))
    cdf = np.cumsum(dist)
    q = lambda x: int(np.searchsorted(cdf, x))
    return {
        "mean": float((dist * k).sum()),
        "median": q(0.5),
        "p10": q(0.1),
        "p90": q(0.9),
    }


def chances(dist, line):
    """(P(over), P(under), P(push)) of a pmf or normal parts at `line`."""
    if isinstance(dist, list):
        from scipy import stats as st

        under = float(sum(w[0] * st.norm.cdf((line - m[0]) / s[0]) for w, m, s in dist))
        return 1 - under, under, 0.0
    k = np.arange(len(dist))
    over = float(dist[k > line].sum())
    push = float(dist[k == line].sum())
    return over, 1 - over - push, push


# ---------------------------------------------------------------- matching


def player_index(games, now, days=ACTIVE_DAYS):
    """Players who started within `days` of `now`, each with their newest team."""
    recent = games[
        games["date"]
        >= (now.tz_localize(None) if now.tzinfo else now) - pd.Timedelta(days=days)
    ]
    newest = recent.sort_values("date").groupby("playerid").tail(1)
    out = newest[
        ["playerid", "playername", "teamid", "teamname", "position", "date"]
    ].copy()
    out["key"] = out["playername"].map(fold)
    return out


def _team_fits(label, teamname):
    """Whether an app's team label (an abbreviation or a full name) fits our name."""
    if not isinstance(label, str) or not label:
        return False
    a, b = fold(label), fold(teamname)
    if a == b or b.startswith(a) or a.startswith(b):
        return True
    initials = "".join(w[0] for w in teamname.split() if w and w[0].isalnum()).lower()
    return a == initials


def resolve_player(name, team, index):
    """Our player for an app's (name, team label), or None."""
    if not isinstance(name, str) or "+" in name:
        return None
    cands = index[index["key"] == fold(name)]
    if cands.empty:
        return None
    fits = cands[[_team_fits(team, t) for t in cands["teamname"]]]
    pick = fits if not fits.empty else cands
    return pick.sort_values("date").iloc[-1]


def match_lines(lines, index, fixtures, tolerance=SERIES_GAP):
    """Add `playerid`, `teamname` and `match_id` to each line we can place."""
    out = lines.copy()
    for col in ("playerid", "teamname", "match_id"):
        out[col] = None
    for i, row in out.iterrows():
        player = resolve_player(row["player"], row.get("team"), index)
        if player is None:
            continue
        out.at[i, "playerid"], out.at[i, "teamname"] = (
            player["playerid"],
            player["teamname"],
        )
        start = row["start"]
        for f in fixtures:
            if (
                player["teamname"] in (f["team1"], f["team2"])
                and pd.notna(start)
                and abs(f["start"] - start) <= tolerance
            ):
                out.at[i, "match_id"] = f["match_id"]
                break
    return out


def _usable(line):
    """Whether we price this line at all: a stat we project over maps 1-N."""
    if line.get("stat") not in LINE_STATS or _maps(line.get("maps")) is None:
        return False
    if line.get("line") is None or pd.isna(line.get("line")):
        return False
    # Only Pick6's fantasy scoring is known.
    return line["stat"] != "fantasy" or line["source"] == "pick6"


def price_line(line, over, under, push, spread):
    """One line's call: our chances, the pick among the sides the app offers (the
    larger edge over its break-even) and the edge over the app's own chance."""
    decided = max(over + under, 1e-9)
    out = {**line, **spread, "p_over": over, "p_under": under, "p_push": push}
    offered = {}
    for side, p in (("over", over), ("under", under)):
        mult = line.get(f"{side}_mult")
        if mult is not None and not pd.isna(mult):
            offered[side] = (p / decided, p / decided - BREAK_EVEN / mult)
    if offered:
        side = max(offered, key=lambda k: offered[k][1])
        out.update(side=side, p_side=offered[side][0], edge=offered[side][1])
    else:
        out.update(side=None, p_side=None, edge=None)
    if line.get("over_prob") is not None and not pd.isna(line.get("over_prob")):
        out["edge_market"] = over / decided - line["over_prob"]
    return out


def price_lines(model, lines, projected, fixtures):
    """Our chances for every matched line of a stat we project."""
    by_fixture = {f["match_id"]: f for f in fixtures}
    proj = {(r["match_id"], r["playerid"]): r for r in projected.to_dict("records")}
    rows = []
    for line in lines.to_dict("records"):
        key = (line.get("match_id"), line.get("playerid"))
        if key not in proj or not _usable(line):
            continue
        f = by_fixture[line["match_id"]]
        maps = min(_maps(line["maps"]), f["best_of"])
        dist = distribution(model, proj[key], line["stat"], f["best_of"], maps)
        rows.append(price_line(line, *chances(dist, line["line"]), summary(dist)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- the hourly refresh
#
# The daily build publishes every projected player's spread (`spread_table`,
# `props-dist.json`); the hourly job (`scripts/update_props.py`, no database)
# matches the newest lines to those players and prices them from it
# (`price_from_table`), saves the calls and writes `props-lines.json` for the page.

CDF_TAIL = 0.0005  # a spread keeps the counts between these tails of its cdf
COUNT_STATS = ("kills", "assists", "deaths", "cs")


def map_counts(best_of):
    """The map counts a line may use for a best-of: maps 1-2 and 1-3 of a Bo3 or
    Bo5, the one map of a Bo1."""
    return [1] if best_of == 1 else [2, 3]


def compact_cdf(pmf):
    """A pmf as {"lo": first count kept, "cdf": cumulative chances from it}, the
    tails beyond `CDF_TAIL` cut (below lo the cdf is 0, past the end 1)."""
    cdf = np.cumsum(pmf)
    lo = int(np.searchsorted(cdf, CDF_TAIL))
    hi = int(np.searchsorted(cdf, 1 - CDF_TAIL))
    return {"lo": lo, "cdf": [round(float(c), 4) for c in cdf[lo : hi + 1]]}


def cdf_at(spread, k):
    """P(X <= k) from a compact cdf."""
    if k < spread["lo"]:
        return 0.0
    i = int(k) - spread["lo"]
    return 1.0 if i >= len(spread["cdf"]) else spread["cdf"][i]


def cdf_chances(spread, line):
    """(P(over), P(under), P(push)) at `line` from a compact cdf."""
    floor = math.floor(line)
    if floor == line:
        under = cdf_at(spread, line - 1)
        push = cdf_at(spread, line) - under
    else:
        under, push = cdf_at(spread, floor), 0.0
    return 1.0 - under - push, under, push


def cdf_summary(spread):
    """Median and 10th and 90th percentiles of a compact cdf."""
    cdf = np.asarray(spread["cdf"])
    q = lambda x: spread["lo"] + int(np.searchsorted(cdf, x))
    return {"median": q(0.5), "p10": q(0.1), "p90": q(0.9)}


def spread_table(model, rows, fixtures, now):
    """Every projected starter's spreads over the map counts lines may use, with
    what matching needs (name key, team, the match): the `props-dist.json` file."""
    by_fixture = {f["match_id"]: f for f in fixtures}
    matches = {}
    for r in rows.to_dict("records"):
        f = by_fixture[r["match_id"]]
        m = matches.setdefault(
            f["match_id"],
            {
                "match_id": f["match_id"],
                "start": f["start"].strftime("%Y-%m-%dT%H:%MZ"),
                "team1": f["team1"],
                "team2": f["team2"],
                "best_of": f["best_of"],
                "players": [],
            },
        )
        spreads = {
            stat: {
                str(maps): compact_cdf(distribution(model, r, stat, f["best_of"], maps))
                for maps in map_counts(f["best_of"])
            }
            for stat in COUNT_STATS
        }
        m["players"].append(
            {
                "playerid": r["playerid"],
                "name": r["playername"],
                "team": r["teamname"],
                "spreads": spreads,
            }
        )
    return {"at": now.strftime("%Y-%m-%dT%H:%MZ"), "matches": list(matches.values())}


def table_fixtures(table):
    return [
        {
            **{k: m[k] for k in ("match_id", "team1", "team2", "best_of")},
            "start": pd.Timestamp(m["start"]),
        }
        for m in table["matches"]
    ]


def table_index(table):
    """`player_index` for the players in a spread table."""
    rows = [
        {
            "playerid": p["playerid"],
            "playername": p["name"],
            "teamname": p["team"],
            "date": pd.Timestamp(m["start"]),
        }
        for m in table["matches"]
        for p in m["players"]
    ]
    index = pd.DataFrame(rows, columns=["playerid", "playername", "teamname", "date"])
    index["key"] = index["playername"].map(fold)
    return index.drop_duplicates("playerid", keep="last")


def price_from_table(lines, table):
    """Match the newest lines to the table's players and price them from their
    spreads. Returns (priced lines, the table's fixtures)."""
    fixtures = table_fixtures(table)
    if lines.empty or not fixtures:
        return pd.DataFrame(), fixtures
    matched = match_lines(lines, table_index(table), fixtures)
    spreads = {
        (m["match_id"], p["playerid"]): p["spreads"]
        for m in table["matches"]
        for p in m["players"]
    }
    by_fixture = {f["match_id"]: f for f in fixtures}
    rows = []
    for line in matched.to_dict("records"):
        key = (line.get("match_id"), line.get("playerid"))
        if key not in spreads or not _usable(line) or line["stat"] not in COUNT_STATS:
            continue
        maps = min(_maps(line["maps"]), by_fixture[line["match_id"]]["best_of"])
        spread = spreads[key][line["stat"]].get(str(maps))
        if spread is None:
            continue
        rows.append(
            price_line(line, *cdf_chances(spread, line["line"]), cdf_summary(spread))
        )
    return pd.DataFrame(rows), fixtures


# ---------------------------------------------------------------- settlement


def series_totals(games, team, opp, start, maps, tolerance=SERIES_GAP):
    """Each starter's totals over the first `maps` maps of `team`'s series against
    `opp` near `start`: playerid -> {stat: total, "maps": maps played}. Empty if
    the series isn't in our games yet."""
    when = start.tz_localize(None) if start.tzinfo else start
    g = games[(games["teamname"] == team) & (games["opp_teamname"] == opp)]
    g = g[(g["date"] - when).abs() <= tolerance]
    if g.empty:
        return {}
    first = g.sort_values("date")["series"].iloc[0]
    g = g[(g["series"] == first) & (g["map"] <= maps)]
    g = g.assign(fantasy=props.fantasy_points(g))
    totals = g.groupby("playerid")[list(props.STATS) + ["fantasy"]].sum()
    totals["maps"] = g.groupby("playerid").size()
    return totals.to_dict("index")


def update_calls(calls, priced, fixtures, now):
    """Save our chances for every priced line that hasn't started, keyed by
    "source|line_id"; a line's call is refreshed until its start, then frozen.
    Each call keeps what settling needs (team, opponent, start, maps)."""
    by_fixture = {f["match_id"]: f for f in fixtures}
    stamp = now.strftime("%Y-%m-%dT%H:%MZ")
    for row in priced.to_dict("records"):
        f = by_fixture.get(row.get("match_id"))
        start = row.get("start")
        if f is None or pd.isna(start) or start <= now:
            continue
        opp = f["team2"] if row["teamname"] == f["team1"] else f["team1"]
        key = f"{row['source']}|{row['line_id']}"
        calls[key] = {
            "source": row["source"],
            "line_id": row["line_id"],
            "player": row["player"],
            "playerid": row["playerid"],
            "team": row["teamname"],
            "opp": opp,
            "match_id": row["match_id"],
            "start": f["start"].strftime("%Y-%m-%dT%H:%MZ"),
            "best_of": f["best_of"],
            "stat": row["stat"],
            "maps": row["maps"],
            "line": row["line"],
            "over_mult": _clean(row.get("over_mult")),
            "under_mult": _clean(row.get("under_mult")),
            "over_prob": _clean(row.get("over_prob")),
            "p_over": round(row["p_over"], 4),
            "p_under": round(row["p_under"], 4),
            "median": row["median"],
            "side": row.get("side"),
            "p_side": _clean(row.get("p_side")),
            "edge": _clean(row.get("edge")),
            "first_priced": calls.get(key, {}).get("first_priced", stamp),
            "priced": stamp,
        }
    return calls


def _clean(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else v


def settle_lines(calls, games, now):
    """Saved calls whose series is in our games, each with `actual` and `result`
    ("over", "under", "push" or "void": the player played none of its maps)."""
    due = [c for c in calls.values() if pd.Timestamp(c["start"]) <= now]
    if not due:
        return pd.DataFrame()
    # Only the games around the calls' matches, and each match side's totals once:
    # scanning every game per call made settling the slowest part of the build.
    starts = pd.to_datetime([c["start"] for c in due]).tz_localize(None)
    window = (games["date"] >= starts.min() - SERIES_GAP) & (
        games["date"] <= starts.max() + SERIES_GAP
    )
    near = games[window]
    cache = {}
    rows = []
    for call in due:
        start = pd.Timestamp(call["start"])
        key = (call["team"], call["opp"], call["start"], _maps(call["maps"]))
        if key not in cache:
            cache[key] = series_totals(near, *key[:2], start, key[3])
        totals = cache[key]
        if not totals:
            continue
        mine = totals.get(call["playerid"])
        if mine is None or mine["maps"] == 0:
            rows.append({**call, "actual": None, "result": "void"})
            continue
        actual = mine[call["stat"]]
        line = call["line"]
        result = "push" if actual == line else ("over" if actual > line else "under")
        rows.append({**call, "actual": actual, "result": result})
    return pd.DataFrame(rows)


def scorecard(settled, min_edge=0.0):
    """How our sides did on settled lines (pushes and voids left out): picks, hit
    rate against the break-even, our log loss and, on Underdog lines, Underdog's."""
    if settled.empty:
        return {"n": 0}
    s = settled[settled["result"].isin(["over", "under"]) & settled["side"].notna()]
    s = s[s["edge"].astype(float) >= min_edge]
    if s.empty:
        return {"n": 0}
    won = (s["result"] == s["side"]).to_numpy()
    went_over = (s["result"] == "over").to_numpy()
    p_over = (
        (s["p_over"] / (s["p_over"] + s["p_under"])).clip(1e-6, 1 - 1e-6).to_numpy()
    )
    out = {
        "n": len(s),
        "matches": s["match_id"].nunique(),
        "hit_rate": float(won.mean()),
        "break_even": BREAK_EVEN,
        "log_loss": float(
            -np.mean(np.where(went_over, np.log(p_over), np.log(1 - p_over)))
        ),
    }
    market = s[s["over_prob"].notna()] if "over_prob" in s else s.iloc[0:0]
    if not market.empty:
        m_over = (market["result"] == "over").to_numpy()
        ours = (
            (market["p_over"] / (market["p_over"] + market["p_under"]))
            .clip(1e-6, 1 - 1e-6)
            .to_numpy()
        )
        theirs = market["over_prob"].astype(float).clip(1e-6, 1 - 1e-6).to_numpy()
        out["market_n"] = len(market)
        out["market_log_loss_ours"] = float(
            -np.mean(np.where(m_over, np.log(ours), np.log(1 - ours)))
        )
        out["market_log_loss_theirs"] = float(
            -np.mean(np.where(m_over, np.log(theirs), np.log(1 - theirs)))
        )
    return out
