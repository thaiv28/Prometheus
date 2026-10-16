"""Offline, fixed-protocol full-gold-timeline research; never refit frozen models."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from gold_timeline import parse_gold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.preprocessing import StandardScaler

from prometheus.live.timeline import FEATURES, features, predict


def load(source):
    checkpoints = pd.read_csv(source / "training_dataset.csv")
    samples = {
        r["gol_id"]: r["series_first_id"]
        for r in json.loads((source / "samples.json").read_text())
    }
    rows, rejected, hashes = [], Counter(), {}
    for gol_id, group in checkpoints.groupby("gol_id", sort=True):
        try:
            if (
                not group.training_ready.eq(True).all()
                or group.oe_gameid.nunique() != 1
            ):
                raise ValueError("unverified_game")
            fixed = [
                "date",
                "year",
                "league",
                "blue_team",
                "red_team",
                "blue_elo",
                "red_elo",
                "blue_won",
            ]
            if any(group[k].nunique() != 1 for k in fixed):
                raise ValueError("inconsistent_game_metadata")
            path = source / "html" / f"{gol_id}-timeline.html"
            raw = path.read_bytes()
            gold = parse_gold(raw.decode())
            # Revalidate all previously verified checkpoint sums before expanding.
            for r in group.itertuples():
                if (
                    r.minute not in gold
                    or max(
                        abs(gold[r.minute][0] - r.blue_gold),
                        abs(gold[r.minute][1] - r.red_gold),
                    )
                    > 1
                ):
                    raise ValueError("checkpoint_gold_disagreement")
            first = group.iloc[0]
            for minute, (blue, red) in gold.items():
                if not 0 <= minute <= 40 or min(blue, red) <= 0:
                    continue
                rows.append(
                    {
                        "gol_id": int(gol_id),
                        "game_id": first.oe_gameid,
                        "series": f"{first.league}:{samples[int(gol_id)]}",
                        "year": int(first.year),
                        "date": first.date,
                        "league": first.league,
                        "minute": minute,
                        "blue_gold": blue,
                        "red_gold": red,
                        "blue_elo": first.blue_elo,
                        "red_elo": first.red_elo,
                        "won": int(first.blue_won),
                    }
                )
            hashes[path.name] = hashlib.sha256(raw).hexdigest()
        except (ValueError, KeyError, OSError) as error:
            rejected[str(error)] += 1
    frame = pd.DataFrame(rows)
    if frame.duplicated(["game_id", "minute"]).any():
        raise ValueError("duplicate game/minute")
    if (
        not frame.year.eq(pd.to_datetime(frame.date, utc=True).dt.year).all()
        or not frame.year.between(2022, 2025).all()
    ):
        raise ValueError("invalid year")
    return frame, dict(rejected), hashes


def fit(train, calibration, columns):
    scaler = StandardScaler()
    weights = 1 / train.groupby("game_id").game_id.transform("size").to_numpy()
    weights *= len(weights) / weights.sum()
    scaler.fit(train[columns], sample_weight=weights)
    base = LogisticRegression(C=1, max_iter=3000).fit(
        scaler.transform(train[columns]), train.won, sample_weight=weights
    )
    cw = 1 / calibration.groupby("game_id").game_id.transform("size").to_numpy()
    cw *= len(cw) / cw.sum()
    cal = LogisticRegression(C=1e6, max_iter=3000).fit(
        base.decision_function(scaler.transform(calibration[columns])).reshape(-1, 1),
        calibration.won,
        sample_weight=cw,
    )
    return scaler, base, cal


def score(fitted, data, columns):
    scaler, base, cal = fitted
    z = base.decision_function(scaler.transform(data[columns]))
    return cal.predict_proba(z.reshape(-1, 1))[:, 1]


def metrics(data, p):
    weights = 1 / data.groupby("game_id").game_id.transform("size").to_numpy()
    ece = 0
    for low in np.arange(0, 1, 0.1):
        mask = (p >= low) & (p < low + 0.1)
        if mask.any():
            ece += (
                weights[mask].sum()
                / weights.sum()
                * abs(
                    np.average(p[mask], weights=weights[mask])
                    - np.average(data.won.to_numpy()[mask], weights=weights[mask])
                )
            )
    return {
        "games": int(data.game_id.nunique()),
        "rows": len(data),
        "log_loss": float(log_loss(data.won, p, sample_weight=weights)),
        "brier": float(brier_score_loss(data.won, p, sample_weight=weights)),
        "ece10": float(ece),
    }


def delta(data, p, control):
    y = data.won.to_numpy()
    loss = lambda q: (
        -(
            y * np.log(np.clip(q, 1e-12, 1 - 1e-12))
            + (1 - y) * np.log(np.clip(1 - q, 1e-12, 1 - 1e-12))
        )
    )
    records = data[["game_id", "series"]].copy()
    records["delta"] = loss(p) - loss(control)
    games = records.groupby(["series", "game_id"]).delta.mean().reset_index()
    groups = [g.delta.to_numpy() for _, g in games.groupby("series")]
    rng = np.random.default_rng(42)
    draws = []
    for _ in range(2000):
        sampled = np.concatenate(
            [groups[i] for i in rng.integers(len(groups), size=len(groups))]
        )
        draws.append(sampled.mean())
    return {
        "delta": float(games.delta.mean()),
        "interval": [float(v) for v in np.quantile(draws, [0.025, 0.975])],
        "series": len(groups),
    }


def train(source, out):
    out.mkdir(parents=True, exist_ok=False)
    data, rejected, hashes = load(source)
    x = np.array(
        [
            features(r.minute * 60, r.blue_gold, r.red_gold, r.blue_elo, r.red_elo)
            for r in data.itertuples()
        ]
    )
    for i, name in enumerate(FEATURES):
        data[name] = x[:, i]
    parts = [
        data[data.year.isin([2022, 2023])].copy(),
        data[data.year.eq(2024)].copy(),
        data[data.year.eq(2025)].copy(),
    ]
    if min(p.game_id.nunique() for p in parts) < 100:
        raise ValueError("at least100 maps per chronological partition required")
    ids = [set(p.series) for p in parts]
    if any(ids[i] & ids[j] for i in range(3) for j in range(i)):
        raise ValueError("series crosses partitions")
    counts = [p.groupby("minute").game_id.nunique() for p in parts]
    supported = [m for m in range(41) if all(c.get(m, 0) >= 30 for c in counts)]
    high = 0
    while high + 1 in supported:
        high += 1
    if 0 not in supported or high < 20:
        raise ValueError("insufficient time coverage")
    parts = [p[p.minute <= high].copy() for p in parts]
    training, calibration, test = parts
    fitted = fit(training, calibration, FEATURES)
    p = score(fitted, test, FEATURES)
    elo = fit(training, calibration, ["elo_hundred"])
    control = score(elo, test, ["elo_hundred"])
    scaler, base, cal = fitted
    model = {
        "schema": "time_gold_elo_v1",
        "features": FEATURES,
        "supported_seconds": [0, high * 60],
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": base.coef_[0].tolist(),
        "intercept": float(base.intercept_[0]),
        "calibration_slope": float(cal.coef_[0, 0]),
        "calibration_intercept": float(cal.intercept_[0]),
        "mode": "research",
        "trained_years": [2022, 2023],
        "calibration_year": 2024,
        "test_year": 2025,
        "subminute_validated": False,
        "competitions": sorted(data.league.unique().tolist()),
    }
    exported = np.array(
        [
            predict(
                model, r.minute * 60, r.blue_gold, r.red_gold, r.blue_elo, r.red_elo
            )
            for r in test.itertuples()
        ]
    )
    if not np.allclose(p, exported, rtol=0, atol=1e-12):
        raise ValueError("export mismatch")
    report = {
        "protocol": "Fixed C=1, six predeclared features, whole-map weighting; train2022-23/calibrate2024/test2025;2000 series bootstrap draws seed42; no tuning after test",
        "partitions": [
            {
                "years": sorted(part.year.unique().tolist()),
                "games": int(part.game_id.nunique()),
                "rows": len(part),
            }
            for part in parts
        ],
        "model": metrics(test, p),
        "elo_control": metrics(test, control),
        "paired_elo": delta(test, p, control),
        "checkpoint_comparison": [],
        "per_minute": [
            dict(minute=int(m), **metrics(group, p[test.minute.to_numpy() == m]))
            for m, group in test.groupby("minute")
        ],
        "rejected_games": rejected,
        "supported_seconds": model["supported_seconds"],
        "sklearn_version": sklearn.__version__,
        "limits": [
            "Historical sampled 2022-25 cohort; 2025 outcomes previously inspected in other experiments",
            "Gold graph semantics cross-checked only at10/15/20; other minute labels not independently verified",
            "Whole-minute observations only; subminute accuracy and prospective receipt timing unmeasured",
            "No CBLOL promotion evaluation; roster/Elo mapping and verified live clock required",
            "Late-game surviving-map selection; no final objectives, no profitability claim",
        ],
    }
    for minute in [10, 15, 20]:
        subset = [part[part.minute.eq(minute)] for part in parts]
        checkpoint = fit(subset[0], subset[1], ["gold_k", "elo_hundred"])
        cp = score(checkpoint, subset[2], ["gold_k", "elo_hundred"])
        current = p[test.minute.to_numpy() == minute]
        report["checkpoint_comparison"].append(
            {
                "minute": minute,
                "time_model": metrics(subset[2], current),
                "checkpoint_control": metrics(subset[2], cp),
                "paired": delta(subset[2], current, cp),
            }
        )
    data.to_csv(out / "timeline_dataset.csv", index=False)
    test = test.copy()
    test["p"] = p
    test["elo_control_p"] = control
    test.to_csv(out / "predictions.csv", index=False)
    (out / "model.json").write_text(json.dumps(model, indent=2) + "\n")
    (out / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    manifest = {
        "source_sha256": hashlib.sha256(
            (source / "training_dataset.csv").read_bytes()
        ).hexdigest(),
        "html_sha256": hashes,
        "script_sha256": {
            name: hashlib.sha256(
                (Path(__file__).parent / name).read_bytes()
            ).hexdigest()
            for name in ["train_time_model.py", "time_model.py", "gold_timeline.py"]
        },
        "artifact_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in out.iterdir()
            if p.is_file()
        },
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    train(args.source, args.out)
