"""Offline 12h alert evaluation from the validated, frozen regional experiment.

No threshold tuning, fetching, fitting, or production-log writes. Input series.csv
comes from regional_correction.py (production parity in validate_regional_calibration.py).
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus import markets


def fresh_book(candles, cutoff):
    """Latest valid hourly close, ending within one hour before cutoff."""
    valid = [c for c in candles if 0 <= cutoff - c["end_period_ts"] <= 3600]
    return markets.book_at(sorted(valid, key=lambda c: c["end_period_ts"]), cutoff)


def prices(row, event, cache):
    cutoff = pd.Timestamp(row.start).timestamp() - 12 * 3600
    costs = [np.nan, np.nan]
    for market in event["markets"]:
        path = cache / "candles" / f"{market['ticker']}.json"
        if not path.exists():
            continue
        bid, ask = fresh_book(json.loads(path.read_text()), cutoff)
        if bid is None or ask - bid > markets.MAX_SPREAD:
            continue
        mine = 0 if market["side"] == row.team1 else 1
        for side, cost in ((mine, ask), (1 - mine, 1 - bid)):
            costs[side] = cost if np.isnan(costs[side]) else min(costs[side], cost)
    return costs


def candidates(frame, model="persistent", slippage=0):
    """One side per fixture, strictly >5 points over an available valid ask."""
    out = []
    for row in frame.to_dict("records"):
        p = row[f"{model}_12h"]
        choices = [(p, row["cost1"], 1), (1 - p, row["cost2"], 2)]
        choices = [(p, c, s) for p, c, s in choices if pd.notna(c) and 0 < c < 1]
        if not choices:
            continue
        p, cost, side = max(choices, key=lambda x: x[0] - x[1])
        if p - cost <= 0.05:
            continue
        paid = min(cost + slippage, 0.999)
        won = bool(row["won1"]) == (side == 1)
        close = row["market_close"] if side == 1 else 1 - row["market_close"]
        out.append(
            dict(
                row,
                side=side,
                probability=p,
                price=paid,
                edge=p - cost,
                won=won,
                profit=(1 / paid - 1 if won else -1) - markets.fee(paid, 1),
                clv=close - paid,
            )
        )
    return pd.DataFrame(out)


def interval(frame, col, cluster=False):
    if frame.empty:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(0)
    if cluster:
        part = frame.groupby("event_id")[col].agg(["sum", "count"])
        draw = rng.integers(len(part), size=(10000, len(part)))
        means = part["sum"].to_numpy()[draw].sum(1) / part["count"].to_numpy()[
            draw
        ].sum(1)
    else:
        values = frame[col].to_numpy()
        means = values[rng.integers(len(values), size=(10000, len(values)))].mean(1)
    return np.quantile(means, [0.025, 0.975])


def summary(label, frame):
    if frame.empty:
        return f"| {label} | 0 | — | — | — | — | — |"
    roi = interval(frame, "profit")
    event = interval(frame, "profit", True)
    clv = interval(frame, "clv")
    return (
        f"| {label} | {len(frame)} | {int(frame.won.sum())} | {frame.profit.mean():+.1%} "
        f"[{roi[0]:+.1%}, {roi[1]:+.1%}] | [{event[0]:+.1%}, {event[1]:+.1%}] | "
        f"{100 * frame.clv.mean():+.2f} [{100 * clv[0]:+.2f}, {100 * clv[1]:+.2f}] | "
        f"{(frame.clv > 0).mean():.1%} |"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--series", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument(
        "--export", type=Path, default=Path("data/international_alerts")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/international_alerts.md")
    )
    args = parser.parse_args()
    frame = pd.read_csv(args.series)
    frame = frame[frame.international & frame.cross_region & frame.timed].copy()
    if not frame.event_ticker.is_unique:
        raise ValueError("Duplicate fixtures")
    events = {
        e["event_ticker"]: e
        for e in markets.events(json.loads((args.cache / "KXLOLGAME.json").read_text()))
    }
    for row in frame.itertuples():
        event = events[row.event_ticker]
        if (
            event["team1"],
            event["team2"],
            event["won1"],
            pd.Timestamp(event["start"]),
        ) != (row.team1, row.team2, row.won1, pd.Timestamp(row.start)):
            raise ValueError(f"Cached fixture changed: {row.event_ticker}")
    frame[["cost1", "cost2"]] = [
        prices(r, events[r.event_ticker], args.cache) for r in frame.itertuples()
    ]
    eligible = frame[frame.cost1.notna() | frame.cost2.notna()]
    bets = candidates(eligible)
    raw = candidates(eligible, "elo")
    lines = [
        "# International alert candidates — 2026-10-15",
        "",
        "Fixed policy: actual cross-home international series, known start time, strictly more than 5 percentage points over the executable ask, one side per fixture. Primary observation is 12 hours before start (within the existing 6+ hour policy). No lead-time or edge tuning. Production-equivalent persistent regional calibration, only earlier completed events used for coefficients; before-day ratings at the 12h cutoff. Raw Elo is a diagnostic control, not another policy to select.",
        "",
        f"{len(frame)} timed cross-region fixtures; {len(eligible)} have an available fresh ask. Re-read hourly candles from the local cache; only valid two-sided books ending at/before the cutoff and no more than one hour old qualify. Spread at most {markets.MAX_SPREAD:.0%}; use the cheaper equivalent yes/no ask. Missing books are excluded, never replaced with a midpoint. Outcomes/fixture matching were validated by the original regional experiment.",
        "",
        "Returns use the existing $1 contract-cost paper convention, plus a separately charged fee: ceil(0.07 × contracts × P × (1−P)) to the cent. ROI below is profit / contract cost (fee is deducted from profit). This is a modeling assumption, not a verified series-specific historical fee/depth/fill record. [Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf).",
        "",
        "| Slice | Calls | Won | ROI (series 95%) | ROI (event sensitivity 95%) | CLV points (series 95%) | Beat close |",
        "|---|---:|---:|---|---|---|---:|",
        summary("Calibrated, fresh asks", bets),
        summary("Raw Elo control", raw),
    ]
    for event, part in bets.groupby("event"):
        lines.append(summary(event, part))
    lines += [
        summary("Senior events (exclude WSCI)", bets[bets.league != "WSCI"]),
        summary(
            "Remove largest winner (sensitivity only)",
            bets.drop(bets.profit.nlargest(1).index),
        ),
        summary(
            "Remove two largest winners (sensitivity only)",
            bets.drop(bets.profit.nlargest(2).index),
        ),
        summary("Pay 1¢ more, original selection", candidates(eligible, slippage=0.01)),
        summary("Pay 2¢ more, original selection", candidates(eligible, slippage=0.02)),
        "",
        "Intervals resample series (10,000 draws, seed 0); event sensitivity resamples whole event blocks and is unreliable with only a few tournaments. Event rows with one block have degenerate event intervals. Profit is concentrated in long-shot wins; leave-winner-out rows describe fragility, not deployable filters. Negative CLV weakens the profit evidence.",
        "",
        "This is retrospective, already-viewed development data through September 30, with no Worlds. Forecast hyperparameters and retrospective best-of reconstruction also limit inference. One 12h observation does not replay the first qualifying hourly alert anywhere 6+ hours out. Quotes do not prove available depth or fills; freshness here means a recent candle close, not a historical live API observation. No significance claim or evidence of improvement in alert returns over raw Elo. Historical candidates must not be inserted into the forward alert record.",
        "",
        "Decision: the positive historical return is enough for a separately labeled experimental international paper track, not a demonstrated profitable strategy. Keep the current 5-point/6h live policy fixed, preserve fresh-price/missing-results guards, freeze first terms and model provenance, and compare forward after-fee returns and CLV across completed tournaments before promotion.",
        "",
    ]
    args.export.mkdir(parents=True, exist_ok=True)
    bets.to_csv(args.export / "candidates.csv", index=False)
    eligible.to_csv(args.export / "eligible.csv", index=False)
    audit = {
        "series_sha256": hashlib.sha256(args.series.read_bytes()).hexdigest(),
        "timed": len(frame),
        "fresh_asks": len(eligible),
        "bets": len(bets),
        "market_list_sha256": hashlib.sha256(
            (args.cache / "KXLOLGAME.json").read_bytes()
        ).hexdigest(),
        "candles_sha256": {
            m["ticker"]: hashlib.sha256(path.read_bytes()).hexdigest()
            for r in frame.itertuples()
            for m in events[r.event_ticker]["markets"]
            if (path := args.cache / "candles" / f"{m['ticker']}.json").exists()
        },
        "model": "persistent_12h",
        "edge": 0.05,
        "hours": 12,
    }
    (args.export / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    args.out.write_text("\n".join(lines))
    print(json.dumps({k: v for k, v in audit.items() if k != "candles_sha256"}))


if __name__ == "__main__":
    main()
