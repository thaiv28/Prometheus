"""Fixed, retrospective alive, Elder/soul and completed-item study; no production changes."""

import argparse
import gzip
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from live_role_leads import (
    STATE_FEATURES,
    attach,
    clock,
    compact_ci,
    delta,
    fit,
    metrics,
    partitions,
    prepared_frames,
    score,
    slices,
    when,
)

OUT = Path("data/research/live_state")
REPORT = Path("docs/research/live_state.md")
CANDIDATES = {
    "alive": ["alive"],
    "alive_respawn": ["alive", "respawn"],
    "elder": ["elder_recent", "elder"],
    "soul_true": [],
    "items": ["items"],
    "combined": ["alive", "respawn", "elder_recent", "elder", "items"],
}
VALUES = ["alive", "respawn", "elder_recent", "elder", "soul_true", "items"]
BASE_TIMER = (
    6,
    6,
    8,
    8,
    10,
    12,
    16,
    21,
    26,
    32.5,
    35,
    37.5,
    40,
    42.5,
    45,
    47.5,
    50,
    52.5,
)


def death_timer(level, seconds):
    """Approximate respawn duration; completed 30-second steps, capped at +50%."""
    steps = lambda lo, hi: max(0, min(seconds, hi) - lo) // 30
    bonus = (
        steps(900, 1800) * 0.00425
        + steps(1800, 2700) * 0.003
        + steps(2700, 3300) * 0.0145
    )
    # Levels 19-20 (raised cap) reuse the level-18 timer.
    return BASE_TIMER[min(int(level), 18) - 1] * (1 + min(0.5, bonus))


def completed_sets(items_dir):
    """Patch-keyed completed items, using only the declared Data Dragon rule."""
    result = {}
    for path in sorted(items_dir.glob("*.json")):
        patch = tuple(map(int, path.stem.split(".")[:2]))
        data = json.loads(path.read_text())["data"]
        result[patch] = {
            int(item_id)
            for item_id, item in data.items()
            if not item.get("into")
            and item.get("gold", {}).get("total", 0) >= 2200
            and item.get("gold", {}).get("purchasable", False)
            and item.get("maps", {}).get("11", False)
            and "Consumable" not in item.get("tags", [])
            and not item.get("requiredChampion")
            and not item.get("requiredAlly")
            and item.get("inStore") is not False
        }
    return result


def patch_items(version, sets):
    try:
        patch = tuple(map(int, version.split(".")[:2]))
    except (AttributeError, ValueError):
        return None
    if len(patch) != 2:
        return None
    earlier = [p for p in sets if p <= patch]
    return sets[max(earlier)] if earlier else None


def raw_frames(path):
    """Retain first window frames and timestamp-matched details, one map at a time."""
    with gzip.open(path, "rt") as stream:
        raw = json.load(stream)
    first = raw.get("first") or {}
    samples = [first if "window" in first else {"window": first}] + raw.get(
        "samples", []
    )
    metadata = next(
        (
            s["window"]["gameMetadata"]
            for s in samples
            if (s.get("window") or {}).get("gameMetadata")
        ),
        {},
    )
    result = {}
    for sample in samples:
        window = sample.get("window") or {}
        frames = window.get("frames") or []
        if not frames:
            continue
        frame = frames[0]
        target = when(frame["rfc460Timestamp"])
        details = (sample.get("details") or {}).get("frames") or []
        exact = [d for d in details if when(d["rfc460Timestamp"]) == target]
        detail = exact[0] if exact else None
        if detail is None and details:
            nearest = min(
                details,
                key=lambda d: abs(
                    (when(d["rfc460Timestamp"]) - target).total_seconds()
                ),
            )
            if abs((when(nearest["rfc460Timestamp"]) - target).total_seconds()) <= 10:
                detail = nearest
        version = (window.get("gameMetadata") or metadata).get("patchVersion")
        result[target] = (frame, detail, version)
    return result


def state_values(frame, sec, dead_since, previous, elder_seen, elder_counts):
    """Update only from kept observations. Death start is first seen, reset on new death."""
    values = {}
    any_dead = False
    for side in ("blue", "red"):
        team = frame.get(f"{side}Team", {})
        people = team.get("participants", [])
        dragons = team.get("dragons")
        if len(people) != 5 or not isinstance(dragons, list):
            return None
        ids = [p.get("participantId") for p in people]
        if None in ids or len(set(ids)) != 5:
            return None
        for p in people:
            for key in ("currentHealth", "maxHealth", "level", "deaths"):
                if not isinstance(p.get(key), (int, float)) or not np.isfinite(p[key]):
                    return None
            if p["maxHealth"] <= 0 or not 1 <= p["level"] <= 20:
                return None
    for side in ("blue", "red"):
        team = frame[f"{side}Team"]
        alive, remaining = 0, 0.0
        for p in team["participants"]:
            key = (side, p["participantId"])
            if p["currentHealth"] > 0:
                alive += 1
                dead_since.pop(key, None)
            else:
                any_dead = True
                if key not in dead_since or p["deaths"] > previous.get(
                    key, p["deaths"]
                ):
                    dead_since[key] = sec
                remaining += max(
                    0, death_timer(p["level"], sec) - (sec - dead_since[key])
                )
            previous[key] = p["deaths"]
        elder = team["dragons"].count("elder")
        if elder > elder_counts.get(side, 0):
            elder_seen[side] = sec
        elder_counts[side] = elder
        values[side] = {
            "alive": alive,
            "respawn": -remaining / 60,
            "elder": elder,
            "elder_recent": int(
                side in elder_seen and 0 <= sec - elder_seen[side] <= 180
            ),
            "soul_true": int(sum(d != "elder" for d in team["dragons"]) >= 4),
        }
    return {
        **{c: values["blue"][c] - values["red"][c] for c in values["blue"]},
        "any_dead": any_dead,
        "elder_taken": any(elder_counts.values()),
    }


def item_gap(frame, detail, completed):
    if detail is None or completed is None:
        return None
    people = detail.get("participants", [])
    lookup = {p.get("participantId"): p.get("items") for p in people}
    total = {}
    for side in ("blue", "red"):
        team = frame.get(f"{side}Team", {}).get("participants", [])
        if len(team) != 5:
            return None
        counts = []
        for p in team:
            items = lookup.get(p.get("participantId"))
            if not isinstance(items, list) or not all(
                isinstance(i, int) for i in items
            ):
                return None
            counts.append(sum(i in completed for i in items))
        total[side] = sum(counts)
    return total["blue"] - total["red"]


def state_rows(joined, raw_dir, items_dir):
    """One row per objective_rows sample, retaining unknown rows as zero features."""
    sets = completed_sets(items_dir)
    sizes = [len(s) for s in sets.values()]
    coverage = {
        "patch_files": len(sets),
        "item_set_min": min(sizes, default=0),
        "item_set_max": max(sizes, default=0),
        "maps_with_raw": 0,
        "exact": 0,
        "nearest": 0,
    }
    rows = []
    for m in joined:
        path = raw_dir / "games" / f"{m['game_id']}.json.gz"
        windows = raw_frames(path) if path.exists() else {}
        coverage["maps_with_raw"] += int(path.exists())
        times = sorted(windows)
        dead_since, previous, elder_seen, elder_counts = {}, {}, {}, {}
        seconds = clock(m["samples"], when(m["start"]))
        for sample, sec in zip(m["samples"], seconds):
            if sec is None or sec < 0 or sample["state"] != "in_game":
                continue
            bg, rg = sample["blue"]["gold"], sample["red"]["gold"]
            if not bg or not rg or bg <= 0 or rg <= 0:
                continue
            target = when(sample["at"])
            match, kind = (target, "exact") if target in windows else (None, "nearest")
            if match is None and times:
                nearest = min(times, key=lambda t: abs((t - target).total_seconds()))
                if abs((nearest - target).total_seconds()) <= 10:
                    match = nearest
            row = dict(
                game_id=m["oe_gameid"],
                seconds=sec,
                state_known=False,
                items_known=False,
                any_dead=False,
                elder_taken=False,
                **dict.fromkeys(VALUES, 0.0),
            )
            if match is not None:
                coverage[kind] += 1
                frame, detail, patch = windows[match]
                state = state_values(
                    frame, sec, dead_since, previous, elder_seen, elder_counts
                )
                if state is not None:
                    row.update(state, state_known=True)
                items = item_gap(frame, detail, patch_items(patch, sets))
                if items is not None:
                    row.update(items=items, items_known=True)
            if not row["state_known"]:
                dead_since.clear()
                previous.clear()
            rows.append(row)
    data = pd.DataFrame(rows)
    coverage.update(
        rows=len(data),
        state_known=int(data.state_known.sum()),
        items_known=int(data.items_known.sum()),
    )
    data.attrs["coverage"] = coverage
    print(f"State coverage: {coverage}", flush=True)
    return data


def candidate_columns(name):
    cols = list(STATE_FEATURES)
    if name in {"soul_true", "combined"}:
        cols = [
            {"obj_soul": "soul_true", "obj_soul_time": "soul_true_time"}.get(c, c)
            for c in cols
        ]
        if "soul_true" not in cols:
            raise ValueError("Deployed soul column not found")
    return cols + [c for v in CANDIDATES[name] for c in (v, f"{v}_time")]


def study_slices(test):
    return slices(test, test.state_known.to_numpy(bool)) + [
        ("Any dead", test.any_dead.to_numpy(bool)),
        ("Elder taken", test.elder_taken.to_numpy(bool)),
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild", action="store_true")
    args = parser.parse_args()
    started = time.monotonic()
    OUT.mkdir(parents=True, exist_ok=True)
    train, calibration, test = prepared_frames()
    n_feed = sum(test.attrs["coverage"][k] for k in ("exact", "nearest", "unknown"))
    cache, counts = OUT / "state_rows.csv.gz", OUT / "state_rows_counts.json"
    if cache.exists() and not args.rebuild:
        states = pd.read_csv(cache, float_precision="round_trip")
        coverage = json.loads(counts.read_text())
        print(f"Cached state coverage: {coverage}", flush=True)
    else:
        parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
        states = state_rows(
            parts["joined"], Path("data/feed_raw"), Path("data/ddragon/items")
        )
        if len(states) != int(parts["data"].source.eq("feed").sum()):
            raise ValueError("state row count differs from feed")
        coverage = states.attrs["coverage"]
        states.to_csv(cache, index=False)
        counts.write_text(json.dumps(coverage, indent=2) + "\n")
    train, calibration, test = (
        attach(f, states, n_feed) for f in (train, calibration, test)
    )
    for frame in (train, calibration, test):
        for col in VALUES:
            frame[f"{col}_time"] = frame[col] * frame.time
    test = test[test.seconds <= 2400].copy()
    control = score(fit(train, calibration, STATE_FEATURES), test, STATE_FEATURES)
    control_metrics = metrics(test, control)
    if abs(control_metrics["log_loss"] - 0.4656) > 0.003:
        raise RuntimeError(f"Control sanity failed: {control_metrics}; stopping")
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
            "state_known",
            "items_known",
            "any_dead",
            "elder_taken",
            "alive",
        ]
    ].copy()
    predictions["control"] = control
    results, model_metrics, coefficients, passed = (
        {},
        {"control": control_metrics},
        {},
        {},
    )
    masks = study_slices(test)
    for name in CANDIDATES:
        cols = candidate_columns(name)
        fitted = fit(train, calibration, cols)
        prob = score(fitted, test, cols)
        predictions[name] = prob
        model_metrics[name] = metrics(test, prob)
        coefficients[name] = {
            c: float(v)
            for c, v in zip(cols, fitted[1].coef_[0])
            if c not in STATE_FEATURES
        }
        results[name] = {
            label: delta(test[mask], prob[mask], control[mask]) if mask.any() else None
            for label, mask in masks
        }
        threshold = 0 if name == "soul_true" else -0.0005
        passed[name] = bool(
            results[name]["All"]["interval"][1] < threshold
            and not any(r and r["interval"][0] > 0 for r in results[name].values())
        )
        print(
            f"{name}: {compact_ci(results[name]['All'])} {'PASS' if passed[name] else 'FAIL'}",
            flush=True,
        )
    coverage["test_rows"] = len(test)
    coverage["test_state_known"] = int(test.state_known.sum())
    coverage["test_items_known"] = int(test.items_known.sum())
    coverage["test_leagues"] = [
        {
            "league": league,
            "rows": len(g),
            "state_known": int(g.state_known.sum()),
            "items_known": int(g.items_known.sum()),
        }
        for league, g in test.groupby("league")
    ]
    unequal = test[test.state_known & test.alive.ne(0)]
    descriptive = {
        "any_dead_share": float(test.any_dead.mean()),
        "alive_unequal_rows": len(unequal),
        "outcome_agreement": float(
            (unequal.alive.gt(0).astype(int) == unequal.won).mean()
        ),
    }
    summary = {
        "control": control_metrics,
        "models": model_metrics,
        "results": results,
        "coefficients": coefficients,
        "coverage": coverage,
        "descriptive": descriptive,
        "passed": passed,
        "elapsed_seconds": time.monotonic() - started,
    }
    predictions.to_csv(OUT / "predictions.csv.gz", index=False)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    write_report(train, calibration, test, summary, masks)
    print(f"Wrote {REPORT} and {OUT}; {time.monotonic() - started:.1f}s", flush=True)


def write_report(train, calibration, test, summary, masks):
    results, coverage = summary["results"], summary["coverage"]
    lines = ["# Alive players, Elder/soul and items in the live model", ""]
    for name in CANDIDATES:
        lines.append(
            f"**{name}: {'PASS' if summary['passed'][name] else 'FAIL'}**, All ΔLL {compact_ci(results[name]['All'])}."
        )
    lines += [
        "",
        "Fixed candidates: alive; alive_respawn; elder (recent, cumulative); soul_true replacement; items; combined (all additions, soul replacement). Add x and x×time (seconds/1200). Control: deployed 20 inputs, objectives + momentum. No post-scoring selection.",
        "",
        f"Feed train/calibration/test maps (rows): {train.game_id.nunique()} ({len(train)})/{calibration.game_id.nunique()} ({len(calibration)})/{test.game_id.nunique()} ({len(test)}). Train through 2024; calibrate January–June 2025; test July 2025 onward, ≤2400 seconds. StandardScaler, L2 C=1, equal map weights, Platt calibration.",
        "",
        "Δ=candidate−control; map-weighted LL, 95% paired whole-series bootstrap, 2,000 draws, seed 42. Pass: All upper <−0.0005 (soul_true: <0), no slice lower >0. Six candidates; no multiple-comparison adjustment. Passing requires live benchmark and trading check before adoption.",
        "",
        "Alive: blue−red living players. Respawn: red−blue remaining seconds /60; scaled level timer minus time since first seen dead, reset on increased deaths. Elder_recent: 180 seconds from observed count increase. soul_true: ≥4 non-elder dragons. History uses earlier/current kept samples.",
        "",
        "Windows match timeline timestamps; details match window timestamps; fallback nearest ≤10 seconds. Items: exact/latest earlier patch; terminal, purchasable, Rift, ≥2200 gold; exclude Consumable, champion/ally-only, inStore=False. Missing data or unsupported state levels (outside 1–20; 19–20 use the level-18 timer): zero features, separate state/items flags excluded from fitting.",
        "",
        "| Model | LL | Brier | ECE10 |",
        "|---|---:|---:|---:|",
    ]
    for name, m in summary["models"].items():
        lines.append(
            f"| {name} | {m['log_loss']:.6f} | {m['brier']:.6f} | {m['ece10']:.6f} |"
        )
    lines += [
        "",
        "| Slice | Maps | alive | alive_respawn | elder | soul_true | items | combined |",
        "|---|---:|---|---|---|---|---|---|",
    ]
    for label, mask in masks:
        lines.append(
            f"| {label} | {test[mask].game_id.nunique()} | "
            + " | ".join(compact_ci(results[n][label]) for n in CANDIDATES)
            + " |"
        )
    lines += [
        "",
        "Cells: ΔLL[95% CI]. Known/Unknown refer to state coverage.",
        "",
        f"Joined coverage: state {coverage['state_known']}/{coverage['rows']}, items {coverage['items_known']}/{coverage['rows']}; {coverage['exact']} exact/{coverage['nearest']} nearest windows. Completed-item set sizes: {coverage['item_set_min']}–{coverage['item_set_max']} across {coverage['patch_files']} patch files.",
        "",
        "Test coverage (league rows:state/items known): "
        + "; ".join(
            f"{r['league']} {r['rows']}:{r['state_known']}/{r['items_known']}"
            for r in coverage["test_leagues"]
        )
        + f". Total {len(test)}:{coverage['test_state_known']}/{coverage['test_items_known']}.",
        "",
        "Standardized logistic coefficients before Platt calibration (x, x×time):",
        "",
        "| Candidate | Added/replacement feature | Coefficients |",
        "|---|---|---:|",
    ]
    for name, coefs in summary["coefficients"].items():
        for c, v in coefs.items():
            if not c.endswith("_time"):
                lines.append(f"| {name} | {c} | {v:+.6f}, {coefs[c + '_time']:+.6f} |")
    d = summary["descriptive"]
    lines += [
        "",
        "| Test-row description | Value |",
        "|---|---:|",
        f"| Any player dead | {d['any_dead_share']:.2%} |",
        f"| More-alive team won (unequal alive, {d['alive_unequal_rows']} rows) | {d['outcome_agreement']:.2%} |",
        "",
        "Limits: retrospective; July-2025+ test viewed by earlier studies. Respawn is estimated; deaths seen at minute resolution. Items follow the patch rule. Level-19 states occur; whole-state zeroing confounds the soul comparison. No live benchmark or trading check; research only, no production change.",
        "",
        "Reproduce:",
        "```bash",
        "OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_state.py",
        "```",
        "",
    ]
    text = "\n".join(lines)
    if len(text.split()) >= 900:
        raise ValueError(f"Report exceeds word budget: {len(text.split())}")
    REPORT.write_text(text)


if __name__ == "__main__":
    main()
