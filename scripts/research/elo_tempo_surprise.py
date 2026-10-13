"""Causal conditional-duration evidence for Elo; opt-in research, never writes DB.

Run with VECLIB_MAXIMUM_THREADS=1 uv run python scripts/research/elo_tempo_surprise.py.
Freeze the three amplitudes before looking at 2022+: 0.05, 0.10, 0.175.
"""

import argparse
from collections import defaultdict
from pathlib import Path

import elo_variants as ev
import numpy as np
import pandas as pd

from prometheus import elo
from prometheus.evaluation import (
    cross_league_games,
    game_losses,
    other_league_games,
    out_of_year_league_probabilities,
    out_of_year_probabilities,
    paired_bootstrap,
)
from prometheus.types import INTERNATIONAL_LEAGUES

AMPLITUDES = (0.05, 0.10, 0.175)


class TempoExpectation:
    """Online ridge regression plus a shrunk league/year residual intercept.

    Prior: 30 min, no mismatch effect, 100 pseudo-games. Pooled regression forgets
    at 0.999 per game. League/year residual forgets at 0.99 and shrinks toward
    zero with 50 pseudo-games. At year changes the local intercept starts fresh.
    Only previous games enter predictions; result is never an explanatory input.
    """

    def __init__(self):
        self.xx = np.eye(2) * 100.0
        self.xy = np.zeros(2)
        self.local = defaultdict(lambda: np.zeros(2))

    @staticmethod
    def features(gap):
        return np.array([1.0, min(abs(gap) / 400, 2.0)])

    def predict(self, league, year, gap):
        x = self.features(gap)
        # Explicit 2x2 solve avoids a BLAS call inside every replayed game.
        a, b, c = self.xx[0, 0], self.xx[0, 1], self.xx[1, 1]
        d, e = self.xy
        beta = np.array([(c * d - b * e), (a * e - b * d)]) / (a * c - b * b)
        pooled = 1800.0 + x @ beta
        count, residual_sum = self.local[(league, year)]
        return float(np.clip(pooled + residual_sum / (50 + count), 900, 3600))

    def update(self, league, year, gap, duration):
        # Local correction observes the residual before this game's pooled update.
        x = self.features(gap)
        a, b, c = self.xx[0, 0], self.xx[0, 1], self.xx[1, 1]
        d, e = self.xy
        beta = np.array([(c * d - b * e), (a * e - b * d)]) / (a * c - b * b)
        residual = duration - (1800.0 + x @ beta)
        self.local[(league, year)] *= 0.99
        self.local[(league, year)] += np.array([1.0, residual])
        self.xx = 0.999 * self.xx + 0.001 * np.eye(2) * 100 + np.outer(x, x)
        self.xy = 0.999 * self.xy + x * (duration - 1800.0)


def surprise_score(duration, expected, amplitude):
    """Winner's score in [.65, 1]; loser always receives its complement.

    .825 is the old curve's midpoint: binary result evidence softened identically
    in every game. Faster-than-expected games increase that evidence. At zero
    amplitude this is a constant softened binary control, not published Elo.
    """
    if not 0 <= amplitude <= 0.175:
        raise ValueError("amplitude must be between 0 and .175")
    return float(
        np.clip(0.825 + amplitude * np.tanh((expected - duration) / 300.0), 0.65, 1)
    )


def replay(inputs, amplitude, records=False):
    """Replay actual candidate gaps; learn expectation after each completed game."""
    model = TempoExpectation()
    context = inputs.games[["league", "year", "gamelength"]].to_numpy()
    diagnostics = []

    def change(elo, opponent_elo, game_length, result):
        league, year, duration = context[int(game_length)]
        gap = elo - opponent_elo
        expected = model.predict(league, year, gap)
        score = surprise_score(duration, expected, amplitude)
        actual = score if result else 1 - score
        diagnostics.append((expected, duration, gap, score))
        model.update(league, year, gap, duration)
        return 20 * (actual - ev.expected_score(elo, opponent_elo))

    games = inputs.games[ev.ELO_COLUMNS].assign(gamelength=np.arange(len(context)))
    rows, offsets = elo.compute_elo_records(games, change, rosters=inputs.rosters)
    pre = rows.set_index(["gameid", "teamid"])["pre_match_elo"]
    diag = pd.DataFrame(diagnostics, columns=["expected", "duration", "gap", "score"])
    return (rows, offsets, diag) if records else (pre, diag)


def pair_frame(inputs, pre):
    g = inputs.games
    out = g[["gameid", "year", "league", "teamid", "opponent_teamid"]].copy()
    out["won"] = g["result"].to_numpy(dtype=int)
    mine = pre.reindex(pd.MultiIndex.from_arrays([g["gameid"], g["teamid"]]))
    theirs = pre.reindex(pd.MultiIndex.from_arrays([g["gameid"], g["opponent_teamid"]]))
    out["elo_live"] = mine.to_numpy() - theirs.to_numpy()
    return out


def all_scores(inputs, pre, years):
    """Repository curves and refitted Form/FORGE on identical held-out games."""
    major = ev._with_elo(inputs.frame, pre)
    major = major[major["year"].isin(years)].reset_index(drop=True)
    states = ev.variant_form_states(inputs, pre)
    relative = ev.em.out_of_year_form(major, states)
    major = ev.em.add_form(major, states, relative)
    ep = out_of_year_probabilities(major, "elo_live")
    fp = ev.em.forge_probabilities(major)
    output = {}
    for label in ev.TEST_SETS:
        keep = (major["test_set"] == label).to_numpy()
        for metric, p in (("Elo", ep), ("FORGE", fp)):
            output[(label, metric)] = (
                major.loc[keep, "gameid"].to_numpy(),
                game_losses(np.asarray(p)[keep], major.loc[keep, "won"])[
                    "log_loss"
                ].to_numpy(),
            )
    pairs = pair_frame(inputs, pre)
    pairs = pairs[pairs["year"].isin(years)].reset_index(drop=True)
    cross = cross_league_games(pairs, INTERNATIONAL_LEAGUES, ev.em.MAJORS)
    output[("Cross-league", "Elo")] = (
        cross["gameid"].to_numpy(),
        game_losses(out_of_year_probabilities(cross, "elo_live"), cross["won"])[
            "log_loss"
        ].to_numpy(),
    )
    other = other_league_games(pairs, INTERNATIONAL_LEAGUES, ev.em.MAJORS)
    other["form"] = ev.em.form_gap(
        relative, other["gameid"], other["teamid"], other["opponent_teamid"]
    )
    # Preserve the evaluator's separate full Elo and Form-covered FORGE cohorts.
    output[("Within other leagues", "Elo")] = (
        other["gameid"].to_numpy(),
        game_losses(out_of_year_league_probabilities(other), other["won"])[
            "log_loss"
        ].to_numpy(),
    )
    other = other[other["form"].notna()].reset_index(drop=True)
    output[("Within other leagues", "FORGE")] = (
        other["gameid"].to_numpy(),
        game_losses(
            out_of_year_probabilities(other, ["elo_live", "form"]), other["won"]
        )["log_loss"].to_numpy(),
    )
    return output


def comparison(base, candidate):
    rows = []
    for (section, metric), (keys, loss) in candidate.items():
        bkeys, bloss = base[(section, metric)]
        if not np.array_equal(keys, bkeys):
            raise ValueError("candidate and baseline cohorts differ")
        delta, lo, hi = paired_bootstrap(loss, bloss)
        rows.append(
            f"| {section} | {metric} | {len(keys):,} | {bloss.mean():.6f} | {loss.mean():.6f} | {delta:+.6f} [{lo:+.6f}, {hi:+.6f}] |"
        )
    return "\n".join(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_tempo_surprise.md")
    )
    args = parser.parse_args()
    inputs = ev.load_inputs()
    baseline, check = ev.reproduction_check(inputs)
    print(check, flush=True)
    train, test = ev.split_years(inputs.frame["year"].unique())
    pre_by_amplitude = {}
    tuning = []
    for amplitude in AMPLITUDES:
        pre, diagnostics = replay(inputs, amplitude)
        pre_by_amplitude[amplitude] = (pre, diagnostics)
        scores = ev.score(inputs, pre, years=train, forge=False)
        objective = scores.log_loss("elo_live", "Domestic").mean()
        tuning.append((objective, amplitude))
        print(
            f"Development amplitude={amplitude}: domestic Elo {objective:.6f}",
            flush=True,
        )
    objective, amplitude = min(tuning)
    print(
        f"Frozen choice: amplitude={amplitude}; computing held-out slices", flush=True
    )
    b = all_scores(inputs, baseline, test)
    pre, diagnostics = pre_by_amplitude[amplitude]
    candidate = all_scores(inputs, pre, test)
    control, _ = replay(inputs, 0)
    softened = all_scores(inputs, control, test)
    true_binary = ev.replay(inputs, lambda g: np.ones(len(g)))
    binary = all_scores(inputs, true_binary, test)
    header = "| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |\n|---|---|---:|---:|---:|---|"
    report = f"""# Conditional tempo surprise Elo

Opt-in research on base `a2f7d37`; no published defaults or DB scripts changed.

## Protocol

The frozen expectation model is online ridge on absolute candidate pregame Elo gap
(capped at 800 points) plus a shrunk league/year residual. Its prior is 30 minutes
with 100 pseudo-games; pooled forgetting is .999/game, league/year .99/game with
50-game shrinkage. Year resets use the current pooled prediction. It predicts
before observing duration, then updates. Expected durations are bounded at 15–60
minutes. Neither result nor a future game is a predictor. Winner/loser updates are
exact complements and K=20, rookie treatment and regional links are unchanged.

Winner score is `.825 + amplitude * tanh((expected_seconds - seconds)/300)`;
.825 is the published duration score midpoint. A fixed softened binary control
(amplitude zero) isolates replacing absolute duration from conditioning on tempo.
This is result evidence plus bounded conditional residual, not a predictive
feature taken from the completed game. The loser receives `1 - winner_score`.

Only amplitudes {list(AMPLITUDES)} were tried, selected on domestic Elo log loss
in {train[0]}–{train[-1]}. Choice: **{amplitude}**, objective {objective:.6f}.
Held-out score years: {test[0]}–{test[-1]}. The candidate and baseline are fairly
refit using the repository's out-of-year win curves and Form/FORGE fitting.
Within-other Elo uses the per-league curves; FORGE uses its pooled Elo+Form curve.
For the primary 2022+ table, calibrators and Form fit only other 2022+ seasons,
matching the existing margin harness held-out protocol rather than the stock
full-history benchmark. Do not compare its absolute losses with differently
calibrated experiments. The validation report includes full-history all-season
guards and an earlier-only sensitivity.
These fits follow the existing non-nested out-of-year protocol, not an earlier-only
calibration experiment. Earlier inspected years are historical development
evidence, not an untouched prospective test. Intervals resample paired game rows;
series/time dependence and multiple research comparisons limit interpretation.

Baseline reproduction: `{check.replace(chr(10), "; ")}`.

## Development scores

| Amplitude | Domestic Elo log loss (through 2021) |
|---:|---:|
"""
    report += "\n".join(f"| {a} | {o:.6f} |" for o, a in tuning)
    report += f"\n\n## Selected candidate, 2022 onward\n\n{header}\n{comparison(b, candidate)}\n"
    report += f"\n## Softened binary control, 2022 onward\n\n{header}\n{comparison(b, softened)}\n"
    report += f"\n## Binary result control (winner score 1), 2022 onward\n\n{header}\n{comparison(b, binary)}\n"
    report += f"\n## Conditional residual versus softened binary control\n\n{header}\n{comparison(softened, candidate)}\n"
    report += f"\nExpectation MAE over all replay games: {(diagnostics['duration'] - diagnostics['expected']).abs().mean():.1f} seconds.\n"
    diagnostics["year"] = inputs.games["year"].to_numpy()
    diagnostics["absolute_error"] = (
        diagnostics["duration"] - diagnostics["expected"]
    ).abs()
    diagnostics["winner_gap"] = np.where(
        inputs.games["result"], diagnostics["gap"], -diagnostics["gap"]
    )
    diagnostics["winner_loses_points"] = diagnostics["score"] < 1 / (
        1 + 10 ** (-diagnostics["winner_gap"] / 400)
    )
    report += "\n## Tempo diagnostics by era\n\n| Year | Mean duration (s) | Expectation MAE (s) | Winners losing update points |\n|---|---:|---:|---:|\n"
    for year, group in diagnostics.groupby("year"):
        report += f"| {year} | {group['duration'].mean():.1f} | {group['absolute_error'].mean():.1f} | {group['winner_loses_points'].mean():.1%} |\n"
    report += "\nA winning favorite can still lose Elo when its bounded soft result is below its pregame expected score, as in the published duration model. This is not a binary-only updater.\n"
    year_by_game = inputs.games.set_index("gameid")["year"]
    report += "\n## Selected candidate annual log-loss differences\n\n| Year | Slice | Metric | Delta |\n|---|---|---|---:|\n"
    for key, (keys, loss) in candidate.items():
        years_for_keys = year_by_game.reindex(keys).to_numpy()
        bloss = b[key][1]
        for year in test:
            mask = years_for_keys == year
            if mask.any():
                report += f"| {year} | {key[0]} | {key[1]} | {(loss[mask] - bloss[mask]).mean():+.6f} |\n"
    from elo_tempo_validation import clustered_comparison

    report += (
        "\n## Team-pair/day cluster sensitivity\n\nLeague × calendar day × unordered team pair is a conservative series proxy; distinct same-day series can be pooled.\n\n"
        + clustered_comparison(inputs, b, candidate)
        + "\n"
    )
    report += "\n## Decision\n\nKeep production defaults unchanged in this research branch. The conditional-tempo variant has a significant held-out within-other-league gain under the repository protocol. [Additional validation](elo_tempo_validation.md) tests whether conditional centering explains it and whether chronological/market checks support it. No production metric, tracked weight, or DB build algorithm was changed.\n"
    args.out.write_text(report)
    print(report, flush=True)


if __name__ == "__main__":
    main()
