"""Export the historical earlier-only fits; offline, never changes execution mode."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/research"))
import live_trading as research


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path, default=ROOT / "prometheus/live_map_blend.json"
    )
    parser.add_argument(
        "--as-of",
        help="Also fit an explicitly requested YYYY-MM-01 snapshot from earlier completed series",
    )
    args = parser.parse_args()
    digest = hashlib.sha256(args.data.read_bytes()).hexdigest()
    if digest != research.PIN:
        raise ValueError("unrecognized research cohort")
    rows, _ = research.prepare(research.el.load_data(args.data), args.db)
    _, fits = research.walk_forward(rows)
    if args.as_of:
        cutoff = research.pd.Timestamp(args.as_of, tz="UTC")
        if cutoff.day != 1 or cutoff != cutoff.normalize():
            raise ValueError("Snapshot cutoff must be the first day of a month")
        train = rows[rows.series_end + research.pd.Timedelta(hours=24) < cutoff]
        if train.series.nunique() < 100 or train.game.nunique() < 200:
            raise ValueError("Insufficient earlier completed series")
        x = research.np.column_stack(
            [research.el.logit(train.p_lag), research.el.logit(train.p)]
        )
        w = 1 / train.groupby("game").game.transform("size").to_numpy()
        model = research.LogisticRegression(
            C=1, fit_intercept=False, max_iter=2000
        ).fit(x, train.won, sample_weight=w)
        market = research.LogisticRegression(
            C=1, fit_intercept=False, max_iter=2000
        ).fit(x[:, :1], train.won, sample_weight=w)
        month = cutoff.strftime("%Y-%m")
        fits = [fit for fit in fits if fit["month"] != month]
        fits.append(
            {
                "month": month,
                "train_maps": train.game.nunique(),
                "train_series": train.series.nunique(),
                "latest_training_available": (
                    train.series_end.max() + research.pd.Timedelta(hours=24)
                ).isoformat(),
                "market_weight": model.coef_[0, 0],
                "model_weight": model.coef_[0, 1],
                "market_only_weight": market.coef_[0, 0],
            }
        )
        fits.sort(key=lambda fit: fit["month"])
    artifact = {
        "version": "live-map-30s-v1",
        "market_input": "last_trade",
        "series_shift": False,
        "model_sha256": hashlib.sha256(
            research.timeline.MODEL_PATH.read_bytes()
        ).hexdigest(),
        "input_sha256": digest,
        "db_sha256": hashlib.sha256(args.db.read_bytes()).hexdigest(),
        "snapshots": fits,
    }
    args.out.write_text(json.dumps(artifact, indent=2, default=float) + "\n")
    print(f"Exported {len(fits)} earlier-only monthly snapshots")


if __name__ == "__main__":
    main()
