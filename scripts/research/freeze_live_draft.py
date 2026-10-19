"""Export the tested v2 live candidate, without refitting on test outcomes.

The live fit is supplied from live_draft_v3.py's v2_research.json (train 2024,
calibration 2025 H1). Draft prior coefficients fit only 2019–2024, as used for
calibration/test there. This artifact is shadow-only in the production worker.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import draft_walkforward as dw

from prometheus.live import timeline


def freeze(games, fitted):
    if fitted.get("draft") != "v2" or fitted.get("fit_through") != "2025-06-30":
        raise ValueError("expected tested v2 live fit through 2025 H1")
    if fitted["features"] != timeline.STATE_FEATURES + ["draft", "draft_time"]:
        raise ValueError("unexpected live draft features")
    train = games[games.year.between(2019, 2024)]
    prior = {}
    for name, cols in [
        ("base", ["forge_logit"]),
        ("draft", ["forge_logit", *dw.FEATURES]),
    ]:
        model = dw._fit(train, cols)
        prior[name] = {
            "intercept": float(model.intercept_[0]),
            **dict(zip(cols, model.coef_[0].tolist())),
        }
    return {
        **fitted,
        "schema": "time_objectives_draft_v2",
        "supported_seconds": [0, 2400],
        "version": "draft-v2-shadow-2026-10-18",
        "mode": "shadow",
        "draft_prior": prior,
        "fallback_model": json.loads(timeline.MODEL_PATH.read_text()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=Path, required=True)
    parser.add_argument("--fit", type=Path, required=True)
    parser.add_argument(
        "--out",
        type=Path,
        default=timeline.MODEL_PATH.with_name("time_model_draft_v2.json"),
    )
    args = parser.parse_args()
    model = freeze(pd.read_pickle(args.games), json.loads(args.fit.read_text()))
    model["input_sha256"] = {
        "games": hashlib.sha256(args.games.read_bytes()).hexdigest(),
        "fit": hashlib.sha256(args.fit.read_bytes()).hexdigest(),
    }
    args.out.write_text(json.dumps(model, indent=2) + "\n")


if __name__ == "__main__":
    main()
