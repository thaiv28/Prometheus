"""Freeze exactly the tested objective + three-minute momentum fit, no retuning.

Train: 2024 feed; calibration: 2025 H1; test from July 2025 is evaluation only.
Export dependency-free parameters and verify every held-out prediction against
runtime inference. Gold momentum uses only observations at or before t-180.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cand_followups import export
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from train_time_model import delta, fit, metrics, score
from train_time_model_v2 import calls, clock, partitions, when

from prometheus.live import timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=timeline.MODEL_PATH)
    args = parser.parse_args()
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    extra = objective_rows(parts["joined"])
    n = int((parts["data"].source == "feed").sum())
    frames = [
        momentum(attach(parts[k][parts[k].source == "feed"], extra, n))
        for k in ("train", "calibration", "test")
    ]
    columns = (
        timeline.FEATURES
        + add_columns(frames[0], PRIMARY)
        + ["momentum", "momentum_time"]
    )
    for frame in frames[1:]:
        add_columns(frame, PRIMARY)
    train, calibration, test = frames
    fitted = fit(train, calibration, columns)
    model = export(fitted, columns)
    model.update(
        schema="time_objectives_momentum_v1",
        supported_seconds=[0, 2400],
        version="objectives-momentum-2026-10-17",
        mode="research",
        fit_through="2025-06-30",
        trained_years=[2024],
        calibration_period=["2025-01-01", "2025-07-01"],
        test_from="2025-07-01",
        subminute_validated=False,
        momentum_lookback_seconds=180,
        objective_semantics="Raw feed counts; soul is dragons>=4, not verified elemental soul",
    )
    expected = score(fitted, test, columns)
    raw = []
    for match in parts["joined"]:
        seconds = clock(match["samples"], when(match["start"]))
        for sample, sec in zip(match["samples"], seconds):
            bg, rg = sample["blue"]["gold"], sample["red"]["gold"]
            if sec is None or sec < 0 or sample["state"] != "in_game":
                continue
            if not bg or not rg or bg <= 0 or rg <= 0:
                continue
            raw.append((sample["blue"], sample["red"]))
    assert len(raw) == n
    actual = np.array(
        [
            timeline.predict(
                model,
                float(row.seconds),
                float(row.blue_gold),
                float(row.red_gold),
                float(row.blue_elo),
                float(row.red_elo),
                objectives=raw[row.Index],
                momentum=float(row.momentum),
            )
            for row in test.itertuples()
        ]
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
    legacy = json.loads(timeline.LEGACY_MODEL_PATH.read_text())
    result = {
        "maps": int(test.game_id.nunique()),
        "metrics": metrics(test, expected),
        "delta_vs_v1": delta(test, expected, calls(legacy, test)),
        "max_export_error": float(np.max(np.abs(np.asarray(actual) - expected))),
    }
    args.out.write_text(json.dumps(model, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
