"""Fixed full-corpus retrospective benchmark and live-input diagnostics."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

import audit_snapshots as audit
import evaluate_gol_objectives as original
import numpy as np
import pandas as pd
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

VARIANTS = {
    "constant_prior": [],
    "elo": ["elo_gap"],
    "gold": ["gold_gap"],
    "gold_elo": original.BASE,
    "scoreboard_objectives": original.BASE + ["tower_gap", "dragon_gap"],
    "all_objectives": original.BASE + original.OBJECTIVES,
}


def temporal_split(frame, year):
    parts = [
        frame[frame.year.lt(year - 1)].copy(),
        frame[frame.year.eq(year - 1)].copy(),
        frame[frame.year.eq(year)].copy(),
    ]
    groups = [set(p.series_first_id) for p in parts]
    if any(groups[a] & groups[b] for a, b in [(0, 1), (0, 2), (1, 2)]):
        raise ValueError("Series straddles chronological splits")
    if any(len(p) < 75 or p.won.nunique() != 2 for p in parts):
        raise ValueError("Insufficient chronological partition")
    return parts


def clusters(frame):
    return frame.league.astype(str) + "/" + frame.series_first_id.astype(str)


def interval(values, group, repetitions=2000):
    if pd.Series(group).nunique() < 2:
        return float("nan"), float("nan")
    return tuple(float(v) for v in audit.clustered_interval(values, group, repetitions))


def ece(y, p, bins):
    assignments = np.minimum((p * bins).astype(int), bins - 1)
    return float(
        sum(
            np.mean(assignments == b)
            * abs(p[assignments == b].mean() - y[assignments == b].mean())
            for b in range(bins)
            if np.any(assignments == b)
        )
    )


def diagnostic_scores(y, p, prior):
    y, p = np.asarray(y), np.asarray(p)
    picked = p >= 0.5
    confidence = np.maximum(p, 1 - p)
    calibration_intercept = calibration_slope = float("nan")
    if np.ptp(p) > 1e-8 and len(np.unique(y)) == 2:
        # TEST-only diagnostic; never used to recalibrate these predictions.
        diagnostic = LogisticRegression(C=1e6, max_iter=3000).fit(
            logit(np.clip(p, 1e-8, 1 - 1e-8)).reshape(-1, 1), y
        )
        calibration_intercept = float(diagnostic.intercept_[0])
        calibration_slope = float(diagnostic.coef_[0, 0])
    baseline_brier = np.mean((prior - y) ** 2)
    result = {
        **audit.scores(y, p),
        "roc_auc": float(roc_auc_score(y, p)),
        "average_precision_blue": float(average_precision_score(y, p)),
        "balanced_accuracy": float(balanced_accuracy_score(y, picked)),
        "mcc": float(matthews_corrcoef(y, picked)),
        "precision_blue": float(precision_score(y, picked, zero_division=0)),
        "recall_blue": float(recall_score(y, picked, zero_division=0)),
        "brier_skill_prior": float(1 - np.mean((p - y) ** 2) / baseline_brier),
        "ece5": ece(y, p, 5),
        "ece15": ece(y, p, 15),
        "blue_win_rate": float(y.mean()),
        "mean_blue_probability": float(p.mean()),
        "calibration_bias": float(p.mean() - y.mean()),
        "diagnostic_calibration_intercept": calibration_intercept,
        "diagnostic_calibration_slope": calibration_slope,
        "sharpness_std": float(p.std()),
        "mean_favourite_confidence": float(confidence.mean()),
        "favourite_calibration_gap": float(confidence.mean() - (picked == y).mean()),
    }
    for cutoff in [0.8, 0.9]:
        mask = confidence >= cutoff
        result[f"confidence_{int(cutoff * 100)}_n"] = int(mask.sum())
        result[f"confidence_{int(cutoff * 100)}_accuracy"] = (
            float(np.mean(picked[mask] == y[mask])) if mask.any() else float("nan")
        )
        result[f"confidence_{int(cutoff * 100)}_wrong"] = int(
            np.sum(mask & (picked != y))
        )
    return result


def predict(parameters, frame, calibrated=True):
    if not parameters["numeric_columns"]:
        return np.full(len(frame), parameters["prior"])
    values = frame[parameters["numeric_columns"]].to_numpy(dtype=float)
    z = (
        (values - np.asarray(parameters["scaler_mean"]))
        / np.asarray(parameters["scaler_std"])
    ) @ np.asarray(parameters["coef"]) + parameters["intercept"]
    if calibrated:
        z = z * parameters["calibration_slope"] + parameters["calibration_intercept"]
    return expit(z)


def bin_rows(frame, p, favourite=False, repetitions=2000):
    y = frame.won.to_numpy()
    values = np.maximum(p, 1 - p) if favourite else p
    target = (p >= 0.5) == y if favourite else y
    bins = np.minimum((values * 10).astype(int), 9)
    rows = []
    for b in range(5 if favourite else 0, 10):
        mask = bins == b
        if not mask.any():
            continue
        low, high = interval(target[mask], clusters(frame)[mask], repetitions)
        rows.append(
            {
                "bin": f"{b / 10:.1f}–{(b + 1) / 10:.1f}",
                "n": int(mask.sum()),
                "series": int(clusters(frame)[mask].nunique()),
                "predicted": float(values[mask].mean()),
                "observed": float(target[mask].mean()),
                "gap": float(values[mask].mean() - target[mask].mean()),
                "low": low,
                "high": high,
            }
        )
    return rows


def paired_rows(frame, probabilities, year, minute, repetitions):
    rows = []
    for name, reference in [
        ("gold_elo", "gold"),
        ("gold_elo", "elo"),
        ("scoreboard_objectives", "gold_elo"),
        ("all_objectives", "gold_elo"),
        ("all_objectives", "scoreboard_objectives"),
    ]:
        p, q = probabilities[name], probabilities[reference]
        y = frame.won.to_numpy()
        deltas = {
            "log_loss": audit.losses(y, p) - audit.losses(y, q),
            "brier": (p - y) ** 2 - (q - y) ** 2,
            "accuracy": ((p >= 0.5) == y).astype(float)
            - ((q >= 0.5) == y).astype(float),
        }
        for metric, delta in deltas.items():
            low, high = interval(delta, clusters(frame), repetitions)
            rows.append(
                {
                    "year": year,
                    "minute": minute,
                    "variant": name,
                    "reference": reference,
                    "metric": metric,
                    "n": len(frame),
                    "series": int(clusters(frame).nunique()),
                    "delta": float(delta.mean()),
                    "low": low,
                    "high": high,
                }
            )
    return rows


def stress_rows(test, params, p, year, minute, variant):
    rows = []
    cases = {}
    for unit in [100, 500, 1000]:
        part = test.copy()
        part["gold_gap"] = (
            np.round(part.blue_gold / unit) * unit
            - np.round(part.red_gold / unit) * unit
        )
        cases[f"round_each_gold_{unit}"] = part
    for column in params["numeric_columns"]:
        if column in original.OBJECTIVES:
            for direction in [-1, 1]:
                part = test.copy()
                part[column] += direction
                cases[f"misread_{column}_{direction:+d}"] = part
    for name, part in cases.items():
        changed = predict(params, part)
        shift = np.abs(changed - p)
        rows.append(
            {
                "year": year,
                "minute": minute,
                "variant": variant,
                "scenario": name,
                "mean_probability_shift": float(shift.mean()),
                "p95_probability_shift": float(np.quantile(shift, 0.95)),
                "max_probability_shift": float(shift.max()),
                "log_loss": float(audit.losses(test.won.to_numpy(), changed).mean()),
                "log_loss_delta": float(
                    (
                        audit.losses(test.won.to_numpy(), changed)
                        - audit.losses(test.won.to_numpy(), p)
                    ).mean()
                ),
            }
        )
    return rows


def evaluate(frame, repetitions=2000, years=(2024, 2025)):
    rows = {
        name: []
        for name in [
            "metrics",
            "predictions",
            "paired",
            "reliability",
            "confidence",
            "subgroups",
            "stress",
            "learning_curves",
            "coefficients",
        ]
    }
    parameters = []
    for year in years:
        for minute in [10, 15, 20]:
            cohort = frame[frame.minute.eq(minute)].sort_values(["date", "oe_gameid"])
            train, cal, test = temporal_split(cohort, year)
            prior = float(cal.won.mean())
            probabilities = {}
            print(
                f"Full corpus {year}/{minute}m: {len(train)} train / {len(cal)} calibrate / {len(test)} test",
                flush=True,
            )
            for name, desired in VARIANTS.items():
                columns = original.columns_for(train, desired)
                if not desired:
                    p = raw = np.full(len(test), prior)
                    params = {"numeric_columns": [], "prior": prior}
                else:
                    p, raw, params = original.champions.fit_predict(
                        train, cal, test, columns, "stats"
                    )
                metadata = {"year": year, "minute": minute, "variant": name}
                params = {
                    **metadata,
                    "omitted_constant_columns": [
                        c for c in desired if c not in columns
                    ],
                    **params,
                }
                assert np.allclose(p, predict(params, test), atol=1e-12, rtol=0)
                parameters.append(params)
                probabilities[name] = p
                metric = {
                    **metadata,
                    "train_games": len(train),
                    "calibration_games": len(cal),
                    "series": int(clusters(test).nunique()),
                    **diagnostic_scores(test.won.to_numpy(), p, prior),
                }
                for key, values in {
                    "log_loss": audit.losses(test.won.to_numpy(), p),
                    "brier": (p - test.won.to_numpy()) ** 2,
                    "accuracy": ((p >= 0.5) == test.won.to_numpy()).astype(float),
                }.items():
                    metric[f"{key}_low"], metric[f"{key}_high"] = interval(
                        values, clusters(test), repetitions
                    )
                raw_scores = diagnostic_scores(test.won.to_numpy(), raw, prior)
                metric.update({f"raw_{k}": v for k, v in raw_scores.items()})
                rows["metrics"].append(metric)
                prediction = test[
                    [
                        "oe_gameid",
                        "gol_id",
                        "date",
                        "league",
                        "series_first_id",
                        "won",
                        "gold_gap",
                        "elo_gap",
                    ]
                ].copy()
                prediction["probability"], prediction["raw_probability"] = p, raw
                for k, v in metadata.items():
                    prediction[k] = v
                rows["predictions"].extend(prediction.to_dict("records"))
                if name in ("gold_elo", "scoreboard_objectives", "all_objectives"):
                    for output, favourite in [
                        ("reliability", False),
                        ("confidence", True),
                    ]:
                        rows[output].extend(
                            {**metadata, **r}
                            for r in bin_rows(test, p, favourite, repetitions)
                        )
                    subgroup = test.assign(probability=p)
                    subgroup["gold_state"] = pd.cut(
                        subgroup.gold_gap.abs(),
                        [-1, 1000, 3000, 6000, np.inf],
                        labels=["0–1k", "1–3k", "3–6k", "6k+"],
                    )
                    subgroup["elo_gold_agreement"] = np.where(
                        subgroup.gold_gap * subgroup.elo_gap < 0,
                        "disagree",
                        "agree_or_tie",
                    )
                    for category in ["league", "gold_state", "elo_gold_agreement"]:
                        for value, part in subgroup.groupby(category, observed=True):
                            rows["subgroups"].append(
                                {
                                    **metadata,
                                    "category": category,
                                    "value": str(value),
                                    **diagnostic_scores(
                                        part.won.to_numpy(),
                                        part.probability.to_numpy(),
                                        prior,
                                    ),
                                }
                                if part.won.nunique() == 2
                                else {
                                    **metadata,
                                    "category": category,
                                    "value": str(value),
                                    **audit.scores(
                                        part.won.to_numpy(), part.probability.to_numpy()
                                    ),
                                }
                            )
                    rows["stress"].extend(
                        stress_rows(test, params, p, year, minute, name)
                    )
                    for c, coefficient, scale in zip(
                        columns, params["coef"], params["scaler_std"]
                    ):
                        unit = (
                            1000 if c == "gold_gap" else (100 if c == "elo_gap" else 1)
                        )
                        rows["coefficients"].append(
                            {
                                **metadata,
                                "feature": c,
                                "unit": unit,
                                "standardized_coefficient": coefficient,
                                "calibrated_log_odds_per_unit": coefficient
                                / scale
                                * params["calibration_slope"]
                                * unit,
                                "conditional_odds_ratio_per_unit": float(
                                    np.exp(
                                        coefficient
                                        / scale
                                        * params["calibration_slope"]
                                        * unit
                                    )
                                ),
                            }
                        )
                if name in ("gold_elo", "scoreboard_objectives", "all_objectives"):
                    for size in sorted(
                        set(
                            [
                                v
                                for v in [100, 200, 400, 600, 800, len(train)]
                                if v <= len(train)
                            ]
                        )
                    ):
                        prefix = train.iloc[:size]
                        if prefix.won.nunique() != 2:
                            continue
                        cols = original.columns_for(prefix, desired)
                        fitted = make_pipeline(
                            StandardScaler(), LogisticRegression(C=1, max_iter=3000)
                        ).fit(prefix[cols], prefix.won)
                        q = fitted.predict_proba(cal[cols])[:, 1]
                        rows["learning_curves"].append(
                            {
                                **metadata,
                                "training_games": size,
                                "development_games": len(cal),
                                "raw_development_log_loss": float(
                                    audit.losses(cal.won.to_numpy(), q).mean()
                                ),
                            }
                        )
            rows["paired"].extend(
                paired_rows(test, probabilities, year, minute, repetitions)
            )
    return {k: pd.DataFrame(v) for k, v in rows.items()}, parameters


def frozen_confirmation(frame, directory, repetitions=2000):
    old_pred = pd.read_csv(directory / "predictions.csv")
    old_models = json.loads((directory / "fitted_models.json").read_text())
    seen = set(old_pred.series_first_id)
    rows = []
    for minute in [10, 15, 20]:
        test = frame[
            frame.year.eq(2025)
            & frame.minute.eq(minute)
            & ~frame.series_first_id.isin(seen)
        ]
        if len(test) == 0:
            continue
        probabilities = {}
        for variant, name in [
            ("gold_elo", "gold_elo"),
            ("gold_elo_objectives", "all_objectives"),
        ]:
            params = next(
                m
                for m in old_models
                if m["minute"] == minute and m["variant"] == variant
            )
            probabilities[name] = predict(params, test)
        y = test.won.to_numpy()
        delta = audit.losses(y, probabilities["all_objectives"]) - audit.losses(
            y, probabilities["gold_elo"]
        )
        low, high = interval(delta, clusters(test), repetitions)
        rows.append(
            {
                "minute": minute,
                "n": len(test),
                "series": int(clusters(test).nunique()),
                "control_log_loss": float(
                    audit.losses(y, probabilities["gold_elo"]).mean()
                ),
                "objective_log_loss": float(
                    audit.losses(y, probabilities["all_objectives"]).mean()
                ),
                "delta": float(delta.mean()),
                "low": low,
                "high": high,
            }
        )
    return pd.DataFrame(rows)


def report(frames, manifest):
    metrics, paired = frames["metrics"], frames["paired"]
    primary = paired.query(
        "year==2025 and minute==15 and variant=='all_objectives' and reference=='gold_elo' and metric=='log_loss'"
    ).iloc[0]
    verdict = "inconclusive"
    if primary.high < 0:
        verdict = "supports improved probability accuracy"
    if primary.low > 0:
        verdict = "supports worse probability accuracy"
    main = metrics[metrics.year.eq(2025)]
    calibration = main[
        main.variant.isin(["gold_elo", "scoreboard_objectives", "all_objectives"])
    ]
    annual = metrics[
        metrics.variant.isin(["gold_elo", "scoreboard_objectives", "all_objectives"])
    ]
    table = audit.table
    return f"""# Completed-corpus win probability evaluation

The primary 15-minute objective comparison {verdict} on this retrospective cohort: added-minus-gold+Elo log loss {primary.delta:+.5f}, paired series-bootstrap 95% interval [{primary.low:+.5f}, {primary.high:+.5f}]. This evaluates map winners, not series contracts or profitability.

## Data and fixed protocol

{manifest["games"]} verified games / {manifest["rows"]} checkpoint rows, selected LCK/LCS/LEC/Worlds events in 2022–2025. LPL and 2026 excluded. Train 2022–2023 / calibrate 2024 / test 2025 is primary. Train 2022 / calibrate 2023 / test 2024 is a secondary temporal stability check. Same games for every variant within a fold/minute; separate models at 10/15/20m, no pooling correlated checkpoints as independent games. Explicit series cannot cross partitions. Logistic C=1, training-only scaling, separate-year sigmoid C=1e6; fixed before scoring, no search or post-score recalibration. Constant baseline uses prior calibration-year blue win rate. 2,000 series-cluster bootstrap draws, seed 42, conditional on fitted models and this selected population.

Primary endpoint: calibrated 2025 15m all-objectives vs gold+Elo log loss. All other metrics, comparisons, subgroups and stress tests are descriptive/secondary; no multiple-testing-based model selection. 2025/2026 outcomes were viewed in earlier research, so these periods are not untouched prospective holdouts.

Scoreboard-objectives uses gold/Elo/tower/elemental-dragon gaps. All-objectives additionally requests Herald/Elder/Baron/grubs/Atakhan gaps; training-constant columns are omitted and recorded. Thus old-year training cannot learn grubs/Atakhan and Baron/Elder have no meaningful pre-20m examples. The live pilot must establish which counters are recoverable; absence in a frame cannot be assumed zero.

## Primary 2025 performance

Lower log loss/Brier/ECE is better; higher AUC/accuracy is better. Brier skill compares with the past-year constant prior. AUC measures ranking, not calibration or profit.

{table(main[["minute", "variant", "train_games", "calibration_games", "n", "series", "log_loss", "brier", "roc_auc", "accuracy", "balanced_accuracy", "mcc", "brier_skill_prior", "ece10"]])}

## Paired improvements and uncertainty

Deltas are added-minus-reference: negative is better for loss/Brier, positive for accuracy. Resampling whole series keeps maps correlated. These intervals do not include model-training uncertainty or unobserved selection/patch shifts.

{table(paired[(paired.year.eq(2025)) & paired.metric.eq("log_loss")][["minute", "variant", "reference", "n", "series", "delta", "low", "high"]])}

Absolute log-loss/Brier/accuracy intervals and paired Brier/accuracy intervals are in metrics.csv and paired.csv. All individual predictions and model parameters are exported for inspection.

## Calibration and raw probabilities

Diagnostic calibration slope ideal=1, intercept ideal=0; they are estimated on evaluation outcomes only for diagnosis and never applied to predictions. A slope below 1 suggests overly extreme scores. Positive bias means blue win probabilities exceed blue win frequency. ECE depends on bins and sample size; it is not a guaranteed pointwise error bound.

{table(calibration[["minute", "variant", "raw_log_loss", "log_loss", "raw_brier", "brier", "ece5", "ece10", "ece15", "calibration_bias", "diagnostic_calibration_intercept", "diagnostic_calibration_slope", "sharpness_std"]])}

## Temporal stability

{table(annual[["year", "minute", "variant", "n", "log_loss", "raw_log_loss", "brier", "accuracy", "ece10"]])}

Expanding chronological training-prefix learning curves use RAW predictions on the earlier calibration year, never fitting a calibrator to those curve scores. See learning_curves.csv. They are not tuning runs against 2025.

## LCS/LTA and other leagues

Small slices can move substantially with a few games; per-league point estimates are descriptive. Additional gold-state and Elo-versus-gold-disagreement slices are in subgroups.csv.

{table(frames["subgroups"].query("year==2025 and category=='league'")[["minute", "variant", "value", "n", "log_loss", "brier", "roc_auc", "accuracy", "ece10"]])}

## Confidence versus actual wins

Favourite confidence bins use the team the model favours; observed is how often that team wins. Intervals resample series within each bin, conditional on bin membership. Very small bins are weak evidence.

{table(frames["confidence"].query("year==2025 and minute==15 and variant=='all_objectives'")[["bin", "n", "series", "predicted", "observed", "gap", "low", "high"]])}

Reliability bins for BLUE probabilities at every checkpoint/model are in reliability.csv; confidence.csv contains all favourite bins. Metrics include counts, wrong calls and accuracy above 80%/90% confidence, mean confidence gap, precision/recall and average precision (blue-positive).

## Fixed old model on newly acquired series

The original 1,031-game experiment stays frozen. This check applies those exact saved weights/calibrators to newly acquired 2025 series, excluding every series in its original scored predictions. No refitting. This is a small retrospective extension, not a pristine new season; it complements the full-corpus refit.

{table(frames["frozen_confirmation"])}

## Broadcast input robustness

Hypothetical rounding/error scenarios use the SAME fitted models and current checkpoint state. These are not measured OCR errors or full latency simulations; no missing objective is imputed zero. Delay can change gold/objectives and market quotes, which this static dataset cannot fully quantify.

{table(frames["stress"].query("year==2025 and variant=='all_objectives'")[["minute", "scenario", "mean_probability_shift", "p95_probability_shift", "max_probability_shift", "log_loss_delta"]])}

Probability shifts are fractions (0.01 = 1 percentage point). Coefficients and conditional odds ratios are in coefficients.csv; correlated gold/objectives mean negative conditional coefficients do not prove an objective is harmful. No isolated objective attribution is claimed.

## What this establishes and what remains

The benchmark can support a live-data paper-prediction pilot if objectives improve on the same games with adequate calibration and robustness. Current limitations remain selected-event/name/roster exclusions, patch changes, no independent broadcast verification of every historical objective time, small league/confidence slices and previously viewed periods. A sigmoid fitted on 2024 does not guarantee 2026 calibration. All current-game inputs must be available when the system receives them; final totals are validation-only, winner labels/identity/date are not numeric predictors.

Profitability, ROI, market-relative incremental information and executable edge remain UNMEASURED: there are no synchronized in-game executable quotes, bid/ask spreads, depth, fees or broadcast receipt-delay records in this dataset. Map probabilities cannot be substituted for series probabilities. Automatic LCS/LTA extraction still needs labelled real frames, replay/overlay rejection, side/game identity, observable counters, rounding and latency measurements. Then freeze a pilot model and assess prospective paper predictions with synchronized quotes.

## Reproduction

Run `.venv/bin/python scripts/research/evaluate_gol_full.py`. First run freezes exact inputs, numeric parameters, predictions, source/helper hashes, diagnostics and plots under data/gol_full_evaluation/. Same-directory reruns are refused. Original experiment is never overwritten. Inspect diagnostics.png for calibration and the paired loss comparison. No published metric, DB or site changes.
"""


def plots(frames, path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for j, minute in enumerate([10, 15, 20]):
        ax = axes[0, j]
        ax.plot([0, 1], [0, 1], color="gray", linestyle="--")
        for name in ["gold_elo", "scoreboard_objectives", "all_objectives"]:
            data = frames["reliability"].query(
                "year==2025 and minute==@minute and variant==@name"
            )
            ax.plot(data.predicted, data.observed, marker="o", label=name)
        ax.set(
            title=f"{minute}m reliability (2025)",
            xlabel="Predicted blue win chance",
            ylabel="Observed blue win rate",
            xlim=(0, 1),
            ylim=(0, 1),
        )
        ax.legend(fontsize=7)
        data = frames["paired"].query(
            "year==2025 and minute==@minute and reference=='gold_elo' and metric=='log_loss'"
        )
        ax = axes[1, j]
        ax.errorbar(
            data.delta,
            range(len(data)),
            xerr=np.array([data.delta - data.low, data.high - data.delta]),
            fmt="o",
            capsize=4,
        )
        ax.axvline(0, color="gray", linestyle="--")
        ax.set_yticks(range(len(data)), data.variant)
        ax.set(
            title=f"{minute}m paired 95% series interval",
            xlabel="Log-loss difference versus gold+Elo",
        )
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/gol_training/training_dataset.csv")
    )
    parser.add_argument(
        "--samples", type=Path, default=Path("data/gol_training/samples.json")
    )
    parser.add_argument(
        "--artifacts", type=Path, default=Path("data/gol_full_evaluation")
    )
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/gol_full_evaluation_report.md")
    )
    args = parser.parse_args()
    if (args.artifacts / "manifest.json").exists():
        raise ValueError(
            "Experiment already frozen; use a separate directory for an explicitly new experiment"
        )
    frame = original.load_dataset(args.dataset, args.samples)
    frames, models = evaluate(frame)
    frames["frozen_confirmation"] = frozen_confirmation(
        frame, Path("data/gol_objectives")
    )
    args.artifacts.mkdir(parents=True, exist_ok=True)
    snapshot = args.artifacts / "source_snapshot"
    snapshot.mkdir(exist_ok=True)
    for source in [args.dataset, args.samples, args.dataset.parent / "manifest.json"]:
        shutil.copyfile(source, snapshot / source.name)
    for name, values in frames.items():
        values.to_csv(args.artifacts / f"{name}.csv", index=False)
    (args.artifacts / "fitted_models.json").write_text(
        json.dumps(models, indent=2) + "\n"
    )
    sources = [
        args.dataset,
        args.samples,
        args.dataset.parent / "manifest.json",
        Path(__file__),
        Path("scripts/research/evaluate_gol_objectives.py"),
        Path("scripts/research/evaluate_champions.py"),
        Path("scripts/research/audit_snapshots.py"),
        Path("data/gol_objectives/fitted_models.json"),
        Path("data/gol_objectives/predictions.csv"),
    ]
    manifest = {
        "games": int(frame.oe_gameid.nunique()),
        "rows": len(frame),
        "sha256": {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
        "primary": "2025/15m calibrated all_objectives versus gold_elo log loss",
        "folds": {
            "2024": {"train": [2022], "calibrate": 2023},
            "2025": {"train": [2022, 2023], "calibrate": 2024},
        },
        "C": 1,
        "calibration_C": 1e6,
        "bootstrap_repetitions": 2000,
        "bootstrap_seed": 42,
        "variants": VARIANTS,
        "purpose": "retrospective probability benchmark; no market execution or model adoption",
    }
    plots(frames, args.artifacts / "diagnostics.png")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(frames, manifest))
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
