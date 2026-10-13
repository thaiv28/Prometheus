"""Finish fixed-duration validation against an explicitly frozen power baseline.

Neither replay uses the current production winner-score default, so the old/new
comparison remains reproducible after adoption. Price inputs are a private cache.
"""

import argparse
from pathlib import Path

import elo_tempo_surprise as tempo
import elo_tempo_validation as validation
import elo_variants as ev
import numpy as np
import pandas as pd

from prometheus import elo
from prometheus.evaluation import game_losses

HEADER = validation.HEADER


def power_scores(games):
    seconds = games["gamelength"].to_numpy(dtype=float)
    return 0.65 + 0.35 / (1 + (seconds / 1800) ** 3)


def fixed_scores(games):
    seconds = games["gamelength"].to_numpy(dtype=float)
    return 0.825 + 0.175 * np.tanh((1800 - seconds) / 300)


def replay(inputs, scorer):
    games = inputs.games[ev.ELO_COLUMNS].assign(gamelength=scorer(inputs.games))
    records, offsets = elo.compute_elo_records(
        games, ev.margin_elo_change, rosters=inputs.rosters
    )
    return records.set_index(["gameid", "teamid"])["pre_match_elo"], records, offsets


def map_probabilities(frame, states, latest, weights):
    """Best-of one returns single-game probability, independent of series rho."""
    form_weights, league_curves, forge_weights = weights
    return validation.market_calls(
        frame.assign(best_of=1),
        states,
        latest,
        form_weights,
        forge_weights,
        league_curves,
    )


def market_scores(frame, probability, methods):
    loss = game_losses(probability, frame["won1"])["log_loss"].to_numpy()
    slices = {
        "All map 1": np.ones(len(frame), dtype=bool),
        "Same major league map 1": (methods == "forge") & frame["major"].to_numpy(),
        "Same other league map 1": (methods == "forge") & ~frame["major"].to_numpy(),
        "Cross-league map 1": methods == "elo-cross",
    }
    return {
        (label, "Map 1"): (frame.index.to_numpy()[keep], loss[keep])
        for label, keep in slices.items()
        if keep.any()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/duration_curve_gates.md")
    )
    parser.add_argument(
        "--market-cache", type=Path, default=Path("data/markets/frames.pkl")
    )
    args = parser.parse_args()
    inputs = ev.load_inputs()
    _, test = ev.split_years(inputs.frame["year"].unique())
    models = []
    forecasts = []
    chronological = []
    for name, scorer in (("power", power_scores), ("fixed", fixed_scores)):
        print(f"Replay and score {name}", flush=True)
        pre, records, offsets = replay(inputs, scorer)
        forecasts.append(tempo.all_scores(inputs, pre, test))
        chronological.append(validation.chronological_scores(inputs, pre, test))
        models.append((pre, records, offsets))
    for result in (forecasts, chronological):
        for key in result[0]:
            np.testing.assert_array_equal(result[0][key][0], result[1][key][0])
    text = "# Fixed duration curve completion gates\n\nThe exact power baseline and fixed tanh candidate are frozen in this runner, independent of production defaults. No tuning is performed. These are retrospective checks on previously examined years. Negative loss deltas improve forecasts.\n\n"
    text += "## 2022+ game clustering\n\nLeague × unordered team pair × calendar day clusters preserve maps from the same series together.\n\n"
    text += validation.clustered_comparison(inputs, forecasts[0], forecasts[1]) + "\n"
    text += "\n## Earlier-only 2022+ clustering\n\nInner Form scores and outer calibrators use earlier years only. Raw-data imputation and first-year state limitations are inherited equally.\n\n"
    text += (
        validation.clustered_comparison(inputs, chronological[0], chronological[1])
        + "\n"
    )
    _, maps, _, _ = pd.read_pickle(args.market_cache)
    maps = maps[maps["start"].map(lambda value: value.year >= 2025)].reset_index(
        drop=True
    )
    outcomes, calls = [], []
    methods = None
    for name, (pre, records, offsets) in zip(("power", "fixed"), models):
        print(f"Frozen <=2024 map-1 calls {name}", flush=True)
        states = ev.variant_form_states(inputs, pre)
        weights = validation.fitted_weights(inputs, pre, states, 2024)
        p, routing = map_probabilities(
            maps, states, validation.memory_latest(records, offsets), weights
        )
        assert np.isfinite(p).all()
        if methods is not None:
            np.testing.assert_array_equal(methods, routing)
        methods = routing
        calls.append(p)
        outcomes.append(market_scores(maps, p, routing))
    text += "\n## Cached map-1 markets, 2025 onward\n\nBoth models' weights are fitted through 2024 only. Calls use the day-before cutoff and latest main roster. Cached old predictions are unused; no prices are fetched.\n\n"
    text += HEADER + "\n" + tempo.comparison(outcomes[0], outcomes[1]) + "\n"
    artifact = Path("data/duration_curve_gates")
    artifact.mkdir(parents=True, exist_ok=True)
    saved = maps[["event_ticker", "start", "team1", "won1"]].copy()
    saved["baseline"] = calls[0]
    saved["candidate"] = calls[1]
    saved.to_csv(artifact / "map_predictions.csv", index=False)
    pd.to_pickle((forecasts, chronological), artifact / "game_losses.pkl")
    args.out.write_text(text)
    print(text, flush=True)


if __name__ == "__main__":
    main()
