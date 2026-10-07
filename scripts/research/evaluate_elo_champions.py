"""Isolate champion additions to stats+Elo at matched C=0.1 on 2023–2025.

Run: .venv/bin/python scripts/research/evaluate_elo_champions.py
"""

import argparse
import hashlib
import json
from pathlib import Path

import evaluate_snapshot_elo as experiment

VARIANTS = {
    "stats_elo": ("stats_shrunk", True, "stats_elo"),
    "champions_elo": ("champions", True, "stats_elo"),
}


def report(pooled, annual, coverage, audit):
    candidate = pooled[pooled.variant.eq("champions_elo")]
    rich = candidate[candidate.base.eq("aura_features")]
    gains = rich[rich.delta_high.lt(0)]
    finding = (
        "No full-stats champion addition improves pooled log loss with a paired 95% interval below zero. Keep stats+Elo as the simpler development candidate."
        if gains.empty
        else "Some full-stats champion additions improve pooled log loss with paired intervals below zero. Inspect annual consistency before selecting a candidate for fresh validation."
    )
    summary = (
        pooled[pooled.base.eq("aura_features")]
        .pivot(index="minute", columns="variant", values="log_loss")
        .reset_index()
    )
    summary.columns.name = None
    return "\n".join(
        [
            "# Champions added to stats + Elo: matched regularization",
            "",
            "Exploratory development folds: 2023–2025 only. The previously viewed 2026 data is excluded.",
            "",
            "## Finding",
            "",
            finding,
            "",
            "## Full-stats comparison",
            "",
            "Log loss (lower is better); both models use C=0.1.",
            "",
            experiment.snapshots.table(summary),
            "",
            "## Protocol",
            "",
            "Each gold or full-stats (30 lane features) base includes blue-minus-red pre-match Elo. Compare the same numeric model with and without signed champion-by-role main effects. Both use logistic C=0.1, fixed from the earlier champion protocol, with identical games, numeric scaling and temporal splits. No parameter search, exact lane-matchup features, champion×state terms or composition synergies. Unknown/rare champions receive zero draft adjustment; the 10-training-occurrence cutoff and vocabulary use training only.",
            "",
            "Each fold trains on three calendar years, uses the following year for sigmoid calibration, and evaluates the next year. Calibration is fit separately for each model using only that preceding year. Report both calibrated and raw log loss. Candidate deltas compare champions+Elo directly with same-C stats+Elo; paired league/day-cluster 95% intervals use 2,000 resamples, seed 42, with no multiple-comparison correction. Gold is a secondary comparison; full stats is the primary requested comparison.",
            "",
            "## Elo provenance and coverage",
            "",
            f"Existing roster-aware Elo replayed unchanged through 2025: {audit['elo_games']} games, maximum difference from stored pre-match ratings {audit['saved_rating_max_difference']:.3g}. Joins validate game/team/side IDs and raw timestamp/result/duration. All models share complete draft/snapshot/rating cohorts. {audit['tied_timestamp_games']} archive games share timestamps; the existing replay uses game-ID tie order. Archive ordering is not a verified result-availability feed. See the prior snapshot Elo report for broader Elo provenance.",
            "",
            "## Pooled scores and paired differences",
            "",
            experiment.snapshots.table(pooled),
            "",
            "## Annual scores and paired differences",
            "",
            experiment.snapshots.table(annual),
            "",
            "## Coverage",
            "",
            experiment.snapshots.table(coverage),
            "",
            "## Decision limits",
            "",
            "These folds have already informed model development, and existing Elo settings were selected in prior work. A small lower point estimate does not establish a reliable benefit. Keep an inconclusive champion addition out of the chosen candidate; freeze the selected design before evaluating newly collected matches. Probability quality does not establish a betting edge without aligned executable prices and costs. This experiment changes no published metrics or live behavior.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_champion_report.md")
    )
    parser.add_argument("--artifacts", type=Path, default=Path("data/elo_champions"))
    args = parser.parse_args()
    ratings, audit = experiment.load_ratings()
    frames, manifest = experiment.snapshots.load_raw(args.raw_dir)
    predictions, parameters, coverage = experiment.evaluate(
        frames, ratings, variants=VARIANTS
    )
    pooled = experiment.score(predictions, variants=VARIANTS)
    annual = experiment.score(predictions, annual=True, variants=VARIANTS)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "predictions": predictions,
        "pooled": pooled,
        "metrics": annual,
        "coverage": coverage,
    }.items():
        frame.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest.update(
        {
            "purpose": "matched-C champion addition to Elo; viewed development only; 2026 excluded",
            "years": experiment.champions.YEARS,
            "variants": VARIANTS,
            "elo_audit": audit,
            "elo_source_sha256": hashlib.sha256(
                Path(experiment.elo.__file__).read_bytes()
            ).hexdigest(),
            "models": parameters,
        }
    )
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(pooled, annual, coverage, audit))
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
