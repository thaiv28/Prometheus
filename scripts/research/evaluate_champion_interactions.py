"""Test champion × state slopes without exact lane matchups, on 2023–2025.

Run: uv run python scripts/research/evaluate_champion_interactions.py
"""

import argparse
import json
from pathlib import Path

import evaluate_champions as champions

VARIANTS = (
    "stats",
    "stats_shrunk",
    "champions",
    "gold_interactions",
    "state_interactions",
)


def report(metrics, pooled, coverage):
    candidates = pooled[
        pooled.variant.isin(["gold_interactions", "state_interactions"])
    ]
    gains = candidates[candidates.delta_high.lt(0)]
    finding = (
        "No interaction variant improves pooled log loss over champion identities alone with a paired "
        "95% interval below zero. Keep the simpler models as the benchmark."
        if gains.empty
        else "Some interaction variants improve pooled development log loss with intervals below zero. "
        "These are exploratory candidates; inspect annual consistency and confirm on a new period before adoption."
    )
    if candidates.delta_base.gt(0).all():
        finding += " Every pooled interaction comparison has worse point-estimate log loss than its champion-only control."
    summary = (
        pooled[
            pooled.base.eq("aura_features")
            & pooled.variant.isin(
                ["champions", "gold_interactions", "state_interactions"]
            )
        ]
        .pivot(index="minute", columns="variant", values="log_loss")
        .reset_index()
    )
    summary.columns.name = None
    return "\n".join(
        [
            "# Champion × game-state interaction experiment",
            "",
            "Exploratory development only: 2023–2025 folds, with the already-viewed 2026 holdout excluded. "
            "Exact lane-matchup features are absent from every model in this experiment.",
            "",
            "## Finding",
            "",
            finding,
            "",
            "## Richer model comparison",
            "",
            "Log loss on the identical AURA-feature development cohorts; lower is better.",
            "",
            champions.snapshots.table(summary),
            "",
            "## Features",
            "",
            "Start with the champion-by-role main effects. For each champion, add separate slopes when its team "
            "is ahead or behind in total gold. Thus the same gold gap may have different effects depending on the "
            "draft and which team is leading. The richer state variant additionally uses each champion's own-role "
            "gold, XP, CS and kill gaps. This is a piecewise-linear response with a fixed knot at zero; it is not "
            "an unrestricted team-composition or causal champion-value model.",
            "",
            "Each interaction slope needs 20 training-game observations with a nonzero relevant gap. "
            "Champion main effects retain the prior 10-occurrence cutoff. Missing/unseen/rare slopes have zero "
            "learned adjustment and rely on the generic game-state and supported main effects. Gap scaling uses "
            "training standard deviation only, without centering, so zero stays an even state. "
            "Blue contributions are added and red contributions subtracted; swapping teams and negating all gaps "
            "negates the draft/state features. Separate minute models capture stage differences.",
            "",
            "## Evaluation",
            "",
            "Same complete-draft/snapshot games, leagues and chronological folds as the earlier champion experiment. "
            "Three years train, the next year calibrates, and the following year evaluates. No hyperparameter search; "
            "C=0.1 for all champion/interaction models. Retain original C=1 and same-C stats-only controls. "
            "The interaction comparison uses champion-only as its control, isolating the new slopes; "
            "delta_original also compares with the original stats-only model. Paired league/day-cluster bootstrap "
            "intervals use 2,000 resamples, seed 42, with no multiple-comparison correction. "
            "Raw log loss before calibration is retained. Older viewed folds remain development evidence; "
            "no fresh holdout or market edge is established.",
            "",
            "## Pooled results",
            "",
            champions.snapshots.table(pooled),
            "",
            "## Annual results",
            "",
            champions.snapshots.table(metrics),
            "",
            "## Coverage",
            "",
            champions.snapshots.table(coverage),
            "",
            "## Limits and next decision",
            "",
            "Additional slopes can overfit sparse champions and stale patch relationships. Team gold is available "
            "from scoreboards, but role gold/XP requires a richer live source. No player identity, team-strength prior, "
            "patch-specific fit, arbitrary draft synergy or market-price data is added. Require a consistent gain "
            "before freezing a candidate for newly collected matches; keep an inconclusive design out of production.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/champion_interaction_report.md")
    )
    parser.add_argument(
        "--artifacts", type=Path, default=Path("data/champion_interactions")
    )
    args = parser.parse_args()
    frames, manifest = champions.snapshots.load_raw(args.raw_dir)
    metrics, predictions, parameters, coverage = champions.evaluate(
        frames, variants=VARIANTS
    )
    pooled = champions.pooled_scores(predictions)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "metrics": metrics,
        "predictions": predictions,
        "coverage": coverage,
        "pooled": pooled,
    }.items():
        frame.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest.update(
        {
            "purpose": "exploratory interactions; 2026 excluded; no exact lane matchups",
            "years": champions.YEARS,
            "variants": VARIANTS,
            "models": parameters,
        }
    )
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(metrics, pooled, coverage))
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
