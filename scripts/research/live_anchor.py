"""Fixed retrospective live-anchor protocol, declared before scoring.

A compares current v1 pregame calls with FORGE and calibrated Elo map priors.
B replaces Elo with logit(FORGE), or adds it, using the frozen production
objective/momentum pipeline and feed-only train 2024/calibration 2025 H1/test
from 2025-07-01. C removes only frozen global calibration, on full feed test
and post-fit live checkpoints. Equal-map losses; 2,000 whole-series bootstrap
draws, seed 42; fixed minute/league slices; no tuning or network access.
B1 + raw is evaluated only if B1 and C pass. The test chronology was already
viewed by earlier studies; all results are retrospective.
A candidate passes when its primary delta's 95% interval is entirely below 0 and no reported slice's interval is entirely above 0.
C additionally requires live checkpoints not to be significantly worse.
"""

import argparse
import contextlib
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit, logit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import evaluate_live as live
import evaluate_metrics as forecasts
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, clock, partitions, when

from prometheus.live import timeline
from prometheus.live.series import map_prior
from prometheus.schedule import series_rho

CACHE = Path("data/research/live_anchor")
RULE = "A candidate passes when its primary delta's 95% interval is entirely below 0 and no reported slice's interval is entirely above 0."


def forge_table(refresh):
    """Reproduce the forecast benchmark's frame and out-of-year calls."""
    path = CACHE / "forge.pkl"
    if path.exists() and not refresh:
        table = pd.read_pickle(path)
    else:
        with contextlib.redirect_stdout(io.StringIO()):
            games = forecasts.load_games()
            results = forecasts.load_results()
            elo = forecasts.load_elo_timeline()
            states = forecasts.form_states()
            frame = forecasts.backtest(
                games,
                results,
                elo,
                forecasts.get_available_years(forecasts.ALL_MAJOR_LEAGUES),
            )
            relative = forecasts.out_of_year_form(frame, states)
            frame = forecasts.add_form(frame, states, relative)
            table = frame[["gameid", "blue_league", "red_league"]].copy()
            table["p_forge"] = np.asarray(forecasts.forge_probabilities(frame))
            table["p_elo"] = np.asarray(
                forecasts.regional_calibration.apply_frame(
                    frame, forecasts.out_of_year_probabilities(frame, "elo_live")
                )
            )
        assert not table.gameid.duplicated().any()
        table = table.set_index("gameid")
        table.to_pickle(path)
    print(f"FORGE coverage: {len(table)} maps", flush=True)
    return table


def tier(league):
    return (
        "International"
        if league in INTERNATIONAL
        else "Majors"
        if league in MAJORS
        else "Other"
    )


def slices(frame, premap=False):
    if premap:
        out = [("map1", frame.k.eq(1)), ("map2+", frame.k.gt(1))]
    else:
        out = [
            (label, frame.seconds.ge(lo) & frame.seconds.lt(hi))
            for label, lo, hi in (
                ("0–5", 0, 300),
                ("5–10", 300, 600),
                ("10–20", 600, 1200),
                ("20–30", 1200, 1800),
                ("30+", 1800, np.inf),
            )
        ]
    tiers = frame.league.map(tier)
    return out + [
        (name, tiers.eq(name)) for name in ("Majors", "International", "Other")
    ]


def compare(lines, label, frame, p, q, subsets=()):
    """Append paired equal-map loss deltas and return adoption evidence."""
    results = []
    for name, mask in [("all", np.ones(len(frame), dtype=bool)), *subsets]:
        mask = np.asarray(mask)
        part = frame[mask]
        if part.empty:
            lines.append(f"| {label}/{name} | 0 | — | — |")
            continue
        result = delta(part, np.asarray(p)[mask], np.asarray(q)[mask])
        lo, hi = result["interval"]
        lines.append(
            f"| {label}/{name} | {part.game_id.nunique()} | {result['delta']:+.4f} | [{lo:+.4f}, {hi:+.4f}] |"
        )
        results.append(result)
    return results


def passes(results):
    return (
        bool(results)
        and results[0]["interval"][1] < 0
        and all(r["interval"][0] <= 0 for r in results[1:])
    )


def metric_line(label, frame, p):
    m = metrics(frame, np.asarray(p))
    return f"{label}: LL {m['log_loss']:.4f}, Brier {m['brier']:.4f}, ECE10 {m['ece10']:.4f}."


def header(title):
    return [
        f"## {title}",
        "",
        "| Comparison/slice | n maps | Delta LL | 95% interval |",
        "|---|---:|---:|---|",
    ]


def production_calls(model, frame, raw):
    """Runtime inference with the exact freeze-script sample alignment."""
    return np.array(
        [
            timeline.predict(
                model,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
                objectives=raw[r.Index],
                momentum=float(r.momentum),
            )
            for r in frame.itertuples()
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=Path("docs/research/live_anchor.md")
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    CACHE.mkdir(parents=True, exist_ok=True)
    table = forge_table(args.refresh)
    data = live.load_data(Path("data/live_bench/live_maps.json.gz"))
    pre = live.replay_premaps(data).rename(columns={"game": "game_id"})
    total = len(data["premaps"])
    pre = pre[pre.game_id.isin(table.index)].copy()
    metadata = {m["game"]: m for m in data["premaps"]}
    pre["k"] = [1 + sum(metadata[g]["score_before"]) for g in pre.game_id]
    for name in ("forge", "elo"):
        pre[name] = [
            map_prior(
                table.loc[g, f"p_{name}"],
                series_rho(table.loc[g, "blue_league"], table.loc[g, "red_league"]),
                *metadata[g]["score_before"],
            )
            for g in pre.game_id
        ]
    # Split A's gain: the series-score shift alone, and FORGE without it.
    pre["current_shift"] = [
        map_prior(
            p,
            series_rho(table.loc[g, "blue_league"], table.loc[g, "red_league"]),
            *metadata[g]["score_before"],
        )
        for p, g in zip(pre.p, pre.game_id)
    ]
    pre["forge_unshifted"] = [table.loc[g, "p_forge"] for g in pre.game_id]
    # Read market fields from the local benchmark's declared schema.
    pre["kalshi"] = [
        dict(zip(data["fields"]["premap"], metadata[g]["market"])).get("p_before")
        for g in pre.game_id
    ]
    lines = [
        "# Live anchor research",
        "",
        "Local OE out-of-year FORGE/Elo backtests, feed timelines and priced live benchmark; train 2024 feed, calibration 2025 H1, test from 2025-07-01. The test chronology was already viewed by earlier studies, so results are retrospective. Fixed C=1 and map weights; 2,000 paired series-bootstrap draws, seed 42. Negative log-loss deltas favor the candidate. B1 replaces Elo with logit(FORGE); B2 adds it. C removes global calibration only.",
        "",
        RULE,
        "",
        f"FORGE table: {len(table)} maps. A kept/dropped {len(pre)}/{total - len(pre)} maps; {pre.series.nunique()} series.",
        "",
    ]
    lines += header("A: pregame")
    a = None
    for name in ("forge", "elo"):
        result = compare(
            lines, f"{name}−current", pre, pre[name], pre.p, slices(pre, True)
        )
        if name == "forge":
            a = result
    compare(
        lines, "current+shift−current", pre, pre.current_shift, pre.p, slices(pre, True)
    )
    compare(lines, "forge−current+shift", pre, pre.forge, pre.current_shift)
    compare(lines, "forge unshifted−current", pre, pre.forge_unshifted, pre.p)
    valid = pre.kalshi.notna() & pre.kalshi.gt(0) & pre.kalshi.lt(1)
    market = pre[valid]
    for name, p in (
        ("current", market.p),
        ("forge", market.forge),
        ("elo", market.elo),
    ):
        compare(lines, f"{name}−Kalshi", market, p, market.kalshi)
    compare(
        lines, "Kalshi−current", market, market.kalshi, market.p, slices(market, True)
    )
    lines += [
        "",
        *[
            metric_line(name, pre, p)
            for name, p in (("Current", pre.p), ("FORGE", pre.forge), ("Elo", pre.elo))
        ],
        metric_line("Kalshi (valid subset)", market, market.kalshi),
        f"Verdict A: {'PASS' if passes(a) else 'FAIL'}.",
        "",
    ]
    print(
        f"A coverage: {len(pre)} kept / {total - len(pre)} dropped; {pre.series.nunique()} series",
        flush=True,
    )
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    extra = objective_rows(parts["joined"])
    n = int(parts["data"].source.eq("feed").sum())
    frames = [
        momentum(attach(parts[k][parts[k].source.eq("feed")], extra, n))
        for k in ("train", "calibration", "test")
    ]
    prod = (
        timeline.FEATURES
        + add_columns(frames[0], PRIMARY)
        + ["momentum", "momentum_time"]
    )
    for frame in frames[1:]:
        add_columns(frame, PRIMARY)
    raw_samples = []
    for match in parts["joined"]:
        for sample, sec in zip(
            match["samples"], clock(match["samples"], when(match["start"]))
        ):
            bg, rg = sample["blue"]["gold"], sample["red"]["gold"]
            if (
                sec is not None
                and sec >= 0
                and sample["state"] == "in_game"
                and bg
                and rg
                and bg > 0
                and rg > 0
            ):
                raw_samples.append((sample["blue"], sample["red"]))
    assert len(raw_samples) == n
    model = json.loads(timeline.MODEL_PATH.read_text())
    test = frames[2]
    frozen = production_calls(model, test, raw_samples)
    restricted = []
    coverage = []
    for name, frame in zip(("train", "calibration", "test"), frames):
        kept = frame[frame.game_id.isin(table.index)].copy()
        p = kept.game_id.map(table.p_forge).clip(1e-4, 1 - 1e-4)
        kept["anchor"] = logit(p)
        kept["anchor_time"] = kept.anchor * kept.time
        restricted.append(kept)
        count = f"{name} {kept.game_id.nunique()}/{frame.game_id.nunique() - kept.game_id.nunique()}"
        coverage.append(count)
    print("B kept/dropped: " + "; ".join(coverage), flush=True)
    tr, ca, te = restricted
    bcols = [c for c in prod if c not in ("elo_hundred", "elo_time")] + [
        "anchor",
        "anchor_time",
    ]
    fitted = fit(tr, ca, bcols)
    predictions = {
        "B1": score(fitted, te, bcols),
        "B2": score(
            fit(tr, ca, prod + ["anchor", "anchor_time"]),
            te,
            prod + ["anchor", "anchor_time"],
        ),
        "Control": score(fit(tr, ca, prod), te, prod),
        "Production": production_calls(model, te, raw_samples),
    }
    lines += header("B: anchor")
    b = compare(
        lines, "B1−prod", te, predictions["B1"], predictions["Production"], slices(te)
    )
    compare(
        lines, "B1−control", te, predictions["B1"], predictions["Control"], slices(te)
    )
    compare(
        lines, "B2−prod", te, predictions["B2"], predictions["Production"], slices(te)
    )
    lines += [
        "",
        "B kept/dropped maps: " + "; ".join(coverage) + ".",
        *[metric_line(name, te, p) for name, p in predictions.items()],
        f"Verdict B: {'PASS' if passes(b) else 'FAIL'}.",
        "",
    ]
    raw_model = dict(model, calibration_slope=1.0, calibration_intercept=0.0)
    raw_path = CACHE / "raw_model.json"
    raw_path.write_text(json.dumps(raw_model) + "\n")
    raw = production_calls(raw_model, test, raw_samples)
    lines += header("C: calibration")
    c = compare(lines, "raw−cal", test, raw, frozen, slices(test))
    checkpoints = []
    for path in (timeline.MODEL_PATH, raw_path):
        calls, skipped = live.replay(data, model_path=path)
        calls = calls[~calls.pregame & calls.start.str[:10].gt(live.fit_through(model))]
        checkpoints.append(live.checkpoints(calls).set_index(["game", "checkpoint"]))
        print(
            f"Live replay: {len(calls)} in-game calls; {skipped} skipped maps",
            flush=True,
        )
    baseline, candidate = checkpoints
    assert baseline.index.is_unique and candidate.index.is_unique
    assert baseline.index.equals(candidate.index)
    bench = baseline.reset_index().rename(columns={"game": "game_id"})
    live_slices = [
        (f"{m}m", bench.checkpoint.eq(m)) for m in sorted(bench.checkpoint.unique())
    ]
    lc = compare(
        lines,
        "live raw−cal",
        bench,
        candidate.ours.to_numpy(),
        baseline.ours.to_numpy(),
        live_slices,
    )
    cpass = passes(c) and bool(lc) and all(r["interval"][0] <= 0 for r in lc)
    lines += [
        "",
        metric_line("Feed calibrated", test, frozen),
        metric_line("Feed raw", test, raw),
        metric_line("Live calibrated", bench, baseline.ours),
        metric_line("Live raw", bench, candidate.ours),
        f"Verdict C: {'PASS' if cpass else 'FAIL'} (needs the feed rule and no significantly worse live checkpoint).",
        "",
    ]
    if passes(b) and cpass:
        scaler, base, _ = fitted
        combined = expit(base.decision_function(scaler.transform(te[bcols])))
        lines += header("Conditional B1 + raw")
        compare(
            lines, "B1raw−prod", te, combined, predictions["Production"], slices(te)
        )
        lines += ["", metric_line("B1 + raw", te, combined)]
    else:
        lines.append("B1 + raw skipped: B and C did not both pass.")
    lines += ["", "Reproduce: `uv run python scripts/research/live_anchor.py`.", ""]
    report = "\n".join(
        line.replace(" | ", "|") if line.startswith("|") else line for line in lines
    )
    assert len(report.split()) < 1100, len(report.split())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(report)
    print(
        f"A {'PASS' if passes(a) else 'FAIL'}: {a[0]}; B {'PASS' if passes(b) else 'FAIL'}: {b[0]}; C {'PASS' if cpass else 'FAIL'}: {c[0]}"
    )
    print(
        f"Report: {args.report}; wall time {time.monotonic() - started:.1f}s",
        flush=True,
    )


if __name__ == "__main__":
    main()
