"""Fixed-protocol follow-ups: causal three-minute gold momentum and calibration.

Same v2 partitions: train <=2024, calibrate 2025 H1, test from 2025 July.
Primary: v1 features plus change in gold lead over the preceding three minutes
(in thousands), and its interaction with time. Use only observations at or
before t-180 seconds; use zero without that history. Fit on feed rows only,
with the same-row six-feature control. No tuning on the test.
Calibration diagnostics: raw refit, global Platt, and four fixed time buckets
(0-10, 10-20, 20-30, 30+ minutes), fit only on calibration rows. These diagnose
calibration; they do not select another winner. All deltas use series bootstrap.
Research only; no runtime changes or network access.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.special import expit
from sklearn.linear_model import LogisticRegression

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cand_objectives import table
from train_time_model import fit, metrics, score
from train_time_model_v2 import V1, calls, partitions

from prometheus.live.timeline import FEATURES


def momentum(data):
    """Gold-lead change using only the latest row at least 180 seconds earlier."""
    out = data.copy()
    out["momentum"] = 0.0
    for _, rows in out.groupby("game_id", sort=False):
        rows = rows.sort_values("seconds", kind="mergesort")
        seconds = rows.seconds.to_numpy()
        lead = (rows.blue_gold - rows.red_gold).to_numpy() / 1000
        lag = np.searchsorted(seconds, seconds - 180, side="right") - 1
        values = np.zeros(len(rows))
        valid = lag >= 0
        values[valid] = lead[valid] - lead[lag[valid]]
        out.loc[rows.index, "momentum"] = values
    out["momentum_time"] = out.momentum * out.time
    return out


def bucket(seconds):
    return np.searchsorted([600, 1200, 1800], seconds, side="right")


def run(args):
    parts = partitions(args.feed, args.gol)
    train, calibration, test = (
        momentum(parts[key][parts[key].source == "feed"])
        for key in ("train", "calibration", "test")
    )
    v1 = json.loads(V1.read_text())
    test = test[test.seconds <= v1["supported_seconds"][1]].copy()
    base = fit(train, calibration, FEATURES)
    candidate = fit(train, calibration, FEATURES + ["momentum", "momentum_time"])
    p1 = calls(v1, test)
    global_p = score(base, test, FEATURES)
    p = score(candidate, test, FEATURES + ["momentum", "momentum_time"])
    scaler, model, _ = base
    zc = model.decision_function(scaler.transform(calibration[FEATURES]))
    zt = model.decision_function(scaler.transform(test[FEATURES]))
    raw = expit(zt)
    time_p = np.empty(len(test))
    for b in range(4):
        cm = bucket(calibration.seconds.to_numpy()) == b
        tm = bucket(test.seconds.to_numpy()) == b
        local = calibration[cm]
        weights = 1 / local.groupby("game_id").game_id.transform("size").to_numpy()
        weights *= len(weights) / weights.sum()
        cal = LogisticRegression(C=1e6, max_iter=3000).fit(
            zc[cm].reshape(-1, 1), local.won, sample_weight=weights
        )
        time_p[tm] = cal.predict_proba(zt[tm].reshape(-1, 1))[:, 1]
    lines = [
        "# Live model: momentum and calibration checks",
        "",
        "Fixed v2 split; feed-only fits, equal map weights, C=1. "
        f"Train {train.game_id.nunique():,} maps; calibration "
        f"{calibration.game_id.nunique():,}; test {test.game_id.nunique():,}. "
        "Negative log-loss deltas are better; intervals resample whole series. "
        "The test has already been used for earlier research; these are retrospective checks.",
        "",
        "## Primary: three-minute gold momentum versus v1",
        "",
        *table(test, p, p1, "v1", "Momentum"),
        "",
        "## Momentum versus same-row refit",
        "",
        *table(test, p, global_p, "Refit", "Momentum"),
        "",
        "## Calibration diagnostics",
        "",
        "| Model | Log loss | ECE (10 bins) |",
        "|---|---:|---:|",
    ]
    for name, prob in [
        ("v1", p1),
        ("Raw refit", raw),
        ("Global calibration", global_p),
        ("Time-bucket calibration", time_p),
    ]:
        m = metrics(test, prob)
        lines.append(f"| {name} | {m['log_loss']:.4f} | {m['ece10']:.4f} |")
    for name, prob in [("Raw refit", raw), ("Time-bucket calibration", time_p)]:
        lines += [
            "",
            f"## {name} versus global calibration (diagnostic)",
            "",
            *table(test, prob, global_p, "Global", name),
        ]
    lines += [
        "",
        "No model is shipped. Momentum uses only past samples, including across pauses "
        "on the existing estimated-clock axis. Its zero-history fallback is shared in all "
        "partitions. Bucket calibration is discontinuous at fixed boundaries and has not "
        "been validated on production ten-second frames. ECE is descriptive, not an adoption test.",
        "",
    ]
    args.report.write_text("\n".join(lines))
    print(args.report)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=Path("data/feed_timelines"))
    parser.add_argument("--gol", type=Path, default=Path("data/gol_training"))
    parser.add_argument(
        "--report", type=Path, default=Path("docs/research/cand_temporal.md")
    )
    run(parser.parse_args())
