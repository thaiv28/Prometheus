"""Draft v3 beyond frozen live objectives/momentum; fixed protocol in the report.

No runtime changes. Train live on 2024, calibrate 2025 H1, test 2025 H2 onward.
Draft fits end 2023 for training inputs and 2024 for calibration/test inputs.
Missing drafts stay in every comparison with shift zero. Never tune on test.
"""

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_walkforward as dw
from cand_followups import export
from cand_objectives import PRIMARY, add_columns, attach, objective_rows, slices
from cand_temporal import momentum
from draft_player_feats import EXTRA
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import ci, partitions

from prometheus.live import timeline

ROOT = Path(__file__).resolve().parents[2]


def draft_shifts(games):
    """Target-independent draft fits; entire v3 player block, no selection."""
    if games.gameid.duplicated().any():
        raise ValueError("duplicate draft game IDs")
    columns = ["forge_logit", *dw.FEATURES, *EXTRA]
    if not np.isfinite(games[columns].to_numpy()).all():
        raise ValueError("nonfinite draft features")
    out = []
    for last, first, final in [(2023, 2024, 2024), (2024, 2025, 9999)]:
        train = games[games.year.between(2019, last)]
        target = games[games.year.between(first, final)].copy()
        if train.empty or target.empty:
            raise ValueError("missing draft training or target period")
        base = dw._fit(train, ["forge_logit"])
        z = base.decision_function(target[["forge_logit"]].to_numpy())
        for name, cols in [
            ("v2", ["forge_logit", *dw.FEATURES]),
            ("v3", columns),
        ]:
            fitted = dw._fit(train, cols)
            target[name] = fitted.decision_function(target[cols].to_numpy()) - z
        out.append(target[["gameid", "v2", "v3"]])
    return pd.concat(out).set_index("gameid")


def add_draft(frame, shifts, name):
    out = frame.copy()
    out["draft_known"] = out.game_id.isin(shifts.index)
    out["draft"] = out.game_id.map(shifts[name]).fillna(0.0)
    out["draft_time"] = out.draft * out.time
    return out


def frozen_calls(model, frame):
    """Vectorized frozen inference, checked against runtime before scoring."""
    x = frame[model["features"]].to_numpy()
    z = ((x - model["mean"]) / model["scale"]) @ np.array(model["coef"])
    return expit(
        model["calibration_slope"] * (z + model["intercept"])
        + model["calibration_intercept"]
    )


def runtime_parity(model, frame):
    # Reconstruct an equivalent nonnegative pair for every signed objective gap.
    # Soul is not independently reconstructed: use the raw dragons counts below.
    out = []
    for r in frame.itertuples():
        teams = [{}, {}]
        for stat in timeline.OBJECTIVES[:-1]:
            gap = int(getattr(r, stat))
            teams[0][stat], teams[1][stat] = max(gap, 0), max(-gap, 0)
        soul = int(r.soul)
        gap = teams[0]["dragons"] - teams[1]["dragons"]
        # A gap alone cannot identify soul (e.g. 5 vs 4); choose a consistent pair.
        if soul == 0 and abs(gap) >= 4:
            teams[0]["dragons"], teams[1]["dragons"] = max(gap, 0) + 4, max(-gap, 0) + 4
        elif soul != 0:
            a, b = max(gap, 0), max(-gap, 0)
            bump = max(0, 4 - (a if soul == 1 else b))
            teams[0]["dragons"], teams[1]["dragons"] = a + bump, b + bump
        out.append(
            timeline.predict(
                model,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
                objectives=teams,
                momentum=float(r.momentum),
            )
        )
    np.testing.assert_allclose(out, frozen_calls(model, frame), atol=1e-12, rtol=0)
    return float(np.max(np.abs(np.array(out) - frozen_calls(model, frame))))


def checkpoint_dump(frame, p, directory):
    """CI comparator schema on feed-only in-game checkpoints; no fake quotes."""
    calls = frame.assign(ours=p).sort_values("seconds", kind="stable")
    rows = []
    for minute in (5, 10, 15, 20, 25, 30):
        pick = calls[calls.seconds.between((minute - 1.5) * 60, minute * 60)]
        rows.append(pick.groupby("game_id").tail(1).assign(checkpoint=minute))
    result = pd.concat(rows).rename(columns={"game_id": "game", "date": "start"})
    result["start"] = result.start.str[:10]
    result["kalshi"] = np.nan
    directory.mkdir(parents=True, exist_ok=True)
    result[["game", "series", "start", "checkpoint", "ours", "kalshi", "won"]].to_csv(
        directory / "calls.csv.gz", index=False
    )
    (directory / "metrics.json").write_text(
        json.dumps(
            {
                "fit_through": "2025-06-30",
                "research_only": True,
                "cohort": "feed-only; no markets or pregame",
            }
        )
        + "\n"
    )


def build_rows(feed, gol):
    parts = partitions(feed, gol)
    extra = objective_rows(parts["joined"])
    n = int(parts["data"].source.eq("feed").sum())
    frames = []
    for key in ("train", "calibration", "test"):
        part = parts[key]
        f = momentum(attach(part[part.source.eq("feed")], extra, n))
        add_columns(f, PRIMARY)
        frames.append(f)
    return pd.concat(frames)


def split_rows(rows):
    at = pd.to_datetime(rows.date, utc=True, format="mixed")
    feed = rows.source.eq("feed") & rows.seconds.between(0, 2400)
    masks = [
        feed & at.between("2024-01-01", "2025-01-01", inclusive="left"),
        feed & at.between("2025-01-01", "2025-07-01", inclusive="left"),
        feed & (at >= "2025-07-01"),
    ]
    parts = [rows[m].copy() for m in masks]
    if any(p.empty for p in parts):
        raise ValueError("empty live partition")
    for i, p in enumerate(parts):
        if any(set(p.series) & set(q.series) for q in parts[:i]):
            raise ValueError("series crosses live partition boundary")
    return parts


def run(args):
    started = time.monotonic()
    args.out.mkdir(parents=True, exist_ok=True)
    if not args.rows.exists():
        print("Building live rows from existing feed inputs", flush=True)
        rows = build_rows(args.feed, args.gol)
        args.rows.parent.mkdir(parents=True, exist_ok=True)
        rows.to_pickle(args.rows)
    rows = pd.read_pickle(args.rows)
    train, calibration, test = split_rows(rows)
    games = pd.read_pickle(args.games)
    print("Fitting earlier-only v2/v3 draft shifts", flush=True)
    shifts = draft_shifts(games)
    model = json.loads(timeline.MODEL_PATH.read_text())
    columns = timeline.STATE_FEATURES
    parity = runtime_parity(model, test)
    baseline = frozen_calls(model, test)
    predictions = {"production": baseline}
    refit = fit(train, calibration, columns)
    predictions["refit"] = score(refit, test, columns)
    # Rebuilt calibration data may differ from the frozen release corpus.
    refit_error = float(np.max(np.abs(predictions["refit"] - baseline)))
    for name in ("v2", "v3"):
        tr, ca, te = [add_draft(p, shifts, name) for p in (train, calibration, test)]
        cols = [*columns, "draft", "draft_time"]
        fitted = fit(tr, ca, cols)
        predictions[name] = score(fitted, te, cols)
        artifact = export(fitted, cols)
        artifact.update(
            fit_through="2025-06-30",
            draft=name,
            draft_fit_for_train_through=2023,
            draft_fit_for_test_through=2024,
        )
        (args.out / f"{name}_research.json").write_text(
            json.dumps(artifact, indent=2) + "\n"
        )
    print("Scoring fixed comparisons", flush=True)
    known = test.game_id.isin(shifts.index)
    masks = [
        ("All", np.ones(len(test), bool)),
        *slices(test),
        ("LPL", test.league.eq("LPL").to_numpy()),
        ("Known draft", known.to_numpy()),
        ("Missing draft", (~known).to_numpy()),
    ]
    masks += [(str(y), test.year.eq(y).to_numpy()) for y in sorted(test.year.unique())]
    records = []
    for candidate, control in [
        ("v3", "production"),
        ("v3", "refit"),
        ("v3", "v2"),
        ("v2", "production"),
    ]:
        for label, mask in masks:
            part = test[mask]
            if part.empty:
                continue
            records.append(
                dict(
                    candidate=candidate,
                    control=control,
                    slice=label,
                    **metrics(part, predictions[candidate][mask]),
                    control_ll=metrics(part, predictions[control][mask])["log_loss"],
                    **delta(
                        part, predictions[candidate][mask], predictions[control][mask]
                    ),
                )
            )
    for name, p in predictions.items():
        checkpoint_dump(test, p, args.out / name / "live")
    pd.DataFrame(records).to_json(args.out / "results.json", orient="records", indent=2)
    test.assign(
        **{f"p_{name}": p for name, p in predictions.items()}, draft_known=known
    ).to_csv(args.out / "predictions.csv.gz", index=False)
    primary = [
        r for r in records if r["candidate"] == "v3" and r["control"] == "production"
    ]
    gate = next(r for r in primary if r["slice"] == "All")["interval"][
        1
    ] < 0 and not any(r["interval"][0] > 0 for r in primary)
    metadata = {
        "base": "f522db3",
        "row_sha256": hashlib.sha256(args.rows.read_bytes()).hexdigest(),
        "games_sha256": hashlib.sha256(args.games.read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(timeline.MODEL_PATH.read_bytes()).hexdigest(),
        "runtime_parity_error": parity,
        "frozen_vs_refit_error": refit_error,
        "seconds": time.monotonic() - started,
        "gate_pass": gate,
    }
    (args.out / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    protocol_path = (
        args.report if args.report.exists() else ROOT / "docs/research/live_draft_v3.md"
    )
    protocol = protocol_path.read_text().split("\n## Results\n")[0]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(protocol)
    with args.report.open("a") as out:
        out.write(
            "\n## Results\n\n"
            + f"Train/calibration/test maps: {train.game_id.nunique():,} / {calibration.game_id.nunique():,} / {test.game_id.nunique():,}. Missing test drafts: {test[~known].game_id.nunique():,}.\n\n"
        )
        out.write(
            "| Candidate | Control | Slice | Maps | LL | Control LL | Delta (95%) | ECE |\n|---|---|---|---:|---:|---:|---|---:|\n"
        )
        for r in records:
            out.write(
                f"| {r['candidate']} | {r['control']} | {r['slice']} | {r['games']:,} | {r['log_loss']:.5f} | {r['control_ll']:.5f} | {ci(r, 5)} | {r['ece10']:.4f} |\n"
            )
        out.write(
            "\nGate: "
            + ("PASS" if gate else "FAIL")
            + ". Retrospective evidence only; no deployment.\n\n```json\n"
            + json.dumps(metadata, indent=2)
            + "\n```\n"
        )
    print(json.dumps(metadata, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--games",
        type=Path,
        default=ROOT / "data/research/draft_v2/player_feats_games.pkl",
    )
    parser.add_argument(
        "--rows", type=Path, default=ROOT / "data/research/live_draft_v3/rows.pkl"
    )
    parser.add_argument("--feed", type=Path, default=ROOT / "data/feed_timelines")
    parser.add_argument("--gol", type=Path, default=ROOT / "data/gol_training")
    parser.add_argument(
        "--out", type=Path, default=ROOT / "data/research/live_draft_v3"
    )
    parser.add_argument(
        "--report", type=Path, default=ROOT / "docs/research/live_draft_v3.md"
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()
