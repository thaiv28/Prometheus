"""Locked exploratory objective ablation; run after >=1,000 verified games."""

import argparse
import hashlib
import json
from pathlib import Path

import audit_snapshots as audit
import evaluate_champions as champions
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

BASE = ["gold_gap", "elo_gap"]
OBJECTIVES = [
    f"{name}_gap"
    for name in ("tower", "dragon", "elder", "baron", "herald", "voidgrubs", "atakhan")
]
VARIANTS = {"gold_elo": BASE, "gold_elo_objectives": BASE + OBJECTIVES}


def load_dataset(path, samples_path, min_games=1000):
    frame = pd.read_csv(path)
    required = [
        "oe_gameid",
        "gol_id",
        "minute",
        "date",
        "year",
        "league",
        "blue_won",
        "training_ready",
        "objective_boundary_events",
        *BASE,
        *OBJECTIVES,
    ]
    if any(c not in frame for c in required):
        raise ValueError("Missing required dataset columns")
    if frame.duplicated(["oe_gameid", "minute"]).any():
        raise ValueError("Duplicate game/checkpoint")
    if (
        not frame.training_ready.eq(True).all()
        or not frame.objective_boundary_events.eq(0).all()
    ):
        raise ValueError("Unverified or boundary rows")
    if not np.isfinite(frame[BASE + OBJECTIVES].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite features")
    frame["date"] = pd.to_datetime(frame.date, utc=True)
    if not frame.year.eq(frame.date.dt.year).all():
        raise ValueError("Calendar year mismatch")
    if not frame.year.between(2022, 2025).all() or frame.league.eq("LPL").any():
        raise ValueError("Out-of-scope year/league")
    if (
        not frame.blue_won.isin([0, 1]).all()
        or not frame.minute.isin([10, 15, 20]).all()
    ):
        raise ValueError("Invalid winner/minute")
    if frame.oe_gameid.nunique() < min_games:
        raise ValueError(
            f"Need {min_games} verified games before exploratory scoring; currently {frame.oe_gameid.nunique()}"
        )
    samples = pd.DataFrame(json.loads(samples_path.read_text()))[
        ["gol_id", "series_first_id"]
    ]
    frame = frame.merge(samples, on="gol_id", how="left", validate="many_to_one")
    if frame.series_first_id.isna().any():
        raise ValueError("Missing explicit series identity")
    frame["won"] = frame.blue_won
    return frame.sort_values(["date", "oe_gameid", "minute"])


def split(frame):
    train = frame[frame.year.isin([2022, 2023])].copy()
    calibration = frame[frame.year.eq(2024)].copy()
    test = frame[frame.year.eq(2025)].copy()
    groups = [set(f.series_first_id) for f in (train, calibration, test)]
    if any(groups[a] & groups[b] for a, b in [(0, 1), (0, 2), (1, 2)]):
        raise ValueError("Series straddles chronological splits")
    for part in [train, calibration, test]:
        if len(part) < 75 or part.won.nunique() != 2:
            raise ValueError("Insufficient games/classes in a chronological partition")
    return train, calibration, test


def columns_for(train, desired):
    # Objective types absent from training years cannot have learned effects.
    return [c for c in desired if train[c].nunique() > 1]


def paired_stats(frame, baseline, added):
    delta = audit.losses(frame.won.to_numpy(), added) - audit.losses(
        frame.won.to_numpy(), baseline
    )
    clusters = frame.league.astype(str) + "/" + frame.series_first_id.astype(str)
    if clusters.nunique() < 2:
        raise ValueError("Need at least two series for a paired uncertainty estimate")
    low, high = audit.clustered_interval(delta, clusters)
    groups = (
        pd.DataFrame({"delta": delta, "cluster": clusters.to_numpy()})
        .groupby("cluster")
        .delta.agg(["sum", "count"])
    )
    k = len(groups)
    n = len(delta)
    mean = float(delta.mean())
    se = (
        float(
            np.sqrt(
                k / (k - 1) * np.square(groups["sum"] - mean * groups["count"]).sum()
            )
            / n
        )
        if k > 1
        else float("nan")
    )
    return {
        "delta": mean,
        "low": float(low),
        "high": float(high),
        "series": k,
        "cluster_se": se,
    }


def evaluate(frame):
    metrics, predictions, parameters, curves, power = [], [], [], [], []
    for minute in [10, 15, 20]:
        cohort = frame[frame.minute.eq(minute)].set_index("oe_gameid", drop=False)
        train, calibration, test = split(cohort)
        fitted = {}
        for name, desired in VARIANTS.items():
            columns = columns_for(train, desired)
            p, raw, params = champions.fit_predict(
                train, calibration, test, columns, "stats"
            )
            fitted[name] = (p, raw)
            parameters.append(
                {
                    "minute": minute,
                    "variant": name,
                    "omitted_constant_training_columns": [
                        c for c in desired if c not in columns
                    ],
                    **params,
                }
            )
            metrics.append(
                {
                    "minute": minute,
                    "variant": name,
                    "train_games": len(train),
                    "calibration_games": len(calibration),
                    "test_games": len(test),
                    **audit.scores(test.won.to_numpy(), p),
                    "raw_log_loss": float(
                        audit.losses(test.won.to_numpy(), raw).mean()
                    ),
                }
            )
            pred = test[
                ["oe_gameid", "gol_id", "date", "league", "series_first_id", "won"]
            ].copy()
            pred["minute"] = minute
            pred["variant"] = name
            pred["probability"] = p
            pred["raw_probability"] = raw
            predictions.extend(pred.reset_index(drop=True).to_dict("records"))
            # Development learning curves: train-only fitting, RAW 2024 scores.
            # Never fit calibration on the same data used to score this curve.
            sizes = sorted(
                set([v for v in [100, 200, 400, 600, len(train)] if v <= len(train)])
            )
            for size in sizes:
                smaller = train.iloc[:size]
                if smaller.won.nunique() < 2:
                    continue
                cols = columns_for(smaller, desired)
                model = make_pipeline(
                    StandardScaler(), LogisticRegression(C=1, max_iter=3000)
                ).fit(smaller[cols], smaller.won)
                q = model.predict_proba(calibration[cols])[:, 1]
                curves.append(
                    {
                        "minute": minute,
                        "variant": name,
                        "training_games": size,
                        "development_games": len(calibration),
                        "raw_development_log_loss": float(
                            audit.losses(calibration.won.to_numpy(), q).mean()
                        ),
                    }
                )
        calibrated = paired_stats(
            test, fitted["gold_elo"][0], fitted["gold_elo_objectives"][0]
        )
        raw = paired_stats(
            test, fitted["gold_elo"][1], fitted["gold_elo_objectives"][1]
        )
        metrics[-1].update(
            {
                **calibrated,
                "raw_delta": raw["delta"],
                "raw_low": raw["low"],
                "raw_high": raw["high"],
            }
        )
        for effect in [0.005, 0.01, 0.02]:
            estimated = len(test) * (2.802 * calibrated["cluster_se"] / effect) ** 2
            power.append(
                {
                    "minute": minute,
                    "hypothetical_log_loss_gain": effect,
                    "estimated_test_games_80pct_power": int(np.ceil(estimated)),
                    "observed_test_games": len(test),
                    "observed_series": calibrated["series"],
                }
            )
    return {
        "metrics": pd.DataFrame(metrics),
        "predictions": pd.DataFrame(predictions),
        "learning_curves": pd.DataFrame(curves),
        "power_estimates": pd.DataFrame(power),
    }, parameters


def report(frames, manifest):
    metrics = frames["metrics"]
    primary = metrics[
        (metrics.minute.eq(15)) & metrics.variant.eq("gold_elo_objectives")
    ].iloc[0]
    verdict = "The primary 15-minute improvement is inconclusive."
    if primary.high < 0:
        verdict = "The primary 15-minute paired interval supports improved log loss on this retrospective cohort."
    elif primary.low > 0:
        verdict = "The primary 15-minute paired interval supports worse log loss on this retrospective cohort."
    cols = [
        "minute",
        "variant",
        "train_games",
        "calibration_games",
        "test_games",
        "log_loss",
        "raw_log_loss",
        "brier",
        "accuracy",
        "ece10",
        "delta",
        "low",
        "high",
    ]
    return f"""# Historical objective feature experiment

{verdict} Primary added-minus-control log loss: {primary.delta:+.5f}, 95% paired interval [{primary.low:+.5f}, {primary.high:+.5f}]. Lower is better. 10/20-minute comparisons are secondary, not separate adoption tests.

## Fixed method

{manifest["games"]} verified games, LPL excluded. Train calendar 2022–2023, calibrate 2024, evaluate 2025; exact same games for both variants at each minute. C=1 logistic regression, training-only scaling; C=1e6 sigmoid calibration on the separate calibration year. Explicit series IDs stay in one partition; paired 2,000-draw bootstrap resamples league/series clusters, seed 42. Primary comparison uses calibrated probabilities; raw results are reported without selecting between them after scoring.

Predictors: gold and pre-match Elo gaps; added past objective gaps for towers, elemental dragons, Elder, Baron, Herald, grubs and Atakhan. Features constant in training are omitted and recorded in fitted_models.json. In particular, newer objectives absent in 2022–2023 have no learned effects; this experiment cannot assess their separate usefulness. Final totals validate source parsing and never enter the model. Winner/identity/date fields are labels/metadata only.

## Scores

{audit.table(metrics[cols])}

## Learning curves and collection estimates

Learning curves use RAW 2024 predictions from increasing chronological 2022–2023 prefixes, with no calibration fit on the curve's evaluation data. No C, feature, cutoff or model selection is made from 2025 scores. `learning_curves.csv` records the development curves.

{audit.table(frames["power_estimates"])}

Power figures are provisional normal-approximation estimates for hypothetical gains, using observed paired series-cluster variance, 80% power / two-sided 5% significance. They concern EVALUATION games in addition to training/calibration data, assume similar future clustering/variance and fixed fitted models, and are not guaranteed minimums. Use them to refine acquisition, not claim accuracy or a market edge.

## Limits and reproduction

Selected spring/Worlds events, uneven league/era coverage, exclusions and small per-league evaluation slices limit generalization. 2025/2026 outcomes were viewed in earlier research; this is a retrospective feature ablation, not an untouched prospective confirmation. Source totals and gold agree where admitted; every objective timestamp has not been independently verified against broadcasts. No forecast adoption, market execution or DB/site changes.

Run `.venv/bin/python scripts/research/evaluate_gol_objectives.py` after at least 1,000 verified games. Dataset/sample/collection hashes and fixed feature/split settings are saved in manifest.json; metrics, predictions, development curves, power estimates and fitted numeric parameters under gitignored data/gol_objectives/. No automatic reruns on each collection batch; freeze the first experiment before further changes.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset", type=Path, default=Path("data/gol_training/training_dataset.csv")
    )
    parser.add_argument(
        "--samples", type=Path, default=Path("data/gol_training/samples.json")
    )
    parser.add_argument("--artifacts", type=Path, default=Path("data/gol_objectives"))
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/gol_objective_report.md")
    )
    args = parser.parse_args()
    if (args.artifacts / "manifest.json").exists():
        raise ValueError(
            "First experiment already frozen; use a separate artifacts directory for explicit later experiments"
        )
    frame = load_dataset(args.dataset, args.samples)
    frames, parameters = evaluate(frame)
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, values in frames.items():
        values.to_csv(args.artifacts / f"{name}.csv", index=False)
    (args.artifacts / "fitted_models.json").write_text(
        json.dumps(parameters, indent=2) + "\n"
    )
    manifest = {
        "games": int(frame.oe_gameid.nunique()),
        "dataset_sha256": hashlib.sha256(args.dataset.read_bytes()).hexdigest(),
        "samples_sha256": hashlib.sha256(args.samples.read_bytes()).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": {
            name: hashlib.sha256(
                (Path(__file__).parent / name).read_bytes()
            ).hexdigest()
            for name in ["evaluate_champions.py", "audit_snapshots.py"]
        },
        "collection_manifest_sha256": (
            hashlib.sha256(
                (args.dataset.parent / "manifest.json").read_bytes()
            ).hexdigest()
            if (args.dataset.parent / "manifest.json").exists()
            else None
        ),
        "train_years": [2022, 2023],
        "calibration_year": 2024,
        "test_year": 2025,
        "C": 1,
        "calibration_C": 1e6,
        "primary_minute": 15,
        "bootstrap_repetitions": 2000,
        "bootstrap_seed": 42,
        "variants": VARIANTS,
    }
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    args.out.write_text(report(frames, manifest))
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
