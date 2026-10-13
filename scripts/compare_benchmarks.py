"""
compare_benchmarks.py: Compare two benchmark dumps (base and head) on the same units.

Reads the `--dump` output of `evaluate_metrics.py`, `evaluate_season_stats.py`,
`evaluate_aura.py` and `evaluate_markets.py` for two versions of the code, pairs them on shared keys (games,
team-seasons, player-seasons) and reports each headline difference with a 95%
paired-bootstrap interval:

- Forecasts: log loss per section and forecast, head minus base
  (`evaluation.paired_bootstrap` over games).
- Season stats: split-half reliability and r with the other half's win %, head
  minus base (resampling team-seasons).
- AURA (held-out check): split-half r, new-team r and roster r, head minus base,
  and each snapshot's calibration ECE.
- Kalshi markets: log loss of our series and map-1 calls on the same settled
  markets, head minus base (Kalshi's prices are the same on both sides).
- Betting (report only, never guarded): the Predictions page's Table IV paper
  bets (`schedule.paper_bets`, $1 12 hours out, 7% fee) by edge, base and head on
  the same series, with head minus base return and CLV over markets.

A line is "better" or "worse" when its interval lies entirely on one side of 0,
otherwise "within noise". The exit code is 1 when a guarded value is significantly
worse (see `GUARDED_*`), or AURA's ECE is above `ECE_LIMIT` at any snapshot, and 0
otherwise. Rows present in only one dump are counted, not compared.

Usage:
    uv run python scripts/compare_benchmarks.py BASE_DIR HEAD_DIR [--out report.md]
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

from prometheus import schedule
from prometheus.evaluation import (
    ece,
    game_losses,
    interval,
    paired_bootstrap,
    paired_correlation_bootstrap,
    resamples,
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# The published forecasts in each section of the forecast backtest (AGENTS.md:
# domestic and international log loss must not get significantly worse; the
# cross-league and within-other-league sections cover accuracy fixes).
GUARDED_FORECASTS = {
    ("Domestic", "forge"),
    ("Domestic", "elo_live"),
    ("International", "forge"),
    ("International", "elo_live"),
    ("Cross-league", "elo_live"),
    ("Within other leagues", "elo_per_league"),
    ("Within other leagues", "forge"),
}
# Published season stats.
GUARDED_STATS = {"glory"}
ECE_LIMIT = 0.01
# Our calls on Kalshi's markets (the accuracy-fix rule's market benchmark): every
# series, FORGE within a major league (the calls the alerts use), and map 1.
GUARDED_MARKETS = {("series", "all"), ("series", "forge (major)"), ("map1", "all")}
MARKET_KEY = ["kind", "event_ticker", "team1"]
N_RESAMPLES = 2000
# Base and head run on different machines, so identical code can differ by about
# 1e-16 per row (floating point); over thousands of rows every resample then lands
# on one side of 0. A difference counts only when its interval clears this.
TOLERANCE = 1e-6
FORECAST_KEY = ["section", "forecast", "gameid", "teamid"]
SEASON_KEY = ["teamname", "year"]
PLAYER_KEY = ["playerid", "year", "position"]
ROSTER_KEY = ["teamname", "year", "half"]


def _verdict(lo, hi, lower_is_better):
    if lower_is_better:
        lo, hi = -hi, -lo
    if lo > TOLERANCE:
        return "better"
    if hi < -TOLERANCE:
        return "worse"
    return "within noise"


def _row(section, name, base, head, interval, lower_is_better, guarded, unpaired):
    diff, lo, hi = interval
    return {
        "section": section,
        "name": name,
        "base": base,
        "head": head,
        "diff": diff,
        "lo": lo,
        "hi": hi,
        "result": _verdict(lo, hi, lower_is_better),
        "guarded": guarded,
        "unpaired": unpaired,
    }


def _missing(section, name, guarded, unpaired):
    return {
        "section": section,
        "name": name,
        "result": "not paired",
        "guarded": guarded,
        "unpaired": unpaired,
    }


def _pair(base, head, key):
    """Inner join on `key` (repeated keys numbered in order), with the rows only
    one side has counted as (base only, head only)."""
    base = base.assign(_n=base.groupby(key).cumcount())
    head = head.assign(_n=head.groupby(key).cumcount())
    both = base.merge(
        head, on=key + ["_n"], how="outer", suffixes=("_base", "_head"), indicator=True
    )
    only = (
        int((both["_merge"] == "left_only").sum()),
        int((both["_merge"] == "right_only").sum()),
    )
    return both[both["_merge"] == "both"].reset_index(drop=True), only


def _rows_bootstrap(stat, base, head, groups=None, n_resamples=N_RESAMPLES, seed=0):
    """stat(head) - stat(base) and its 95% interval, resampling rows (or `groups`
    of rows together) in both at once. `base` and `head` are 2-D arrays."""
    codes = (
        np.arange(len(base)) if groups is None else pd.factorize(pd.Series(groups))[0]
    )
    members = [np.flatnonzero(codes == k) for k in range(codes.max() + 1)]
    diffs = [
        stat(head[rows]) - stat(base[rows])
        for rows in resamples(members, n_resamples, seed)
    ]
    return (stat(head) - stat(base), *interval(diffs))


def _corr(x, y):
    return np.corrcoef(x, y)[0, 1]


def compare_forecasts(base, head, n_resamples=N_RESAMPLES):
    """Log loss per (section, forecast) on the games both dumps scored."""
    rows = []
    sections = pd.concat([base, head])[["section", "forecast"]].drop_duplicates()
    for section, forecast in sections.itertuples(index=False):
        guarded = (section, forecast) in GUARDED_FORECASTS

        def pick(d, section=section, forecast=forecast):
            return d[(d["section"] == section) & (d["forecast"] == forecast)]

        both, only = _pair(pick(base), pick(head), FORECAST_KEY)
        if both.empty:
            rows.append(_missing(section, forecast, guarded, only))
            continue
        b, h = both["log_loss_base"].to_numpy(), both["log_loss_head"].to_numpy()
        rows.append(
            _row(
                section,
                f"{forecast} log loss ({len(both):,} games)",
                b.mean(),
                h.mean(),
                paired_bootstrap(h, b, n_resamples=n_resamples),
                True,
                guarded,
                only,
            )
        )
    return rows


def _season_side(halves, stat, min_games):
    t = halves[halves["stat"] == stat]
    t = t.dropna(subset=["h0", "h1"])
    return t[(t["n0"] >= min_games) & (t["n1"] >= min_games)]


def _centred(both, cols):
    years = both["year"]
    return np.column_stack(
        [both[c] - both[c].groupby(years).transform("mean") for c in cols]
    )


def _other_half_r(x):
    """Mean of r(h0, other win h1) and r(h1, win h0): columns h0, h1, win_h0, win_h1."""
    return (_corr(x[:, 0], x[:, 3]) + _corr(x[:, 1], x[:, 2])) / 2


def compare_season_stats(base, base_meta, head, head_meta, n_resamples=N_RESAMPLES):
    """Split-half r and r with the other half's win %, per stat, on shared team-seasons.

    Each side's halves are filtered with its own `min_half_games`; values are
    centred within year on the paired sample, as the report does on its own.
    """
    rows = []
    stats = list(dict.fromkeys([*base["stat"], *head["stat"]]))
    sides = {
        "base": (base, base_meta["min_half_games"]),
        "head": (head, head_meta["min_half_games"]),
    }
    for stat in stats:
        guarded = stat in GUARDED_STATS
        b, h = (_season_side(d, stat, m) for d, m in sides.values())
        both, only = _pair(b, h, SEASON_KEY)
        if both.empty:
            rows.append(_missing("Season stats", stat, guarded, only))
            continue
        cb = _centred(both, ["h0_base", "h1_base"])
        ch = _centred(both, ["h0_head", "h1_head"])
        rows.append(
            _row(
                "Season stats",
                f"{stat} split-half r ({len(both):,} team-seasons)",
                _corr(cb[:, 0], cb[:, 1]),
                _corr(ch[:, 0], ch[:, 1]),
                paired_correlation_bootstrap(
                    (ch[:, 0], ch[:, 1]), (cb[:, 0], cb[:, 1]), n_resamples=n_resamples
                ),
                False,
                guarded,
                only,
            )
        )
        # r with the other half's win %: each side against its own win % halves
        # (filtered on the stat's half sizes only, as `other_half` does).
        with_win = []
        for d, m in sides.values():
            win = d[d["stat"] == "win_pct"].dropna(subset=["h0", "h1"])
            win = win[SEASON_KEY + ["h0", "h1"]]
            side = _season_side(d, stat, m).merge(
                win.rename(columns={"h0": "win_h0", "h1": "win_h1"}), on=SEASON_KEY
            )
            with_win.append(side)
        both, only = _pair(*with_win, SEASON_KEY)
        if both.empty:
            rows.append(_missing("Season stats", f"{stat} other half", guarded, only))
            continue
        cols = ["h0", "h1", "win_h0", "win_h1"]
        cb = _centred(both, [f"{c}_base" for c in cols])
        ch = _centred(both, [f"{c}_head" for c in cols])
        rows.append(
            _row(
                "Season stats",
                f"{stat} r with other half's win % ({len(both):,} team-seasons)",
                _other_half_r(cb),
                _other_half_r(ch),
                _rows_bootstrap(_other_half_r, cb, ch, n_resamples=n_resamples),
                False,
                guarded,
                only,
            )
        )
    return rows


def compare_aura(base, head, n_resamples=N_RESAMPLES):
    """The AURA rule's 'not significantly worse' checks on the held-out data.

    `base` and `head` map halves, moved, roster and calibration to their frames.
    """
    rows = []
    section = "AURA"
    for name, frame, key, cols in (
        ("split-half r", "halves", PLAYER_KEY, ("aura_0", "aura_1")),
        ("new-team r", "moved", PLAYER_KEY, ("aura", "aura_next")),
    ):
        both, only = _pair(base[frame], head[frame], key)
        if both.empty:
            rows.append(_missing(section, name, True, only))
            continue
        b = tuple(both[f"{c}_base"].to_numpy() for c in cols)
        h = tuple(both[f"{c}_head"].to_numpy() for c in cols)
        rows.append(
            _row(
                section,
                f"{name} ({len(both):,} player-seasons)",
                _corr(*b),
                _corr(*h),
                paired_correlation_bootstrap(h, b, n_resamples=n_resamples),
                False,
                True,
                only,
            )
        )
    both, only = _pair(base["roster"], head["roster"], ROSTER_KEY)
    if both.empty:
        rows.append(_missing(section, "roster r", True, only))
    else:
        cols = lambda s: both[[f"aura_{s}", f"win_{s}"]].to_numpy()
        r = lambda x: _corr(x[:, 0], x[:, 1])
        seasons = both["teamname"].astype(str) + "|" + both["year"].astype(str)
        n = seasons.nunique()
        rows.append(
            _row(
                section,
                f"roster r ({n:,} team-seasons)",
                r(cols("base")),
                r(cols("head")),
                _rows_bootstrap(
                    r, cols("base"), cols("head"), seasons, n_resamples=n_resamples
                ),
                False,
                True,
                only,
            )
        )
    return rows


def aura_ece(base, head):
    """ECE at each snapshot, base and head (head must stay under `ECE_LIMIT`)."""
    rows = []
    minutes = sorted(set(base["minute"]) | set(head["minute"]))
    for minute in minutes:
        b, h = (d[d["minute"] == minute] for d in (base, head))
        value = lambda d: (
            ece(d["p"].to_numpy(), d["won"].to_numpy()) if len(d) else np.nan
        )
        head_ece = value(h)
        bad = np.isfinite(head_ece) and head_ece > ECE_LIMIT
        only = (
            int((~b["gameid"].isin(h["gameid"])).sum()),
            int((~h["gameid"].isin(b["gameid"])).sum()),
        )
        rows.append(
            {
                "section": "AURA",
                "name": f"ECE at {minute} min (limit {ECE_LIMIT})",
                "base": value(b),
                "head": head_ece,
                "result": f"above {ECE_LIMIT}" if bad else "under the limit",
                "guarded": True,
                "failed": bad,
                "unpaired": only,
            }
        )
    return rows


def _market_slice(frame):
    major = frame["major"].astype(str).str.lower() == "true"
    forge = frame["method"] == "forge"
    return np.select(
        [forge & major, forge], ["forge (major)", "forge (other league)"], "other"
    )


def compare_markets(base, head, n_resamples=N_RESAMPLES):
    """Log loss of our calls per kind (series, map 1) and slice, on the markets
    both dumps scored. Slices follow the head's method."""
    rows = []
    for kind in ("series", "map1"):
        both, only = _pair(
            base[base["kind"] == kind], head[head["kind"] == kind], MARKET_KEY
        )
        if both.empty:
            rows.append(_missing("Markets", f"{kind} log loss", True, only))
            continue
        head_rows = both.rename(
            columns={"method_head": "method", "major_head": "major"}
        )
        slices = _market_slice(head_rows)
        for name in ["all", "forge (major)", "forge (other league)", "other"]:
            pick = both if name == "all" else both[slices == name]
            if pick.empty or (kind == "map1" and name != "all"):
                continue
            b = game_losses(pick["p_base"], pick["won1_base"])["log_loss"].to_numpy()
            h = game_losses(pick["p_head"], pick["won1_head"])["log_loss"].to_numpy()
            rows.append(
                _row(
                    "Markets",
                    f"{kind} log loss, {name} ({len(pick):,})",
                    b.mean(),
                    h.mean(),
                    paired_bootstrap(h, b, n_resamples=n_resamples),
                    True,
                    (kind, name) in GUARDED_MARKETS,
                    only,
                )
            )
    return rows


# The Predictions page's paper bets: its edges and fee (`schedule.edge_record`).
BET_RATE = 0.07
PRICE_COLUMNS = ["cost1", "cost2", "market_close"]


def _prices(both):
    """Kalshi's bet prices per paired series. They are the same market data on
    both sides, so either side's columns serve (the head's first): a base from
    before the dump carried prices still gets its bets scored."""
    out = {}
    for c in PRICE_COLUMNS:
        for name in (f"{c}_head", c, f"{c}_base"):
            if name in both.columns:
                out[c] = pd.to_numeric(both[name], errors="coerce").to_numpy()
                break
        else:
            return None
    return out


def _bet_arrays(p, won1, prices, edges):
    """Per series and edge, the paper bet's profit, CLV and whether it beat the
    close (NaN where no bet), as Table IV makes them."""
    n = len(p)
    profit = {e: np.full(n, np.nan) for e in edges}
    clv = {e: np.full(n, np.nan) for e in edges}
    nan = lambda x: None if x != x else float(x)
    for i in range(n):
        made = schedule.paper_bets(
            float(p[i]),
            (nan(prices["cost1"][i]), nan(prices["cost2"][i])),
            1 if won1[i] else 2,
            nan(prices["market_close"][i]),
            BET_RATE,
        )
        if made is None:
            continue
        for e in edges:
            bet = made["pick"] if e is None else made["value"]
            if bet is None or (e is not None and not bet["edge"] > e):
                continue
            profit[e][i] = bet["profit"]
            if bet["clv"] is not None:
                clv[e][i] = bet["clv"]
    return profit, clv


def _mean(x):
    return float(np.nanmean(x)) if np.isfinite(x).any() else np.nan


def _diff_interval(b, h, draws):
    """Head minus base of the mean over bets made, and its 95% interval over
    resampled series (both sides drawn together)."""
    diffs = [_mean(h[i]) - _mean(b[i]) for i in draws]
    diffs = [d for d in diffs if np.isfinite(d)]
    if not np.isfinite(_mean(h) - _mean(b)) or len(diffs) < len(draws) / 2:
        return None
    return (_mean(h) - _mean(b), *interval(diffs))


def compare_betting(base, head, n_resamples=N_RESAMPLES, edges=schedule.BET_EDGES):
    """Table IV's paper bets on the series both dumps scored, per slice (all,
    FORGE within a major league, other; the head's method) and edge: bets, mean
    return per $1 and CLV for base and head, and head minus base with a 95%
    interval over series. Returns (rows, note); rows are never guarded."""
    both, only = _pair(
        base[base["kind"] == "series"], head[head["kind"] == "series"], MARKET_KEY
    )
    if both.empty:
        return [], "Betting: no series both dumps scored, not compared."
    prices = _prices(both)
    if prices is None:
        return [], (
            "Betting: neither dump carries Kalshi's bet prices (an older "
            "`evaluate_markets.py`), not compared."
        )
    won1 = both["won1_head"].astype(bool).to_numpy()
    sides = {
        s: _bet_arrays(both[f"p_{s}"].to_numpy(), won1, prices, edges)
        for s in ("base", "head")
    }
    head_rows = both.rename(columns={"method_head": "method", "major_head": "major"})
    slices = _market_slice(head_rows)
    slices = np.where(slices == "forge (major)", "FORGE", "Other")
    rows = []
    for name in ("All", "FORGE", "Other"):
        pick = np.ones(len(both), bool) if name == "All" else slices == name
        if not pick.any():
            continue
        draws = list(resamples(int(pick.sum()), n_resamples, seed=0))
        for e in edges:
            (bp, bc), (hp, hc) = (
                (sides[s][0][e][pick], sides[s][1][e][pick]) for s in ("base", "head")
            )
            rows.append(
                {
                    "section": "Betting",
                    "slice": name,
                    "series": int(pick.sum()),
                    "edge": e,
                    "bets": (int(np.isfinite(bp).sum()), int(np.isfinite(hp).sum())),
                    "roi": (_mean(bp), _mean(hp)),
                    "roi_diff": _diff_interval(bp, hp, draws),
                    "clv": (_mean(bc), _mean(hc)),
                    "clv_diff": _diff_interval(bc, hc, draws),
                    "beat": tuple(
                        _mean(np.where(np.isfinite(c), c > 0, np.nan)) for c in (bc, hc)
                    ),
                    "guarded": False,
                    "unpaired": only,
                }
            )
    return rows, None


def _pct(v, signed=True):
    return (
        "—"
        if v is None or not np.isfinite(v)
        else f"{100 * v:{'+' if signed else ''}.1f}"
    )


def _pct_interval(d):
    if d is None:
        return "—"
    return f"{100 * d[0]:+.1f} ({100 * d[1]:+.1f} to {100 * d[2]:+.1f})"


def render_betting(rows):
    """Markdown for the betting rows: one table, slices as row groups."""
    if not rows:
        return []
    lines = [
        "",
        "#### Betting (report only)",
        "",
        "$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in "
        "every series (Any), or where our chance beat Kalshi's price by more than the edge. Return "
        "is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. "
        "Never fails the check.",
        "",
        "| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) "
        "| CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |",
        "|---|---:|---:|---:|---|---:|---|---:|",
    ]
    for r in rows:
        edge = "Any" if r["edge"] is None else f"> {100 * r['edge']:g}"
        lines.append(
            f"| {r['slice']} ({r['series']:,}) | {edge} | {r['bets'][0]:,} / {r['bets'][1]:,} "
            f"| {_pct(r['roi'][0])} / {_pct(r['roi'][1])} | {_pct_interval(r['roi_diff'])} "
            f"| {_pct(r['clv'][0])} / {_pct(r['clv'][1])} | {_pct_interval(r['clv_diff'])} "
            f"| {_pct(r['beat'][0], False)} / {_pct(r['beat'][1], False)} |"
        )
    return lines


def failures(rows):
    """Guarded rows that are significantly worse, or an ECE over the limit."""
    return [
        r
        for r in rows
        if r["guarded"] and (r["result"] == "worse" or r.get("failed", False))
    ]


def _fmt(v, digits):
    return "—" if v is None or not np.isfinite(v) else f"{v:.{digits}f}"


def render(sections, notes=()):
    """Markdown: a verdict line, then one table per benchmark."""
    rows = [r for _, part in sections for r in part]
    bad = failures(rows)
    if bad:
        names = "; ".join(f"{r['section']}: {r['name']}" for r in bad)
        lines = [f"**Benchmarks: {len(bad)} guarded check(s) failed** ({names})."]
    else:
        lines = ["**Benchmarks: no guarded value is significantly worse.**"]
    lines += list(notes)
    for title, part in sections:
        if not part or title == "Betting":
            continue
        digits = 4 if title in ("Forecasts", "Markets") else 3
        lines += [
            "",
            f"#### {title}",
            "",
            "| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |",
            "|---|---|---:|---:|---|---|---:|",
        ]
        for r in part:
            interval = (
                f"{r['diff']:+.{digits}f} ({r['lo']:+.{digits}f} to {r['hi']:+.{digits}f})"
                if "diff" in r
                else "—"
            )
            name = f"**{r['name']}**" if r["guarded"] else r["name"]
            result = r["result"]
            if any(r is x for x in bad):
                result = f"**{result}**"
            lines.append(
                f"| {r['section']} | {name} | {_fmt(r.get('base'), digits)} "
                f"| {_fmt(r.get('head'), digits)} | {interval} | {result} "
                f"| {r['unpaired'][0]:,} / {r['unpaired'][1]:,} |"
            )
    lines += render_betting(dict(sections).get("Betting", []))
    lines += [
        "",
        "Bold measures are guarded: the check fails when one is significantly worse "
        "(its interval entirely on the bad side) or AURA's ECE is above "
        f"{ECE_LIMIT}. Lower log loss and higher r are better.",
    ]
    return "\n".join(lines)


def _read(dirname, name):
    path = os.path.join(dirname, name)
    return pd.read_csv(path) if os.path.exists(path) else None


def _meta(dirname, name):
    path = os.path.join(dirname, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def compare_dirs(base_dir, head_dir, n_resamples=N_RESAMPLES):
    """Compare every benchmark both directories hold; returns (sections, notes)."""
    sections, notes = [], []
    sub = lambda d, s: os.path.join(d, s)

    b, h = (_read(sub(d, "metrics"), "forecasts.csv.gz") for d in (base_dir, head_dir))
    if b is not None and h is not None:
        sections.append(("Forecasts", compare_forecasts(b, h, n_resamples)))
    else:
        notes.append("Forecast backtest: missing from one side, not compared.")

    b, h = (_read(sub(d, "season"), "halves.csv.gz") for d in (base_dir, head_dir))
    bm, hm = (_meta(sub(d, "season"), "metrics.json") for d in (base_dir, head_dir))
    if b is not None and h is not None:
        sections.append(
            ("Season stats", compare_season_stats(b, bm, h, hm, n_resamples))
        )
    else:
        notes.append("Season-stat report: missing from one side, not compared.")

    names = ("halves", "moved", "roster", "calibration")
    b, h = (
        {n: _read(sub(d, "aura"), f"{n}.csv.gz") for n in names}
        for d in (base_dir, head_dir)
    )
    if all(v is not None for v in [*b.values(), *h.values()]):
        sections.append(
            (
                "AURA",
                compare_aura(b, h, n_resamples)
                + aura_ece(b["calibration"], h["calibration"]),
            )
        )
    else:
        notes.append("AURA report: missing from one side, not compared.")

    b, h = (_read(sub(d, "markets"), "calls.csv.gz") for d in (base_dir, head_dir))
    if b is not None and h is not None:
        sections.append(("Markets", compare_markets(b, h, n_resamples)))
        betting, note = compare_betting(b, h, n_resamples)
        if betting:
            sections.append(("Betting", betting))
        if note:
            notes.append(note)
    else:
        notes.append(
            "Market benchmark: missing from one side (no Kalshi cache in CI yet, "
            "or the base can't dump it), not compared."
        )
    return sections, notes


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "base", help="Base dump directory (metrics/, season/, aura/, markets/ inside)"
    )
    parser.add_argument("head", help="Head dump directory (same layout)")
    parser.add_argument("--out", help="Also write the report to this Markdown file")
    args = parser.parse_args()

    sections, notes = compare_dirs(args.base, args.head)
    report = render(sections, notes)
    print(report)
    if args.out:
        with open(args.out, "w") as f:
            f.write(report + "\n")
    sys.exit(1 if failures([r for _, part in sections for r in part]) else 0)


if __name__ == "__main__":
    main()
