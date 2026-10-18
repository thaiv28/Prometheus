"""Combine qualifying fixed draft-feature blocks under draft_v3_protocol.md.

Protocol committed to disk before any track result was read, 2026-10-17.
Supply each full predeclared primary block, including failures. Never choose
columns from test coefficients. Gate entire blocks on all/pre2025 benefit and
no significantly worse named league slice, then fit their union once. Same
annual folds and logistic fitting as draft_walkforward; no test tuning.
This is retrospective selection, not independent confirmation. Research only.

Example (all four blocks must be supplied, not just observed winners):
 uv run python scripts/research/draft_v3.py --block composition FILE scaling,scaling_strength,early ... --out docs/research/draft_v3.md
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

BASE = [
    "date",
    "year",
    "league",
    "blue",
    "red",
    "won",
    "series",
    "forge_logit",
    *dw.FEATURES,
]
EXPECTED = {"composition", "form", "meta", "player_feats"}


def merge_blocks(specs):
    """Refuse changing cohorts/targets/baselines or duplicate columns silently."""
    base, blocks, manifest = None, {}, []
    if {s[0] for s in specs} != EXPECTED or len(specs) != len(EXPECTED):
        raise ValueError("supply exactly the four declared blocks")
    for name, filename, names in specs:
        path = Path(filename)
        frame = pd.read_pickle(path).set_index("gameid").sort_index()
        cols = names.split(",")
        if not frame.index.is_unique:
            raise ValueError(f"duplicate game IDs: {name}")
        if not all(c in frame for c in [*BASE, *cols]):
            raise ValueError(f"missing baseline/feature columns: {name}")
        if base is None:
            base = frame[BASE].copy()
        else:
            try:
                pd.testing.assert_frame_equal(
                    base[BASE], frame[BASE], check_dtype=False, check_exact=True
                )
            except AssertionError as exc:
                raise ValueError(f"cohort/target/baseline mismatch: {name}") from exc
        if any(c in base for c in cols) or len(set(cols)) != len(cols):
            raise ValueError(f"duplicate feature names: {name}")
        if not np.isfinite(frame[cols].to_numpy(dtype=float)).all():
            raise ValueError(f"nonfinite features: {name}")
        base = base.join(frame[cols], validate="one_to_one")
        blocks[name] = cols
        manifest.append(
            {
                "block": name,
                "columns": cols,
                "source": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return base.reset_index(), blocks, manifest


def score(games, extras):
    parts, weights = [], {}
    cols = ["forge_logit", *dw.FEATURES]
    for year in dw.TEST_YEARS:
        train = games[games.year.between(dw.FIT_FROM, year - 1)]
        test = games[games.year.eq(year)].copy()
        if test.empty:
            continue
        for label, features in (("v2", cols), ("candidate", [*cols, *extras])):
            model = dw._fit(train, features)
            test[label] = model.predict_proba(test[features].to_numpy())[:, 1]
            if label == "candidate":
                weights[year] = dict(
                    zip(
                        ["intercept", *features], [model.intercept_[0], *model.coef_[0]]
                    )
                )
        parts.append(test)
    return pd.concat(parts, ignore_index=True), weights


def gate(scored):
    rows = []
    for label, frame in [
        *dw.slices(scored),
        ("before 2025", scored[scored.year < 2025]),
    ]:
        if frame.empty:
            return False, rows
        a, b, d, lo, hi = dw.paired(frame, "candidate", "v2")
        rows.append(
            {
                "slice": label,
                "games": len(frame),
                "candidate": a,
                "v2": b,
                "delta": d,
                "lo": lo,
                "hi": hi,
            }
        )
    gain = all(r["hi"] < 0 for r in rows if r["slice"] in ("all", "before 2025"))
    safe = all(r["lo"] <= 0 for r in rows if r["slice"] not in ("all", "before 2025"))
    return gain and safe, rows


def table(rows):
    lines = [
        "| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |",
        "|---|---:|---:|---:|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['slice']} | {r['games']:,} | {r['v2']:.6f} | {r['candidate']:.6f} | {r['delta']:+.6f} ({r['lo']:+.6f} to {r['hi']:+.6f}) |"
        )
    return lines


def run(args):
    games, blocks, manifest = merge_blocks(args.block)
    chosen, results = [], {}
    lines = [
        "# Draft v3: fixed union of qualifying blocks",
        "",
        "Selection/scoring protocol: [draft_v3_protocol.md](draft_v3_protocol.md), fixed before reading track results. Every full primary block is supplied. Blocks qualify only on all/pre-2025 benefit with no significantly worse named league slice. Tests reuse viewed outcomes; intervals condition on selection, without multiplicity adjustment.",
        "",
        f"Identical baseline cohort: {len(games):,} training/test games, {games.year.min()}–{games.year.max()}. No production calls are rebuilt.",
    ]
    for name, cols in blocks.items():
        scored, _ = score(games, cols)
        eligible, rows = gate(scored)
        results[name] = {"eligible": eligible, "rows": rows, "columns": cols}
        if eligible:
            chosen.extend(cols)
        lines += [
            "",
            f"## Block: {name} — {'qualifies' if eligible else 'excluded'}",
            "",
            *table(rows),
        ]
    if chosen:
        scored, weights = score(games, chosen)
        passes, rows = gate(scored)
        for year, f in scored.groupby("year"):
            a, b, d, lo, hi = dw.paired(f, "candidate", "v2")
            rows.append(
                {
                    "slice": str(year),
                    "games": len(f),
                    "candidate": a,
                    "v2": b,
                    "delta": d,
                    "lo": lo,
                    "hi": hi,
                }
            )
        lines += [
            "",
            "## Combined candidate",
            "",
            f"Included columns: {', '.join(chosen)}. Fixed comparison rule: {'passes retrospectively' if passes else 'does not pass; retain v2'}.",
            "",
            *table(rows),
            "",
            "| Test year | "
            + " | ".join(["intercept", "forge_logit", *dw.FEATURES, *chosen])
            + " |",
            "|---|" + "---:|" * (2 + len(dw.FEATURES) + len(chosen)),
        ]
        for year, w in weights.items():
            lines.append(
                f"| {year} | " + " | ".join(f"{v:+.6f}" for v in w.values()) + " |"
            )
        results["combined"] = {"eligible": passes, "rows": rows, "weights": weights}
    else:
        lines += [
            "",
            "## Combined candidate",
            "",
            "No fixed block qualifies. Retain v2; no combined variant was fit or selected.",
        ]
    lines += [
        "",
        "## Limits",
        "",
        "Whole-block significance does not attribute gains to individual columns. Prior annual FORGE calibration/weights are current artifacts, not historical vintages. All periods are retrospective; the v3 block gate viewed the same before-2025 years subsequently reported. Future untouched evaluation is required for confirmation. Market, series and live tracks remain separate; no shipping or trading claim.",
        "",
        "## Input provenance",
        "",
        "```json",
        json.dumps(manifest, indent=2),
        "```",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    args.out.with_suffix(".json").write_text(json.dumps(results, indent=2))
    print(f"wrote {args.out}; included {chosen}", flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--block",
        action="append",
        nargs=3,
        metavar=("NAME", "PATH", "COLS"),
        required=True,
    )
    p.add_argument("--out", type=Path, required=True)
    run(p.parse_args())


if __name__ == "__main__":
    main()
