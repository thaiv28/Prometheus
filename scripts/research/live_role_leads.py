"""Fixed, retrospective role gold/level/CS study; no production changes."""

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, ci, clock, partitions, when

from prometheus.live.timeline import STATE_FEATURES

OUT = Path("data/research/live_role_leads")
REPORT = Path("docs/research/live_role_leads.md")
ROLES = ("top", "jungle", "mid", "bottom", "support")
GAPS = [f"{stat}_{role}" for stat in ("gold", "level", "cs") for role in ROLES]
CANDIDATES = {
    "primary": GAPS[:5],
    "level": GAPS[5:10],
    "cs": GAPS[10:],
    "totals": ["level_sum", "cs_sum"],
    "all": GAPS,
}


def raw_windows(path):
    """Read a map once, retaining only first-frame participant measurements."""
    with gzip.open(path, "rt") as stream:
        raw = json.load(stream)
    first = raw.get("first") or {}
    windows = [first.get("window", first)] + [
        sample.get("window") or {} for sample in raw.get("samples", [])
    ]
    metadata = next((w["gameMetadata"] for w in windows if w.get("gameMetadata")), {})
    roles = {}
    for side in ("blue", "red"):
        people = metadata.get(f"{side}TeamMetadata", {}).get("participantMetadata", [])
        for role in ROLES:
            ids = [p["participantId"] for p in people if p.get("role") == role]
            if len(ids) != 1:
                return {}
            roles[side, role] = ids[0]
        if len({roles[side, role] for role in ROLES}) != len(ROLES):
            return {}
    result = {}
    for window in windows:
        frames = window.get("frames") or []
        if not frames:
            continue
        frame = frames[0]
        values = {}
        for side in ("blue", "red"):
            people = frame.get(f"{side}Team", {}).get("participants", [])
            for role in ROLES:
                matches = [
                    p for p in people if p.get("participantId") == roles[side, role]
                ]
                if len(matches) != 1:
                    break
                person = matches[0]
                for stat, key, scale in (
                    ("gold", "totalGold", 1000),
                    ("level", "level", 1),
                    ("cs", "creepScore", 10),
                ):
                    value = person.get(key)
                    if not isinstance(value, (int, float)) or not np.isfinite(value):
                        break
                    values[side, f"{stat}_{role}"] = value / scale
        gaps = (
            {col: values["blue", col] - values["red", col] for col in GAPS}
            if len(values) == 30
            else None
        )
        result[when(frame["rfc460Timestamp"])] = gaps
    return result


def role_rows(joined, raw_dir):
    """One row per kept feed sample, with all-or-nothing role coverage."""
    rows = []
    counts = {"maps_with_raw": 0, "exact": 0, "nearest": 0, "unknown": 0}
    for m in joined:
        path = raw_dir / "games" / f"{m['game_id']}.json.gz"
        windows = raw_windows(path) if path.exists() else {}
        counts["maps_with_raw"] += int(path.exists())
        times = sorted(windows)
        seconds = clock(m["samples"], when(m["start"]))
        for s, sec in zip(m["samples"], seconds):
            if sec is None or sec < 0 or s["state"] != "in_game":
                continue
            bg, rg = s["blue"]["gold"], s["red"]["gold"]
            if not bg or not rg or bg <= 0 or rg <= 0:
                continue
            target = when(s["at"])
            match = target if target in windows else None
            kind = "exact"
            if match is None and times:
                nearest = min(times, key=lambda t: abs((t - target).total_seconds()))
                if abs((nearest - target).total_seconds()) <= 10:
                    match, kind = nearest, "nearest"
            gaps = windows.get(match)
            known = gaps is not None
            counts[kind if known else "unknown"] += 1
            rows.append(
                dict(
                    game_id=m["oe_gameid"],
                    seconds=sec,
                    role_known=known,
                    **(gaps if known else dict.fromkeys(GAPS, 0.0)),
                )
            )
    print(f"Role coverage: {counts}", flush=True)
    data = pd.DataFrame(rows)
    data.attrs["coverage"] = counts
    return data


def slices(test, known):
    league = test.league
    tier = league.map(
        lambda name: (
            name
            if name in {"LPL", "LCK", "LEC", "LCS"}
            else "International"
            if name in INTERNATIONAL
            else "Other majors"
            if name in MAJORS
            else "Other"
        )
    )
    return (
        [("All", np.ones(len(test), bool))]
        + [
            (label, ((test.seconds >= lo) & (test.seconds < hi)).to_numpy())
            for label, lo, hi in [
                ("0–10", 0, 600),
                ("10–20", 600, 1200),
                ("20–30", 1200, 1800),
                ("30+", 1800, np.inf),
            ]
        ]
        + [
            (label, tier.eq(label).to_numpy())
            for label in [
                "LPL",
                "LCK",
                "LEC",
                "LCS",
                "Other majors",
                "International",
                "Other",
            ]
        ]
        + [
            ("Known", known),
            ("Unknown", ~known),
            (
                "2026",
                pd.to_datetime(test.date, utc=True, format="mixed")
                .dt.year.eq(2026)
                .to_numpy(),
            ),
        ]
    )


def compact_ci(result):
    if result is None:
        return "n/a"
    lo, hi = result["interval"]
    return f"{result['delta']:+.6f}[{lo:+.6f},{hi:+.6f}]"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    objectives = objective_rows(parts["joined"])
    cache = OUT / "role_rows.csv.gz"
    count_path = OUT / "role_rows_counts.json"
    if cache.exists() and not args.rebuild:
        roles = pd.read_csv(cache, float_precision="round_trip")
        coverage = json.loads(count_path.read_text())
        print(f"Cached role coverage: {coverage}", flush=True)
    else:
        roles = role_rows(parts["joined"], Path("data/feed_raw"))
        coverage = roles.attrs["coverage"]
        roles.to_csv(cache, index=False)
        count_path.write_text(json.dumps(coverage, indent=2) + "\n")
    n = int(parts["data"].source.eq("feed").sum())
    frames = [
        momentum(
            attach(
                attach(parts[key][parts[key].source == "feed"], objectives, n), roles, n
            )
        )
        for key in ("train", "calibration", "test")
    ]
    for frame in frames:
        add_columns(frame, PRIMARY)
        frame["level_sum"] = frame[GAPS[5:10]].sum(axis=1)
        frame["cs_sum"] = frame[GAPS[10:]].sum(axis=1)
        for col in GAPS + CANDIDATES["totals"]:
            frame[f"{col}_time"] = frame[col] * frame.time
    train, calibration, test = frames
    test = test[test.seconds <= 2400].copy()
    control = score(fit(train, calibration, STATE_FEATURES), test, STATE_FEATURES)
    control_metrics = metrics(test, control)
    if abs(control_metrics["log_loss"] - 0.4675) > 0.003:
        raise RuntimeError(
            f"Control sanity failed: {control_metrics}; stopping before candidates"
        )
    print(f"Control sanity PASS: LL={control_metrics['log_loss']:.6f}", flush=True)
    predictions = test[
        [
            "game_id",
            "series",
            "date",
            "league",
            "seconds",
            "minute",
            "won",
            "role_known",
        ]
    ].copy()
    predictions["control"] = control
    all_results, model_metrics, coefficients = {}, {"control": control_metrics}, {}
    known = test.role_known.to_numpy(dtype=bool)
    for name, gaps in CANDIDATES.items():
        added = [c for col in gaps for c in (col, f"{col}_time")]
        cols = STATE_FEATURES + added
        fitted = fit(train, calibration, cols)
        prob = score(fitted, test, cols)
        predictions[name] = prob
        model_metrics[name] = metrics(test, prob)
        if name == "primary":
            coefficients = dict(zip(added, fitted[1].coef_[0][-len(added) :].tolist()))
        all_results[name] = {
            label: delta(test[mask], prob[mask], control[mask]) if mask.any() else None
            for label, mask in slices(test, known)
        }
        print(f"{name}: {ci(all_results[name]['All'], 6)}", flush=True)
    primary = all_results["primary"]["All"]
    passed = primary["interval"][1] < -0.0005 and not any(
        result and result["interval"][0] > 0
        for result in all_results["primary"].values()
    )
    coverage["test_rows"] = len(test)
    coverage["test_known_rows"] = int(known.sum())
    coverage["test_maps"] = int(test.game_id.nunique())
    leagues = []
    for league, group in test.groupby("league"):
        leagues.append(
            {
                "league": league,
                "maps": int(group.game_id.nunique()),
                "rows": len(group),
                "unknown_rows": int((~group.role_known).sum()),
            }
        )
    coverage["test_leagues"] = leagues
    predictions.to_csv(OUT / "predictions.csv.gz", index=False)
    summary = {
        "control": control_metrics,
        "models": model_metrics,
        "results": all_results,
        "coefficients": coefficients,
        "coverage": coverage,
        "elapsed_seconds": time.monotonic() - started,
    }
    summary["pass"] = bool(passed)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    lines = [
        f"**{'PASS' if passed else 'FAIL'}: primary ΔLL {ci(primary, 6)}; retrospective, research only.**",
        "",
        "# Role leads in the live model",
        "",
        "Protocol fixed before scoring: primary five role gold gaps; level five level gaps; "
        "cs five CS gaps; totals summed level and CS gaps; all fifteen role gaps. "
        "Each adds x and x×time; no variants selected after scoring. "
        f"Feed train/calibration/test maps (rows): {train.game_id.nunique()} ({len(train)})/"
        f"{calibration.game_id.nunique()} ({len(calibration)})/{test.game_id.nunique()} ({len(test)}). "
        "Train through 2024, calibrate January–June 2025, test July 2025 onward, ≤2400 seconds. "
        "Control uses the deployed objectives + momentum recipe (20 inputs). "
        "StandardScaler, L2 C=1, equal map weights, Platt calibration.",
        "",
        "Blue-minus-red totalGold/1000, level, creepScore/10 for top/jungle/mid/bottom/support; "
        "time=seconds/1200. Metadata comes from any available raw window. Match the window's "
        "first frame exactly to the timeline timestamp, otherwise nearest within 10 seconds "
        "(first frame only). Missing file/window, incomplete measurements or missing/duplicate "
        "roles on either side give all-zero gaps, role_known=False; no rows dropped. "
        "role_known is excluded from features.",
        "",
        "LL is map-weighted. Δ=candidate−control; 95% paired whole-series bootstrap "
        "intervals use 2,000 draws, seed 42. Pass requires primary All upper bound <−0.0005 "
        "and no primary slice lower bound >0. Others are descriptive only, never adopted. "
        "No multiple-comparison adjustment.",
        "",
        "| Model | LL | Brier | ECE10 |",
        "|---|---:|---:|---:|",
    ]
    for name, m in model_metrics.items():
        lines.append(
            f"| {name} | {m['log_loss']:.6f} | {m['brier']:.6f} | {m['ece10']:.6f} |"
        )
    lines += [
        "",
        "| Slice | Maps | Primary ΔLL (95% CI) | Level | CS | Totals | All |",
        "|---|---:|---|---|---|---|---|",
    ]
    for label, mask in slices(test, known):
        cells = [compact_ci(all_results[name][label]) for name in CANDIDATES]
        lines.append(
            f"| {label} | {test[mask].game_id.nunique()} | " + " | ".join(cells) + " |"
        )
    lines += [
        "",
        "Known/Unknown refer to row-level role coverage.",
        "",
        "| Test league | Maps | Rows | Rows with unknown roles |",
        "|---|---:|---:|---:|",
    ]
    for row in leagues:
        lines.append(
            f"| {row['league']} | {row['maps']} | {row['rows']} | {row['unknown_rows']} |"
        )
    lines += [
        "",
        f"Test known roles: {known.sum()}/{len(test)} rows. "
        f"Across joined maps: {coverage['maps_with_raw']} raw files; "
        f"{coverage['exact']} exact, {coverage['nearest']} nearest, {coverage['unknown']} unknown rows.",
        "",
        "Primary standardized logistic coefficients before Platt calibration:",
        "",
        "| Added column | Coefficient |",
        "|---|---:|",
    ]
    for col, value in coefficients.items():
        lines.append(f"| {col} | {value:+.6f} |")
    lines += [
        "",
        "Limits: retrospective; July-2025+ test outcomes were viewed by earlier studies. "
        "Participant gold overlaps team gold lead already in the model. "
        "No trading check; no production change.",
        "",
        "Reproduce:",
        "```bash",
        "OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_role_leads.py",
        "```",
        "",
    ]
    text = "\n".join(lines)
    if len(text.split()) >= 900:
        raise ValueError(f"Report exceeds word budget: {len(text.split())}")
    REPORT.write_text(text)
    print(
        f"{'PASS' if passed else 'FAIL'} primary {ci(primary, 6)}; "
        f"{time.monotonic() - started:.1f}s; wrote {REPORT} and {OUT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
