"""International-only diagnostic on saved prices, rebuilding current published calls.

No fetching, refitting, DB writes or production changes. Run after setup_db.sh:
VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/international_markets.py
"""

import argparse
import datetime as dt
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from prometheus import form, schedule, utils
from prometheus.evaluation import game_losses
from prometheus.forge import other_league_weight
from prometheus.types import INTERNATIONAL_LEAGUES


def load_games(since):
    return pd.read_sql(
        """SELECT a.gameid, a.date, a.league, a.teamname AS team,
                  b.teamname AS opponent, a.result
           FROM matches a JOIN matches b
             ON a.gameid = b.gameid AND a.teamid != b.teamid
           WHERE a.date >= :since ORDER BY a.date, a.gameid""",
        utils.get_engine(),
        params={"since": since},
    ).assign(day=lambda g: pd.to_datetime(g.date).dt.date)


def attach_games(frame, games, series):
    """Reject ambiguous/repeated fixtures or disagreement with cached outcomes."""
    rows, rejected = [], []
    for row in frame.to_dict("records"):
        day = row["start"].date()
        found = games[
            (games.team == row["ours1"])
            & (games.opponent == row["ours2"])
            & (games.day >= day - dt.timedelta(days=1))
            & (games.day <= day + dt.timedelta(days=1))
        ]
        reason = None
        if found.empty:
            reason = "no games"
        elif found.league.nunique() != 1:
            reason = "multiple leagues"
        elif found.day.nunique() != 1:
            reason = "multiple game dates"
        else:
            wins = int(found.result.sum())
            losses = len(found) - wins
            won = wins > losses if series else bool(found.iloc[0].result)
            if series and (
                wins == losses or 2 * max(wins, losses) - 1 != row["best_of"]
            ):
                reason = "series length/tie mismatch"
            elif won != bool(row["won1"]):
                reason = "outcome mismatch"
        if reason:
            rejected.append({"event_ticker": row["event_ticker"], "reason": reason})
            continue
        row.update(
            league=found.iloc[0].league,
            first_game=found.iloc[0].gameid,
            game_date=str(found.iloc[0].date),
        )
        # OE labels EWC regional qualifiers as EWC too: retain that provenance,
        # but exclude qualifiers explicitly rather than treating them as global.
        row["qualifier"] = any(
            word in row["event"].lower() for word in ("qualifier", "regional finals")
        )
        row["international"] = (
            row["league"] in INTERNATIONAL_LEAGUES and not row["qualifier"]
        )
        rows.append(row)
    return pd.DataFrame(rows), pd.DataFrame(rejected)


def rebuild(frame, before, series):
    """Discard cached calls, home regions and methods; price/outcome remain fixed."""
    rows = []
    for row in frame.to_dict("records"):
        for hours, suffix in ((0, "close"), (12, "12h")):
            cutoff = (row["start"] - dt.timedelta(hours=hours)).date()
            ratings = before(cutoff)
            a, b = ratings.loc[row["ours1"]], ratings.loc[row["ours2"]]
            p, method = schedule.game_probability(a, b)
            slope = (
                schedule.CROSS_REGION_ELO_WEIGHT
                if a.league != b.league
                else schedule.ELO_WEIGHT
                if a.league in schedule.MAJORS
                else other_league_weight(a.league)
            )
            elo_p = float(expit(slope * (a.elo - b.elo)))
            if series:
                rho = schedule.series_rho(a.league, b.league)
                p = schedule.series_probability(p, row["best_of"], rho)
                elo_p = schedule.series_probability(elo_p, row["best_of"], rho)
            row[f"ours_{suffix}"] = p
            row[f"elo_{suffix}"] = elo_p
            row[f"cutoff_{suffix}"] = cutoff.isoformat()
            if hours == 0:
                row.update(
                    home1=a.league,
                    home2=b.league,
                    method=method,
                    major=a.league in schedule.MAJORS and b.league in schedule.MAJORS,
                    elo_gap=float(a.elo - b.elo),
                )
        row["pair"] = " / ".join(sorted((str(row["home1"]), str(row["home2"]))))
        row["cross_region"] = row["home1"] != row["home2"]
        rows.append(row)
    return pd.DataFrame(rows)


def phase_labels(frame, games):
    """First appearance proxy, not bracket rounds; count prior games, not prices."""
    out = frame.copy()
    out["phase"] = "later appearances"
    for _, part in out.groupby("event"):
        begin = pd.to_datetime(part.game_date).min().date()
        for idx, row in part.iterrows():
            day = pd.Timestamp(row.game_date).date()
            prior = games[
                (games.league == row.league) & (games.day >= begin) & (games.day < day)
            ]
            if not all((prior.team == team).any() for team in (row.ours1, row.ours2)):
                out.loc[idx, "phase"] = "either team's first appearance"
    return out


def interval(values, clusters=None, draws=4000):
    """Paired series bootstrap; cluster version resamples whole tournaments."""
    values = np.asarray(values, float)
    if not len(values):
        return (np.nan, np.nan)
    rng = np.random.default_rng(0)
    if clusters is None:
        means = values[rng.integers(len(values), size=(draws, len(values)))].mean(
            axis=1
        )
    else:
        codes, labels = pd.factorize(np.asarray(clusters))
        if len(labels) < 2:
            return (np.nan, np.nan)
        sums = np.bincount(codes, weights=values)
        counts = np.bincount(codes)
        samples = rng.integers(len(labels), size=(draws, len(labels)))
        means = sums[samples].sum(axis=1) / counts[samples].sum(axis=1)
    return tuple(np.quantile(means, [0.025, 0.975]))


def summarize(frame, ours, market):
    a, b = game_losses(frame[ours], frame.won1), game_losses(frame[market], frame.won1)
    delta = a["log_loss"] - b["log_loss"]
    lo, hi = interval(delta)
    elo_col = ours.replace("ours_", "elo_")
    e = game_losses(frame[elo_col], frame.won1)
    elo_delta = e["log_loss"] - b["log_loss"]
    elo_lo, elo_hi = interval(elo_delta)
    return {
        "n": len(frame),
        "events": frame.event.nunique(),
        "ours": a["log_loss"].mean(),
        "elo": e["log_loss"].mean(),
        "market": b["log_loss"].mean(),
        "delta": delta.mean(),
        "lo": lo,
        "hi": hi,
        "elo_delta": elo_delta.mean(),
        "elo_lo": elo_lo,
        "elo_hi": elo_hi,
        "accuracy": a["accuracy"].mean(),
        "market_accuracy": b["accuracy"].mean(),
        "brier_delta": (a["brier"] - b["brier"]).mean(),
    }


def format_delta(r, elo):
    prefix = "elo_" if elo else ""
    point = f"{r[prefix + 'delta']:+.4f}"
    if r["n"] < 10:
        return point + " (n < 10)"
    return point + f" [{r[prefix + 'lo']:+.4f}, {r[prefix + 'hi']:+.4f}]"


def table(slices, ours="ours_close", market="market_close"):
    lines = [
        "| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    for label, frame in slices:
        if frame.empty:
            continue
        r = summarize(frame, ours, market)
        lines.append(
            f"| {label} | {r['n']} | {r['ours']:.4f} | {r['elo']:.4f} | {r['market']:.4f} | "
            f"{format_delta(r, False)} | {format_delta(r, True)} |"
        )
    return lines + [""]


def residuals(frame, by):
    """Orient every match toward each region/team. Rows overlap; not independent."""
    rows = []
    for r in frame.itertuples():
        for side in (1, 2):
            rows.append(
                {
                    "label": getattr(r, f"{by}{side}"),
                    "won": float(r.won1) if side == 1 else 1 - float(r.won1),
                    "ours": r.ours_close if side == 1 else 1 - r.ours_close,
                    "market": r.market_close if side == 1 else 1 - r.market_close,
                }
            )
    f = pd.DataFrame(rows)
    if f.empty:
        return []
    lines = [
        "| Region/team | n | Won | Our mean chance | Kalshi mean chance | Won − ours | Kalshi − ours |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for label, part in f.groupby("label"):
        lines.append(
            f"| {label} | {len(part)} | {part.won.mean():.1%} | {part.ours.mean():.1%} | "
            f"{part.market.mean():.1%} | {part.won.mean() - part.ours.mean():+.1%} | "
            f"{part.market.mean() - part.ours.mean():+.1%} |"
        )
    return lines + [""]


def report(series, maps, audit):
    cross = series[series.cross_region]
    same = series[~series.cross_region]
    common = series[series.timed & series.market_early.notna()]
    lines = [
        "# International calls against Kalshi",
        "",
        "## Scope and limitations",
        "",
        f"Base commit `{audit['base_commit'][:7]}`, generated {audit['generated_utc']}. "
        "Current published ratings rebuilt from a private DB; saved odds, methods and home leagues are discarded. "
        "Prices/outcomes come from a fixed copied frames.pkl cohort. No new market fetching or forecast refitting.",
        "",
        f"Price cohort: {audit['price_start']} to {audit['price_end']}; DB through {audit['db_end']}. "
        f"Matched {audit['matched_series']} / {audit['cached_series']} series and "
        f"{audit['matched_maps']} / {audit['cached_maps']} map-1 contracts. "
        f"International non-qualifier sample: {len(series)} series, {len(maps)} maps. No Worlds fixture is in this price cohort.",
        "",
        "International means an OE INTERNATIONAL_LEAGUES event, excluding Kalshi titles containing ‘qualifier’ or ‘regional finals’ (three LPL regional-final series are labelled Worlds in OE). "
        "Same-home-region fixtures at these events are reported separately. Regional home leagues are as known at the forecast cutoff.",
        "",
        "At both the close and 12h, our call uses only games before the UTC calendar day of that cutoff, as production does. "
        "This matches the day-level information policy, not Kalshi's hour-level freshness: same-day games/news are omitted. "
        "Untimed starts are excluded from lead-time comparisons. Map-1 early quotes are unavailable in the saved frames.",
        "",
        "Series format is reconstructed from completed scores and checked against the saved best-of; this is a retrospective "
        "format assumption, not proof the format was available before start. Published fitted weights/rho include evaluated "
        "periods and prior experiments viewed these outcomes. This is a diagnostic, not held-out model selection or a trading result.",
        "",
        "LL is log loss (lower is better). Elo LL removes Form but retains the published forecast curve and series correlation; "
        "on cross-region fixtures it is exactly the published Elo forecast. Intervals resample paired series, 4,000 draws, fixed seed; maps are map 1 only. "
        "Small slices and multiple comparisons are descriptive; intervals are withheld below 10 fixtures. Event-cluster intervals below are especially weak with few events.",
        "",
        "## Series at the close",
        "",
    ]
    lines += table(
        [
            ("All international events", series),
            ("Cross-region", cross),
            ("Same-region at international events", same),
        ]
    )
    lines += [
        "## Same series, close versus 12 hours",
        "",
        f"{len(common)} exactly timed series priced at both cutoffs.",
        "",
    ]
    lines += table(
        [("Close", common)]
        + [(f"Close: {phase}", f) for phase, f in common.groupby("phase")]
    )
    lines += table(
        [("12h, rebuilt at that cutoff", common)]
        + [(f"12h: {phase}", f) for phase, f in common.groupby("phase")],
        "ours_12h",
        "market_early",
    )
    lines += [
        "## Senior events versus academy invitational",
        "",
        "WSCI is an academy event; report separately from MSI/First Stand/EWC.",
        "",
    ]
    lines += table(
        [
            ("Senior events", series[series.league != "WSCI"]),
            ("Academy WSCI", series[series.league == "WSCI"]),
        ]
    )
    lines += table([("Cross-region, close", common[common.cross_region])])
    lines += table(
        [("Cross-region, 12h", common[common.cross_region])], "ours_12h", "market_early"
    )
    lines += ["## Events at the close", ""] + table(list(series.groupby("event")))
    lines += ["## Region pairs at the close", ""] + table(list(cross.groupby("pair")))
    lines += ["## Best-of at the close", ""] + table(
        [(f"Bo{bo}", f) for bo, f in series.groupby("best_of")]
    )
    lines += [
        "## Tournament entry versus later appearances",
        "",
        "Proxy only: either team has no earlier game day in the OE event since its first matched fixture. "
        "Prior games need no market price. Same-day earlier fixtures are excluded, matching the forecast's day cutoff. "
        "Bracket round/stage labels are unavailable; this cannot distinguish Swiss/group/playoff rounds.",
        "",
    ]
    lines += table(list(series.groupby("phase")))
    lines += table(
        [
            (f"{event}: {phase}", f)
            for (event, phase), f in series.groupby(["event", "phase"])
        ]
    )
    lines += table(
        [(f"Cross-region: {phase}", f) for phase, f in cross.groupby("phase")]
    )
    lines += ["## Map 1 at the close", ""] + table(
        [
            ("All international maps", maps),
            ("Cross-region maps", maps[maps.cross_region]),
            ("Same-region maps", maps[~maps.cross_region]),
        ]
    )
    # Matched contracts identify exactly the same fixture, not identical event ticker families.
    keys = ["ours1", "ours2", "start"]
    shared = series.merge(
        maps[keys + ["ours_close", "elo_close", "market_close", "won1"]],
        on=keys,
        suffixes=("", "_map"),
        validate="one_to_one",
    )
    lines += [
        "## Series and map 1 on matched fixtures",
        "",
        f"{len(shared)} fixtures have both contracts.",
        "",
    ]
    lines += table([("Series", shared)])
    map_shared = shared.copy()
    for col in ("ours_close", "elo_close", "market_close", "won1"):
        map_shared[col] = shared[f"{col}_map"]
    lines += table([("Map 1", map_shared)])
    lines += [
        "## Favourite calibration at entry",
        "",
        "Each cross-region series oriented toward Elo's favourite. This separates underconfidence from overconfidence; "
        "these selected slices are descriptive and do not choose a recalibration curve.",
        "",
        "| Appearance | n | Favourite won | Elo mean chance | Kalshi mean chance | Elo picked | Kalshi picked |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for phase, f in cross.groupby("phase"):
        fav = f.ours_close >= 0.5
        y = np.where(fav, f.won1, 1 - f.won1.astype(int))
        ours = np.where(fav, f.ours_close, 1 - f.ours_close)
        market = np.where(fav, f.market_close, 1 - f.market_close)
        r = summarize(f, "ours_close", "market_close")
        lines.append(
            f"| {phase} | {len(f)} | {y.mean():.1%} | {ours.mean():.1%} | {market.mean():.1%} | {r['accuracy']:.1%} | {r['market_accuracy']:.1%} |"
        )
    lines += [""]
    lines += [
        "## Cross-region residuals",
        "",
        "Series probabilities oriented toward each region/team. Positive won − ours means underestimated observed wins; "
        "positive Kalshi − ours means the market rated it higher. Overlapping rows, selected representatives, tiny samples: "
        "these do not identify a regional effect independently of team strength.",
        "",
    ]
    lines += residuals(cross, "home")
    lines += residuals(cross, "ours")
    lines += [
        "## Event-cluster sensitivity",
        "",
        "Paired series LL differences resampled by complete Kalshi tournament title. With very few tournaments "
        "these intervals do not establish future-event generalization.",
        "",
    ]
    for label, f in (("All international", series), ("Cross-region", cross)):
        if f.empty:
            continue
        diff = (
            game_losses(f.ours_close, f.won1)["log_loss"]
            - game_losses(f.market_close, f.won1)["log_loss"]
        )
        lo, hi = interval(diff, f.event)
        lines.append(
            f"- {label}: {f.event.nunique()} events; Δ {diff.mean():+.4f}, event-cluster 95% [{lo:+.4f}, {hi:+.4f}]."
        )
    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cache", type=Path, default=Path("data/markets/frames.pkl"))
    p.add_argument(
        "--out", type=Path, default=Path("docs/research/international_market_report.md")
    )
    p.add_argument("--export", type=Path, default=Path("data/international_markets"))
    args = p.parse_args()
    started = time.perf_counter()
    series, maps, *_ = pd.read_pickle(args.cache)
    since = (series.start.min() - dt.timedelta(days=2)).date().isoformat()
    games = load_games(since)
    s, sr = attach_games(series, games, True)
    m, mr = attach_games(maps, games, False)
    audit = {
        "cached_series": len(series),
        "cached_maps": len(maps),
        "matched_series": len(s),
        "matched_maps": len(m),
        "price_start": str(series.start.min()),
        "price_end": str(series.start.max()),
        "db_end": str(games.date.max()),
        "cache_sha256": hashlib.sha256(args.cache.read_bytes()).hexdigest(),
        "qualifier_series": int(
            (s.league.isin(INTERNATIONAL_LEAGUES) & s.qualifier).sum()
        ),
    }
    print(json.dumps(audit, indent=2), flush=True)
    audit.update(
        base_commit=subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        generated_utc=dt.datetime.now(dt.UTC).isoformat(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        weights_sha256={
            name: hashlib.sha256((Path("prometheus") / name).read_bytes()).hexdigest()
            for name in (
                "forge_weights.json",
                "form_weights.json",
                "league_curves.json",
            )
        },
        rejected_series_reasons=sr.reason.value_counts().to_dict(),
        rejected_map_reasons=mr.reason.value_counts().to_dict(),
    )
    before = schedule.RatingsBefore(form.load_states())
    s = phase_labels(rebuild(s[s.international], before, True), games)
    m = rebuild(m[m.international], before, False)
    args.export.mkdir(parents=True, exist_ok=True)
    for name, frame in (
        ("series", s),
        ("map1", m),
        ("rejected_series", sr),
        ("rejected_map1", mr),
    ):
        frame.to_csv(args.export / f"{name}.csv", index=False)
    audit.update(
        runtime_seconds=round(time.perf_counter() - started, 3), cutoff_days=len(before)
    )
    (args.export / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    args.out.write_text(report(s, m, audit))
    print(
        f"Wrote {args.out}; {audit['runtime_seconds']}s, {len(before)} cutoff days",
        flush=True,
    )


if __name__ == "__main__":
    main()
