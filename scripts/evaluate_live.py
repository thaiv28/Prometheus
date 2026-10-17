"""
evaluate_live.py: How do our in-game calls compare with Kalshi's in-game prices?

The live pages' in-game call (`prometheus.live.timeline.timeline_calls` with the
model at `timeline.MODEL_PATH`, the same path the live service takes) is replayed
over past maps' Riot live-stats feed timelines (about one sample a minute, from
`scripts/research/feed_timelines.py`), for every map with a settled Kalshi map
market (`KXLOLMAP`, from late 2025). Kalshi's side comes from its trade tape:
every trade on both teams' contracts, with its time and which side took the book.

Our call from a feed sample with source time `s` reaches us at `s + LAG`. The
live pilot (KC-C9, Worlds 2026 maps 4-5) measured that lag from its request log:
the newest frame received was never under 20 s old, median 21 s on the map
polled steadily. Kalshi trades on the broadcast and is ahead of our feed, so a
paper bet is placed only when the market has had no trade for a quiet window
before our call arrives, at the last price paid to back our side.

The report, each interval over whole series resampled together:

1. log loss and Brier, ours against Kalshi's last trade when our call arrives,
   at fixed game minutes, and by lag;
2. our weight beside the market: a logistic fit of the result on both
   log-odds; above zero means we add something Kalshi's price lacks;
3. paper bets: the first call in a map where our chance beats the price of
   backing that side by the edge while the market is quiet, at $1 flat and at
   quarter Kelly, after Kalshi's taker fee, with the price two minutes later;
4. the gap between our call and Kalshi's price, trading and implied spread.

Data. `--build-data` (local: needs the feed timelines, the Kalshi market list in
`data/markets/`, Kalshi's trade API and the DB) reduces each map to what the
benchmark reads: the feed samples in team order, who played blue (the feed's
`blue_id`, else Oracle's Elixir; lolesports' own side labels are often
swapped), Kalshi's result, Oracle's Elixir team names, and Kalshi's state at
each sample (price at the sample time and at +LAG, seconds since the last
trade, last cost to back each side, price two minutes later, trades in the
minute before, implied spread). `--publish-data` uploads it as a GitHub release
asset and pins it in `scripts/live_bench_data.json`; `--fetch-data` downloads the
pinned file (CI). Elo comes from the DB at run time, so a change to Elo moves
this benchmark too.

Usage:
    uv run python scripts/evaluate_live.py --out docs/live_report.md
    uv run python scripts/evaluate_live.py --dump DIR        # the PR benchmark check
    uv run python scripts/evaluate_live.py --build-data [--refresh-markets]
    uv run python scripts/evaluate_live.py --publish-data    # upload and pin (gh CLI)
    uv run python scripts/evaluate_live.py --fetch-data      # download the pinned data

Limits: Kalshi's price is the last trade, not the book (quiet means no trade);
one call a minute where the live service makes one every 10 s; the lag is from
one pilot match; maps whose feed end state disagrees with Kalshi's result are
dropped.
"""

import argparse
import datetime as dt
import difflib
import gzip
import hashlib
import json
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from prometheus import DB_PATH, markets, schedule
from prometheus.evaluation import game_losses, resamples
from prometheus.live import timeline

TIMELINES = ROOT / "data" / "feed_timelines" / "games"
MARKET_LIST = ROOT / "data" / "markets" / f"{markets.MAP}.json"
TRADES = ROOT / "data" / "live_bench" / "trades"
DATA = ROOT / "data" / "live_bench" / "live_maps.json.gz"
PIN = ROOT / "scripts" / "live_bench_data.json"
REPO = "thaiv28/Prometheus"
RELEASE = "live-bench-data"

KALSHI_START = "2025-10-27"  # the first KXLOLMAP market
LAG = 21  # seconds from a feed sample's source time to our call (measured)
QUIETS = (0, 10, 21, 30)  # seconds with no trade before a bet
EDGES = (0.03, 0.05, 0.10, 0.15)
EDGE = 0.05
KELLY = 0.25
MINUTES = (0, 5, 10, 15, 20, 25, 30)
# The minute bands the PR check guards (and "all": every minute row).
BANDS = {"pregame": (0,), "early": (5, 10), "mid": (15, 20), "late": (25, 30)}
CALL_WINDOW = (
    1.5  # a checkpoint's call is the last one up to this many minutes before it
)
STALE = 300  # a trade older than this (seconds) is no price
BET_STALE = 120  # the cost to back a side comes from a trade at most this old
CLV_AFTER = 120  # our side's price this long after a bet
SPREAD_STALE = 60
OE_WINDOW = pd.Timedelta(hours=3)
SERIES_WINDOW = pd.Timedelta(hours=8)  # earlier maps of the same series
N_RESAMPLES = 2000
STATS = ("gold", "kills", "towers", "inhibitors", "barons", "dragons")
# Kalshi's state at each sample, in this order.
MARKET_FIELDS = (
    "p_now",
    "p_lag",
    "quiet",
    "cost0",
    "cost1",
    "p_clv",
    "trades",
    "spread",
)

# Words too common in team names to identify a team.
GENERIC = {"esports", "esport", "gaming", "team", "club", "e", "sports", "the", "gg"}


def _log(message):
    print(message, flush=True)


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


def feed_blue(game):
    """Feed team (0 or 1) on blue from the feed's own `blue_id`, or None."""
    ids = [t.get("id") for t in game["teams"]]
    blue_id = game.get("blue_id")
    return ids.index(blue_id) if blue_id in ids else None


def team_history(names, db=DB_PATH):
    """Every game of the given OE teams: name, date, side, result, gameid and Elo
    after."""
    marks = ",".join("?" * len(names))
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        hist = pd.read_sql(
            "SELECT m.teamname, m.date, m.side, m.result, m.gameid,"
            " e.post_match_elo AS elo"
            " FROM matches m JOIN game_length_elo e"
            " ON e.gameid=m.gameid AND e.teamid=m.teamid"
            f" WHERE m.teamname IN ({marks})",
            conn,
            params=list(names),
        )
    hist["date"] = pd.to_datetime(hist["date"], utc=True)
    return hist.sort_values("date")


def oe_blue(hist, names, start, window=OE_WINDOW):
    """Which of two OE teams (0 or 1) played blue in their game nearest `start`
    (within `window`), or None."""
    a = hist[hist["teamname"] == names[0]]
    b = hist[hist["teamname"] == names[1]]
    games = a.merge(b, on="gameid", suffixes=("_0", "_1"))
    if games.empty:
        return None
    gap = (games["date_0"] - start).abs()
    if gap.min() > window:
        return None
    return 0 if games.loc[gap.idxmin(), "side_0"] == "Blue" else 1


def score_before(hist, names, start, window=SERIES_WINDOW):
    """[team 0's wins, team 1's wins] in this series before the map: their games
    with each other that ended in the `window` before `start` (minus 5 minutes,
    so this map's own row is never counted)."""
    a = hist[hist["teamname"] == names[0]]
    b = hist[hist["teamname"] == names[1]]
    games = a.merge(b, on="gameid", suffixes=("_0", "_1"))
    cutoff = start - pd.Timedelta(minutes=5)
    earlier = games[(games["date_0"] < cutoff) & (games["date_0"] > start - window)]
    wins0 = int((earlier["result_0"] == 1).sum())
    return [wins0, len(earlier) - wins0]


def elo_before(hist, name, day):
    """A team's game-length Elo after its last game before a UTC day. The live
    service reads the latest DB, which holds games through the day before."""
    rows = hist[
        (hist["teamname"] == name) & (hist["date"] < pd.Timestamp(day, tz="UTC"))
    ]
    return None if rows.empty else float(rows["elo"].iloc[-1])


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
    path = TRADES / f"{ticker}.json"
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
    path = TRADES / f"{ticker}.json"
    return json.loads(path.read_text()) if path.exists() else None


def tape(event, trades_by_ticker, first_is_team1):
    """One map's trades for feed team 0: time, price (team 0's chance) and the
    cost to back the side the taker took (`back` 0 or 1)."""
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
                }
            )
    if not rows:
        return pd.DataFrame(columns=["at", "p0", "back", "cost"])
    return pd.DataFrame(rows).sort_values("at", kind="stable").reset_index(drop=True)


def price_at(tp, at, stale=STALE):
    """Kalshi's chance for team 0 from the last trade at or before `at`."""
    i = tp["at"].searchsorted(at, side="right") - 1
    if i < 0 or (at - tp["at"].iloc[i]).total_seconds() > stale:
        return None
    return float(tp["p0"].iloc[i])


def quiet_for(tp, at):
    """Seconds since the last trade at or before `at` (None if none)."""
    i = tp["at"].searchsorted(at, side="right") - 1
    return None if i < 0 else (at - tp["at"].iloc[i]).total_seconds()


def cost_to_back(tp, at, side, stale=BET_STALE):
    """Price of the last trade that backed `side` at or before `at`, if recent."""
    before = tp[(tp["at"] <= at) & (tp["back"] == side)]
    if before.empty or (at - before["at"].iloc[-1]).total_seconds() > stale:
        return None
    return float(before["cost"].iloc[-1])


def market_state(tp, source):
    """Kalshi at one feed sample (see MARKET_FIELDS); our call arrives at +LAG."""
    at = source + pd.Timedelta(seconds=LAG)
    costs = [cost_to_back(tp, at, s, stale=SPREAD_STALE) for s in (0, 1)]
    quiet = quiet_for(tp, at)
    return [
        price_at(tp, source),
        price_at(tp, at),
        None if quiet is None else round(quiet, 2),
        cost_to_back(tp, at, 0),
        cost_to_back(tp, at, 1),
        price_at(tp, at + pd.Timedelta(seconds=CLV_AFTER)),
        int(((tp["at"] > at - pd.Timedelta(minutes=1)) & (tp["at"] <= at)).sum()),
        None if None in costs else round(costs[0] + costs[1] - 1, 4),
    ]


# ---------------------------------------------------------------- building the data


def _team_stats(sample, side):
    block = sample.get(side) or {}
    return [block.get(s) for s in STATS]


def build_data(refresh_markets=False):
    """Reduce feed timelines and Kalshi trade tapes to the benchmark's data."""
    if refresh_markets:
        sys.path.insert(0, str(ROOT / "scripts"))
        import evaluate_markets

        evaluate_markets.fetch_markets(markets.MAP, refresh=True)
    from prometheus.elo import get_latest_elos

    matcher = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **markets.MARKET_ALIASES},
    )
    by_map = {}
    for r in markets.events(json.loads(MARKET_LIST.read_text())):
        by_map.setdefault(r["map"], []).append(r)

    counts = dict.fromkeys(
        [
            "feed games",
            "no market",
            "unrated",
            "no side",
            "feed and OE sides disagree",
            "winner mismatch",
            "no trades",
        ],
        0,
    )
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
        matched.append((g, event, first_is_team1, oe))

    hist = team_history(sorted({n for *_, oe in matched for n in oe}))
    cutoff = markets.get("/historical/cutoff")["trades_created_ts"]
    maps = []
    for i, (g, event, first_is_team1, oe) in enumerate(matched, 1):
        start = pd.Timestamp(g["start"])
        blue, from_oe = feed_blue(g), oe_blue(hist, oe, start)
        if blue is not None and from_oe is not None and blue != from_oe:
            counts["feed and OE sides disagree"] += 1
        blue = blue if blue is not None else from_oe
        if blue is None:
            counts["no side"] += 1
            continue
        won0 = event["won1"] if first_is_team1 else not event["won1"]
        check = feed_winner(g, blue)
        if check is not None and check != (0 if won0 else 1):
            counts["winner mismatch"] += 1
            continue
        end = pd.Timestamp((g.get("final") or {}).get("at") or g["start"])
        trades = {}
        for m in event["markets"]:
            trades[m["ticker"]] = cached_trades(m["ticker"]) or fetch_trades(
                m["ticker"],
                int((start - pd.Timedelta(minutes=30)).timestamp()),
                int((end + pd.Timedelta(minutes=10)).timestamp()),
                historical=m["close"] < cutoff,
            )
        tp = tape(event, trades, first_is_team1)
        if not ((tp["at"] >= start) & (tp["at"] <= end)).any():
            counts["no trades"] += 1
            continue
        sides = ["blue", "red"] if blue == 0 else ["red", "blue"]
        samples = []
        for s in g["samples"]:
            source = pd.Timestamp(s["at"])
            samples.append(
                {
                    "t": round((source - start).total_seconds(), 3),
                    "state": s.get("state"),
                    "flat": bool(s.get("flat")),
                    "teams": [_team_stats(s, side) for side in sides],
                    "market": market_state(tp, source),
                }
            )
        maps.append(
            {
                "game": g["game_id"],
                "series": g["match_id"],
                "league": g["league"],
                "map": g["number"],
                "start": g["start"],
                "end": end.isoformat(),
                "teams": oe,
                "blue": blue,
                "won0": bool(won0),
                # For the series shift once the live calls carry it.
                "score_before": score_before(hist, oe, start),
                "pregame_market": market_state(tp, start),
                "samples": samples,
            }
        )
        if i % 200 == 0:
            _log(f"  {i}/{len(matched)}")
    counts["maps"] = len(maps)
    counts["series"] = len({m["series"] for m in maps})
    data = {
        "built": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "lag": LAG,
        "fields": {"teams": STATS, "market": MARKET_FIELDS},
        "counts": counts,
        "maps": maps,
    }
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(DATA, "wt") as f:
        json.dump(data, f, separators=(",", ":"))
    _log(f"{counts}\nwrote {DATA} ({DATA.stat().st_size / 1e6:.1f} MB)")
    return data


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def publish_data():
    """Upload the built data as a release asset named by its hash, and pin it."""
    digest = _sha256(DATA)
    name = f"live_maps-{digest[:12]}.json.gz"
    asset = DATA.with_name(name)
    asset.write_bytes(DATA.read_bytes())
    if subprocess.run(
        ["gh", "release", "view", RELEASE], capture_output=True
    ).returncode:
        subprocess.run(
            [
                "gh",
                "release",
                "create",
                RELEASE,
                "--title",
                "Live benchmark data",
                "--notes",
                "Data for scripts/evaluate_live.py (pinned in scripts/live_bench_data.json).",
                "--latest=false",
            ],
            check=True,
        )
    subprocess.run(["gh", "release", "upload", RELEASE, str(asset)], check=True)
    with gzip.open(DATA, "rt") as f:
        counts = json.load(f)["counts"]
    PIN.write_text(
        json.dumps({"asset": name, "sha256": digest, "maps": counts["maps"]}, indent=2)
        + "\n"
    )
    _log(f"uploaded {name}; pinned in {PIN.relative_to(ROOT)}")


def fetch_data():
    """Download the pinned data (skipped when the local copy already matches)."""
    pin = json.loads(PIN.read_text())
    if DATA.exists() and _sha256(DATA) == pin["sha256"]:
        return
    url = f"https://github.com/{REPO}/releases/download/{RELEASE}/{pin['asset']}"
    DATA.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        DATA.write_bytes(response.read())
    if _sha256(DATA) != pin["sha256"]:
        DATA.unlink()
        raise SystemExit(f"{pin['asset']}: hash does not match the pin")


def load_data(path=DATA):
    with gzip.open(path, "rt") as f:
        return json.load(f)


# ---------------------------------------------------------------- our calls


def page_for(m, fields):
    """The live page's game block for one map, as `timeline_calls` reads it."""
    start = pd.Timestamp(m["start"])
    frames = []
    for s in m["samples"]:
        if s["state"] != "in_game":
            continue
        at = (start + pd.Timedelta(seconds=s["t"])).isoformat()
        frames.append(
            {
                "at": at,
                "source_at": at,
                "teams": [dict(zip(fields, team)) for team in s["teams"]],
            }
        )
    return {"game": {"blue": m["blue"], "frames": frames}}


def map_calls(m, model, elos, fields):
    """(pregame call, calls with game minute and sample offset) for team 0."""
    page = page_for(m, fields)
    ratings = [{"elo": e} for e in elos]
    pregame, calls = timeline.timeline_calls(page, model, ratings, start=m["start"])
    start = pd.Timestamp(m["start"])
    offset = {s["t"]: i for i, s in enumerate(m["samples"])}
    rows = []
    for c in calls:
        t = round((pd.Timestamp(c["at"]) - start).total_seconds(), 3)
        rows.append({"minute": c["minute"], "p": c["p"], "sample": offset.get(t)})
    return pregame, rows


def replay(data, db=DB_PATH, model_path=timeline.MODEL_PATH):
    """Every map's calls, with Kalshi's state at each: one row per call."""
    model = json.loads(Path(model_path).read_text())
    fields = data["fields"]["teams"]
    hist = team_history(sorted({n for m in data["maps"] for n in m["teams"]}), db)
    rows, skipped = [], 0
    for m in data["maps"]:
        day = m["start"][:10]
        elos = [elo_before(hist, n, day) for n in m["teams"]]
        if None in elos:
            skipped += 1
            continue
        pregame, calls = map_calls(m, model, elos, fields)
        base = {
            "game": m["game"],
            "series": m["series"],
            "league": m["league"],
            "won": int(m["won0"]),
        }
        if pregame is not None:
            market = _market(m["pregame_market"])
            rows.append(dict(base, pregame=True, minute=0.0, p=pregame, **market))
        for c in calls:
            if c["sample"] is None:
                continue
            market = _market(m["samples"][c["sample"]]["market"])
            rows.append(
                dict(base, pregame=False, minute=c["minute"], p=c["p"], **market)
            )
    return pd.DataFrame(rows), skipped


def _market(values):
    return dict(zip(MARKET_FIELDS, values))


# ---------------------------------------------------------------- 1, 2, 4: checkpoints


def checkpoints(calls, price="p_lag"):
    """One row per map and game minute: our latest call, and Kalshi's price.
    Minute 0 is the pregame call (before the first frame)."""
    rows = []
    live = calls[~calls["pregame"]]
    for minute in MINUTES:
        pick = live[
            (live["minute"] <= minute) & (live["minute"] >= minute - CALL_WINDOW)
        ]
        if minute == 0:
            pick = calls[calls["pregame"]]
        last = pick.groupby("game").tail(1)
        rows.append(last.assign(checkpoint=minute))
    out = pd.concat(rows, ignore_index=True)
    out = out.rename(columns={"p": "ours"})
    out["kalshi"] = out[price]
    ok = out["kalshi"].notna() & (out["kalshi"] > 0) & (out["kalshi"] < 1)
    return out[ok].reset_index(drop=True)


def clusters(frame):
    codes = pd.factorize(frame["series"])[0]
    return [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]


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
        model = LogisticRegression(fit_intercept=False, C=1e6)
        return model.fit(x[idx], y[idx]).coef_[0]

    point = fit(np.arange(len(y)))
    draws = np.array(
        [fit(i) for i in resamples(clusters(frame), 1000) if len(set(y[i])) == 2]
    )
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return {"kalshi": (point[0], lo[0], hi[0]), "ours": (point[1], lo[1], hi[1])}


# ---------------------------------------------------------------- 3: paper bets


def first_bets(calls, quiet, edge):
    """The first bet per map: our chance for a side beats the cost of backing it
    by `edge`, with no trade for `quiet` seconds before our call arrives."""
    live = calls[~calls["pregame"]]
    bets = []
    for game, rows in live.groupby("game", sort=False):
        for r in rows.itertuples(index=False):
            if quiet and (r.quiet is None or pd.isna(r.quiet) or r.quiet < quiet):
                continue
            placed = None
            for side, p, cost in ((0, r.p, r.cost0), (1, 1 - r.p, r.cost1)):
                if cost is None or pd.isna(cost) or not 0 < cost < 1:
                    continue
                if p - cost >= edge:
                    placed = (side, p, cost)
                    break
            if placed is None:
                continue
            side, p, cost = placed
            later = r.p_clv
            if later is not None and not pd.isna(later) and side == 1:
                later = 1 - later
            bets.append(
                {
                    "series": r.series,
                    "game": game,
                    "order": len(bets),
                    "p": p,
                    "cost": cost,
                    "won": bool(r.won) == (side == 0),
                    "clv": None if later is None or pd.isna(later) else later - cost,
                }
            )
            break
    return pd.DataFrame(bets)


def flat_profit(bets):
    fee = bets["cost"].map(lambda c: markets.fee(c, 1.0))
    return np.where(bets["won"], 1 / bets["cost"] - 1, -1.0) - fee


def kelly_growth(bets):
    """Per-bet log growth of a bankroll staking quarter Kelly (the taker fee in
    the cost), in order; and the final multiple and worst drawdown."""
    eff = bets["cost"] + markets.TAKER_RATE * bets["cost"] * (1 - bets["cost"])
    f = (KELLY * (bets["p"] - eff) / (1 - eff)).clip(lower=0)
    growth = np.log1p(np.where(bets["won"], f * (1 - eff) / eff, -f))
    path = np.exp(np.cumsum(growth))
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


def _ci(v, digits=4):
    point, lo, hi = v
    return f"{point:+.{digits}f} ({lo:+.{digits}f} to {hi:+.{digits}f})"


def report(data, calls, skipped):
    counts = dict(data["counts"], **{"no Elo": skipped})
    games = calls["game"].unique()
    leagues = calls.drop_duplicates("game")["league"].value_counts().to_dict()
    lines = [
        "# In-game calls against Kalshi",
        "",
        f"Generated by `scripts/evaluate_live.py` from data built {data['built'][:10]}.",
        "Our in-game call replayed over past maps' Riot feed timelines, against",
        "Kalshi's map-market trade tape. Intervals resample whole series. Kalshi's",
        f"price is the last trade (team 0's chance), at most {STALE // 60} minutes old.",
        "",
        "## Coverage",
        "",
        "| Step | Count |",
        "|---|---:|",
        *(f"| {k} | {v} |" for k, v in counts.items()),
        f"| scored maps | {len(games)} |",
        "",
        f"Leagues: {leagues}.",
        "",
        "## 1. Log loss against Kalshi by game minute",
        "",
        f"Our call reaches us {LAG} s after its feed time (measured). Negative favours us.",
        "",
        "| Minute | Maps | Series | Ours LL | Kalshi LL | Ours − Kalshi (95%) "
        "| Ours Brier | Kalshi Brier | Ours − Kalshi Brier (95%) |",
        "|---:|---:|---:|---:|---:|---|---:|---:|---|",
    ]
    frame = checkpoints(calls)
    for minute in MINUTES:
        rows = frame[frame["checkpoint"] == minute]
        if len(rows) < 10:
            continue
        c = compare(rows)
        ll, br = c["log_loss"], c["brier"]
        lines.append(
            f"| {minute} | {c['n']} | {c['series']} | {ll[0]:.4f} | {ll[1]:.4f} "
            f"| {_ci(ll[2:])} | {br[0]:.4f} | {br[1]:.4f} | {_ci(br[2:])} |"
        )
    lines += [
        "",
        "Minutes 5-30 pooled, Kalshi's price when our call arrives and at our feed",
        "time (the same moment in the game, before the market sees what we will):",
        "",
        "| Kalshi's price | Rows | Ours LL | Kalshi LL | Ours − Kalshi (95%) |",
        "|---|---:|---:|---:|---|",
    ]
    for label, price in ((f"+{LAG} s", "p_lag"), ("+0 s", "p_now")):
        rows = checkpoints(calls, price)
        c = compare(rows[rows["checkpoint"] > 0])
        ll = c["log_loss"]
        lines.append(
            f"| {label} | {c['n']} | {ll[0]:.4f} | {ll[1]:.4f} | {_ci(ll[2:])} |"
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
        ("5-30 pooled", frame[frame["checkpoint"] > 0]),
        ("10-20", frame[frame["checkpoint"].between(10, 20)]),
        ("0 (pregame)", frame[frame["checkpoint"] == 0]),
    ):
        if len(rows) < 20:
            continue
        w = weights(rows)
        lines.append(
            f"| {label} | {len(rows)} | {_ci(w['kalshi'], 2)} | {_ci(w['ours'], 2)} |"
        )

    lines += [
        "",
        "## 3. Paper bets",
        "",
        "First call per map where our chance beats the last traded cost of backing",
        f"that side (traded within {BET_STALE} s) by the edge, after the market has had",
        "no trade for the quiet window. Flat: $1 a bet after Kalshi's taker fee. Kelly:",
        f"{KELLY:g} Kelly on one bankroll in map order. CLV: our side's price {CLV_AFTER} s",
        "later minus the cost paid, in points.",
        "",
        "| Quiet (s) | Edge | Bets | Won | Avg cost | Avg ours | Flat ROI (95%) "
        "| Kelly growth/bet (95%) | Kelly multiple | Max drawdown | CLV |",
        "|---:|---:|---:|---:|---:|---:|---|---|---:|---:|---:|",
    ]
    grid = [(q, EDGE) for q in QUIETS]
    grid += [(q, e) for q in (10, LAG) for e in EDGES if e != EDGE]
    for quiet, edge in grid:
        s = bet_summary(first_bets(calls, quiet, edge))
        if s is None:
            lines.append(f"| {quiet} | {edge:.2f} | 0 | | | | | | | | |")
            continue
        clv = "" if s["clv"] is None else f"{s['clv'] * 100:+.1f}"
        lines.append(
            f"| {quiet} | {edge:.2f} | {s['n']} | {s['won']:.1%} | {s['cost']:.3f} "
            f"| {s['p']:.3f} | {_ci(s['roi'], 3)} | {_ci(s['growth'], 4)} "
            f"| {s['multiple']:.2f} | {s['drawdown']:.0%} | {clv} |"
        )

    live = frame[frame["checkpoint"] > 0]
    lines += [
        "",
        "## 4. Gap, trading and spread",
        "",
        "Gap: mean |ours − Kalshi| when our call arrives. Trades: in the minute",
        "before (median). Quiet: seconds since the last trade (median), and the share",
        "of calls arriving after at least 10 and 21 s without one. Spread: both",
        f"sides' last costs minus 1, where both traded in the last {SPREAD_STALE} s.",
        "",
        "| Minute | Maps | Mean gap | Trades/min | Quiet (s) | Quiet ≥10 s "
        "| Quiet ≥21 s | Spread | Spread n |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for minute in MINUTES[1:]:
        rows = live[live["checkpoint"] == minute]
        if rows.empty:
            continue
        quiet = rows["quiet"].astype(float)
        spread = rows["spread"].dropna()
        lines.append(
            f"| {minute} | {len(rows)} | {(rows['ours'] - rows['kalshi']).abs().mean():.3f} "
            f"| {rows['trades'].median():.0f} | {quiet.median():.0f} "
            f"| {(quiet >= 10).mean():.0%} | {(quiet >= 21).mean():.0%} "
            f"| {spread.median() if len(spread) else float('nan'):.3f} | {len(spread)} |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "- Kalshi's price is the last trade, not the book: quiet means no trade, and a",
        "  bet's cost is the last trade backing that side, not the ask at that moment.",
        "- One feed sample a minute (live: every 10 s), so fewer chances to bet than",
        "  live, and the estimated game clock misses pauses between samples.",
        "- The lag is from one pilot match; the feed's delay may differ by league or day.",
        "- Feed games are matched to Kalshi's events by fuzzy team names, map number",
        "  and time; maps whose feed end state disagrees with Kalshi's result are dropped.",
        "- 2026 games were seen while building the in-game model (as development",
        "  evidence, not training), so this is retrospective, not a fresh holdout.",
    ]
    return "\n".join(lines) + "\n"


def write_dump(calls, dirname):
    """Each map's checkpoint calls for `compare_benchmarks.py` (Kalshi's price
    rides along for the report; it is the same on both sides)."""
    out = Path(dirname)
    out.mkdir(parents=True, exist_ok=True)
    frame = checkpoints(calls)
    frame[["game", "series", "checkpoint", "ours", "kalshi", "won"]].to_csv(
        out / "calls.csv.gz", index=False
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--out", type=Path, help="write the report here")
    parser.add_argument("--dump", help="write checkpoint calls for the PR check")
    parser.add_argument("--build-data", action="store_true")
    parser.add_argument("--refresh-markets", action="store_true")
    parser.add_argument("--publish-data", action="store_true")
    parser.add_argument("--fetch-data", action="store_true")
    parser.add_argument("--data", type=Path, default=DATA)
    args = parser.parse_args()
    if args.build_data:
        build_data(args.refresh_markets)
    if args.publish_data:
        publish_data()
    if args.fetch_data:
        fetch_data()
    if (args.build_data or args.publish_data or args.fetch_data) and not (
        args.out or args.dump
    ):
        return
    started = time.monotonic()
    data = load_data(args.data)
    calls, skipped = replay(data)
    _log(
        f"{calls['game'].nunique()} maps, {len(calls)} calls "
        f"({time.monotonic() - started:.1f} s)"
    )
    if args.dump:
        write_dump(calls, args.dump)
    if args.out or not args.dump:
        text = report(data, calls, skipped)
        if args.out:
            args.out.write_text(text)
            _log(f"wrote {args.out}")
        else:
            print(text)


if __name__ == "__main__":
    main()
