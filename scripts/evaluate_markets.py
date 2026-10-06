"""
evaluate_markets.py: How do our match calls compare with the prediction market?

Kalshi lists a market for nearly every pro League of Legends series (series
`KXLOLGAME`, one yes/no contract per team) and for each map (`KXLOLMAP`), from
the majors down to ERLs and academy leagues, back to late 2025. A contract's
price is a probability with no bookmaker margin, only the bid-ask spread.

For every settled series market between two teams we rate, this script:

- reconstructs our call as the Predictions page makes it (FORGE within a major
  league, Elo across leagues, Elo within other leagues), from games before the
  match day (`schedule.ratings_before`), with the best-of taken from the games in
  our data;
- reads the market's mid price (from hourly candlesticks) at two moments: the
  close, the last hour before the scheduled start, which knows lineups and late
  news our day-old ratings don't, and 12 hours before the start, nearer to what
  our call knew;
- scores both on the series result (accuracy, Brier, log loss), with a paired
  bootstrap of the difference, by slice (major-league or international, other
  leagues; FORGE, Elo, cross-league Elo);
- asks whether our call adds anything to the market: a logistic fit of the
  result on both log-odds, with a bootstrap interval for our weight. A weight
  near zero means the market already knows what we know;
- repeats the comparison for single games: the map-1 market before the series
  starts against our one-game chance, scored on map 1. That needs no best-of and
  doesn't lean on the independent-games assumption behind our series odds.

Prices with no two-sided quote, or a spread wider than `MAX_SPREAD`, are left
out. Our forecast weights were fit on data that includes these matches, which
flatters us a little.

Kalshi's market data is public (no key). Markets and candlesticks are cached
under `data/markets/` (gitignored); `--refresh` refetches the market lists.

Usage:
    uv run python scripts/evaluate_markets.py [--out docs/market_report.md] [--refresh]
"""

import argparse
import datetime
import json
import time
import urllib.error
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sqlalchemy import text

from prometheus import schedule, utils
from prometheus.markets import (
    MAP,
    MARKET_ALIASES,
    MAX_SPREAD,
    SERIES,
    book_at,
    events,
    fee,
    get,
    quote_at,
)
from prometheus.elo import get_latest_elos
from prometheus.evaluation import game_losses, paired_bootstrap
from prometheus.form import form_states, load_form_games, opponent_adjust

CACHE = Path("data/markets")
EARLY_HOURS = 12
# Betting: hours before the start the bets are placed, Kalshi's fee rates
# (fee per order = ceil(rate × contracts × P × (1 − P)), to the cent; taker 7%,
# resting maker orders 1.75%), and the value-bet edges tried, fixed in advance.
BET_HOURS = 12
FEE_RATES = (("Taker 7%", 0.07), ("Maker 1.75%", 0.0175), ("None", 0.0))
EDGES = (0.0, 0.03, 0.05, 0.10)
# Lead times for the ladder: the market's price this many hours before the start.
LEAD_HOURS = (6, 12, 18, 24)


# ---------------------------------------------------------------- fetching


def fetch_markets(series, refresh=False):
    """Every market in a Kalshi series, live and historical (settled before
    Kalshi's historical cutoff), cached as one JSON list."""
    path = CACHE / f"{series}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())
    markets = {}
    for endpoint in ("/historical/markets", "/markets"):
        cursor = None
        while True:
            query = {"series_ticker": series, "limit": 1000}
            if cursor:
                query["cursor"] = cursor
            page = get(endpoint, **query)
            for m in page.get("markets", []):
                markets[m["ticker"]] = m
            cursor = page.get("cursor")
            if not cursor or not page.get("markets"):
                break
    path.parent.mkdir(parents=True, exist_ok=True)
    out = list(markets.values())
    path.write_text(json.dumps(out))
    return out


def historical_cutoff():
    """Markets settled before this moment are served only by Kalshi's historical endpoints."""
    return get("/historical/cutoff")["market_settled_ts"]


def fetch_candles(series, ticker, start_ts, end_ts, historical=False):
    """Hourly candlesticks for one market, cached (settled markets don't change).
    `historical` asks the historical endpoint first; the other is the fallback.
    A market that opened after `end_ts` (a day-only start) has none to fetch."""
    path = CACHE / "candles" / f"{ticker}.json"
    if path.exists():
        return json.loads(path.read_text())
    candles = []
    if end_ts > start_ts:
        query = {"start_ts": start_ts, "end_ts": end_ts, "period_interval": 60}
        paths = [
            f"/historical/markets/{ticker}/candlesticks",
            f"/series/{series}/markets/{ticker}/candlesticks",
        ]
        if not historical:
            paths.reverse()
        try:
            candles = get(paths[0], **query)["candlesticks"]
        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise
            candles = get(paths[1], **query)["candlesticks"]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(candles))
    return candles


def cached_candles(ticker):
    path = CACHE / "candles" / f"{ticker}.json"
    return json.loads(path.read_text()) if path.exists() else None


# ---------------------------------------------------------------- pricing


def _ts(value):
    if isinstance(value, str):
        value = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return int(value.timestamp())


def prefetch_candles(rows, series, pause=0.1):
    """Fetch candlesticks for `rows`, one market per match (the more traded of the
    two contracts; the other is used too when already cached), one request at a
    time with a short pause: parallel requests trip Kalshi's rate limit."""
    cutoff = historical_cutoff()
    todo = []
    for r in rows:
        if any(cached_candles(m["ticker"]) is not None for m in r["markets"]):
            continue
        todo.append(max(r["markets"], key=lambda m: m["volume"]))
    print(f"Fetching candlesticks for {len(todo)} {series} matches")
    for i, m in enumerate(todo, 1):
        fetch_candles(
            series,
            m["ticker"],
            _ts(m["open"]),
            _ts(m["start"]) + 3600,
            historical=m["close"] < cutoff,
        )
        time.sleep(pause)
        if i % 250 == 0:
            print(f"  {i}/{len(todo)}")


def market_chance(markets, team1, at):
    """Chance team1 wins from an event's markets at time `at`: the mean of team1's
    mid and one minus the opponent's, over the cached quotes within `MAX_SPREAD`."""
    chances, spreads = [], []
    for m in markets:
        candles = cached_candles(m["ticker"])
        if candles is None:
            continue
        mid, spread = quote_at(candles, _ts(at))
        if mid is None or spread > MAX_SPREAD:
            continue
        chances.append(mid if m["side"] == team1 else 1 - mid)
        spreads.append(spread)
    if not chances:
        return None, None
    return float(np.mean(chances)), float(np.mean(spreads))


# ---------------------------------------------------------------- our calls


def costs_at(markets, team1, at):
    """(cost of a team-1 contract, cost of a team-2 contract) when buying at the
    market at time `at`: the cheaper of the team's "yes" ask and one minus the
    opponent's "yes" bid, over cached quotes with a spread of at most
    `MAX_SPREAD`. None for a side with no quote."""
    best = [None, None]
    for m in markets:
        candles = cached_candles(m["ticker"])
        if candles is None:
            continue
        bid, ask = book_at(candles, _ts(at))
        if bid is None or ask - bid > MAX_SPREAD:
            continue
        mine, other = (0, 1) if m["side"] == team1 else (1, 0)
        for side, cost in ((mine, ask), (other, 1 - bid)):
            best[side] = cost if best[side] is None else min(best[side], cost)
    return tuple(best)


def _priced(cost):
    return cost is not None and cost == cost  # not None, not NaN


def bets(frame, edge=None):
    """Each bet as (cost, won, close): $1 on our pick (edge None), or only on a
    team whose chance by us beats its cost by more than `edge`. `close` is the
    market's closing chance for that team (None when unpriced)."""
    out = []
    for r in frame.itertuples():
        close = None if pd.isna(r.market_close) else r.market_close
        options = [
            (r.p_series, r.cost1, r.won1, close),
            (1 - r.p_series, r.cost2, not r.won1, None if close is None else 1 - close),
        ]
        if edge is None:
            p, cost, won, shut = options[0] if r.p_series >= 0.5 else options[1]
            if not _priced(cost):
                continue
        else:
            value = [
                (p - c, p, c, w, x)
                for p, c, w, x in options
                if _priced(c) and p - c > edge
            ]
            if not value:
                continue
            _, p, cost, won, shut = max(value, key=lambda v: v[0])
        out.append((cost, won, shut))
    return out


def bet_profits(frame, rate, edge=None, stake=1.0):
    """Profit of each bet (see `bets`) of $`stake` after Kalshi's fee at `rate`."""
    return np.array(
        [
            (stake / cost - stake if won else -stake) - fee(cost, stake, rate)
            for cost, won, _ in bets(frame, edge)
        ]
    )


def bet_clv(frame, edge=None):
    """Closing line value of each bet with a closing price: the market's closing
    chance for the team backed minus the price paid. It doesn't depend on who won,
    so it needs far fewer bets than profit to show an edge."""
    return np.array(
        [close - cost for cost, _, close in bets(frame, edge) if close is not None]
    )


def roi_interval(profits, n_resamples=2000, seed=0):
    """95% bootstrap interval of the mean profit per bet."""
    rng = np.random.default_rng(seed)
    means = [
        profits[rng.integers(0, len(profits), len(profits))].mean()
        for _ in range(n_resamples)
    ]
    return np.percentile(means, [2.5, 97.5])


def betting_section(s):
    frame = s[s["cost1"].notna() | s["cost2"].notna()]
    lines = [
        f"## Betting $1 a match, {BET_HOURS} hours before the start",
        "",
        f"Each bet buys $1 of a team's contract {BET_HOURS} hours before the scheduled start at the price a market "
        "order would pay (the team's ask, or one minus the opponent's bid, whichever is cheaper), then pays Kalshi's "
        "fee per order: ceil(rate × contracts × P × (1 − P)), to the cent (taker orders 7%, resting maker orders "
        "1.75%, which would fill at a better price than assumed here). *Back our pick* bets every match on the team "
        "we favour; *value* bets only where our chance beats the price by more than the edge shown. ROI is profit "
        "per dollar staked, with a 95% bootstrap interval over bets. CLV (closing line value) is the market's closing "
        "chance for the team backed minus the price paid, in points, with its interval and the share of bets that "
        "beat the close; it doesn't depend on results or fees. Contracts are treated as divisible, and the "
        "matches are those with an exact start time. The strategies were fixed before looking at the results.",
        "",
    ]
    for label, part in slices_of(frame):
        if label not in ("All", "FORGE (same major league)", "Other leagues"):
            continue
        lines += [
            f"**{label}** ({len(part)} series with a price)",
            "",
            "| Strategy | Fee | Bets | Won | Profit | ROI (95%) | CLV, points (95%) | Beat close |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for name, edge in [("Back our pick", None)] + [
            (f"Value, edge > {e:.2f}", e) for e in EDGES
        ]:
            clv = bet_clv(part, edge)
            if len(clv) >= 10:
                c_lo, c_hi = roi_interval(clv)
                clv_cells = (
                    f"{100 * clv.mean():+.2f} ({100 * c_lo:+.2f} to {100 * c_hi:+.2f}) | "
                    f"{100 * (clv > 0).mean():.0f}% |"
                )
            else:
                clv_cells = "— | — |"
            for fee_name, rate in FEE_RATES:
                prof = bet_profits(part, rate, edge)
                if len(prof) < 10:
                    continue
                lo, hi = roi_interval(prof)
                lines.append(
                    f"| {name} | {fee_name} | {len(prof)} | {int((prof > 0).sum())} | {prof.sum():+.2f} | "
                    f"{100 * prof.mean():+.1f}% ({100 * lo:+.1f}% to {100 * hi:+.1f}%) | {clv_cells}"
                )
        lines.append("")
    return lines


def bet_summary(s, rate=0.07):
    """The betting section's value bets at Kalshi's taker fee, split as the
    Predictions page splits calls (FORGE, and Elo: every other call), for the
    page's backtest rows (`docs/market_bets.json`). Like the report, only matches
    with an exact start time."""
    s = s[s["timed"]]
    frame = s[s["cost1"].notna() | s["cost2"].notna()]
    rows = []
    for label, part in (
        ("FORGE", frame[frame["method"] == "forge"]),
        ("Elo", frame[frame["method"] != "forge"]),
    ):
        for edge in (None, *EDGES):  # None: back our pick in every match
            prof, clv = bet_profits(part, rate, edge), bet_clv(part, edge)
            row = {
                "label": label,
                "edge": edge,
                "bets": len(prof),
                "won": int((prof > 0).sum()),
            }
            row["roi"] = float(prof.mean()) if len(prof) else None
            row["roi_ci"] = (
                [float(x) for x in roi_interval(prof)] if len(prof) >= 30 else None
            )
            row["clv"] = float(clv.mean()) if len(clv) else None
            row["clv_ci"] = (
                [float(x) for x in roi_interval(clv)] if len(clv) >= 30 else None
            )
            row["beat"] = float((clv > 0).mean()) if len(clv) else None
            rows.append(row)
    return {
        "generated": str(datetime.date.today()),
        "from": f"{frame['start'].min():%Y-%m-%d}",
        "to": f"{frame['start'].max():%Y-%m-%d}",
        "hours_before": BET_HOURS,
        "rows": rows,
    }


def load_pairs(since):
    """Every game since `since` from each team's side: gameid, date, team, opponent, result."""
    stmt = """
        SELECT a.gameid, a.date, a.teamname AS team, b.teamname AS opponent, a.result
        FROM matches a JOIN matches b ON a.gameid = b.gameid AND a.teamid != b.teamid
        WHERE a.date >= :since
    """
    pairs = pd.read_sql(
        text(stmt), utils.get_engine(), params={"since": since.isoformat()}
    )
    pairs["day"] = pd.to_datetime(pairs["date"]).dt.date
    return pairs


def series_games(pairs, team1, team2, start):
    """Games each team won against the other from the day before to two days after
    `start` (our dates and Kalshi's times can disagree by a day), from our data."""
    lo, hi = (start - datetime.timedelta(days=1)).date(), (
        start + datetime.timedelta(days=1)
    ).date()
    games = pairs[
        (pairs["team"] == team1)
        & (pairs["opponent"] == team2)
        & (pairs["day"] >= lo)
        & (pairs["day"] <= hi)
    ]
    return int(games["result"].sum()), int((1 - games["result"]).sum())


def _log(message):
    print(f"[{datetime.datetime.now():%H:%M:%S}] {message}", flush=True)


def our_calls(rows, states, match_team, cache):
    """Adds p_game, method, our names and `major` to rows we can rate. `cache`
    holds `ratings_before` by day, shared between calls."""
    out = []
    for row in rows:
        ours = [match_team(row["team1"]), match_team(row["team2"])]
        if None in ours or ours[0] == ours[1]:
            continue
        day = row["start"].date()
        if day not in cache:
            cache[day] = schedule.ratings_before(states, day)
            if len(cache) % 25 == 0:
                _log(f"ratings for {len(cache)} match days")
        ratings = cache[day]
        if not all(t in ratings.index for t in ours):
            continue
        p, method = schedule.game_probability(
            ratings.loc[ours[0]], ratings.loc[ours[1]]
        )
        major = row_is_major(
            ratings.loc[ours[0]]["league"], ratings.loc[ours[1]]["league"], method
        )
        out.append(
            {
                **row,
                "ours1": ours[0],
                "ours2": ours[1],
                "p_game": p,
                "method": method,
                "major": major,
            }
        )
    return out


def row_is_major(home1, home2, method):
    """Major-league or international (both teams from major leagues, or a FORGE call)."""
    majors = set(schedule.MAJORS)
    return method == "forge" or (home1 in majors and home2 in majors)


# ---------------------------------------------------------------- scoring


def compare(frame, ours_col, market_col, won_col="won1"):
    """Scores for ours and the market on the same rows, and the paired differences
    (ours minus market; negative log loss or Brier difference favours us)."""
    ours = game_losses(frame[ours_col], frame[won_col])
    market = game_losses(frame[market_col], frame[won_col])
    out = {"n": len(frame)}
    for stat in ("accuracy", "brier", "log_loss"):
        diff, lo, hi = paired_bootstrap(ours[stat], market[stat])
        out.update(
            {
                f"ours_{stat}": ours[stat].mean(),
                f"market_{stat}": market[stat].mean(),
                f"diff_{stat}": diff,
                f"lo_{stat}": lo,
                f"hi_{stat}": hi,
            }
        )
    return out


def logit(p):
    p = np.clip(np.asarray(p, dtype=float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def combined_weights(
    frame, ours_col, market_col, won_col="won1", n_resamples=1000, seed=0
):
    """Weights of the market's and our log-odds in a logistic fit of the result,
    with 95% bootstrap intervals. Team order is arbitrary, so no intercept."""
    x = np.column_stack([logit(frame[market_col]), logit(frame[ours_col])])
    y = frame[won_col].astype(int).to_numpy()

    def fit(xs, ys):
        return LogisticRegression(fit_intercept=False, C=1e6).fit(xs, ys).coef_[0]

    point = fit(x, y)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_resamples):
        idx = rng.integers(0, len(y), len(y))
        if len(set(y[idx])) == 2:
            draws.append(fit(x[idx], y[idx]))
    lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    return {"market": (point[0], lo[0], hi[0]), "ours": (point[1], lo[1], hi[1])}


def calibration(p, won, bins=10):
    """Expected calibration error over equal-width bins of the chance."""
    p, won = np.asarray(p, dtype=float), np.asarray(won, dtype=float)
    idx = np.minimum((p * bins).astype(int), bins - 1)
    return sum(
        abs(p[idx == b].mean() - won[idx == b].mean()) * (idx == b).sum()
        for b in range(bins)
        if (idx == b).any()
    ) / len(p)


# ---------------------------------------------------------------- report


def _fmt_diff(row, stat, scale=1.0, digits=4):
    return f"{scale * row[f'diff_{stat}']:+.{digits}f} ({scale * row[f'lo_{stat}']:+.{digits}f} to {scale * row[f'hi_{stat}']:+.{digits}f})"


def comparison_table(slices, ours_col, market_col):
    lines = [
        "| Matches | n | Picked, ours | Picked, market | Log loss, ours | Log loss, market | Δ log loss (95%) | Δ Brier (95%) |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, frame in slices:
        if len(frame) < 20:
            continue
        r = compare(frame, ours_col, market_col)
        lines.append(
            f"| {label} | {r['n']} | {100 * r['ours_accuracy']:.1f}% | {100 * r['market_accuracy']:.1f}% | "
            f"{r['ours_log_loss']:.4f} | {r['market_log_loss']:.4f} | {_fmt_diff(r, 'log_loss')} | {_fmt_diff(r, 'brier')} |"
        )
    return lines


def slices_of(frame):
    return [
        ("All", frame),
        ("Major league or international", frame[frame["major"]]),
        ("Other leagues", frame[~frame["major"]]),
        ("FORGE (same major league)", frame[frame["method"] == "forge"]),
        ("Elo (same other league)", frame[frame["method"] == "elo"]),
        ("Elo across leagues", frame[frame["method"] == "elo-cross"]),
    ]


def lead_ladder(s):
    """Ours against the market at each lead time, on the same matches: those with
    an exact start time (day-only starts have no real lead time) and a quote at the
    longest lead. Log loss with a paired bootstrap, and our weight beside the
    market in the joint fit at that lead."""
    common = s[s["timed"]].dropna(subset=[f"market_{h}h" for h in LEAD_HOURS])
    cols = [("At the close", "market_close")] + [
        (f"{h} hours before", f"market_{h}h") for h in LEAD_HOURS
    ]
    lines = [
        "## By lead time",
        "",
        f"The market's price at each lead time against our call (from the day before), on the same matches: "
        f"exact start times and a usable quote at every lead time up to {max(LEAD_HOURS)} hours. Our weight is from the joint fit described "
        "in the next section, refit at each lead time.",
        "",
    ]
    for label, frame in slices_of(common):
        if (
            label
            not in (
                "FORGE (same major league)",
                "Major league or international",
                "Other leagues",
            )
            or len(frame) < 50
        ):
            continue
        lines += [
            f"**{label}** ({len(frame)} series; our log loss {game_losses(frame['p_series'], frame['won1'])['log_loss'].mean():.4f})",
            "",
            "| Market price | Market log loss | Δ log loss, ours − market (95%) | Our weight beside it (95%) |",
            "|---|---:|---:|---:|",
        ]
        for name, col in cols:
            r = compare(frame, "p_series", col)
            w = combined_weights(frame, "p_series", col)["ours"]
            lines.append(
                f"| {name} | {r['market_log_loss']:.4f} | {_fmt_diff(r, 'log_loss')} | {w[0]:.2f} ({w[1]:.2f} to {w[2]:.2f}) |"
            )
        lines.append("")
    return lines


def report(series_frame, map_frame, counts):
    s = series_frame
    lines = [
        "# Our calls against the prediction market",
        "",
        f"Generated by `scripts/evaluate_markets.py` on {datetime.date.today()}. Market: Kalshi "
        f"(`{SERIES}` series winners, `{MAP}` single maps). Matches from {s['start'].min():%d %b %Y} to {s['start'].max():%d %b %Y}.",
        "",
        "Our call is reconstructed from games before the match day, as the Predictions page does for matches it "
        "missed; the forecast weights were fit on data that includes these matches, which flatters us a little. "
        f"The market's chance is the mid of the bid and ask, averaged over the two teams' contracts, left out when "
        f"no quote has a spread of {MAX_SPREAD:.2f} or less. Δ is ours minus the market's: a negative Δ log loss or "
        "Δ Brier means we did better. Intervals are paired bootstraps over matches.",
        "",
        "## Coverage",
        "",
        f"- Settled series markets (events): {counts['series_events']}; both teams rated by us: {counts['series_rated']}; "
        f"with the series found in our games: {counts['series_found']}; result agreeing with Kalshi's: {counts['series_agree']}.",
        f"- With a market quote at the close: {counts['series_close']}; also 12 hours before: {counts['series_early']}.",
        f"- Map-1 markets with both teams rated and a quote before the start: {len(map_frame)}.",
        f"- Kalshi team names we couldn't match (most are teams outside Oracle's Elixir): {counts['unmatched']}.",
        "",
        "## Series winners, at the close",
        "",
        "Last quote before the scheduled start. The market then knows lineups and late news; our call is the day before's.",
        "",
        *comparison_table(slices_of(s), "p_series", "market_close"),
        "",
    ]
    early = s.dropna(subset=["market_early"])
    lines += [
        f"## Series winners, {EARLY_HOURS} hours before the start",
        "",
        "Closer to what our call knew. Only matches whose market had a quote by then.",
        "",
        *comparison_table(slices_of(early), "p_series", "market_early"),
        "",
        "How far the market moved in those hours, on the same matches: "
        + _fmt_diff(compare(early, "market_early", "market_close"), "log_loss")
        + " log loss (early minus close).",
        "",
        *lead_ladder(s),
        *betting_section(s[s["timed"]]),
        "## Does our call add to the market?",
        "",
        "Logistic fit of the series result on the market's log-odds at the close and ours, without an intercept. "
        "A weight of 1 on the market and 0 on ours means we add nothing it doesn't already price.",
        "",
        "| Matches | n | Market weight (95%) | Our weight (95%) |",
        "|---|---:|---:|---:|",
    ]
    for label, frame in slices_of(s)[:3]:
        if len(frame) < 50:
            continue
        w = combined_weights(frame, "p_series", "market_close")
        lines.append(
            f"| {label} | {len(frame)} | {w['market'][0]:.2f} ({w['market'][1]:.2f} to {w['market'][2]:.2f}) | "
            f"{w['ours'][0]:.2f} ({w['ours'][1]:.2f} to {w['ours'][2]:.2f}) |"
        )
    lines += [
        "",
        "## Calibration",
        "",
        "Expected calibration error (games-weighted gap between chance and result over ten bins), series at the close.",
        "",
        "| Matches | n | Ours | Market |",
        "|---|---:|---:|---:|",
    ]
    for label, frame in slices_of(s)[:3]:
        lines.append(
            f"| {label} | {len(frame)} | {calibration(frame['p_series'], frame['won1']):.3f} | "
            f"{calibration(frame['market_close'], frame['won1']):.3f} |"
        )
    lines += [
        "",
        "## Single games: map 1",
        "",
        "The map-1 market's last quote before the series starts against our one-game chance, scored on map 1. "
        "Later maps' markets open during the series, when the score is known, so they don't compare.",
        "",
        *comparison_table(slices_of(map_frame), "p_game", "market_close"),
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------- main


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--out", help="Write the markdown report here")
    parser.add_argument(
        "--refresh", action="store_true", help="Refetch Kalshi's market lists"
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Rewrite the report from the last run's saved match tables (skips the slow ratings)",
    )
    args = parser.parse_args()
    saved = CACHE / "frames.pkl"
    if args.reuse:
        series_frame, map_frame, counts, unmatched = pd.read_pickle(saved)
        return _finish(series_frame, map_frame, counts, unmatched, args.out)

    _log("loading games and Form states")
    states = form_states(opponent_adjust(load_form_games()))
    data_end = pd.to_datetime(states["date"]).max().date()
    match_team = schedule.TeamMatcher(
        get_latest_elos("game_length"),
        {**json.loads(schedule.ALIASES_PATH.read_text()), **MARKET_ALIASES},
    )

    series_rows = [
        r
        for r in events(fetch_markets(SERIES, args.refresh))
        if r["start"].date() < data_end
    ]
    unmatched = sorted(
        {
            r[f"team{i}"]
            for r in series_rows
            for i in (1, 2)
            if match_team(r[f"team{i}"]) is None
        }
    )
    ratings_cache = {}
    rated = our_calls(series_rows, states, match_team, ratings_cache)
    print(f"{len(series_rows)} series markets, {len(rated)} between rated teams")

    prefetch_candles(rated, SERIES)
    pairs = load_pairs(
        min(r["start"] for r in series_rows).date() - datetime.timedelta(days=2)
    )
    found, agree, rows = 0, 0, []
    for i, r in enumerate(rated):
        w1, w2 = series_games(pairs, r["ours1"], r["ours2"], r["start"])
        if max(w1, w2) == 0:
            continue
        found += 1
        if (w1 > w2) != r["won1"]:
            continue
        agree += 1
        r["best_of"] = 2 * max(w1, w2) - 1
        r["p_series"] = schedule.series_probability(r["p_game"], r["best_of"])
        r["market_close"], r["spread_close"] = market_chance(
            r["markets"], r["team1"], r["start"]
        )
        early = r["start"] - datetime.timedelta(hours=EARLY_HOURS)
        r["market_early"], _ = market_chance(r["markets"], r["team1"], early)
        bet_at = r["start"] - datetime.timedelta(hours=BET_HOURS)
        r["cost1"], r["cost2"] = costs_at(r["markets"], r["team1"], bet_at)
        for h in LEAD_HOURS:
            at = r["start"] - datetime.timedelta(hours=h)
            r[f"market_{h}h"], _ = market_chance(r["markets"], r["team1"], at)
        if r["market_close"] is not None:
            rows.append(r)
    series_frame = pd.DataFrame(rows).drop(columns=["markets"])
    for col in ["market_early", "cost1", "cost2"] + [
        f"market_{h}h" for h in LEAD_HOURS
    ]:
        series_frame[col] = series_frame[col].astype(float)

    # Map 1, priced at the series' start.
    map_rows = [
        r
        for r in events(fetch_markets(MAP, args.refresh))
        if r["map"] == 1 and r["start"].date() < data_end
    ]
    map_rated = our_calls(map_rows, states, match_team, ratings_cache)
    prefetch_candles(map_rated, MAP)
    priced = []
    for r in map_rated:
        r["market_close"], _ = market_chance(r["markets"], r["team1"], r["start"])
        if r["market_close"] is not None:
            priced.append(r)
    map_frame = pd.DataFrame(priced).drop(columns=["markets"])

    counts = {
        "series_events": len(series_rows),
        "series_rated": len(rated),
        "series_found": found,
        "series_agree": agree,
        "series_close": len(series_frame),
        "series_early": int(series_frame["market_early"].notna().sum()),
        "unmatched": len(unmatched),
    }
    pd.to_pickle((series_frame, map_frame, counts, unmatched), saved)
    _finish(series_frame, map_frame, counts, unmatched, args.out)


def _finish(series_frame, map_frame, counts, unmatched, out):
    _log("writing the report")
    text = report(series_frame, map_frame, counts)
    print(text)
    print("\nUnmatched Kalshi names:", ", ".join(unmatched))
    if out:
        Path(out).write_text(text + "\n")
        print(f"Wrote {out}")
        bets = Path(out).with_name("market_bets.json")
        bets.write_text(json.dumps(bet_summary(series_frame), indent=1) + "\n")
        print(f"Wrote {bets}")


if __name__ == "__main__":
    main()
