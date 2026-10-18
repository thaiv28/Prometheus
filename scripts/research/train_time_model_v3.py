"""
train_time_model_v3.py: the live map model with weights that change with game time.

v1 lets each input's weight move only in a straight line with time (one
`x * time` term each). v2 refit that on 3x the maps and tied v1
(`docs/research/time_model_v2.md`), while a separate fit at each Oracle's Elixir
checkpoint beat v1 at 15 and 20 minutes (`docs/research/series_checkpoint.md`):
the time terms, not the data, look like the limit. Fixed protocol, declared
before scoring:

- **Data and split.** v2's (`train_time_model_v2.partitions`): train through
  2024, calibrate January-June 2025, test July 2025 on (feed maps only).
- **Model.** Logistic regression on a clamped cubic B-spline of game time
  (knots every 5 minutes to 30, then 40; 10 basis functions) and on each of
  gold lead (thousands), gold share and Elo gap (hundreds) times that basis:
  40 columns. Standardized, L2 with C=1, each map weighted equally, then v1's
  calibration layer (`train_time_model.fit`). One candidate, no tuning.
- **Adoption.** v3 replaces v1 when its test log loss is lower with a 95%
  series-bootstrap interval below zero.

    uv run python scripts/research/train_time_model_v3.py \\
        --out data/research/time_model_v3 --report docs/research/time_model_v3.md
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import INTERNATIONAL, MAJORS, V1, calls, ci, partitions

from prometheus.live.timeline import features

ROOT = Path(__file__).resolve().parents[2]


def spline_basis(knots, degree, x):
    """Clamped B-spline basis at x (Cox-de Boor), x held inside the knot range."""
    t = [knots[0]] * degree + list(knots) + [knots[-1]] * degree
    x = min(max(x, knots[0]), knots[-1])
    n = len(t) - degree - 1
    # Degree 0: the one interval holding x (the last interval holds the end).
    b = [
        1.0
        if (t[i] <= x < t[i + 1]) or (x == t[-1] and t[i] < t[i + 1] == t[-1])
        else 0.0
        for i in range(len(t) - 1)
    ]
    for d in range(1, degree + 1):
        nxt = []
        for i in range(len(t) - d - 1):
            left = (x - t[i]) / (t[i + d] - t[i]) * b[i] if t[i + d] > t[i] else 0.0
            right = (
                (t[i + d + 1] - x) / (t[i + d + 1] - t[i + 1]) * b[i + 1]
                if t[i + d + 1] > t[i + 1]
                else 0.0
            )
            nxt.append(left + right)
        b = nxt
    return b[:n]


def spline_features(
    knots, degree, clock_seconds, blue_gold, red_gold, blue_elo, red_elo
):
    """The time basis, then gold lead (thousands), gold share and Elo gap
    (hundreds), each times the basis."""
    x = features(clock_seconds, blue_gold, red_gold, blue_elo, red_elo)
    basis = spline_basis(knots, degree, clock_seconds)
    out = list(basis)
    for value in x[:3]:  # gold_k, gold_fraction, elo_hundred
        out += [value * b for b in basis]
    return out


def predict_v3(model, row):
    """A time_spline_v1 model's blue chance for one row (research inference)."""
    x = spline_features(
        model["knots"],
        model["degree"],
        float(row.seconds),
        float(row.blue_gold),
        float(row.red_gold),
        float(row.blue_elo),
        float(row.red_elo),
    )
    z = model["intercept"] + sum(
        (v - m) / s * c
        for v, m, s, c in zip(x, model["mean"], model["scale"], model["coef"])
    )
    z = model["calibration_slope"] * z + model["calibration_intercept"]
    return 1 / (1 + np.exp(-z))


KNOTS = [0, 300, 600, 900, 1200, 1500, 1800, 2400]  # seconds
DEGREE = 3
INPUTS = ["gold_k", "gold_fraction", "elo_hundred"]


def design(data):
    """The 40 spline columns for every row, from the shipped feature function."""
    x = np.array(
        [
            spline_features(
                KNOTS,
                DEGREE,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
            )
            for r in data.itertuples()
        ]
    )
    names = [f"c{i}" for i in range(x.shape[1])]
    for i, name in enumerate(names):
        data[name] = x[:, i]
    return names


def model_json(fitted, high, years):
    scaler, base, cal = fitted
    return {
        "schema": "time_spline_v1",
        "knots": KNOTS,
        "degree": DEGREE,
        "inputs": ["time"] + INPUTS,
        "supported_seconds": [0, high * 60],
        "mean": scaler.mean_.tolist(),
        "scale": scaler.scale_.tolist(),
        "coef": base.coef_[0].tolist(),
        "intercept": float(base.intercept_[0]),
        "calibration_slope": float(cal.coef_[0, 0]),
        "calibration_intercept": float(cal.intercept_[0]),
        "mode": "research",
        "version": 3,
        "trained_years": years,
        "calibration_period": ["2025-01-01", "2025-07-01"],
        "test_from": "2025-07-01",
        "sources": [
            "feed.lolesports.com timelines (estimated clock)",
            "gol.gg timelines through 2024",
        ],
        "subminute_validated": False,
    }


def run(args):
    parts = partitions(args.feed, args.gol)
    train, calibration, test, high = (
        parts["train"],
        parts["calibration"],
        parts["test"],
        parts["high"],
    )
    names = design(train)
    design(calibration)
    design(test)
    fitted = fit(train, calibration, names)
    model = model_json(fitted, high, sorted(train.year.unique().tolist()))
    p3 = score(fitted, test, names)
    exported = np.array([predict_v3(model, r) for r in test.itertuples()])
    if not np.allclose(p3, exported, atol=1e-9):
        raise ValueError("export mismatch")
    v1 = json.loads(V1.read_text())
    in_v1 = (test.seconds <= v1["supported_seconds"][1]).to_numpy()
    shared = test[in_v1]
    p1 = calls(v1, shared)
    p3 = p3[in_v1]
    paired = delta(shared, p3, p1)
    adopt = paired["interval"][1] < 0

    tier = shared.league.map(
        lambda lg: (
            "International"
            if lg in INTERNATIONAL
            else ("Major league" if lg in MAJORS else "Other")
        )
    )
    slices = [
        (
            f"Minutes {label}",
            ((shared.seconds >= lo) & (shared.seconds < hi)).to_numpy(),
        )
        for label, lo, hi in (
            ("0–10", 0, 600),
            ("10–20", 600, 1200),
            ("20–30", 1200, 1800),
            ("30+", 1800, 1e9),
        )
    ] + [
        (name, (tier == name).to_numpy())
        for name in ("Major league", "International", "Other")
    ]

    lines = [
        "# Live map model v3: weights that change with game time",
        "",
        f"Generated by `scripts/research/train_time_model_v3.py` on {date.today().isoformat()}. "
        "v2's data and split (`docs/research/time_model_v2.md`): "
        f"train {train.game_id.nunique():,} maps, calibrate {calibration.game_id.nunique():,}, "
        f"test {test.game_id.nunique():,}. Cubic B-spline of game time, knots at "
        f"{', '.join(str(k // 60) for k in KNOTS)} minutes; time and gold lead, gold share "
        "and Elo gap each times the basis (40 columns), C=1, v1's calibration.",
        "",
        "## v3 against v1 on the test maps",
        "",
        "Log loss per map (each map's rows weighted equally), v3 minus v1; negative is better; "
        "95% intervals resample whole series.",
        "",
        "| Slice | Maps | v1 LL | v3 LL | v3 − v1 |",
        "|---|---|---|---|---|",
        f"| All | {shared.game_id.nunique():,} | {metrics(shared, p1)['log_loss']:.4f} | "
        f"{metrics(shared, p3)['log_loss']:.4f} | {ci(paired)} |",
    ]
    for label, mask in slices:
        part = shared[mask]
        if part.game_id.nunique() >= 30:
            lines.append(
                f"| {label} | {part.game_id.nunique():,} | {metrics(part, p1[mask])['log_loss']:.4f} | "
                f"{metrics(part, p3[mask])['log_loss']:.4f} | {ci(delta(part, p3[mask], p1[mask]))} |"
            )
    lines += [
        "",
        f"**Adopted: {'yes' if adopt else 'no'}** (rule: the all-maps interval is below zero).",
    ]
    # Each input's weight across the game, for reading the fit (log-odds per unit).
    scaler, base, _ = fitted
    raw = base.coef_[0] / scaler.scale_
    k = len(raw) // 4
    lines += [
        "",
        "## Weights across the game",
        "",
        "Log-odds per unit before calibration: gold lead per 1,000, Elo gap per 100.",
        "",
        "| Minute | Gold lead | Gold share | Elo gap |",
        "|---|---|---|---|",
    ]
    for minute in (0, 5, 10, 15, 20, 25, 30, 35, 40):
        if minute * 60 > high * 60:
            break
        b = np.array(spline_basis(KNOTS, DEGREE, minute * 60.0))
        w = [float(b @ raw[k * (i + 1) : k * (i + 2)]) for i in range(3)]
        lines.append(f"| {minute} | {w[0]:+.3f} | {w[1]:+.2f} | {w[2]:+.3f} |")
    text = "\n".join(lines) + "\n"
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "model.json").write_text(json.dumps(model, indent=2) + "\n")
    if args.report:
        args.report.write_text(text)
    print(text)
    return adopt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feed", type=Path, default=ROOT / "data" / "feed_timelines")
    parser.add_argument("--gol", type=Path, default=ROOT / "data" / "gol_training")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "data" / "research" / "time_model_v3"
    )
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    run(args)


if __name__ == "__main__":
    main()
