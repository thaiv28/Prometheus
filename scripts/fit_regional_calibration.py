"""Fit/export frozen regional calibration offline; never runs in a site build.

Requires the international diagnostic's fixed cohort/provenance and a private DB.
Latest coefficients are the last evaluated event's pre-event fit, not a fit on a
possibly incomplete current tournament. Rerun validation before publishing updates.
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "research"))
import regional_correction as rc


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("prometheus/regional_calibration.json")
    )
    args = parser.parse_args()
    games, _, _, _, _, _ = rc.load_data(Path("data/international_markets"))
    _, models = rc.event_predictions(games, penalty=4.0, half_life=float("inf"))
    slope = rc.schedule.CROSS_REGION_ELO_WEIGHT
    by_date = {}
    events = []
    for model in models:
        part = games[games.event_id == model["event_id"]]
        available = (
            (pd.Timestamp(model["trained_through"]) + pd.Timedelta(days=1))
            .date()
            .isoformat()
            if model["trained_through"]
            else None
        )
        events.append(
            {
                "event": part.iloc[0].league,
                "start": str(part.day.min().date()),
                "end": str(part.day.max().date()),
                "model": available if model["n_train"] >= 50 else None,
            }
        )
        if model["n_train"] < 50:
            continue
        snapshot = {
            "available_from": available,
            "trained_through": model["trained_through"],
            "n_train": model["n_train"],
            "slope": slope * model["alpha"],
            "effects": model["effects"],
        }
        if available in by_date:
            assert by_date[available] == snapshot
        by_date[available] = snapshot
    snapshots = sorted(by_date.values(), key=lambda m: m["available_from"])
    # OE labels regional EWC qualifying games as EWC. Main-event dates are metadata,
    # not numeric predictors or market outcomes.
    series = pd.read_csv(
        "data/international_markets/series.csv", parse_dates=["game_date"]
    )
    ewc = series[series.league == "EWC"].game_date
    artifact = {
        "version": "regional-v1",
        "scope": "international events only; qualifiers/regional finals excluded",
        "penalty": 4.0,
        "tune_end": 2021,
        "base_slope": slope,
        "price_cohort_sha256": hashlib.sha256(
            Path("data/markets/frames.pkl").read_bytes()
        ).hexdigest(),
        "data_through": str(games.day.max().date()),
        "event_windows": {"EWC-2026": [str(ewc.min().date()), str(ewc.max().date())]},
        "snapshots": snapshots,
        "events": events,
    }
    args.out.write_text(json.dumps(artifact, indent=2, allow_nan=False) + "\n")
    print(
        f"Wrote {len(snapshots)} snapshots; latest fit through {snapshots[-1]['trained_through']}"
    )


if __name__ == "__main__":
    main()
