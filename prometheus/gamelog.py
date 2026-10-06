"""Game logs for team and player pages: every series played, game by game.

Oracle's Elixir has no series id, so a series is a run of a team's games against
one opponent with no more than `SERIES_GAP` between a game and the next. Each
game carries the result, side, length, the Elo change, the starting five (team
logs) or the champion and AURA (player logs), and our call before it: FORGE
between two teams from the same major league, Elo otherwise, the way the
Predictions page calls a match (`schedule.game_probability`), from the pre-game
Elo and pre-game Form. A series carries our chance of taking it (game 1's call
and the best-of read off the score) and Kalshi's last price before it started,
when there is one.

The logs are written as compact JSON (short keys, see `team_logs` and
`player_logs`) that `site_static/js/gamelog.js` renders: the newest series
embedded in each page, every series in a file fetched on request.
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus.forge import CROSS_REGION_ELO_WEIGHT, ELO_WEIGHT, FORM_POINTS
from prometheus.form import league_relative, load_weights as load_form_weights, scores
from prometheus.schedule import series_probability
from prometheus.types import ALL_MAJOR_LEAGUES
from prometheus.utils import get_engine

MAJORS = {l.value for l in ALL_MAJOR_LEAGUES}
# Longest wait between two games of one series (a Bo5 with a long pause, or games
# either side of midnight UTC). The same two teams rarely meet twice in a day.
SERIES_GAP = pd.Timedelta(hours=12)
# A Kalshi price belongs to the series between the same two teams starting nearest
# its scheduled start, within this window (Kalshi's times and ours can differ).
MARKET_WINDOW = pd.Timedelta(hours=36)
ROLE_ORDER = ["top", "jng", "mid", "bot", "sup"]
# Method codes in the JSON: FORGE, Elo within a league, Elo across leagues.
METHOD_CODES = {"forge": "F", "elo": "E", "elo-cross": "X"}


def load_team_games():
    """Every team-game with its opponent, side, length, result and Elo, oldest first."""
    stmt = """
    SELECT m.gameid, m.date, m.year, m.league, m.teamid, m.teamname, m.side, m.gamelength,
           m.result, o.teamid AS opp_id, o.teamname AS opp,
           e.pre_match_elo AS elo_pre, e.post_match_elo AS elo, e.elo_change,
           oe.pre_match_elo AS opp_elo_pre
    FROM matches m
    JOIN matches o ON o.gameid = m.gameid AND o.teamid != m.teamid
    LEFT JOIN game_length_elo e ON e.gameid = m.gameid AND e.teamid = m.teamid
    LEFT JOIN game_length_elo oe ON oe.gameid = o.gameid AND oe.teamid = o.teamid
    ORDER BY m.date, m.gameid, m.teamid
    """
    games = pd.read_sql(stmt, get_engine())
    games["when"] = pd.to_datetime(games["date"])
    return games


def load_player_games():
    """Every player-game: role, name, champion (when Oracle's Elixir has it) and player Elo before and after."""
    # Three plain reads merged here: SQLite has no index for these joins.
    engine = get_engine()
    players = pd.read_sql(
        "SELECT gameid, teamid, position, playerid, playername FROM match_players",
        engine,
    )
    champions = pd.read_sql(
        "SELECT gameid, teamid, position, champion FROM player_stats", engine
    )
    elos = pd.read_sql(
        "SELECT gameid, teamid, playerid, pre_match_elo AS elo_pre, post_match_elo AS elo FROM game_length_player_elo",
        engine,
    )
    return players.merge(
        champions, on=["gameid", "teamid", "position"], how="left"
    ).merge(elos, on=["gameid", "teamid", "playerid"], how="left")


def add_calls(games, states, form_weights=None):
    """Add `p` (chance this team wins the game, from before it) and `method` to `games`.

    `states` is `form.form_states` output for every game. Form is league-relative
    as FORGE's is (`form.league_relative`); a team-game without a Form state, or
    without pre-game Elo, gets no call.
    """
    if form_weights is None:
        form_weights = load_form_weights()["weights"]
    rel = league_relative(states, scores(states, form_weights, "pre_"))
    key = pd.MultiIndex.from_frame(states[["gameid", "teamid"]])
    form = pd.Series(FORM_POINTS * rel, index=key)
    home = pd.Series(states["home"].to_numpy(), index=key)

    own = pd.MultiIndex.from_arrays([games["gameid"], games["teamid"]])
    opp = pd.MultiIndex.from_arrays([games["gameid"], games["opp_id"]])
    f, of = form.reindex(own).to_numpy(), form.reindex(opp).to_numpy()
    h, oh = home.reindex(own).to_numpy(), home.reindex(opp).to_numpy()

    e, oe = games["elo_pre"].to_numpy(dtype=float), games["opp_elo_pre"].to_numpy(
        dtype=float
    )
    h, oh = pd.Series(h).fillna("").to_numpy(), pd.Series(oh).fillna("").to_numpy()
    cross = (h != "") & (oh != "") & (h != oh)
    forge = ~cross & pd.Series(h).isin(MAJORS).to_numpy() & ~np.isnan(f) & ~np.isnan(of)
    p = np.where(
        cross,
        1 / (1 + np.exp(-CROSS_REGION_ELO_WEIGHT * (e - oe))),
        np.where(
            forge,
            1 / (1 + np.exp(-ELO_WEIGHT * ((e + f) - (oe + of)))),
            1 / (1 + 10 ** ((oe - e) / 400)),
        ),
    )
    method = np.where(cross, "elo-cross", np.where(forge, "forge", "elo")).astype(
        object
    )
    unrated = np.isnan(e) | np.isnan(oe)
    p[unrated] = np.nan
    method[unrated] = None
    return games.assign(p=p, method=method)


def add_series(games):
    """Add `series`, an id shared by a team's consecutive games against one opponent.

    Ids are per team name, so the two sides of a series get different ids.
    """
    g = games.sort_values(["teamname", "when", "gameid"], kind="mergesort")
    new = (
        (g["teamname"] != g["teamname"].shift())
        | (g["opp"] != g["opp"].shift())
        | (g["when"] - g["when"].shift() > SERIES_GAP)
    )
    return games.assign(series=new.cumsum().reindex(games.index))


def best_of(wins, losses):
    """The shortest odd best-of a series with this score could be, or None for a tie (a Bo2)."""
    if wins == losses:
        return None
    return 2 * max(wins, losses) - 1


# ---------------------------------------------------------------- Kalshi


def load_prices(path, log=None):
    """Kalshi series prices: [{"t1", "t2", "start" (Timestamp, UTC), "p1", "ticker"}].

    `path` is the file `scripts/export_market_prices.py` writes (the last price
    before each settled series, from the market benchmark); it may be missing.
    `log` is the prediction log, whose matches keep the price read at the last
    build before the start; a match priced in both keeps the file's.
    """
    prices = []
    path = Path(path)
    if path.exists():
        prices = json.loads(path.read_text())
    seen = {p["ticker"] for p in prices}
    for entry in (log or {}).values():
        market = entry.get("market")
        if entry.get("matched") and market and market.get("ticker") not in seen:
            prices.append(
                {
                    "t1": entry["ours1"],
                    "t2": entry["ours2"],
                    "start": entry["start"],
                    "p1": market["p"],
                    "ticker": market.get("ticker"),
                }
            )
    for p in prices:
        start = pd.Timestamp(p["start"])
        p["start"] = start.tz_convert(None) if start.tzinfo else start
    return prices


class PriceBook:
    """Finds the Kalshi price for a series by its two teams and first game's time."""

    def __init__(self, prices):
        self.by_pair = {}
        for p in prices:
            self.by_pair.setdefault(frozenset((p["t1"], p["t2"])), []).append(p)

    def chance(self, team, opp, when):
        """(team's chance, ticker) from the nearest price within `MARKET_WINDOW`, or (None, None)."""
        options = [
            p
            for p in self.by_pair.get(frozenset((team, opp)), [])
            if abs(p["start"] - when) <= MARKET_WINDOW
        ]
        if not options:
            return None, None
        p = min(options, key=lambda p: abs(p["start"] - when))
        return (p["p1"] if p["t1"] == team else 1 - p["p1"]), p["ticker"]


# ---------------------------------------------------------------- logs


def _pct(p):
    """A chance as a whole percentage, never 0 or 100 (None stays None)."""
    if p is None or pd.isna(p):
        return None
    return min(99, max(1, round(p * 100)))


def _num(v, digits=0):
    if v is None or pd.isna(v):
        return None
    return round(float(v), digits) if digits else int(round(float(v)))


def _compact(d):
    """Drop empty fields and the default method (FORGE) to keep the JSON small."""
    return {k: v for k, v in d.items() if v is not None and not (k == "m" and v == "F")}


def series_heads(games, pricebook):
    """{series id: the fields a series row shows}, from each series' first game and score."""
    totals = games.groupby("series")["result"].agg(["sum", "size"])
    firsts = games.sort_values(["when", "gameid"], kind="mergesort").drop_duplicates(
        "series"
    )
    heads = {}
    for first in firsts.itertuples():
        wins = int(totals.at[first.series, "sum"])
        losses = int(totals.at[first.series, "size"]) - wins
        bo = best_of(wins, losses)
        p_series = (
            series_probability(first.p, bo)
            if bo is not None and not pd.isna(first.p)
            else None
        )
        kalshi, ticker = pricebook.chance(first.teamname, first.opp, first.when)
        heads[first.series] = _compact(
            {
                "d": first.date[:10],
                "l": first.league,
                "o": first.opp,
                "w": wins,
                "x": losses,
                "p": _pct(p_series),
                "m": METHOD_CODES.get(first.method),
                "k": _pct(kalshi),
                "kt": ticker,
            }
        )
    return heads


def _close(series):
    """Finish a series built game by game: its Elo change and the rating after it."""
    changes = [g["de"] for g in series["g"] if g["de"] is not None]
    series["de"] = round(sum(changes), 1) if changes else None
    series["e"] = series["g"][-1].pop("e", None)
    for g in series["g"]:
        g.pop("e", None)
    return _compact(series)


def team_logs(games, players, heads, player_slugs):
    """{teamname: {"players": [[name, slug], ...], "series": [...]}}, newest series first.

    `games` has `add_calls` and `add_series` applied; `players` is
    `load_player_games` output; `heads` is `series_heads`; `player_slugs` maps
    playerid to a page slug.

    A series: d (date of game 1), l (league), o (opponent), w and x (games won
    and lost), p (our chance of taking it, %), m (method code), k (Kalshi's
    chance, %), kt (Kalshi event ticker), de (Elo change over the series), e (Elo
    after it), g (games, in order). A game: r (1 won, 0 lost), t (length in
    seconds), s ("B" blue, "R" red), p (our chance, %), m, de, ro (the five
    starters, top to support, as indexes into "players"). Empty fields are left
    out, and so is m when the call is FORGE ("F").
    """
    rank = {r: i for i, r in enumerate(ROLE_ORDER)}
    lineup = players.assign(rank=players["position"].map(rank)).sort_values(
        ["gameid", "teamid", "rank"]
    )
    lineups = lineup.groupby(["gameid", "teamid"], sort=False).agg(
        ids=("playerid", list), names=("playername", list)
    )
    lineups = dict(zip(lineups.index, zip(lineups["ids"], lineups["names"])))

    logs = {}
    team = sid = None
    people = index = log = current = None
    ordered = games.sort_values(["teamname", "when", "gameid"], kind="mergesort")
    for g in ordered.itertuples():
        if g.teamname != team:
            team, sid, people, index = g.teamname, None, [], {}
            log = logs[team] = {"players": people, "series": []}
        if g.series != sid:
            sid = g.series
            current = {**heads[sid], "g": []}
            log["series"].append(current)
        ro = []
        ids, names = lineups.get((g.gameid, g.teamid), ((), ()))
        for pid, name in zip(ids, names):
            if pid not in index:
                index[pid] = len(people)
                people.append([name, player_slugs.get(pid)])
            ro.append(index[pid])
        current["g"].append(
            _compact(
                {
                    "r": int(g.result),
                    "t": int(g.gamelength),
                    "s": g.side[0],
                    "p": _pct(g.p),
                    "m": METHOD_CODES.get(g.method),
                    "de": _num(g.elo_change, 1),
                    "e": _num(g.elo),
                    "ro": ro,
                }
            )
        )
    for log in logs.values():
        log["series"] = [_close(s) for s in reversed(log["series"])]
    return logs


def player_logs(games, players, heads, player_slugs, aura_by_game=None):
    """{slug: {"teams": [name, ...], "series": [...]}} for players with a page, newest first.

    A series is the team's series (as in `team_logs`) cut to the games the player
    started, plus tm (index into "teams"); w and x stay the team's whole score.
    Its de and e are the player's Elo change and rating; a game has c (champion)
    and a (AURA in win-chance points, where `aura_by_game` has it) instead of ro.
    """
    aura_by_game = aura_by_game or {}
    listed = players[players["playerid"].isin(player_slugs.keys())]
    joined = listed.merge(
        games[
            [
                "gameid",
                "teamid",
                "teamname",
                "when",
                "side",
                "gamelength",
                "result",
                "p",
                "method",
                "series",
            ]
        ],
        on=["gameid", "teamid"],
    ).sort_values(["playerid", "when", "gameid"], kind="mergesort")

    logs = {}
    player = sid = None
    teams = index = log = current = None
    for g in joined.itertuples():
        if g.playerid != player:
            player, sid, teams, index = g.playerid, None, [], {}
            log = logs[player_slugs[player]] = {"teams": teams, "series": []}
        if g.series != sid:
            sid = g.series
            if g.teamname not in index:
                index[g.teamname] = len(teams)
                teams.append(g.teamname)
            current = {**heads[sid], "tm": index[g.teamname], "g": []}
            log["series"].append(current)
        change = None if pd.isna(g.elo) or pd.isna(g.elo_pre) else g.elo - g.elo_pre
        current["g"].append(
            _compact(
                {
                    "r": int(g.result),
                    "t": int(g.gamelength),
                    "s": g.side[0],
                    "p": _pct(g.p),
                    "m": METHOD_CODES.get(g.method),
                    "de": _num(change, 1),
                    "e": _num(g.elo),
                    "c": g.champion if isinstance(g.champion, str) else None,
                    "a": _num(aura_by_game.get((g.gameid, g.playerid)), 1),
                }
            )
        )
    for log in logs.values():
        log["series"] = [_close(s) for s in reversed(log["series"])]
    return logs


def year_records(series):
    """[[year, series won, series lost, games won, games lost]] newest first.

    A tied series (a Bo2 at 1–1) counts as neither won nor lost. Games are the
    ones in the log (for a player, the games they started).
    """
    years = {}
    for s in series:
        y = years.setdefault(s["d"][:4], [s["d"][:4], 0, 0, 0, 0])
        y[1] += s["w"] > s["x"]
        y[2] += s["w"] < s["x"]
        won = sum(g["r"] for g in s["g"])
        y[3] += won
        y[4] += len(s["g"]) - won
    return sorted(years.values(), reverse=True)
