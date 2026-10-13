"""Rebuild published calls on a saved priced market cohort; never reuse old odds.

Used when market lists/candlesticks are incomplete but frames.pkl still preserves
settled outcomes and prices. Both base and head must use the same cache snapshot.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import evaluate_markets as markets

from prometheus import form, schedule


def rebuild(frame, before, series):
    out = frame.copy()
    probabilities, methods = [], []
    for row in frame.itertuples(index=False):
        ratings = before(row.start.date())
        probability, method = schedule.game_probability(
            ratings.loc[row.ours1], ratings.loc[row.ours2]
        )
        probabilities.append(probability)
        methods.append(method)
    out["p_game"], out["method"] = probabilities, methods
    if series:
        out["p_series"] = [
            schedule.series_probability(p, row.best_of, schedule.SERIES_RHO[row.major])
            for p, row in zip(probabilities, frame.itertuples(index=False))
        ]
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache", type=Path, default=Path("data/markets/frames.pkl"))
    parser.add_argument("--dump", type=Path, required=True)
    args = parser.parse_args()
    series, maps, counts, _ = pd.read_pickle(args.cache)
    states = form.form_states(form.opponent_adjust(form.load_form_games()))
    before = schedule.RatingsBefore(states)
    print(f"Rebuilding {len(series)} series and {len(maps)} map-1 calls", flush=True)
    series = rebuild(series, before, True)
    maps = rebuild(maps, before, False)
    markets.write_dump(series, maps, counts, args.dump)
    print(
        f"Rebuilt {len(before)} cutoff dates; prices and outcomes unchanged", flush=True
    )


if __name__ == "__main__":
    main()
