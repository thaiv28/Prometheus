"""Earlier-series-only live trading study; see live_trading_protocol.md.

No production imports are mutated, no network requests, and no orders.
"""

import argparse
import hashlib
import heapq
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_live as el

from prometheus.live import timeline

PIN = "0705f02b1edf6df391809ba59a34ea4857fe2224757d7c509225e3875692422c"


def effective_cost(price):
    """One-contract rounded fee; continuous scaling only for research sizing."""
    price = np.asarray(price, dtype=float)
    return price + np.ceil((0.07 * price * (1 - price) - 1e-12) * 10000) / 10000


def prepare(data, db):
    current, skipped = el.replay(data, db=db)
    legacy, _ = el.replay(
        data, db=db, model_path=ROOT / "prometheus/live/time_model_v1.json"
    )
    # replay's rows preserve map/sample order; metadata uses the same map_calls.
    model = json.loads(timeline.MODEL_PATH.read_text())
    hist = el.team_history(sorted({n for m in data["maps"] for n in m["teams"]}), db)
    elo = el.EloBefore(hist)
    meta = []
    fields = data["fields"]["teams"]
    for m in data["maps"]:
        ratings = [elo(n, m["start"][:10]) for n in m["teams"]]
        if None in ratings:
            continue
        _, calls = el.map_calls(m, model, ratings, fields)
        for c in calls:
            if c["sample"] is None:
                continue
            s = m["samples"][c["sample"]]
            teams = [dict(zip(fields, team)) for team in s["teams"]]
            try:
                timeline.objective_gaps(*teams)
                valid = True
            except ValueError:
                valid = False
            source = pd.Timestamp(m["start"]) + pd.Timedelta(seconds=s["t"])
            meta.append(
                {
                    "game": m["game"],
                    "minute": c["minute"],
                    "arrival": source + pd.Timedelta(seconds=data["lag"]),
                    "end": pd.Timestamp(m["end"]),
                    "flat": s["flat"],
                    "objectives_valid": valid,
                }
            )
    live = current[~current.pregame].merge(
        pd.DataFrame(meta), on=["game", "minute"], validate="one_to_one"
    )
    old = legacy[~legacy.pregame][["game", "minute", "p"]].rename(columns={"p": "v1"})
    live = live.merge(old, on=["game", "minute"], validate="one_to_one")
    live["series_end"] = live.groupby("series").end.transform("max")
    live = live[live.minute.between(5, 30)].copy()
    live = live[live.p_lag.between(0.000001, 0.999999)].copy()
    live["month"] = live.arrival.dt.strftime("%Y-%m")
    return live.sort_values(["arrival", "game", "minute"]).reset_index(
        drop=True
    ), skipped


def walk_forward(rows):
    """No same-series or not-yet-completed results enter a monthly fit."""
    out, fits = [], []
    for month in sorted(rows.month.unique()):
        cutoff = pd.Timestamp(month + "-01", tz="UTC")
        test = rows[rows.month == month].copy()
        train = rows[rows.series_end + pd.Timedelta(hours=24) < cutoff]
        # Defensive whole-series exclusion even for a series spanning months.
        train = train[~train.series.isin(test.series)]
        if train.series.nunique() < 100 or train.game.nunique() < 200:
            continue
        x = np.column_stack([el.logit(train.p_lag), el.logit(train.p)])
        xt = np.column_stack([el.logit(test.p_lag), el.logit(test.p)])
        w = 1 / train.groupby("game").game.transform("size").to_numpy()
        blend = LogisticRegression(C=1, fit_intercept=False, max_iter=2000)
        blend.fit(x, train.won, sample_weight=w)
        market = LogisticRegression(C=1, fit_intercept=False, max_iter=2000)
        market.fit(x[:, :1], train.won, sample_weight=w)
        test["blend"] = blend.predict_proba(xt)[:, 1]
        test["market_cal"] = market.predict_proba(xt[:, :1])[:, 1]
        fits.append(
            {
                "month": month,
                "train_maps": train.game.nunique(),
                "train_series": train.series.nunique(),
                "latest_training_available": (
                    train.series_end.max() + pd.Timedelta(hours=24)
                ).isoformat(),
                "market_weight": blend.coef_[0, 0],
                "model_weight": blend.coef_[0, 1],
                "market_only_weight": market.coef_[0, 0],
            }
        )
        out.append(test)
    if not out:
        raise ValueError("No month has enough strictly earlier settled series")
    return pd.concat(out, ignore_index=True), fits


def select(rows, forecast="blend", window=21, edge=0.05, stress=0.0):
    r = rows[rows.objectives_valid & ~rows.flat & rows.quiet.le(10)].copy()
    if window is not None:
        r = r[r[f"n_{window}"].ge(2) & r[f"range_{window}"].le(0.010000001)]
    sides = []
    for side in (0, 1):
        s = r.copy()
        s["side"] = side
        s["prob"] = s[forecast] if side == 0 else 1 - s[forecast]
        s["win"] = s.won if side == 0 else 1 - s.won
        cost = s[f"cost{side}" if window is None else f"cost{side}_{window}"]
        latest = s.p_lag if side == 0 else 1 - s.p_lag
        s["price"] = np.maximum(cost, latest) + stress
        s = s[s.price.between(0.000001, 0.999999)].copy()
        s["eff"] = effective_cost(s.price)
        s["edge"] = s.prob - s.eff
        s["clv"] = (s.p_clv if side == 0 else 1 - s.p_clv) - s.price
        sides.append(s[s.edge >= edge - 1e-12])
    bets = (
        pd.concat(sides)
        .sort_values(
            ["arrival", "game", "edge", "side"], ascending=[True, True, False, True]
        )
        .drop_duplicates("game", keep="first")
    )
    return bets.sort_values(["arrival", "game"]).reset_index(drop=True)


def cluster_ci(frame, values):
    if not len(frame):
        return [None, None]
    table = pd.DataFrame({"series": frame.series.to_numpy(), "v": np.asarray(values)})
    grouped = table.groupby("series").v.agg(["sum", "count"])
    rng = np.random.default_rng(20261018)
    draw = rng.integers(0, len(grouped), (2000, len(grouped)))
    values = grouped["sum"].to_numpy()[draw].sum(axis=1) / grouped["count"].to_numpy()[
        draw
    ].sum(axis=1)
    return np.quantile(values, [0.025, 0.975]).tolist()


def summary(bets):
    if bets.empty:
        return {"bets": 0}
    roi = bets.win / bets.eff - 1
    lo, hi = cluster_ci(bets, roi)
    return {
        "bets": len(bets),
        "series": bets.series.nunique(),
        "win_rate": bets.win.mean(),
        "price": bets.price.mean(),
        "probability": bets.prob.mean(),
        "roi": roi.mean(),
        "lo": lo,
        "hi": hi,
        "profit_per_100": roi.sum() * 100 / len(bets),
        "clv": bets.clv.mean(),
        "clv_n": int(bets.clv.notna().sum()),
    }


def kelly(bets, fraction, sequential=False, map_cap=None, series_cap=None):
    """Cash-reserved event-time Kelly; no payout before the settlement proxy."""
    cash, held, peak, dd, placed, cash_limited, largest, max_held = (
        100.0,
        0.0,
        100.0,
        0.0,
        0,
        0,
        0.0,
        0.0,
    )
    pending, series_held = [], {}

    def settle(until):
        nonlocal cash, held, peak, dd
        while pending and pending[0][0] <= until:
            _, _, series, outlay, payout = heapq.heappop(pending)
            held -= outlay
            series_held[series] -= outlay
            cash += payout
            equity = cash + held
            peak = max(peak, equity)
            dd = max(dd, 1 - equity / peak)

    for i, r in enumerate(bets.itertuples(index=False)):
        settle(r.arrival)
        equity = cash + held
        f = fraction * max(0.0, (r.prob - r.eff) / (1 - r.eff))
        desired = equity * f
        allowed = cash
        if map_cap is not None:
            allowed = min(allowed, equity * map_cap)
        if series_cap is not None:
            allowed = min(
                allowed, max(0.0, equity * series_cap - series_held.get(r.series, 0.0))
            )
        spend = min(desired, allowed)
        if spend < desired - 1e-9:
            cash_limited += 1
        if spend <= 1e-9:
            continue
        largest = max(largest, spend / equity)
        placed += 1
        payout = spend / r.eff * r.win
        cash -= spend
        held += spend
        series_held[r.series] = series_held.get(r.series, 0.0) + spend
        max_held = max(max_held, held / equity)
        when = r.arrival if sequential else r.end + pd.Timedelta(minutes=5)
        heapq.heappush(pending, (when, i, r.series, spend, payout))
        if sequential:
            settle(r.arrival)
    settle(pd.Timestamp.max.tz_localize("UTC"))
    return {
        "fraction": fraction,
        "terminal": cash,
        "multiple": cash / 100,
        "drawdown": dd,
        "placed": placed,
        "limited": cash_limited,
        "largest": largest,
        "max_held": max_held,
    }


def markdown_table(frame):
    # Avoid the optional tabulate dependency.
    return "\n".join(
        [
            "| " + " | ".join(frame.columns) + " |",
            "|" + "|".join("---" for _ in frame.columns) + "|",
            *(
                "| " + " | ".join(map(str, row)) + " |"
                for row in frame.itertuples(index=False, name=None)
            ),
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=ROOT / "data/research/live_trading")
    args = parser.parse_args()
    started = time.perf_counter()
    digest = hashlib.sha256(args.data.read_bytes()).hexdigest()
    if digest != PIN:
        raise ValueError("Input must match the protocol's pinned data hash")
    args.out.mkdir(parents=True, exist_ok=True)
    data = el.load_data(args.data)
    rows, skipped = prepare(data, args.db)
    scored, fits = walk_forward(rows)
    scored.to_csv(args.out / "calls.csv.gz", index=False)
    pd.DataFrame(fits).to_csv(args.out / "monthly_fits.csv", index=False)
    all_results, ledgers = [], {}

    def run(label, **kwargs):
        bets = select(scored, **kwargs)
        ledgers[label] = bets
        all_results.append({"strategy": label, **summary(bets)})
        return bets

    primary = run("Primary blend")
    run("Current model", forecast="p")
    run("Legacy v1", forecast="v1")
    run("Calibrated market", forecast="market_cal")
    run("Raw market", forecast="p_lag")
    run("Blend no stability", window=None)
    run("Blend 10s stability", window=10)
    run("Blend 30s stability", window=30)
    for edge in (0.03, 0.10, 0.15):
        run(f"Blend net edge {edge:.0%}", edge=edge)
    for stress in (0.01, 0.02, 0.03, 0.05):
        run(f"Blend reselect +{stress:.0%} cost", stress=stress)
        fixed = primary.copy()
        fixed["price"] += stress
        # A quote above $1 cannot be bought; report skipped entries explicitly.
        fixed = fixed[fixed.price < 1].copy()
        fixed["eff"] = effective_cost(fixed.price)
        fixed["clv"] -= stress
        label = f"Frozen entries +{stress:.0%} cost"
        ledgers[label] = fixed
        all_results.append({"strategy": label, **summary(fixed)})
    results = pd.DataFrame(all_results)
    results.to_csv(args.out / "strategies.csv", index=False)
    primary.to_csv(args.out / "primary_bets.csv", index=False)
    pd.concat(
        [bets.assign(strategy=label) for label, bets in ledgers.items()],
        ignore_index=True,
    ).to_csv(args.out / "all_bets.csv.gz", index=False)
    monthly = pd.DataFrame(
        [{"month": month, **summary(b)} for month, b in primary.groupby("month")]
    )
    monthly.to_csv(args.out / "monthly.csv", index=False)
    league = pd.DataFrame(
        [{"league": league, **summary(b)} for league, b in primary.groupby("league")]
    )
    league.to_csv(args.out / "leagues.csv", index=False)
    ks = []
    for fraction in (0.1, 0.25, 0.5, 1.0):
        for sequential in (False, True):
            row = {
                "mode": "sequential" if sequential else "cash reserved",
                **kelly(primary, fraction, sequential),
            }
            if sequential:
                f = fraction * ((primary.prob - primary.eff) / (1 - primary.eff)).clip(
                    lower=0
                )
                increments = np.log1p(
                    np.where(primary.win, f * (1 - primary.eff) / primary.eff, -f)
                )
                row["log_growth_lo"], row["log_growth_hi"] = cluster_ci(
                    primary, increments
                )
            ks.append(row)
    ks.append(
        {
            "mode": "1% map / 2% series caps",
            **kelly(primary, 0.25, map_cap=0.01, series_cap=0.02),
        }
    )
    kf = pd.DataFrame(ks)
    kf.to_csv(args.out / "kelly.csv", index=False)
    stress_kelly = []
    for stress in (0.0, 0.02, 0.05):
        fixed = primary.copy()
        fixed["price"] += stress
        fixed = fixed[fixed.price < 1].copy()
        fixed["eff"] = effective_cost(fixed.price)
        for fraction in (0.1, 0.25, 0.5, 1.0):
            stress_kelly.append({"cost_addition": stress, **kelly(fixed, fraction)})
    stress_kelly = pd.DataFrame(stress_kelly)
    stress_kelly.to_csv(args.out / "kelly_stress.csv", index=False)
    # One average loss per map, then series-cluster inference.
    losses = []
    for name, column in (
        ("blend", "blend"),
        ("current", "p"),
        ("v1", "v1"),
        ("market", "p_lag"),
        ("market_cal", "market_cal"),
    ):
        p = np.clip(scored[column], 1e-6, 1 - 1e-6)
        ll = -(scored.won * np.log(p) + (1 - scored.won) * np.log1p(-p))
        maps = (
            scored.assign(loss=ll).groupby(["series", "game"]).loss.mean().reset_index()
        )
        losses.append(maps.rename(columns={"loss": name}))
    loss = losses[0]
    for other in losses[1:]:
        loss = loss.merge(other, on=["series", "game"], validate="one_to_one")
    comparison = []
    for name in ("blend", "current", "v1", "market", "market_cal"):
        delta = loss[name] - loss.market
        comparison.append(
            {
                "forecast": name,
                "log_loss": loss[name].mean(),
                "delta_market": delta.mean(),
                "interval": cluster_ci(loss, delta),
            }
        )
    blend_controls = [
        {
            "control": name,
            "delta": (loss.blend - loss[name]).mean(),
            "interval": cluster_ci(loss, loss.blend - loss[name]),
        }
        for name in ("current", "market_cal")
    ]
    manifest = {
        "base": "f522db3",
        "input_sha256": digest,
        "model_sha256": hashlib.sha256(timeline.MODEL_PATH.read_bytes()).hexdigest(),
        "db_sha256": hashlib.sha256(args.db.read_bytes()).hexdigest(),
        "input_maps": len(data["maps"]),
        "input_series": len({m["series"] for m in data["maps"]}),
        "skipped_elo": skipped,
        "scored_maps": scored.game.nunique(),
        "scored_series": scored.series.nunique(),
        "scored_rows": len(scored),
        "first_arrival": scored.arrival.min().isoformat(),
        "last_arrival": scored.arrival.max().isoformat(),
        "comparison": comparison,
        "blend_controls": blend_controls,
        "seconds": time.perf_counter() - started,
    }
    (args.out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=float) + "\n"
    )
    view = results.copy()
    view["ROI (95%)"] = view.apply(
        lambda r: (
            "—" if pd.isna(r.get("roi")) else f"{r.roi:+.1%} ({r.lo:+.1%}, {r.hi:+.1%})"
        ),
        axis=1,
    )
    view["Win"] = view.win_rate.map(lambda x: "—" if pd.isna(x) else f"{x:.1%}")
    view["CLV"] = view.clv.map(lambda x: "—" if pd.isna(x) else f"{100 * x:+.2f}¢")
    view["series"] = view.series.map(lambda x: "—" if pd.isna(x) else str(int(x)))
    report = [
        "# Historical live-map trading study — 2026-10-18",
        "",
        "Research only. Protocol fixed before this run: [protocol](live_trading_protocol.md).",
        "The historical input contains trade tapes, not executable books. Every return below is a paper simulation.",
        "",
        f"Input: {manifest['input_maps']} maps / {manifest['input_series']} series; earlier-only scored cohort: {manifest['scored_maps']} maps / {manifest['scored_series']} series / {len(scored)} calls.",
        f"Scored arrivals {manifest['first_arrival']} to {manifest['last_arrival']}. Input/model/DB hashes and all ledgers are saved in `data/research/live_trading/`.",
        "",
        "## Forecast accuracy",
        "",
        markdown_table(pd.DataFrame(comparison).round(6).astype(str)),
        "",
        "Additional paired blend comparisons:",
        "",
        markdown_table(pd.DataFrame(blend_controls).round(6).astype(str)),
        "",
        "Equal-map log loss on every eligible 5–30 minute call, before entry filters. Intervals resample whole series; the market blend is fitted only to earlier completed series. Calibrated-market control uses the same chronology and regularization.",
        "",
        "## Entries and flat returns",
        "",
        markdown_table(
            view[["strategy", "bets", "series", "Win", "ROI (95%)", "CLV"]].astype(str)
        ),
        "",
        "All-in $1 outlay per bet, including 7% quadratic taker fees rounded up per contract to $0.0001. One first entry per map. Primary: earlier-only blend, 5-cent AFTER-fee edge, estimated minutes 5–30, valid objectives, non-flat sample, latest trade within 10 seconds, >=2 trades in 21 seconds within 1 cent. Cost is max(recent backing-side trade, latest side price). CLV uses the trade price 120 seconds later, not an executable exit. Raw market cannot beat its own cost plus fees; that row is a negative control.",
        "",
        "Sensitivity rows are exploratory, not a strategy selection. Frozen-entry stresses retain original choices and worsen cost; reselect rows require the same net edge at the stressed price. Neither reconstructs fills, depth, or additional latency.",
        "",
        "## Monthly primary results",
        "",
        markdown_table(monthly.round(5).astype(str)),
        "",
        "## League primary results (descriptive)",
        "",
        markdown_table(league.round(5).astype(str)),
        "",
        "## Monthly earlier-series-only fits",
        "",
        markdown_table(pd.DataFrame(fits).round(5).astype(str)),
        "",
        "## Kelly",
        "",
        markdown_table(kf.round(5).astype(str)),
        "",
        "Sequential mean log-growth intervals (columns log_growth_lo/hi) resample series and do not exclude zero for the primary Kelly fractions; cash-reserved results have no uncertainty interval. A terminal multiple is one observed path, not an expected return.",
        "",
        "Starts with $100; ideal continuous quantities, same probabilities and entries. `f = fraction × max(0, (p − c)/(1 − c))`, where c includes entry fees, is the fraction of bankroll spent. Sequential settles each bet immediately before the next entry and is an optimistic reference. Cash-reserved simulation keeps spend unavailable until recorded map end +5 minutes, releases winning payout or zero, and sizes from cash + open outlay; it never uses outcomes before settlement. Largest/max-held are fractions of equity; capped case limits outlay to 1% per map and 2% per series. Drawdown uses realized/cost-valued equity, excluding intra-map liquidation risk. This is constrained sequential allocation, not joint portfolio Kelly.",
        "",
        "Kelly sensitivity on frozen entry times/sides at worse purchase prices, resizing to the changed fee-inclusive cost (skips if implied edge becomes nonpositive):",
        "",
        markdown_table(stress_kelly.round(5).astype(str)),
        "",
        "## Limits and interpretation",
        "",
        "- No historical asks, depth, fills, observed model receipt time or settlement time in this dataset. A stable tape is not a stable book. The 21-second lag is one pilot estimate; cost stresses do not simulate changing feed lag.",
        "- Feed is about one sample a minute. Flat samples and invalid objective counters are excluded; pauses, outages, match identity and clock uncertainty cannot be fully screened. Matching exclusions inherit the pinned benchmark audit (including winner disagreement).",
        "- Current model and historical test have already been examined in research; this is an earlier-only blend backtest on reused history, not untouched confirmation. No series-shift or draft input is added; runtime series-shift parity remains a separate limit.",
        "- Bootstrap intervals preserve within-series dependence but not dependence across dates, teams or model selection. Monthly/league slices and sensitivity comparisons are descriptive and not multiplicity-adjusted.",
        "- Fees assume general 7% taker rate, multiplier 1 throughout; historical market-specific fee changes and actual fill/quantity rounding are not reconstructed. Fractional contracts and unlimited size are research abstractions. [Official fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf); [series fee metadata](https://docs.kalshi.com/api-reference/market/get-series).",
        "- Kelly is usable mathematically, but probabilities and executable costs determine whether its recommended exposure has positive growth. Fractional Kelly reduces exposure; it cannot repair a negative edge. Huge historical compounded multiples do not establish scalable profit.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \\",
        "  /Users/tvillalu/repos/Prometheus/.venv/bin/python scripts/research/live_trading.py \\",
        "  --data /private/tmp/live_maps-0705f02b1edf.json.gz \\",
        "  --db /Users/tvillalu/repos/Prometheus/db/prometheus.db",
        "```",
        "",
        f"Measured analysis runtime: {manifest['seconds']:.2f}s. No production/CI workload or dependency added.",
        "",
    ]
    primary_stats = summary(primary)
    full = kf[(kf["mode"] == "cash reserved") & (kf.fraction == 1)].iloc[0]
    quarter = kf[(kf["mode"] == "cash reserved") & (kf.fraction == 0.25)].iloc[0]
    capped = kf[kf["mode"] == "1% map / 2% series caps"].iloc[0]
    report[2:2] = [
        "The primary earlier-only blend is promising but inconclusive: "
        f"{primary_stats['bets']} entries, {primary_stats['roi']:+.1%} after-fee flat ROI "
        f"(95% series-bootstrap {primary_stats['lo']:+.1%} to {primary_stats['hi']:+.1%}). "
        "Blending improves accuracy over our model alone; its gain over the raw market "
        "still includes zero. The 30-second stability sensitivity has a positive ROI "
        "interval, but it is one of several comparisons on reused history, not a "
        "confirmed superior rule.",
        "",
        "Full Kelly is mathematically available, but on this same historical path "
        f"it falls {full.drawdown:.1%} from peak to trough. Quarter Kelly falls "
        f"{quarter.drawdown:.1%}; a quarter-Kelly allocation capped at 1% per map "
        f"and 2% per series falls {capped.drawdown:.1%}. "
        "These are observed cost-valued drawdowns under idealized trade prices. "
        "No Kelly fraction has a sequential mean log-growth interval excluding zero. "
        "Keep the primary rule frozen for an executable-book forward test; "
        "no strategy or Kelly fraction is selected by these retrospective returns.",
        "",
    ]
    (ROOT / "docs/research/live_trading.md").write_text("\n".join(report))
    print(json.dumps(manifest, indent=2, default=float))
    print(results[["strategy", "bets", "roi", "lo", "hi"]].to_string(index=False))
    print(kf.to_string(index=False))


if __name__ == "__main__":
    main()
