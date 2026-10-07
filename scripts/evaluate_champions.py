"""Exploratory champion ablation on 2023–2025; never evaluates 2026.

Run: uv run python scripts/evaluate_champions.py
"""

import argparse
from collections import Counter
import json
from pathlib import Path

import pandas as pd
from scipy import sparse
from sklearn.feature_extraction import DictVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

import audit_snapshots as snapshots

YEARS = (2023, 2024, 2025)
CHAMPION_MIN = 10
MATCHUP_MIN = 20
CHAMPION_C = 0.1  # Fixed before this experiment; no hyperparameter search.
DRAFT_COLS = [
    f"{side}_{role}_champion" for side in ("blue", "red") for role in snapshots.ROLES
]


def draft_features(games):
    """Signed champion-by-role effects and canonical same-role matchup effects.

    Swapping the two drafts negates every feature. Unknown features map to zero
    in the fitted vocabulary; sparse matchups fall back to champion main effects.
    """
    main, matchups = [], []
    for values in games[DRAFT_COLS].itertuples(index=False, name=None):
        champions = dict(zip(DRAFT_COLS, values))
        own, pairs = {}, {}
        for role in snapshots.ROLES:
            blue, red = (
                champions[f"blue_{role}_champion"],
                champions[f"red_{role}_champion"],
            )
            for champ, sign in ((blue, 1), (red, -1)):
                key = f"champion/{role}/{champ}"
                own[key] = own.get(key, 0) + sign
            low, high = sorted((blue, red))
            if low != high:
                pairs[f"matchup/{role}/{low}/{high}"] = 1 if blue == low else -1
        main.append({k: v for k, v in own.items() if v})
        matchups.append(pairs)
    return main, matchups


class DraftEncoder:
    """Learn occurrence cutoffs and feature vocabulary from training games only."""

    def __init__(self, matchups=False):
        self.matchups = matchups
        self.allowed = set()
        self.vectorizer = DictVectorizer(sparse=True)

    def fit(self, games):
        main, pairs = draft_features(games)
        counts = Counter(k for row in main for k in row)
        self.allowed = {k for k, count in counts.items() if count >= CHAMPION_MIN}
        if self.matchups:
            counts = Counter(k for row in pairs for k in row)
            self.allowed.update(
                k for k, count in counts.items() if count >= MATCHUP_MIN
            )
        self.vectorizer.fit(self.rows(main, pairs))
        return self

    def rows(self, main, pairs):
        return [
            {k: v for k, v in {**a, **b}.items() if k in self.allowed}
            for a, b in zip(main, pairs)
        ]

    def transform(self, games):
        return self.vectorizer.transform(self.rows(*draft_features(games)))


class InteractionEncoder:
    """Signed champion-specific responses to ahead/behind game-state gaps.

    Divide gaps by training std without centering: zero remains an even state.
    Each champion contributes its own ahead or behind slope, with red-side
    contributions subtracted. Swapping drafts and negating gaps reverses features.
    """

    MIN_SUPPORT = 20

    def __init__(self, lane_stats=False):
        self.lane_stats = lane_stats
        self.main = DraftEncoder()
        self.allowed = set()
        self.scales = {}
        self.vectorizer = DictVectorizer(sparse=True)

    def fit(self, games):
        self.main.fit(games)
        columns = ["total_gold"]
        if self.lane_stats:
            columns += [
                f"{role}_{stat}"
                for role in snapshots.ROLES
                for stat in ("gold", "xp", "cs", "kills")
            ]
        self.scales = {col: float(games[col].std(ddof=0)) or 1.0 for col in columns}
        rows = self.rows(games, restrict=False)
        counts = Counter(
            key
            for row in rows
            for key, value in row.items()
            if key.startswith("interaction/") and value != 0
        )
        self.allowed = set(self.main.allowed)
        self.allowed.update(
            key for key, count in counts.items() if count >= self.MIN_SUPPORT
        )
        self.vectorizer.fit(self.rows(games))
        return self

    def rows(self, games, restrict=True):
        main, _ = draft_features(games)
        rows = []
        for own, (_, game) in zip(main, games.iterrows()):
            row = dict(own)
            for role in snapshots.ROLES:
                fields = ["total_gold"]
                if self.lane_stats:
                    fields += [
                        f"{role}_{stat}" for stat in ("gold", "xp", "cs", "kills")
                    ]
                for side, sign in (("blue", 1), ("red", -1)):
                    champion = game[f"{side}_{role}_champion"]
                    for col in fields:
                        gap = float(game[col]) / self.scales[col]
                        if gap == 0:
                            continue
                        state = "ahead" if sign * gap > 0 else "behind"
                        key = f"interaction/{role}/{champion}/{col}/{state}"
                        row[key] = row.get(key, 0) + gap
            rows.append(
                {
                    key: value
                    for key, value in row.items()
                    if not restrict or key in self.allowed
                }
            )
        return rows

    def transform(self, games):
        return self.vectorizer.transform(self.rows(games))


def control_for(variant):
    if variant in ("gold_interactions", "state_interactions"):
        return "champions"
    return "stats" if variant == "stats" else "stats_shrunk"


def fit_predict(train, calibration, test, columns, variant):
    scaler = StandardScaler().fit(train[columns])
    inputs = [scaler.transform(part[columns]) for part in (train, calibration, test)]
    encoder = None
    if variant not in ("stats", "stats_shrunk"):
        if variant in ("gold_interactions", "state_interactions"):
            encoder = InteractionEncoder(
                lane_stats=variant == "state_interactions"
            ).fit(train)
        else:
            encoder = DraftEncoder(matchups=variant == "matchups").fit(train)
        inputs = [
            sparse.hstack(
                [sparse.csr_matrix(values), encoder.transform(part)], format="csr"
            )
            for values, part in zip(inputs, (train, calibration, test))
        ]
    model = LogisticRegression(C=1 if variant == "stats" else CHAMPION_C, max_iter=3000)
    model.fit(inputs[0], train.won)
    calibrator = LogisticRegression(C=1e6, max_iter=2000)
    calibrator.fit(model.decision_function(inputs[1]).reshape(-1, 1), calibration.won)
    raw = model.predict_proba(inputs[2])[:, 1]
    p = calibrator.predict_proba(model.decision_function(inputs[2]).reshape(-1, 1))[
        :, 1
    ]
    parameters = {
        "numeric_columns": columns,
        "scaler_mean": scaler.mean_.tolist(),
        "scaler_std": scaler.scale_.tolist(),
        "coef": model.coef_[0].tolist(),
        "intercept": float(model.intercept_[0]),
        "C": model.C,
        "draft_columns": (
            encoder.vectorizer.get_feature_names_out().tolist() if encoder else []
        ),
        "calibration_slope": float(calibrator.coef_[0, 0]),
        "calibration_intercept": float(calibrator.intercept_[0]),
    }
    if isinstance(encoder, InteractionEncoder):
        parameters["interaction_scales"] = encoder.scales
        parameters["interaction_min_support"] = encoder.MIN_SUPPORT
    return p, raw, parameters


def evaluate(frames, variants=("stats", "stats_shrunk", "champions", "matchups")):
    metrics, predictions, parameters, coverage = [], [], [], []
    for minute, frame in frames.items():
        cohort = frame[
            frame.valid_roster
            & frame.league.isin(snapshots.LEAGUES)
            & frame.gamelength.gt(minute * 60)
            & frame[snapshots.FEATURES["aura_features"]].notna().all(axis=1)
        ]
        # Do not inspect or score 2026. Older folds are exploratory because their
        # outcomes have already been examined in the first baseline experiment.
        cohort = cohort[cohort.year.le(max(YEARS))]
        complete = cohort[DRAFT_COLS].notna().all(axis=1) & cohort[DRAFT_COLS].ne(
            ""
        ).all(axis=1)
        for year, games in cohort.groupby("year"):
            coverage.append(
                {
                    "minute": minute,
                    "year": year,
                    "snapshot_complete": len(games),
                    "draft_complete": int(complete.loc[games.index].sum()),
                }
            )
        cohort = cohort[complete]
        for year in YEARS:
            train, calibration, test = snapshots.temporal_split(cohort, year)
            if min(len(train), len(calibration), len(test)) < 100:
                continue
            y = test.won.to_numpy(dtype=int)
            print(
                f"Champions {minute}m/{year}: {len(train)} train, {len(calibration)} calibrate, {len(test)} evaluate",
                flush=True,
            )
            for base in ("gold", "aura_features"):
                columns = snapshots.FEATURES[base]
                probabilities = {}
                for variant in variants:
                    if base == "gold" and variant == "state_interactions":
                        continue
                    p, raw, fitted = fit_predict(
                        train, calibration, test, columns, variant
                    )
                    probabilities[variant] = p
                    original = probabilities["stats"]
                    reference = probabilities[control_for(variant)]
                    delta = snapshots.losses(y, p) - snapshots.losses(y, reference)
                    clusters = test.league + "/" + test.date.dt.strftime("%Y-%m-%d")
                    low, high = snapshots.clustered_interval(delta, clusters)
                    metrics.append(
                        {
                            "minute": minute,
                            "year": year,
                            "base": base,
                            "variant": variant,
                            **snapshots.scores(y, p),
                            "raw_log_loss": snapshots.scores(y, raw)["log_loss"],
                            "control": control_for(variant),
                            "delta_original": float(
                                (
                                    snapshots.losses(y, p)
                                    - snapshots.losses(y, original)
                                ).mean()
                            ),
                            "delta_base": float(delta.mean()),
                            "delta_low": low,
                            "delta_high": high,
                            "draft_features": len(fitted["draft_columns"]),
                            "interaction_features": sum(
                                col.startswith("interaction/")
                                for col in fitted["draft_columns"]
                            ),
                        }
                    )
                    pred = test[["date", "league", "won"]].copy().reset_index()
                    pred["minute"], pred["year"], pred["base"], pred["variant"] = (
                        minute,
                        year,
                        base,
                        variant,
                    )
                    pred["probability"], pred["raw_probability"] = p, raw
                    predictions.append(pred)
                    parameters.append(
                        {
                            "minute": minute,
                            "year": year,
                            "base": base,
                            "variant": variant,
                            "train_years": [year - 4, year - 2],
                            "calibration_year": year - 1,
                            "train_n": len(train),
                            "calibration_n": len(calibration),
                            **fitted,
                        }
                    )
    if not predictions:
        raise ValueError("Insufficient historical snapshot/draft coverage")
    return (
        pd.DataFrame(metrics),
        pd.concat(predictions, ignore_index=True),
        parameters,
        pd.DataFrame(coverage),
    )


def pooled_scores(predictions):
    rows = []
    for (minute, base), group in predictions.groupby(["minute", "base"]):
        original = group[group.variant.eq("stats")].set_index("gameid")
        for variant, games in group.groupby("variant"):
            control_name = control_for(variant)
            baseline = (
                group[group.variant.eq(control_name)]
                .set_index("gameid")
                .loc[original.index]
            )
            games = games.set_index("gameid").loc[original.index]
            y, p = games.won.to_numpy(), games.probability.to_numpy()
            delta = snapshots.losses(y, p) - snapshots.losses(
                y, baseline.probability.to_numpy()
            )
            low, high = snapshots.clustered_interval(
                delta, games.league + "/" + games.date.dt.strftime("%Y-%m-%d")
            )
            rows.append(
                {
                    "minute": minute,
                    "base": base,
                    "variant": variant,
                    **snapshots.scores(y, p),
                    "control": control_name,
                    "delta_original": float(
                        (
                            snapshots.losses(y, p)
                            - snapshots.losses(y, original.probability.to_numpy())
                        ).mean()
                    ),
                    "delta_base": float(delta.mean()),
                    "delta_low": low,
                    "delta_high": high,
                }
            )
    return pd.DataFrame(rows)


def report(metrics, pooled, coverage):
    candidates = pooled[pooled.variant.isin(["champions", "matchups"])]
    clear_gains = candidates[candidates.delta_high.lt(0)]
    conclusion = (
        "No champion or matchup variant has a pooled log-loss improvement whose paired 95% interval "
        "excludes zero. Keep the stats-only model as the benchmark; these results do not justify adopting "
        "the champion variants."
        if clear_gains.empty
        else "Some exploratory comparisons have intervals below zero; inspect annual consistency and "
        "confirm a frozen design on a new period before adoption."
    )
    return "\n".join(
        [
            "# Champion and lane-matchup experiment",
            "",
            "Exploratory only: evaluated on 2023–2025 chronological folds. The already-viewed 2026 baseline "
            "holdout is excluded from champion model selection and scoring. Confirm any candidate on a new period.",
            "",
            "## Finding",
            "",
            conclusion,
            "",
            "## How champions enter the model",
            "",
            "Each role has a champion effect, entered +1 for blue and −1 for red. These ten champion identities "
            "produce an additive team-composition score. The matchup variant adds signed, same-role champion-pair "
            "effects beyond those main effects. For example, top-lane Aatrox against Ornn has a different residual "
            "effect from either champion alone. Swapping drafts reverses every feature. Mirror matchups cancel.",
            "",
            "Champion-role effects need at least 10 training occurrences; exact lane matchups need at least 20. "
            "Cutoffs and feature vocabularies use training only. Unseen/sparse matchups fall back to main effects; "
            "unseen champions have zero learned draft effect and rely on game-state stats. Stronger ridge regularization "
            "(C=0.1 for champion models) is fixed in advance. A stats-only C=0.1 control separates feature additions "
            "from a change in regularization; the original C=1 baseline is also retained.",
            "",
            "Models are separate at 10/15/20 minutes, allowing champion effects to differ by game stage. This first "
            "experiment does not model champion×gold interactions, arbitrary five-champion synergies, player identity, "
            "pregame team strength, or patch-specific effects. An additive composition score is not a full composition model.",
            "",
            "## Evaluation",
            "",
            "Compare gold-only and AURA-feature baselines with champion and champion+matchup variants on identical "
            "complete-snapshot/draft cohorts. Each fold trains on three older calendar years, fits a sigmoid calibrator "
            "on the next year, and evaluates the following year. Numeric scaling and draft encoding see training only. "
            "Log loss and Brier judge probabilities; accuracy and ten-bin ECE are diagnostics. Paired 95% intervals "
            "resample league/day clusters (2,000 draws, seed 42), approximating series grouping. Intervals are not "
            "adjusted for multiple comparisons. These older folds have already been viewed; they are development evidence.",
            "",
            "## Pooled development results",
            "",
            "Negative delta_base means lower log loss than the indicated same-regularization control. "
            "delta_original compares with the original C=1 stats-only model.",
            "",
            snapshots.table(pooled),
            "",
            "## Annual results",
            "",
            snapshots.table(metrics),
            "",
            "## Cohort coverage",
            "",
            snapshots.table(coverage),
            "",
            "## Next decision",
            "",
            "Prefer a consistent log-loss improvement across years and minutes, rather than the best isolated row. "
            "An inconclusive or worse result is a reason to keep the simpler model. Exact champion pairs are sparse "
            "and the meta changes with patches; adding more interactions is not automatically an improvement. "
            "Any selected design must be frozen before collecting/evaluating new matches. There is no fresh untouched "
            "champion holdout in this report and no synchronized market-price or profitability evaluation.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("docs/champion_report.md"))
    parser.add_argument(
        "--artifacts", type=Path, default=Path("data/champion_experiment")
    )
    args = parser.parse_args()
    frames, manifest = snapshots.load_raw(args.raw_dir)
    metrics, predictions, parameters, coverage = evaluate(frames)
    pooled = pooled_scores(predictions)
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
            "purpose": "exploratory development; 2026 excluded",
            "years": YEARS,
            "champion_min": CHAMPION_MIN,
            "matchup_min": MATCHUP_MIN,
            "models": parameters,
        }
    )
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(metrics, pooled, coverage))
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
