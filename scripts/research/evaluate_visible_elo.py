"""Locked 2026 test plus broadcast-compatible gold/kills + Elo research.

Run: .venv/bin/python scripts/research/evaluate_visible_elo.py
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

import evaluate_snapshot_elo as history

snapshots = history.snapshots
MODELS = {
    "gold": ["total_gold"],
    "gold_elo": ["total_gold", "elo_gap"],
    "scoreboard": ["total_gold", "total_kills"],
    "scoreboard_elo": ["total_gold", "total_kills", "elo_gap"],
    "rich": snapshots.FEATURES["aura_features"],
    "rich_elo": snapshots.FEATURES["aura_features"] + ["elo_gap"],
}
CONTROLS = {
    "gold": "gold",
    "gold_elo": "gold",
    "scoreboard": "gold",
    "scoreboard_elo": "gold_elo",
    "rich": "rich",
    "rich_elo": "rich",
}
YEARS = (2023, 2024, 2025, 2026)


def cohorts(frame, ratings, minute):
    part = frame[
        frame.valid_roster
        & frame.league.isin(snapshots.LEAGUES)
        & frame.gamelength.gt(minute * 60)
        & frame.year.le(2026)
    ]
    part = history.attach_ratings(part, ratings)
    visible = part[
        part.elo_available & part[["total_gold", "total_kills"]].notna().all(axis=1)
    ]
    common = visible[visible[snapshots.FEATURES["aura_features"]].notna().all(axis=1)]
    return {"common": common, "visible": visible}


def evaluate(frames, ratings):
    predictions, parameters, coverage = [], [], []
    for minute, frame in frames.items():
        for cohort_name, cohort in cohorts(frame, ratings, minute).items():
            for year, part in cohort.groupby("year"):
                coverage.append(
                    {
                        "minute": minute,
                        "cohort": cohort_name,
                        "year": int(year),
                        "games": len(part),
                    }
                )
            models = (
                MODELS
                if cohort_name == "common"
                else {k: v for k, v in MODELS.items() if not k.startswith("rich")}
            )
            for year in YEARS:
                train, calibration, test = snapshots.temporal_split(cohort, year)
                if min(len(train), len(calibration), len(test)) < 100:
                    continue
                print(
                    f"{cohort_name} {minute}m/{year}: {len(train)} train, {len(calibration)} calibrate, {len(test)} test",
                    flush=True,
                )
                for name, columns in models.items():
                    p, raw, fitted = history.champions.fit_predict(
                        train, calibration, test, columns, "stats"
                    )
                    pred = test[["date", "league", "won"]].reset_index()
                    pred["minute"], pred["year"], pred["cohort"], pred["variant"] = (
                        minute,
                        year,
                        cohort_name,
                        name,
                    )
                    pred["probability"], pred["raw_probability"] = p, raw
                    predictions.append(pred)
                    parameters.append(
                        {
                            "minute": minute,
                            "year": year,
                            "cohort": cohort_name,
                            "variant": name,
                            "train_years": [year - 4, year - 2],
                            "calibration_year": year - 1,
                            "train_n": len(train),
                            "calibration_n": len(calibration),
                            **fitted,
                        }
                    )
    return pd.concat(predictions, ignore_index=True), parameters, pd.DataFrame(coverage)


def score(predictions):
    rows = []
    for (minute, year, cohort), group in predictions.groupby(
        ["minute", "year", "cohort"]
    ):
        for variant, part in group.groupby("variant"):
            reference = (
                group[group.variant.eq(CONTROLS[variant])]
                .set_index("gameid")
                .loc[part.gameid]
            )
            y, p = part.won.to_numpy(), part.probability.to_numpy()
            delta = snapshots.losses(y, p) - snapshots.losses(
                y, reference.probability.to_numpy()
            )
            low, high = snapshots.clustered_interval(
                delta, part.league + "/" + part.date.dt.strftime("%Y-%m-%d")
            )
            rows.append(
                {
                    "minute": minute,
                    "year": year,
                    "cohort": cohort,
                    "variant": variant,
                    **snapshots.scores(y, p),
                    "raw_log_loss": snapshots.scores(
                        y, part.raw_probability.to_numpy()
                    )["log_loss"],
                    "control": CONTROLS[variant],
                    "delta": float(delta.mean()),
                    "delta_low": low,
                    "delta_high": high,
                }
            )
    return pd.DataFrame(rows)


def predict_visible(
    parameters,
    minute,
    blue_gold,
    red_gold,
    blue_kills,
    red_kills,
    blue_elo,
    red_elo,
    variant="scoreboard_elo",
    calibrated=True,
):
    """Blue map-win chance at an exact trained checkpoint; gold in actual units.

    Uses frozen exported numeric weights. Ratings must be pre-match, and gold /
    kills must be a synchronized snapshot at 10, 15 or 20 minutes. No interpolation.
    """
    if variant not in ("gold_elo", "scoreboard_elo") or minute not in snapshots.MINUTES:
        raise ValueError("Use gold_elo or scoreboard_elo at 10, 15 or 20 minutes")
    values = np.asarray(
        [blue_gold, red_gold, blue_kills, red_kills, blue_elo, red_elo], dtype=float
    )
    if not np.isfinite(values).all() or (values[:4] < 0).any():
        raise ValueError("Snapshot inputs must be finite, with nonnegative gold/kills")
    model = next(
        p
        for p in parameters
        if p["year"] == 2026
        and p["cohort"] == "visible"
        and p["minute"] == minute
        and p["variant"] == variant
    )
    fields = {
        "total_gold": blue_gold - red_gold,
        "total_kills": blue_kills - red_kills,
        "elo_gap": blue_elo - red_elo,
    }
    x = np.asarray([fields[c] for c in model["numeric_columns"]])
    z = (x - np.asarray(model["scaler_mean"])) / np.asarray(model["scaler_std"])
    logit = float(np.dot(z, model["coef"]) + model["intercept"])
    if calibrated:
        logit = model["calibration_slope"] * logit + model["calibration_intercept"]
    return float(expit(logit))


def report(metrics, coverage, audit):
    holdout = metrics[metrics.year.eq(2026)]
    common = holdout[holdout.cohort.eq("common")]
    visible = holdout[holdout.cohort.eq("visible")]
    gains = common[common.variant.isin(["gold_elo", "rich_elo"])]
    finding = (
        "Elo improves both gold-only and full-stats models at all three checkpoints, with paired 95% intervals below zero."
        if gains.delta_high.lt(0).all()
        else "Elo gains vary by checkpoint; inspect paired intervals below."
    )
    kills = visible[visible.variant.eq("scoreboard_elo")]
    if not kills.delta_high.lt(0).any():
        finding += " Adding kills to gold+Elo shows no reliable improvement at any checkpoint. Keep gold+Elo as the simplest broadcast-compatible candidate."
    finding += " Calibration remains imperfect; rounded or delayed broadcast inputs have not been validated."
    summary = common.pivot(
        index="minute", columns="variant", values="log_loss"
    ).reset_index()
    summary.columns.name = None
    return "\n".join(
        [
            "# 2026 validation and broadcast-visible Elo models",
            "",
            "Fixed settings: C=1, three-year training, next-year sigmoid calibration, next-year test; no 2026-driven tuning. The 2026 baseline outcomes were viewed previously, so this is retrospective validation, not an untouched holdout.",
            "",
            "## Finding",
            "",
            finding,
            "",
            "## Input availability",
            "",
            "Historical snapshots support team gold and kills, summed across five players per side. Towers, dragons, Baron, Herald and Atakhan in local OE files are final-game totals, with no checkpoint counts. They are excluded to avoid future information. Future objective features need timestamped events or archived screenshots; Baron buff status, dragon type/soul and timers may require more than a count. Game time is represented by separate 10/15/20-minute models, not a continuously validated model.",
            "",
            "## Evaluation",
            "",
            "Train 2022–2024, calibrate 2025, test available 2026 matches. Historical Elo updates after each finished game in archive order; current-match results do not enter its own pre-match rating. Existing Elo constants remain fixed. The common cohort compares rich stats, gold and gold+kills fairly on identical complete-rich games; the visible cohort only requires gold/kills/Elo and therefore has its own training population. Draft completeness is not required. Do not compare scores across cohorts as if they use the same games.",
            "",
            "The full-stats+Elo candidate uses the original C=1 protocol. All visible models also use C=1, fixed before scoring this run. Elo gains compare gold+Elo vs gold and rich+Elo vs rich. The extra-kills comparison is scoreboard+Elo vs gold+Elo. Paired league/day-cluster 95% intervals use 2,000 draws, seed 42, without multiplicity adjustment. Raw and calibrated scores are both retained; no selecting calibration from 2026 results. 2023–2025 development folds for visible features are also shown.",
            "",
            f"Elo replay includes {audit['elo_games']} games through 2026 and reproduces stored pre-match ratings with max difference {audit['saved_rating_max_difference']:.3g}. {audit['tied_timestamp_games']} archive games share timestamps (existing game-ID tie ordering). Game/team/side joins require matching raw timestamp, duration and outcome. Result-availability timing and existing Elo parameter selection limit causal timing claims.",
            "",
            "## 2026 common-cohort log loss",
            "",
            snapshots.table(summary),
            "",
            "## 2026 scores and paired differences",
            "",
            snapshots.table(holdout),
            "",
            "## Development scores",
            "",
            snapshots.table(metrics[metrics.year.lt(2026)]),
            "",
            "## Coverage",
            "",
            snapshots.table(coverage),
            "",
            "## Model export and live use",
            "",
            "Fitted parameters, source hashes, predictions and scores are saved in data/visible_elo/. predict_visible() uses the exported visible-cohort 2026 model weights and calibrator without refitting. Provide blue/red gold in actual units (32.1k → 32100), kills and pre-match Elo at an exact trained checkpoint. It returns blue map-win probability. These snapshots are historical totals; broadcast rounding, extraction errors and display delay are not simulated. Gold+Elo can omit kill features. Objective features and interpolation between checkpoints are not trained yet. No live integration, DB changes, published metric changes or profitable trading claim.",
            "",
        ]
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--out", type=Path, default=Path("docs/research/visible_elo_report.md"))
    parser.add_argument("--artifacts", type=Path, default=Path("data/visible_elo"))
    args = parser.parse_args()
    ratings, audit = history.load_ratings(end_year=2026)
    frames, manifest = snapshots.load_raw(args.raw_dir)
    predictions, parameters, coverage = evaluate(frames, ratings)
    metrics = score(predictions)
    objective_columns = {}
    for source in sorted(
        args.raw_dir.glob("*_LoL_esports_match_data_from_OraclesElixir.csv")
    ):
        header = pd.read_csv(source, nrows=0).columns
        objective_columns[source.name] = [
            c
            for c in header
            if any(
                word in c.lower()
                for word in ("tower", "dragon", "baron", "herald", "atakhan")
            )
        ]
    manifest["objective_column_inventory"] = objective_columns
    args.artifacts.mkdir(parents=True, exist_ok=True)
    for name, frame in {
        "predictions": predictions,
        "metrics": metrics,
        "coverage": coverage,
    }.items():
        frame.to_csv(args.artifacts / f"{name}.csv", index=False)
    manifest.update(
        {
            "purpose": "fixed 2026 retrospective validation plus visible gold/kills + Elo models",
            "years": YEARS,
            "models_spec": MODELS,
            "controls": CONTROLS,
            "elo_audit": audit,
            "elo_source_sha256": hashlib.sha256(
                Path(history.elo.__file__).read_bytes()
            ).hexdigest(),
            "models": parameters,
        }
    )
    (args.artifacts / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    (args.artifacts / "visible_models.json").write_text(
        json.dumps(
            {
                "train_years": [2022, 2024],
                "calibration_year": 2025,
                "checkpoint_minutes": list(snapshots.MINUTES),
                "gold_unit": "actual gold; convert 32.1k to 32100",
                "recommended_visible_features": "gold_elo; deployment simplicity, no 2026 tuning",
                "models": [
                    p
                    for p in parameters
                    if p["year"] == 2026 and p["cohort"] == "visible"
                ],
            },
            indent=2,
        )
        + "\n"
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(report(metrics, coverage, audit))
    print(f"Wrote {args.out} and {args.artifacts}")


if __name__ == "__main__":
    main()
