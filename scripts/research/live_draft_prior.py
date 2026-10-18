"""Live draft prior, protocol fixed 2026-10-17 before scoring.

One candidate: v1 six features + v2 log-odds shift + shift*time (seconds/1200).
C=1 standardized/map-weighted logistic fit and calibration reuse train_time_model.
Primary candidate versus refit on identical rows; secondary versus frozen v1.
Reuse train_time_model_v2.partitions' saved rows: train <2025, calibrate 2025 H1,
test feed maps >=2025-07-01, common supported minutes >=30 maps/partition.
The helper is not present on base 5811254: this script applies its exact split
and support logic to its cached rows, never imports another worktree at runtime.
For the live TRAIN rows the draft is frozen fit 2019-2021 (hence retain only
live training rows >=2022); calibration/test shifts fit 2019-2024, frozen before
calibration. This avoids fitting a draft on its live training targets. Features
use earlier UTC days via draft_walkforward. No shift refit on 2025/2026 outcomes.
Score within frozen v1 range, equal map weights, 2000 series bootstrap draws.
Report minute bands, all/majors/LPL/international/other and test year. Pre-2025
live TEST is unavailable under the mandated split; explicitly report this.
No tuning, market fetching, production changes or export to runtime.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_walkforward as dw
from train_time_model import delta, fit, metrics, score

from prometheus.live.timeline import FEATURES, predict

ROOT = Path(__file__).resolve().parents[2]
# Read-only reference protocol inspected before execution; never imported at runtime.
REFERENCE_SHA = "74fd491f26153cecd2b0dfcbeea5a24036ff16e8336cfe6f7bd97e838fdf9d52"
PARTITIONS_SHA = "8236029492c6cb48b0f572ec69f23be2ac0b1edfa17095a915de66c93bc8325e"
COLUMNS = [*FEATURES, "draft_shift", "draft_time"]


def frozen_games():
    """Reuse the handoff's frozen FORGE calls without rebuilding missing calls."""
    rows = dw.player_features(dw.load_rows())
    games = dw.game_table(rows, dw.synergy(rows))
    games = games[games.year >= dw.FIT_FROM]
    frozen = pd.read_pickle(dw.CACHE / "forge.pkl")
    games = games.merge(frozen, on="gameid", validate="one_to_one")
    games["forge_logit"] = dw._logit(games.p_forge)
    return games


def draft_shifts(games):
    """Separate prior-only fits for live training and calibration/test."""
    out = []
    for stop, lo, hi in ((2021, 2022, 2024), (2024, 2025, 2026)):
        train = games[games.year.between(2019, stop)]
        test = games[games.year.between(lo, hi)].copy()
        base = dw._fit(train, ["forge_logit"])
        draft = dw._fit(train, ["forge_logit", *dw.FEATURES])
        test["draft_shift"] = draft.decision_function(
            test[["forge_logit", *dw.FEATURES]].to_numpy()
        ) - base.decision_function(test[["forge_logit"]].to_numpy())
        out.append(test[["gameid", "draft_shift"]])
    return pd.concat(out).set_index("gameid").draft_shift


def partitions(data, min_maps=30):
    """Exact cached-row split/support from train_time_model_v2.partitions."""
    at = pd.to_datetime(data.date, utc=True, format="mixed").dt.tz_convert(None)
    parts = [
        data[at < "2025-01-01"].copy(),
        data[
            (at >= "2025-01-01") & (at < "2025-07-01") & data.source.eq("feed")
        ].copy(),
        data[(at >= "2025-07-01") & data.source.eq("feed")].copy(),
    ]
    counts = [p.groupby("minute").game_id.nunique() for p in parts]
    high = 0
    while high < 40 and all(c.get(high + 1, 0) >= min_maps for c in counts):
        high += 1
    if high < 20:
        raise ValueError("insufficient common support")
    return [p[p.seconds <= high * 60].copy() for p in parts]


def attach(frame, shifts):
    kept = frame[frame.game_id.isin(shifts.index)].copy()
    kept["draft_shift"] = kept.game_id.map(shifts)
    kept["draft_time"] = kept.draft_shift * kept.time
    return kept


def run(args):
    data = pd.read_csv(args.rows)
    original = partitions(data)
    games = frozen_games()
    shifts = draft_shifts(games)
    parts = [attach(p[p.year >= 2022], shifts) for p in original]
    train, calibration, test = parts
    v1 = json.loads((ROOT / "prometheus/live/time_model_v1.json").read_text())
    test = test[test.seconds <= v1["supported_seconds"][1]].copy()
    candidate = fit(train, calibration, COLUMNS)
    refit = fit(train, calibration, FEATURES)
    p = score(candidate, test, COLUMNS)
    q = score(refit, test, FEATURES)
    old = np.array(
        [
            predict(
                v1,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
            )
            for r in test.itertuples()
        ]
    )
    lines = [
        "# Draft v2 as a live prior",
        "",
        "Protocol fixed before scoring in `scripts/research/live_draft_prior.py`.",
        "One candidate, draft shift and shift × time. Negative log-loss difference favours the candidate.",
        "",
        "Saved rows from `train_time_model_v2.partitions()`; that helper is absent at the branch base.",
        f"Input SHA256: `{hashlib.sha256(args.rows.read_bytes()).hexdigest()}`.",
        f"Read-only design reference `../Prometheus-cand-draft/scripts/research/cand_draft.py`, SHA256 `{REFERENCE_SHA}`; adapted to v2, with primary same-row refit control.",
        f"Partition reference `../Prometheus-cand-mapelo/scripts/research/train_time_model_v2.py`, SHA256 `{PARTITIONS_SHA}`. Cache origin: main checkout `data/research/time_model_v2/rows.csv` (saved helper rows). Neither sibling module is imported.",
        "",
        "| Partition | Original maps | Retained maps |",
        "|---|---:|---:|",
    ]
    for label, raw, kept in zip(("train", "calibration", "test"), original, parts):
        lines.append(
            f"| {label} | {raw.game_id.nunique():,} | {kept.game_id.nunique():,} |"
        )
    lines += [
        "",
        "Train live rows start 2022; their draft weights freeze through 2021. Calibration/test draft weights freeze through 2024.",
        "All comparisons share retained maps; absent shifts drop from all calls. Prior-year feature histories still update from earlier days.",
        "",
        "| Slice | Maps | Candidate LL | Refit LL | v1 LL | Candidate − refit (95%) | Candidate − v1 (95%) |",
        "|---|---:|---:|---:|---:|---|---|",
    ]
    slices = [
        ("all", np.ones(len(test), bool)),
        ("majors", test.league.isin(dw.MAJORS)),
        ("LPL", test.league.eq("LPL")),
        ("international", test.league.isin(dw.INTERNATIONAL_LEAGUES)),
        ("other", ~test.league.isin(set(dw.MAJORS) | set(dw.INTERNATIONAL_LEAGUES))),
    ]
    slices += [
        (
            f"minutes {lo // 60}–{hi // 60 if hi < 1e8 else '+'}",
            (test.seconds >= lo) & (test.seconds < hi),
        )
        for lo, hi in ((0, 600), (600, 1200), (1200, 1800), (1800, 1e9))
    ]
    slices += [(str(y), test.year.eq(y)) for y in sorted(test.year.unique())]
    for name, mask in slices:
        mask = np.asarray(mask)
        part = test[mask]
        if part.game_id.nunique() < 10:
            lines.append(
                f"| {name} | {part.game_id.nunique()} | — | — | — | insufficient maps | — |"
            )
            continue
        d, e = delta(part, p[mask], q[mask]), delta(part, p[mask], old[mask])
        fmt = lambda x: dw._ci(x["delta"], *x["interval"])
        vals = [metrics(part, x[mask])["log_loss"] for x in (p, q, old)]
        lines.append(
            f"| {name} | {part.game_id.nunique():,} | {vals[0]:.4f} | {vals[1]:.4f} | {vals[2]:.4f} | {fmt(d)} | {fmt(e)} |"
        )
    lines += [
        "",
        "## Limits",
        "",
        "Pre-2025 test: unavailable (test begins July 2025). v2 features were selected after viewing 2025–26; this is a follow-up, not an untouched holdout.",
        "Cached feed clock, OE joins and historical pre-series Elo inherit the v2 study's limitations. The live training draft fit freezes earlier than the test fit; a larger clean rolling-origin live study is future work.",
        "The full shift includes intercept/FORGE recalibration terms; this is the requested prior, not a pure champion-effect causal estimate.",
        "No live draft computation, fill test or trading claim. Published models/weights unchanged.",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "docs/research/live_draft_prior.md"
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
