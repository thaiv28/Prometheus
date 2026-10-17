"""Offline export of the fixed market/model blend; never run in builds.

Input is calibration_audit.py's rebuilt.csv (one fresh-priced series per row).
Fits fixed C=1 symmetric logistic coefficients on older completed series only;
monthly snapshots reproduce the audit, plus the next full month for deployment.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.linear_model import LogisticRegression

from prometheus.market_blend import VERSION


def fit(frame, cutoff):
    train = frame[frame.result_available < cutoff]
    if len(train) < 300 or train.won.nunique() < 2:
        return None
    a = logit(np.clip(train.p.to_numpy(float), 1e-6, 1 - 1e-6))
    m = logit(np.clip(train.market.to_numpy(float), 1e-6, 1 - 1e-6))
    model = LogisticRegression(
        C=1, fit_intercept=False, solver="lbfgs", tol=1e-9, max_iter=200
    ).fit(np.column_stack([m, a - m]), train.won)
    return {
        "available_from": cutoff.isoformat(),
        "trained_through": train.result_available.max().isoformat(),
        "training_series": len(train),
        "market_slope": float(model.coef_[0, 0]),
        "gap_slope": float(model.coef_[0, 1]),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path, default=Path("prometheus/market_blend.json")
    )
    parser.add_argument(
        "--available-through", default=pd.Timestamp.now(tz="UTC").strftime("%Y-%m-01")
    )
    args = parser.parse_args()
    frame = pd.read_csv(args.input, parse_dates=["decision", "result_available"])
    if frame.event_ticker.duplicated().any():
        raise ValueError("duplicate training fixture")
    first = pd.Timestamp(frame.decision.min().strftime("%Y-%m-01"), tz="UTC")
    last = frame.result_available.max().ceil("D") + pd.offsets.MonthBegin(0)
    last = min(last, pd.Timestamp(args.available_through, tz="UTC"))
    models = [
        model
        for cutoff in pd.date_range(first, last, freq="MS", tz="UTC")
        if (model := fit(frame, cutoff))
    ]
    data = {
        "version": VERSION,
        "training_source_sha256": hashlib.sha256(args.input.read_bytes()).hexdigest(),
        "protocol": "Fresh 12h series; fixed C=1, no intercept; outcome available 24h after scheduled start. Monthly earlier-only fits. No build-time fitting.",
        "snapshots": models,
    }
    args.out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Wrote {len(models)} snapshots to {args.out}")


if __name__ == "__main__":
    main()
