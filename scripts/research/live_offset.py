"""Fixed-offset FORGE prior for in-game calls, declared before scoring.

Anchor B1 (`live_anchor.py`) let the fit choose FORGE's weight, so its 0:00 call
need not equal the pre-map call. D enters logit(FORGE) as an offset with weight
exactly 1 at 0:00 and fits only its fade (offset x time) beside production's
gold/objective/momentum terms; Elo is dropped. The intercept stays free (FORGE is
side-free) and there is no global calibration, which would rescale the offset.
D2 adds an offset x time^2 fade. Same split, maps, losses and bootstrap as B;
D passes under `live_anchor.RULE` against production. Retrospective: the test
chronology was viewed by earlier studies.

The diagnosis section, added after D failed at 30+ minutes, isolates D's four
differences from production: fit sample (Control refits production's design on
D's maps), calibration (Control raw, D+cal), Elo terms (D+elo_time keeps the
0:00 pin, D+elo does not) and prior source (E: offset from the calibrated Elo
map prior). It selects nothing.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from live_anchor import (
    CACHE,
    RULE,
    compare,
    forge_table,
    header,
    metric_line,
    passes,
    production_calls,
    slices,
)
from train_time_model import fit, metrics, score
from train_time_model_v2 import clock, partitions, when

from prometheus.live import timeline


def weights(frame):
    w = 1 / frame.groupby("game_id").game_id.transform("size").to_numpy()
    return w * len(w) / w.sum()


def fit_offset(train, columns, offset="anchor"):
    """Weighted logistic regression with an offset column, L2 as sklearn C=1."""
    scaler = StandardScaler().fit(train[columns], sample_weight=weights(train))
    x = scaler.transform(train[columns])
    y, w, o = train.won.to_numpy(), weights(train), train[offset].to_numpy()

    def loss(beta):
        z = o + beta[0] + x @ beta[1:]
        p = expit(z)
        value = np.sum(w * (np.logaddexp(0, z) - y * z)) + 0.5 * beta[1:] @ beta[1:]
        g = w * (p - y)
        return value, np.concatenate([[g.sum()], x.T @ g + beta[1:]])

    beta = minimize(loss, np.zeros(x.shape[1] + 1), jac=True, method="L-BFGS-B").x
    return scaler, beta, offset


def offset_logit(fitted, frame, columns):
    scaler, beta, offset = fitted
    return (
        frame[offset].to_numpy() + beta[0] + scaler.transform(frame[columns]) @ beta[1:]
    )


def score_offset(fitted, frame, columns):
    return expit(offset_logit(fitted, frame, columns))


def calibrated(fitted, calibration, frame, columns):
    """`fit`'s global calibration step applied to an offset model."""
    cal = LogisticRegression(C=1e6, max_iter=3000).fit(
        offset_logit(fitted, calibration, columns).reshape(-1, 1),
        calibration.won,
        sample_weight=weights(calibration),
    )
    z = offset_logit(fitted, frame, columns).reshape(-1, 1)
    return cal.predict_proba(z)[:, 1], cal.coef_[0, 0]


def prior_weight(fitted, columns, minutes):
    """FORGE's log-odds weight at each minute: 1 + the fitted fade terms."""
    scaler, beta, _ = fitted
    coef = dict(zip(columns, beta[1:] / scaler.scale_))
    t = np.asarray(minutes) * 60 / 1200
    return 1 + coef["anchor_time"] * t + coef.get("anchor_time2", 0) * t**2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=Path, default=Path("docs/research/live_offset.md")
    )
    args = parser.parse_args()
    started = time.monotonic()
    CACHE.mkdir(parents=True, exist_ok=True)
    table = forge_table(False)
    # The anchor study's frames, production design and runtime objective inputs.
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    extra = objective_rows(parts["joined"])
    n = int(parts["data"].source.eq("feed").sum())
    frames = [
        momentum(attach(parts[k][parts[k].source.eq("feed")], extra, n))
        for k in ("train", "calibration", "test")
    ]
    prod = (
        timeline.FEATURES
        + add_columns(frames[0], PRIMARY)
        + ["momentum", "momentum_time"]
    )
    for frame in frames[1:]:
        add_columns(frame, PRIMARY)
    raw_samples = []
    for match in parts["joined"]:
        for sample, sec in zip(
            match["samples"], clock(match["samples"], when(match["start"]))
        ):
            bg, rg = sample["blue"]["gold"], sample["red"]["gold"]
            if sec is not None and sec >= 0 and sample["state"] == "in_game":
                if bg and rg and bg > 0 and rg > 0:
                    raw_samples.append((sample["blue"], sample["red"]))
    assert len(raw_samples) == n
    kept = []
    for frame in frames:
        part = frame[frame.game_id.isin(table.index)].copy()
        part["anchor"] = logit(part.game_id.map(table.p_forge).clip(1e-4, 1 - 1e-4))
        part["anchor_time"] = part.anchor * part.time
        part["anchor_time2"] = part.anchor_time * part.time
        p_elo = part.game_id.map(table.p_elo).clip(1e-4, 1 - 1e-4)
        part["elo_anchor"] = logit(p_elo)
        part["elo_anchor_time"] = part.elo_anchor * part.time
        kept.append(part)
    tr, ca, te = kept
    state = [c for c in prod if c not in ("elo_hundred", "elo_time")]
    b1cols = state + ["anchor", "anchor_time"]
    dcols = state + ["anchor_time"]
    d2cols = dcols + ["anchor_time2"]
    d, d2 = fit_offset(tr, dcols), fit_offset(tr, d2cols)
    model = json.loads(timeline.MODEL_PATH.read_text())
    predictions = {
        "D": score_offset(d, te, dcols),
        "D2": score_offset(d2, te, d2cols),
        "B1": score(fit(tr, ca, b1cols), te, b1cols),
        "Production": production_calls(model, te, raw_samples),
    }
    lines = [
        "# Live offset research",
        "",
        "Follow-up to [anchor B1](live_anchor.md): logit(FORGE) as a fixed offset (weight 1 at 0:00), fitting only its fade beside production's state terms; no Elo, free side intercept, no global calibration. D fades linearly in time, D2 adds time². Train 2024 feed, test from 2025-07-01 on B's maps; retrospective. Negative deltas favor the candidate; 2,000 paired series-bootstrap draws, seed 42.",
        "",
        RULE + " Primary: D−prod.",
        "",
        f"Test maps: {te.game_id.nunique()}.",
        "",
    ]
    lines += header("Results")
    result = compare(
        lines, "D−prod", te, predictions["D"], predictions["Production"], slices(te)
    )
    compare(
        lines, "D2−prod", te, predictions["D2"], predictions["Production"], slices(te)
    )
    compare(lines, "D−B1", te, predictions["D"], predictions["B1"], slices(te))
    minutes = [0, 10, 20, 30, 40]
    # Diagnosis: one difference from production at a time.
    ecols = state + ["elo_anchor_time"]
    d_cal, slope = calibrated(d, ca, te, dcols)
    diagnosis = {
        "Control": score(fit(tr, ca, prod), te, prod),
        "Control raw": score_offset(
            fit_offset(tr.assign(zero=0.0), prod, "zero"), te.assign(zero=0.0), prod
        ),
        "D+cal": d_cal,
        "D+elo_time": score_offset(
            fit_offset(tr, dcols + ["elo_time"]), te, dcols + ["elo_time"]
        ),
        "D+elo": score_offset(
            fit_offset(tr, dcols + ["elo_hundred", "elo_time"]),
            te,
            dcols + ["elo_hundred", "elo_time"],
        ),
        "E": score_offset(fit_offset(tr, ecols, "elo_anchor"), te, ecols),
    }
    late = [s for s in slices(te) if s[0] in ("20–30", "30+")]
    lines += ["", *header("Diagnosis")]
    for name, p in diagnosis.items():
        compare(lines, f"{name}−prod", te, p, predictions["Production"], late)
        compare(lines, f"{name}−D", te, p, predictions["D"], late)
    lines += [
        "",
        f"D+cal slope {slope:.3f}.",
        *[metric_line(name, te, p) for name, p in diagnosis.items()],
    ]
    lines += [
        "",
        *[metric_line(name, te, p) for name, p in predictions.items()],
        "",
        "FORGE log-odds weight by minute (" + ", ".join(map(str, minutes)) + "):",
        *[
            f"- {name}: "
            + ", ".join(f"{w:.2f}" for w in prior_weight(f, cols, minutes))
            for name, f, cols in (("D", d, dcols), ("D2", d2, d2cols))
        ],
        f"- D side intercept: {d[1][0]:+.3f} log-odds.",
        "",
        f"Verdict: {'PASS' if passes(result) else 'FAIL'}.",
        "",
    ]
    # F: D's design on every map, the dated Elo prior where FORGE has no call.
    full = []
    for frame in frames:
        part = frame.copy()
        elo = 1 / (1 + 10 ** (-(part.blue_elo - part.red_elo) / 400))
        p = part.game_id.map(table.p_forge).fillna(elo).clip(1e-4, 1 - 1e-4)
        part["anchor"] = logit(p)
        part["anchor_time"] = part.anchor * part.time
        full.append(part)
    ftr, fte = full[0], full[2]
    f = fit_offset(ftr, dcols)
    f_calls = score_offset(f, fte, dcols)
    production = production_calls(model, fte, raw_samples)
    covered = fte.game_id.isin(table.index).to_numpy()
    lines += [
        "## Full sample (F)",
        "",
        f"Declared after the diagnosis: D's design fit on all {ftr.game_id.nunique()} train maps, offset logit(FORGE) where the backtest has it, else the 400-scale Elo chance from the map's pre-match ratings. Primary F−prod on all {fte.game_id.nunique()} test maps under the rule above; FORGE maps secondary. Retrospective on a viewed split: a pass marks F for prospective checks only.",
        "",
        *header("F")[2:],
    ]
    fresult = compare(lines, "F−prod", fte, f_calls, production, slices(fte))
    compare(
        lines,
        "F−prod FORGE maps",
        fte[covered],
        f_calls[covered],
        production[covered],
        [s for s in slices(fte[covered]) if s[0] in ("0–5", "20–30", "30+")],
    )
    lines += [
        "",
        metric_line("F", fte, f_calls),
        metric_line("Production (all maps)", fte, production),
        "F prior weight by minute: "
        + ", ".join(f"{w:.2f}" for w in prior_weight(f, dcols, minutes))
        + f"; side intercept {f[1][0]:+.3f}.",
        f"Verdict F: {'PASS' if passes(fresult) else 'FAIL'}.",
        "",
        "Reproduce: `uv run python scripts/research/live_offset.py` (needs `live_anchor.py`'s inputs).",
        "",
    ]
    report = "\n".join(
        line.replace(" | ", "|") if line.startswith("|") else line for line in lines
    )
    args.report.write_text(report)
    m = {k: metrics(te, p)["log_loss"] for k, p in predictions.items()}
    print(
        f"{'PASS' if passes(result) else 'FAIL'}: {result[0]}; LL {m}; "
        f"report {args.report}; {time.monotonic() - started:.0f}s"
    )


if __name__ == "__main__":
    main()
