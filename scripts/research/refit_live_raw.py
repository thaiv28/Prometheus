"""Refit the deployed objective + momentum model on every feed map before
`--train-before`, without the calibration layer (identity slope/intercept).

Same 20 inputs, C=1 and equal map weights as `freeze_live_objectives.py`; the
runtime is unchanged. Writes a candidate artifact (not `timeline.MODEL_PATH`)
and checks every later prediction against runtime inference, so
`evaluate_live.py --model <out>` scores it only on maps after its fit.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cand_followups import export
from cand_objectives import PRIMARY, add_columns, attach, objective_rows
from cand_temporal import momentum
from train_time_model import fit, metrics
from train_time_model_v2 import clock, partitions, when

from prometheus.live import timeline


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--train-before", default="2026-01-01")
    parser.add_argument(
        "--out", type=Path, default=Path("data/research/time_model_raw.json")
    )
    args = parser.parse_args()
    parts = partitions(Path("data/feed_timelines"), Path("data/gol_training"))
    data = parts["data"]
    n = int((data.source == "feed").sum())
    feed = momentum(
        attach(data[data.source == "feed"], objective_rows(parts["joined"]), n)
    )
    columns = timeline.STATE_FEATURES
    add_columns(feed, PRIMARY)
    at = pd.to_datetime(feed["date"], utc=True, format="mixed").dt.tz_convert(None)
    high = timeline.legacy_model()["supported_seconds"][1]
    feed = feed[feed.seconds <= high]
    at = at[feed.index]
    train, later = feed[at < args.train_before], feed[at >= args.train_before]
    # `fit` needs a calibration partition; its layer is discarded below.
    scaler, base, cal = fit(train, train, columns)
    cal.coef_[:] = 1.0
    cal.intercept_[:] = 0.0
    model = export((scaler, base, cal), columns)
    end = (pd.Timestamp(args.train_before) - pd.Timedelta(days=1)).date().isoformat()
    model.update(
        schema="time_objectives_momentum_v1",
        supported_seconds=[0, 2400],
        version=f"objectives-momentum-raw-{end}",
        mode="research",
        fit_through=end,
        trained_years=sorted(
            int(y) for y in at[at < args.train_before].dt.year.unique()
        ),
        calibration_period=None,
        test_from=args.train_before,
        subminute_validated=False,
        momentum_lookback_seconds=180,
        objective_semantics="Raw feed counts; soul is dragons>=4, not verified elemental soul",
        research_only=True,
    )
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
    expected = base.predict_proba(scaler.transform(later[columns]))[:, 1]
    actual = np.array(
        [
            timeline.predict(
                model,
                float(r.seconds),
                float(r.blue_gold),
                float(r.red_gold),
                float(r.blue_elo),
                float(r.red_elo),
                objectives=raw[r.Index],
                momentum=float(r.momentum),
            )
            for r in later.itertuples()
        ]
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(model, indent=2) + "\n")
    print(
        json.dumps(
            {
                "train_maps": int(train.game_id.nunique()),
                "later_maps": int(later.game_id.nunique()),
                "later": metrics(later, expected),
                "max_export_error": float(np.max(np.abs(actual - expected))),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
