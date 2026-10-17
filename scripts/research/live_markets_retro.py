"""
live_markets_retro.py: our in-game calls against Kalshi's in-game prices, replayed.

The live pages' in-game model (`prometheus/live/time_model_v1.json`, trained on
2022-2023, calibrated on 2024) is replayed over saved Riot live-stats feed
timelines (`data/feed_timelines/games/`, about one sample a minute) for every
map that has a settled Kalshi map market (`KXLOLMAP`, from late 2025, so every
scored map is outside the model's training years). Kalshi's side is its trade
tape: every trade on both teams' contracts, with its time to the millisecond
and which side took the book.

Our call from a feed sample with source time `s` reaches us at `s + lag`. The
live pilot (KC-C9, Worlds 2026 maps 4-5) measured that lag from its request
log: the newest frame received was never under 20 s old, median 21 s on the
map polled steadily (26 s on the other). Kalshi trades on the broadcast and is
always ahead of our feed, so a bet is placed only when the market has been
quiet (no trade on either contract) for `quiet` seconds before our call
arrives, at the price of the last trade that backed our side.

Reported, each over whole series resampled together (maps in a series and
minutes in a map are not independent):

1. log loss and Brier, ours against Kalshi's last trade price when our call
   arrives, at fixed game minutes, with the paired difference;
2. our weight beside the market: a logistic fit of the result on both
   log-odds; above zero means we add something Kalshi's price lacks;
4. paper bets: the first time in a map our chance beats the price of backing
   that side by the edge while the market is quiet, at flat $1 and at quarter
   Kelly, after Kalshi's taker fee; with closing-line value two minutes later;
5. the gap between our call and Kalshi's price, how often the market trades,
   and the implied spread (both sides' last costs, recent trades only).

What a trade tape can't show: quotes that move with no trade. "Quiet" here
means no trade, and the price paid is the last trade's, not the live ask.
Feed samples are about a minute apart, so we get a call a minute where the live
service gets one every few seconds. The game clock is estimated from the feed
(pauses between samples are missed).

Usage:
    uv run python scripts/research/live_markets_retro.py --out docs/research/live_markets_retro.md
    uv run python scripts/research/live_markets_retro.py --offline   # cached trades only

Trades are cached under `data/research/live_markets/trades/` (settled markets
don't change). The first run fetches about 800 trade tapes (a few minutes).
"""

import argparse
import datetime as dt
import difflib
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from prometheus import markets, schedule
from prometheus.elo import get_latest_elos
from prometheus.evaluation import game_losses, resamples
from prometheus.live import timeline

TIMELINES = ROOT / "data" / "feed_timelines" / "games"
MARKET_LIST = ROOT / "data" / "markets" / f"{markets.MAP}.json"
CACHE = ROOT / "data" / "research" / "live_markets"
MODEL = ROOT / "prometheus" / "live" / "time_model_v1.json"
DB = ROOT / "db" / "prometheus.db"

KALSHI_START = "2025-10-27"  # first KXLOLMAP market
LAGS = (0, 10, 21, 30)  # seconds from a feed sample's source time to our call
LAG = 21  # measured on the live pilot
QUIETS = (0, 10, 21, 30)  # seconds with no trade before a bet
EDGES = (0.03, 0.05, 0.10, 0.15)
EDGE = 0.05
KELLY = 0.25
MINUTES = (0, 5, 10, 15, 20, 25, 30)
CALL_WINDOW = (
    90  # a checkpoint's call is the last one up to this many seconds before it
)
STALE = 300  # a price older than this (seconds) is no price
BET_STALE = 120  # the cost to back a side comes from a trade at most this old
CLV_AFTER = 120  # closing-line value: our side's price this long after the bet
N_RESAMPLES = 2000

# Words too common in team names to identify a team.
GENERIC = {"esports", "esport", "gaming", "team", "club", "e", "sports", "the", "gg"}


# ---------------------------------------------------------------- matching


def _tokens(name):
    return set(schedule.fold(name).split()) - GENERIC


def name_similarity(team, kalshi_name):
    """How well a feed team ({name, code}) fits a Kalshi team name (0-1)."""
    k = schedule.fold(kalshi_name)
    best = difflib.SequenceMatcher(None, schedule.fold(team["name"]), k).ratio()
    shared = _tokens(team["name"]) & _tokens(kalshi_name)
    code = schedule.fold(team.get("code") or "")
    if any(len(t) >= 2 for t in shared) or (len(code) >= 2 and code in k.split()):
        best = max(best, 0.9)
    return best


def _pair_fits(a, b):
    """Both names fit, or one fits well and the other partly (sponsor names)."""
    return min(a, b) >= 0.6 or (max(a, b) >= 0.85 and min(a, b) >= 0.4)


def match_market(game, rows):
    """(Kalshi map event, feed team 0 is Kalshi's team1) for a feed game, or None
    when no event or more than one fits. `rows` are settled map events for the
    game's map number."""
    start = dt.datetime.fromisoformat(game["start"])
    a, b = game["teams"]
    fits = []
    for r in rows:
        window = dt.timedelta(hours=8 if r["timed"] else 32)
        if not dt.timedelta(hours=-1) < start - r["start"] < window:
            continue
        straight = (name_similarity(a, r["team1"]), name_similarity(b, r["team2"]))
        flipped = (name_similarity(a, r["team2"]), name_similarity(b, r["team1"]))
        for scores, same in ((straight, True), (flipped, False)):
            if _pair_fits(*scores):
                fits.append((sum(scores), r, same))
    fits.sort(key=lambda f: -f[0])
    if not fits or (len(fits) > 1 and fits[1][1] is not fits[0][1]):
        return None
    return fits[0][1], fits[0][2]


def load_games():
    games = []
    for path in sorted(TIMELINES.glob("*.json")):
        g = json.loads(path.read_text())
        if g.get("start") and g["start"] >= KALSHI_START and not g.get("error"):
            games.append(g)
    return games


def feed_winner(game, blue):
    """Team (0 or 1) with more towers at the end (a mismatch check), or None."""
    final = game.get("final") or {}
    sides = ["blue", "red"] if blue == 0 else ["red", "blue"]
    towers = [(final.get(s) or {}).get("towers") for s in sides]
    if None in towers or towers[0] == towers[1]:
        return None
    return int(towers[1] > towers[0])


# ---------------------------------------------------------------- Kalshi trades


def fetch_trades(ticker, min_ts, max_ts, historical):
    """Every trade on one market between two Unix times, oldest first, cached."""
    path = CACHE / "trades" / f"{ticker}.json"
    if path.exists():
        return json.loads(path.read_text())
    endpoint = "/historical/trades" if historical else "/markets/trades"
    trades, cursor = [], None
    while True:
        query = {"ticker": ticker, "min_ts": min_ts, "max_ts": max_ts, "limit": 1000}
        if cursor:
            query["cursor"] = cursor
        page = markets.get(endpoint, **query)
        trades += page.get("trades", [])
        cursor = page.get("cursor")
        if not cursor or not page.get("trades"):
            break
        time.sleep(0.1)
    trades.sort(key=lambda t: t["created_time"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(trades))
    return trades


def cached_trades(ticker):
    path = CACHE / "trades" / f"{ticker}.json"
    return json.loads(path.read_text()) if path.exists() else None


def tape(event, trades_by_ticker, first_is_team1):
    """One map's trades in feed-team-0 terms: time, price (team 0's chance) and
    the cost to back the side the taker took (`back` 0 or 1)."""
    rows = []
    for m in event["markets"]:
        side_is_team1 = m["side"] == event["team1"]
        # Whether a "yes" on this contract backs feed team 0.
        yes_backs_0 = side_is_team1 == first_is_team1
        for t in trades_by_ticker.get(m["ticker"]) or []:
            yes, no = float(t["yes_price_dollars"]), float(t["no_price_dollars"])
            took_yes = t["taker_side"] == "yes"
            rows.append(
                {
                    "at": pd.Timestamp(t["created_time"]),
                    "p0": yes if yes_backs_0 else no,
                    "back": 0 if took_yes == yes_backs_0 else 1,
                    "cost": yes if took_yes else no,
                    "count": float(t.get("count_fp") or t.get("count") or 0),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["at", "p0", "back", "cost", "count"])
    return pd.DataFrame(rows).sort_values("at", kind="stable").reset_index(drop=True)


# ---------------------------------------------------------------- our calls


def team_history(names):
    """Every game of the given OE teams: name, date, side, gameid and Elo after."""
    marks = ",".join("?" * len(names))
    with sqlite3.connect(f"file:{DB}?mode=ro", uri=True) as conn:
        hist = pd.read_sql(
            "SELECT m.teamname, m.date, m.side, m.gameid, e.post_match_elo AS elo"
            " FROM matches m JOIN game_length_elo e"
            " ON e.gameid=m.gameid AND e.teamid=m.teamid"
            f" WHERE m.teamname IN ({marks})",
            conn,
            params=list(names),
        )
    hist["date"] = pd.to_datetime(hist["date"], utc=True)
    return hist.sort_values("date")


def elo_before(hist, name, day):
    """A team's game-length Elo after its last game before a UTC day. The live
    service reads the latest DB, which holds games through the day before."""
    rows = hist[
        (hist["teamname"] == name) & (hist["date"] < pd.Timestamp(day, tz="UTC"))
    ]
    return None if rows.empty else float(rows["elo"].iloc[-1])


OE_WINDOW = pd.Timedelta(hours=3)


def oe_blue(hist, names, start, window=OE_WINDOW):
    """Which of two OE teams (0 or 1) played blue in their game nearest `start`
    (within `window`), or None. The saved feed timelines sometimes attach the
    team names to the wrong side; their blue/red stats are right."""
    a = hist[hist["teamname"] == names[0]]
    b = hist[hist["teamname"] == names[1]]
    games = a.merge(b, on="gameid", suffixes=("_0", "_1"))
    if games.empty:
        return None
    gap = (games["date_0"] - start).abs()
    best = games.loc[gap.idxmin()]
    if gap.min() > window:
        return None
    return 0 if best["side_0"] == "Blue" else 1


def our_calls(game, elos, model, blue):
    """Calls for team 0 at each feed sample: game clock (s), source time, p.
    `elos` in team order; `blue` is the team (0 or 1) on blue."""
    sides = ["blue", "red"] if blue == 0 else ["red", "blue"]
    frames = [
        {
            "source_at": s["at"],
            "teams": [
                {"gold": (s.get(sides[0]) or {}).get("gold")},
                {"gold": (s.get(sides[1]) or {}).get("gold")},
            ],
        }
        for s in game["samples"]
        if s.get("state") == "in_game"
    ]
    clocks = timeline.elapsed_seconds(frames, start=game["start"])
    blue_elo, red_elo = (elos[0], elos[1]) if blue == 0 else (elos[1], elos[0])
    rows = [
        {
            "clock": 0.0,
            "source": pd.Timestamp(game["start"]),
            "p0": _first(
                timeline.predict(
                    model,
                    0,
                    timeline.START_GOLD,
                    timeline.START_GOLD,
                    blue_elo,
                    red_elo,
                ),
                blue,
            ),
        }
    ]
    for frame, clock in zip(frames, clocks):
        gold = [t["gold"] for t in frame["teams"]]  # feed order
        if clock is None or clock <= 0 or clock > model["supported_seconds"][1]:
            continue
        if None in gold or min(gold) <= 0:
            continue
        blue_gold, red_gold = (gold[0], gold[1]) if blue == 0 else (gold[1], gold[0])
        p_blue = timeline.predict(model, clock, blue_gold, red_gold, blue_elo, red_elo)
        rows.append(
            {
                "clock": clock,
                "source": pd.Timestamp(frame["source_at"]),
                "p0": _first(p_blue, blue),
            }
        )
    return pd.DataFrame(rows)


def _first(p_blue, blue):
    return p_blue if blue == 0 else 1 - p_blue


# ---------------------------------------------------------------- reading the tape


def price_at(tp, at, stale=STALE):
    """Kalshi's chance for team 0 from the last trade at or before `at`."""
    i = tp["at"].searchsorted(at, side="right") - 1
    if i < 0 or (at - tp["at"].iloc[i]).total_seconds() > stale:
        return None
    return float(tp["p0"].iloc[i])


def quiet_for(tp, at):
    """Seconds since the last trade at or before `at` (inf if none)."""
    i = tp["at"].searchsorted(at, side="right") - 1
    return math.inf if i < 0 else (at - tp["at"].iloc[i]).total_seconds()


def cost_to_back(tp, at, side, stale=BET_STALE):
    """Price of the last trade that backed `side` at or before `at`, if recent."""
    before = tp[(tp["at"] <= at) & (tp["back"] == side)]
    if before.empty or (at - before["at"].iloc[-1]).total_seconds() > stale:
        return None
    return float(before["cost"].iloc[-1])


def side_price_at(tp, at, side):
    p = price_at(tp, at)
    return None if p is None else (p if side == 0 else 1 - p)


# ---------------------------------------------------------------- the maps


def build_maps(offline=False):
    """Every scorable map: its calls, Kalshi tape, result and metadata."""
    model = json.loads(MODEL.read_text())
    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    by_map = {}
    for r in markets.events(json.loads(MARKET_LIST.read_text())):
        by_map.setdefault(r["map"], []).append(r)

    counts = {"feed games": 0, "no market": 0, "unrated": 0}
    matched = []
    for g in load_games():
        counts["feed games"] += 1
        hit = match_market(g, by_map.get(g["number"], []))
        if hit is None:
            counts["no market"] += 1
            continue
        event, first_is_team1 = hit
        kalshi = [event["team1"], event["team2"]]
        if not first_is_team1:
            kalshi.reverse()
        oe = [matcher(n) for n in kalshi]
        if None in oe:
            counts["unrated"] += 1
            continue
        won0 = event["won1"] if first_is_team1 else not event["won1"]
        matched.append((g, event, first_is_team1, oe, won0))

    hist = team_history(sorted({n for *_, oe, _ in matched for n in oe}))
    counts.update({"no OE game": 0, "winner mismatch": 0, "feed sides swapped": 0})
    checked = []
    for g, event, first_is_team1, oe, won0 in matched:
        blue = oe_blue(hist, oe, pd.Timestamp(g["start"]))
        if blue is None:
            counts["no OE game"] += 1
            continue
        check = feed_winner(g, blue)
        if check is not None and check != (0 if won0 else 1):
            counts["winner mismatch"] += 1
            continue
        if (g["teams"][0]["side"] == "blue") != (blue == 0):
            counts["feed sides swapped"] += 1
        checked.append((g, event, first_is_team1, oe, won0, blue))
    matched = checked

    cutoff = (
        markets.get("/historical/cutoff")["trades_created_ts"] if not offline else None
    )
    todo = [
        (g, m)
        for g, event, *_ in matched
        for m in event["markets"]
        if cached_trades(m["ticker"]) is None
    ]
    if todo and offline:
        print(f"{len(todo)} trade tapes not cached; skipping their maps")
    elif todo:
        print(f"Fetching {len(todo)} trade tapes")
        for i, (g, m) in enumerate(todo, 1):
            start = pd.Timestamp(g["start"])
            end = pd.Timestamp((g.get("final") or {}).get("at") or g["start"])
            fetch_trades(
                m["ticker"],
                int((start - pd.Timedelta(minutes=30)).timestamp()),
                int((end + pd.Timedelta(minutes=10)).timestamp()),
                historical=m["close"] < cutoff,
            )
            time.sleep(0.1)
            if i % 100 == 0:
                print(f"  {i}/{len(todo)}")

    maps = []
    counts["no Elo"] = counts["no trades"] = 0
    for g, event, first_is_team1, oe, won0, blue in matched:
        day = dt.datetime.fromisoformat(g["start"]).date().isoformat()
        pair = [elo_before(hist, n, day) for n in oe]
        if None in pair:
            counts["no Elo"] += 1
            continue
        trades = {m["ticker"]: cached_trades(m["ticker"]) for m in event["markets"]}
        tp = tape(event, trades, first_is_team1)
        start = pd.Timestamp(g["start"])
        end = pd.Timestamp((g.get("final") or {}).get("at") or g["start"])
        in_game = tp[(tp["at"] >= start) & (tp["at"] <= end)]
        if in_game.empty:
            counts["no trades"] += 1
            continue
        maps.append(
            {
                "game": g["game_id"],
                "series": g["match_id"],
                "league": g["league"],
                "map": g["number"],
                "start": start,
                "end": end,
                "teams": oe,
                "won0": bool(won0),
                "calls": our_calls(g, pair, model, blue),
                "tape": tp,
            }
        )
    counts["scored maps"] = len(maps)
    counts["series"] = len({m["series"] for m in maps})
    return maps, counts


# ---------------------------------------------------------------- 1, 2, 5: checkpoints


def checkpoints(maps, lag):
    """One row per map and game minute: our call, Kalshi's price when it arrives."""
    rows = []
    for m in maps:
        calls = m["calls"]
        for minute in MINUTES:
            target = minute * 60
            got = calls[
                (calls["clock"] <= target) & (calls["clock"] >= target - CALL_WINDOW)
            ]
            if got.empty:
                continue
            call = got.iloc[-1]
            at = call["source"] + pd.Timedelta(seconds=lag)
            if at > m["end"]:
                continue
            kalshi = price_at(m["tape"], at)
            if kalshi is None or not 0 < kalshi < 1:
                continue
            rows.append(
                {
                    "series": m["series"],
                    "game": m["game"],
                    "minute": minute,
                    "ours": float(call["p0"]),
                    "kalshi": kalshi,
                    "won": int(m["won0"]),
                }
            )
    return pd.DataFrame(rows)


def clusters(frame):
    return [
        np.flatnonzero(frame["series"].to_numpy() == s)
        for s in frame["series"].unique()
    ]


def interval(values):
    return tuple(np.percentile(values, [2.5, 97.5]))


def compare(frame):
    ours = game_losses(frame["ours"], frame["won"])
    kalshi = game_losses(frame["kalshi"], frame["won"])
    out = {"n": len(frame), "series": frame["series"].nunique()}
    groups = clusters(frame)
    for stat in ("log_loss", "brier"):
        diff = (ours[stat] - kalshi[stat]).to_numpy()
        draws = [diff[i].mean() for i in resamples(groups, N_RESAMPLES)]
        out[stat] = (
            ours[stat].mean(),
            kalshi[stat].mean(),
            diff.mean(),
            *interval(draws),
        )
    return out


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def weights(frame):
    """Logistic weights of Kalshi's and our log-odds on the result (no intercept:
    team order is arbitrary), with series-bootstrap intervals."""
    x = np.column_stack([logit(frame["kalshi"]), logit(frame["ours"])])
    y = frame["won"].to_numpy()

    def fit(idx):
        return (
            LogisticRegression(fit_intercept=False, C=1e6).fit(x[idx], y[idx]).coef_[0]
        )

    point = fit(np.arange(len(y)))
    draws = np.array(
        [fit(i) for i in resamples(clusters(frame), 1000) if len(set(y[i])) == 2]
    )
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return {"kalshi": (point[0], lo[0], hi[0]), "ours": (point[1], lo[1], hi[1])}


def market_activity(maps):
    """Per game minute: trades per minute, median seconds since the last trade,
    and the implied spread from both sides' last costs (each under 60 s old)."""
    rows = []
    for m in maps:
        tp = m["tape"]
        for minute in MINUTES[1:]:
            at = m["start"] + pd.Timedelta(minutes=minute)
            if at > m["end"]:
                continue
            window = tp[(tp["at"] > at - pd.Timedelta(minutes=1)) & (tp["at"] <= at)]
            costs = [cost_to_back(tp, at, s, stale=60) for s in (0, 1)]
            rows.append(
                {
                    "minute": minute,
                    "trades": len(window),
                    "since": min(quiet_for(tp, at), 3600),
                    "spread": None if None in costs else costs[0] + costs[1] - 1,
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 4: paper bets


def taker_fee_per_contract(price):
    return markets.TAKER_RATE * price * (1 - price)


def first_bets(maps, lag, quiet, edge):
    """The first bet per map: our chance for a side beats the cost of backing it
    by `edge`, with no trade for `quiet` seconds before our call arrives."""
    bets = []
    for m in maps:
        tp = m["tape"]
        for call in m["calls"].itertuples(index=False):
            at = call.source + pd.Timedelta(seconds=lag)
            if at > m["end"] or at < m["start"]:
                continue
            if quiet and quiet_for(tp, at) < quiet:
                continue
            placed = None
            for side, p in ((0, call.p0), (1, 1 - call.p0)):
                cost = cost_to_back(tp, at, side)
                if cost is None or not 0 < cost < 1 or p - cost < edge:
                    continue
                placed = (side, p, cost)
                break
            if placed is None:
                continue
            side, p, cost = placed
            won = m["won0"] == (side == 0)
            later = side_price_at(tp, at + pd.Timedelta(seconds=CLV_AFTER), side)
            bets.append(
                {
                    "series": m["series"],
                    "at": at,
                    "minute": call.clock / 60,
                    "p": p,
                    "cost": cost,
                    "won": won,
                    "clv": None if later is None else later - cost,
                }
            )
            break
    return pd.DataFrame(bets)


def flat_profit(bets):
    fee = bets["cost"].map(lambda c: markets.fee(c, 1.0))
    return np.where(bets["won"], 1 / bets["cost"] - 1, -1.0) - fee


def kelly_growth(bets):
    """Per-bet log growth of a bankroll staking quarter Kelly (fee included in
    the cost), in time order; and the final multiple and worst drawdown."""
    eff = bets["cost"] + bets["cost"].map(taker_fee_per_contract)
    f = (KELLY * (bets["p"] - eff) / (1 - eff)).clip(lower=0)
    ret = np.where(bets["won"], f * (1 - eff) / eff, -f)
    growth = np.log1p(ret)
    order = np.argsort(bets["at"].to_numpy())
    path = np.exp(np.cumsum(growth[order]))
    peak = np.maximum.accumulate(np.concatenate([[1.0], path]))[1:]
    drawdown = float((1 - path / peak).max()) if len(path) else 0.0
    return growth, float(path[-1]) if len(path) else 1.0, drawdown


def bet_summary(bets):
    if bets.empty:
        return None
    flat = flat_profit(bets)
    growth, multiple, drawdown = kelly_growth(bets)
    groups = clusters(bets)
    roi = [flat[i].mean() for i in resamples(groups, N_RESAMPLES)]
    grow = [growth[i].mean() for i in resamples(groups, N_RESAMPLES)]
    clv = bets["clv"].dropna()
    return {
        "n": len(bets),
        "won": bets["won"].mean(),
        "cost": bets["cost"].mean(),
        "p": bets["p"].mean(),
        "roi": (flat.mean(), *interval(roi)),
        "growth": (growth.mean(), *interval(grow)),
        "multiple": multiple,
        "drawdown": drawdown,
        "clv": clv.mean() if len(clv) else None,
        "clv_n": len(clv),
    }


# ---------------------------------------------------------------- report


def _ci(v, digits=4, scale=1.0):
    point, lo, hi = (x * scale for x in v)
    return f"{point:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


def report(maps, counts):
    lines = [
        "# In-game calls against Kalshi, replayed",
        "",
        f"Generated by `scripts/research/live_markets_retro.py` on {dt.date.today()}.",
        "The in-game model (`time_model_v1.json`) replayed over saved Riot feed",
        "timelines against Kalshi's map-market trade tape. Intervals resample whole",
        "series. Kalshi's price is the last trade's (team 0's chance), at most",
        f"{STALE // 60} minutes old.",
        "",
        "## Coverage",
        "",
        "| Step | Count |",
        "|---|---:|",
        *(f"| {k} | {v} |" for k, v in counts.items()),
        "",
        f"Leagues: {pd.Series([m['league'] for m in maps]).value_counts().to_dict()}.",
        "",
        "## 1. Log loss against Kalshi by game minute",
        "",
        f"Our call reaches us {LAG} s after its feed time (measured). Negative favours us.",
        "",
        "| Minute | Maps | Series | Ours LL | Kalshi LL | Ours − Kalshi (95%) | Ours Brier | Kalshi Brier | Ours − Kalshi Brier (95%) |",
        "|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    by_lag = {lag: checkpoints(maps, lag) for lag in LAGS}
    frame = by_lag[LAG]
    for minute in MINUTES:
        rows = frame[frame["minute"] == minute]
        if len(rows) < 10:
            continue
        c = compare(rows)
        ll, br = c["log_loss"], c["brier"]
        lines.append(
            f"| {minute} | {c['n']} | {c['series']} | {ll[0]:.4f} | {ll[1]:.4f} | {_ci(ll[2:])} "
            f"| {br[0]:.4f} | {br[1]:.4f} | {_ci(br[2:])} |"
        )
    lines += [
        "",
        "By lag, minutes 5-30 pooled (lag 0 is Kalshi's price at our feed time:",
        "the same moment in the game, before the market sees what we will).",
        "",
        "| Lag (s) | Rows | Ours LL | Kalshi LL | Ours − Kalshi (95%) |",
        "|---:|---:|---:|---:|---|",
    ]
    for lag, f in by_lag.items():
        rows = f[f["minute"] > 0]
        c = compare(rows)
        ll = c["log_loss"]
        lines.append(
            f"| {lag} | {c['n']} | {ll[0]:.4f} | {ll[1]:.4f} | {_ci(ll[2:])} |"
        )

    lines += [
        "",
        "## 2. Our weight beside the market",
        "",
        "Logistic fit of the result on Kalshi's and our log-odds (no intercept).",
        "Kalshi alone would be 1 and 0; our weight above 0 means we add information.",
        "",
        "| Minutes | Rows | Kalshi weight (95%) | Our weight (95%) |",
        "|---|---:|---|---|",
    ]
    for label, rows in (
        ("5-30 pooled", frame[frame["minute"] > 0]),
        ("10-20", frame[frame["minute"].between(10, 20)]),
        ("0 (pregame)", frame[frame["minute"] == 0]),
    ):
        if len(rows) < 20:
            continue
        w = weights(rows)
        lines.append(
            f"| {label} | {len(rows)} | {_ci(w['kalshi'], 2)} | {_ci(w['ours'], 2)} |"
        )

    lines += [
        "",
        "## 4. Paper bets",
        "",
        "First call per map where our chance beats the last traded cost of backing",
        f"that side (traded within {BET_STALE} s) by the edge, after the market has had no",
        "trade for the quiet window. Flat: $1 a bet after Kalshi's taker fee (ROI per",
        f"bet). Kelly: {KELLY:g} Kelly on one bankroll in time order (log growth per bet,",
        f"final multiple of the bankroll, worst drawdown). CLV: our side's price {CLV_AFTER} s",
        "later minus the cost paid, in points.",
        "",
        "| Lag | Quiet | Edge | Bets | Won | Avg cost | Avg ours | Flat ROI (95%) | Kelly growth/bet (95%) | Kelly multiple | Max drawdown | CLV |",
        "|---:|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    grid = [(LAG, q, EDGE) for q in QUIETS]
    grid += [(LAG, 10, e) for e in EDGES if e != EDGE]
    grid += [(LAG, LAG, e) for e in EDGES if e != EDGE]
    grid += [(10, 10, EDGE)]
    for lag, quiet, edge in grid:
        s = bet_summary(first_bets(maps, lag, quiet, edge))
        if s is None:
            lines.append(f"| {lag} | {quiet} | {edge:.2f} | 0 | | | | | | | | |")
            continue
        clv = "" if s["clv"] is None else f"{s['clv'] * 100:+.1f} ({s['clv_n']})"
        lines.append(
            f"| {lag} | {quiet} | {edge:.2f} | {s['n']} | {s['won']:.1%} | {s['cost']:.3f} "
            f"| {s['p']:.3f} | {_ci(s['roi'], 3)} | {_ci(s['growth'], 4)} "
            f"| {s['multiple']:.2f} | {s['drawdown']:.0%} | {clv} |"
        )

    act = market_activity(maps)
    lines += [
        "",
        "## 5. Gap, trading and spread",
        "",
        f"Gap: mean |ours − Kalshi| at lag {LAG} s. Trades: in the minute before. Since:",
        "median seconds since the last trade. Spread: both sides' last costs minus 1,",
        "where both traded in the last 60 s (a proxy; the book itself isn't saved).",
        "",
        "| Minute | Maps | Mean gap | Trades/min (median) | Since last trade (median s) | Share quiet ≥10 s | Share quiet ≥21 s | Spread (median) | Spread n |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for minute in MINUTES[1:]:
        rows = act[act["minute"] == minute]
        gaps = frame[frame["minute"] == minute]
        if rows.empty:
            continue
        spread = rows["spread"].dropna()
        lines.append(
            f"| {minute} | {len(rows)} | {(gaps['ours'] - gaps['kalshi']).abs().mean():.3f} "
            f"| {rows['trades'].median():.0f} | {rows['since'].median():.0f} "
            f"| {(rows['since'] >= 10).mean():.0%} | {(rows['since'] >= 21).mean():.0%} "
            f"| {spread.median():.3f} | {len(spread)} |"
            if len(spread)
            else f"| {minute} | {len(rows)} | {(gaps['ours'] - gaps['kalshi']).abs().mean():.3f} "
            f"| {rows['trades'].median():.0f} | {rows['since'].median():.0f} "
            f"| {(rows['since'] >= 10).mean():.0%} | {(rows['since'] >= 21).mean():.0%} | | 0 |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Kalshi's price is the last trade, not the book: quiet means no trade, and a",
        "  bet's cost is the last trade backing that side, not the ask at that moment.",
        "- One feed sample a minute (live: every few seconds), so fewer chances to bet",
        "  than live, and the estimated game clock misses pauses between samples.",
        "- Lag is from one pilot match; the feed's delay may differ by league or day.",
        "- Matching feed games to Kalshi events is by fuzzy team names, map number and",
        "  time; maps whose feed end state disagrees with Kalshi's result are dropped.",
        "- 2026 games were seen while building the in-game model (as development",
        "  evidence, not training), so this is retrospective, not a fresh holdout.",
    ]
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--out", type=Path)
    parser.add_argument("--offline", action="store_true", help="cached trades only")
    args = parser.parse_args()
    maps, counts = build_maps(offline=args.offline)
    print(counts)
    text = report(maps, counts)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)


if __name__ == "__main__":
    main()
