"""Fixed confirmation of role level gaps on the pinned live and trading studies."""

import contextlib
import hashlib
import io
import json
import subprocess
import sys
import time
from bisect import bisect_left
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from live_role_leads import CANDIDATES, prepared_frames, raw_windows
from train_time_model import fit, score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import compare_benchmarks as cb
import evaluate_live as el
import live_trading as trading

from prometheus.live import timeline

OUT = Path("data/research/live_role_levels")
REPORT = Path("docs/research/live_role_levels_check.md")
LEVEL_COLS = [c for col in CANDIDATES["level"] for c in (col, f"{col}_time")]
KEY = ["game", "minute"]


def match_raw(windows, target):
    """Nearest first-frame source timestamp within two seconds, inclusive."""
    times = sorted(windows)
    index = bisect_left(times, target)
    choices = times[max(0, index - 1) : index + 1]
    if not choices:
        return None
    nearest = min(choices, key=lambda t: abs((t - target).total_seconds()))
    return windows[nearest] if abs((nearest - target).total_seconds()) <= 2 else None


def first_probability(blue_probability, blue):
    """Convert a blue probability to match-team-zero orientation."""
    return np.where(np.asarray(blue) == 0, blue_probability, 1 - blue_probability)


def candidate_probabilities(control, blue_probability, blue, matched):
    """Keep control on every unsupported or unmatched call."""
    return np.where(matched, first_probability(blue_probability, blue), control)


def substitute(calls, probabilities, arm):
    """Replace only in-game probabilities, requiring identical unique call keys."""
    live = calls.loc[~calls.pregame, KEY]
    paired = live.merge(
        probabilities[KEY + [arm]],
        on=KEY,
        how="outer",
        validate="one_to_one",
        indicator=True,
    )
    assert paired._merge.eq("both").all(), "arm/replay call keys differ"
    out = calls.copy()
    aligned = live.merge(
        probabilities[KEY + [arm]], on=KEY, how="left", validate="one_to_one"
    )
    out.loc[~out.pregame, "p"] = aligned[arm].to_numpy()
    return out


def benchmark_predictions(data, db, model, control, level):
    hist = el.team_history(sorted({n for m in data["maps"] for n in m["teams"]}), db)
    elo = el.EloBefore(hist)
    records, designs = [], []
    for m in data["maps"]:
        ratings = [elo(n, m["start"][:10]) for n in m["teams"]]
        if None in ratings:
            continue
        page = el.page_for(m, data["fields"]["teams"])
        _, calls = timeline.timeline_calls(
            page,
            model,
            [{"elo": e} for e in ratings],
            start=m["start"],
            include_inputs=True,
        )
        windows = raw_windows(Path("data/feed_raw/games") / f"{m['game']}.json.gz")
        offsets = {s["t"] for s in m["samples"]}
        for call in calls:
            offset = round(
                (pd.Timestamp(call["at"]) - pd.Timestamp(m["start"])).total_seconds(), 3
            )
            if offset not in offsets:
                continue
            state = call["model"] == "time_objectives_momentum_v1"
            gaps = (
                match_raw(windows, pd.Timestamp(call["source_at"])) if state else None
            )
            record = {
                "game": m["game"],
                "minute": call["minute"],
                "deployed": call["p"],
                "blue": m["blue"],
                "state": state,
                "matched": gaps is not None,
            }
            if state:
                design = dict(
                    zip(
                        timeline.STATE_FEATURES,
                        timeline.state_features(**call["inputs"]),
                    )
                )
                for col in CANDIDATES["level"]:
                    design[col] = gaps[col] if gaps is not None else 0.0
                    design[f"{col}_time"] = design[col] * design["time"]
                design["row"] = len(records)
                designs.append(design)
            records.append(record)
    probabilities = pd.DataFrame(records)
    design = pd.DataFrame(designs)
    indices = design.row.to_numpy()
    research = first_probability(
        score(control, design, timeline.STATE_FEATURES),
        probabilities.loc[indices, "blue"].to_numpy(),
    )
    difference = float(
        np.max(np.abs(research - probabilities.loc[indices, "deployed"].to_numpy()))
    )
    parity = difference < 1e-6
    probabilities["control"] = probabilities.deployed
    if not parity:
        probabilities.loc[indices, "control"] = research
    probabilities["level"] = probabilities.control
    probabilities.loc[indices, "level"] = candidate_probabilities(
        probabilities.loc[indices, "control"].to_numpy(),
        score(level, design, timeline.STATE_FEATURES + LEVEL_COLS),
        probabilities.loc[indices, "blue"].to_numpy(),
        probabilities.loc[indices, "matched"].to_numpy(),
    )
    counts = {
        "calls": len(probabilities),
        "state_model": int(probabilities.state.sum()),
        "matched": int(probabilities.matched.sum()),
        "fallback": int((~probabilities.matched).sum()),
    }
    return (
        probabilities,
        {"max_abs_difference": difference, "deployed_control": parity},
        counts,
    )


def run_trading(probabilities, arm, original_replay):
    report = ROOT / "docs/research/live_trading.md"
    snapshot = report.read_bytes()
    model = timeline.MODEL_PATH.read_bytes()
    out = OUT / f"trading_{arm}"

    def replay(data, db=el.DB_PATH, model_path=timeline.MODEL_PATH):
        calls, skipped = original_replay(data, db=db, model_path=model_path)
        if Path(model_path).resolve() == timeline.MODEL_PATH.resolve():
            calls = substitute(calls, probabilities, arm)
        return calls, skipped

    try:
        with (
            patch.object(el, "replay", replay),
            patch.object(
                sys,
                "argv",
                [
                    "live_trading.py",
                    "--data",
                    "data/live_bench/live_maps.json.gz",
                    "--db",
                    "db/prometheus.db",
                    "--out",
                    str(out),
                ],
            ),
            contextlib.redirect_stdout(io.StringIO()) as log,
        ):
            trading.main()
        (out / "run.log").write_text(log.getvalue())
    finally:
        report.write_bytes(snapshot)
        assert report.read_bytes() == snapshot
        assert timeline.MODEL_PATH.read_bytes() == model
    strategies = pd.read_csv(out / "strategies.csv")
    primary = strategies[strategies.strategy == "Primary blend"].iloc[0]
    return pd.read_csv(out / "calls.csv.gz"), {
        "roi": float(primary.roi),
        "bets": int(primary.bets),
    }


def paired_loss(frame, column):
    """Equal-map loss differences; 2,000 whole-series draws with seed 42."""
    y = frame.won_control.to_numpy()

    def loss(p):
        p = np.clip(p.to_numpy(), 1e-6, 1 - 1e-6)
        return -(y * np.log(p) + (1 - y) * np.log1p(-p))

    values = frame[["game", "series_control"]].copy()
    values["delta"] = loss(frame[f"{column}_level"]) - loss(frame[f"{column}_control"])
    maps = values.groupby(["series_control", "game"]).delta.mean().reset_index()
    grouped = maps.groupby("series_control").delta.agg(["sum", "count"])
    rng = np.random.default_rng(42)
    draws = rng.integers(0, len(grouped), (2000, len(grouped)))
    means = grouped["sum"].to_numpy()[draws].sum(axis=1) / grouped["count"].to_numpy()[
        draws
    ].sum(axis=1)
    return {
        "delta": float(maps.delta.mean()),
        "interval": np.quantile(means, [0.025, 0.975]).tolist(),
        "maps": len(maps),
    }


def formatted(result):
    lo, hi = result["interval"]
    return f"{result['delta']:+.6f} [{lo:+.6f}, {hi:+.6f}]"


def main():
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    model_bytes = timeline.MODEL_PATH.read_bytes()
    data_path = Path("data/live_bench/live_maps.json.gz")
    assert hashlib.sha256(data_path.read_bytes()).hexdigest() == trading.PIN
    print("Preparing fixed training frames and fitting control/level", flush=True)
    train, calibration, _ = prepared_frames()
    control = fit(train, calibration, timeline.STATE_FEATURES)
    level = fit(train, calibration, timeline.STATE_FEATURES + LEVEL_COLS)
    data = el.load_data(data_path)
    model = json.loads(model_bytes)
    probabilities, parity, counts = benchmark_predictions(
        data, Path("db/prometheus.db"), model, control, level
    )
    print(f"Parity: {parity}; counts: {counts}", flush=True)
    original_replay = el.replay
    calls, skipped = original_replay(data)
    pre = el.replay_premaps(data)
    candidate_path = OUT / "candidate.json"
    candidate_path.write_text(
        json.dumps({**model, "fit_through": el.fit_through(model)}) + "\n"
    )
    for arm, dirname in (("control", "base"), ("level", "head")):
        el.write_dump(
            substitute(calls, probabilities, arm),
            OUT / dirname / "live",
            model_path=candidate_path if arm == "level" else timeline.MODEL_PATH,
            pre=pre,
        )
    command = [
        "uv",
        "run",
        "python",
        "scripts/compare_benchmarks.py",
        str(OUT / "base"),
        str(OUT / "head"),
    ]
    compared = subprocess.run(command, capture_output=True, text=True)
    # uv's dependency/system-configuration check panics in this sandbox.
    if compared.returncode == 101 and "panicked" in compared.stderr:
        command.insert(2, "--no-sync")
        compared = subprocess.run(command, capture_output=True, text=True)
    (OUT / "compare.log").write_text(compared.stdout + compared.stderr)
    sections, _ = cb.compare_dirs(OUT / "base", OUT / "head")
    dump = pd.read_csv(OUT / "base/live/calls.csv.gz")
    dump = dump[dump.start > el.fit_through(model)]
    live = {}
    for row in dict(sections)["Live"]:
        band = row["name"].removeprefix("log loss, ").rsplit(" (", 1)[0]
        mask = (
            dump.checkpoint.ge(0)
            if band == "all"
            else dump.checkpoint.isin(cb.LIVE_BANDS[band])
        )
        live[band] = {
            "delta": row["diff"],
            "interval": [row["lo"], row["hi"]],
            "maps": int(dump.loc[mask, "game"].nunique()),
        }
    print(
        f"Live All: {formatted(live['all'])}; compare exit {compared.returncode}; running trading arms",
        flush=True,
    )
    current, current_roi = run_trading(probabilities, "control", original_replay)
    candidate, candidate_roi = run_trading(probabilities, "level", original_replay)
    paired = current.merge(
        candidate,
        on=KEY,
        suffixes=("_control", "_level"),
        validate="one_to_one",
        how="outer",
        indicator=True,
    )
    assert paired._merge.eq("both").all()
    for column in ("won", "series", "league"):
        assert paired[f"{column}_control"].equals(paired[f"{column}_level"])
    results = {
        "Model All": paired_loss(paired, "p"),
        "Blend All": paired_loss(paired, "blend"),
    }
    for label, lo, hi in (("5–10", 5, 10), ("10–20", 10, 20), ("20–30", 20, 30)):
        mask = paired.minute.ge(lo) & (
            paired.minute.le(hi) if hi == 30 else paired.minute.lt(hi)
        )
        results[f"Blend {label}"] = paired_loss(paired[mask], "blend")
    for league, group in paired.groupby("league_control"):
        if group.game.nunique() >= 100:
            results[f"Blend {league}"] = paired_loss(group, "blend")
    parts = {
        "a": bool(live["all"]["interval"][1] < 0 and live["all"]["delta"] <= -0.0005),
        "b": compared.returncode == 0,
        "c": bool(
            results["Blend All"]["delta"] < 0
            and not any(
                r["interval"][0] > 0
                for k, r in results.items()
                if k.startswith("Blend")
            )
        ),
    }
    passed = all(parts.values())
    verdict = "PASS" if passed else "FAIL"
    summary = {
        "verdict": verdict,
        "parts": parts,
        "parity": parity,
        "counts": counts,
        "skipped_elo": skipped,
        "live": live,
        "trading": results,
        "roi": {"control": current_roi, "level": candidate_roi},
        "compare": {
            "command": command,
            "exit_code": compared.returncode,
            "output": compared.stdout,
            "stderr": compared.stderr,
        },
        "input_sha256": trading.PIN,
        "model_sha256": hashlib.sha256(model_bytes).hexdigest(),
        "seconds": time.monotonic() - started,
    }
    assert timeline.MODEL_PATH.read_bytes() == model_bytes
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"**{verdict}: role level confirmation; research only.**",
        "",
        "# Role level confirmation",
        "",
        "Fixed level candidate: deployed 20 inputs plus five blue-minus-red role level gaps and their ×time terms. Same feed train/calibration split, C=1, map weights and Platt fit as the role study. Pinned 1,666-map live input; no candidates or verdict rules changed.",
        "",
        f"Parity max |Δp|={parity['max_abs_difference']:.9g}; control uses {'deployed probabilities' if parity['deployed_control'] else 'research fit probabilities in both research arms'}. Objectives and momentum come directly from deployed call inputs. Candidate blue probabilities convert to teams[0]; nearest raw first-frame source timestamp within 2 seconds. Unsupported/unmatched calls retain control.",
        "",
        f"In-game calls {counts['calls']}; state-model {counts['state_model']}; matched {counts['matched']}; fallback {counts['fallback']}; Elo-skipped maps {skipped}. Pregame and pre-map calls unchanged.",
        "",
        "ΔLL=new−current; 95% whole-series bootstrap. Live uses the benchmark's checkpoint weighting, fit-date filter and bootstrap; trading averages calls per map, 2,000 draws, seed 42. Trading minute bands are [5,10), [10,20), [20,30]; leagues require ≥100 paired maps. Monthly blends refit separately using earlier settled series.",
        "",
        "| Live band | Maps | ΔLL [95% CI] |",
        "|---|---:|---|",
    ]
    lines += [f"| {band} | {r['maps']} | {formatted(r)} |" for band, r in live.items()]
    lines += ["", "| Trading measure | ΔLL [95% CI] |", "|---|---|"]
    lines += [f"| {name} | {formatted(r)} |" for name, r in results.items()]
    lines += [
        "",
        f"Primary paper ROI per $1 entry: current {current_roi['roi']:+.2%} ({current_roi['bets']} bets); level {candidate_roi['roi']:+.2%} ({candidate_roi['bets']} bets).",
        "",
        f"(a) {'PASS' if parts['a'] else 'FAIL'}: live All upper <0 and point ≤−0.0005. (b) {'PASS' if parts['b'] else 'FAIL'}: compare_benchmarks exit {compared.returncode}, no significantly worse live band. (c) {'PASS' if parts['c'] else 'FAIL'}: trading blend All point <0 and no reported blend slice lower >0. Full comparator output: `data/research/live_role_levels/compare.log` and `summary.json`.",
        "",
        "Limits: level was a post hoc candidate among four secondaries; the 2026 benchmark maps overlap the study's test period; trade prices are not executable asks; no forward holdout used. Historical blend refitting and paper ROI do not establish executable profitability. No production change.",
        "",
        "Reproduce:",
        "```bash",
        "OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_role_levels_check.py",
        "```",
        "",
    ]
    report = "\n".join(lines)
    assert len(report.split()) < 600
    REPORT.write_text(report)
    print(
        f"{verdict}: {parts}; trading Blend All {formatted(results['Blend All'])}; {summary['seconds']:.1f}s; wrote {REPORT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
