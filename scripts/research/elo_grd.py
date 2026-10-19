"""Forecast-only Glicko g(RD) attenuation of unchanged published player Elo.

Fixed grid: lambda {0.25,0.5,1,2,4} x {both,independent}; lambda=0 is
published. Tune games-weighted domestic + other-league Elo loss through 2021
on chronological prefixes. Extend lambda once to .125 or 8 if the initial
winner is on that edge (both combinations); never extend the categorical axis.
Freeze before 2022+ scoring. Use existing leave-one-year-out curves/blends,
not earlier-only fits. Form uses unchanged published ratings throughout.

Usage: VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_grd.py
"""

import argparse
import datetime
import json
import time
from pathlib import Path

import elo_glicko as glicko
import numpy as np
import pandas as pd

from prometheus.evaluation import (
    cross_league_games,
    game_losses,
    other_league_games,
    out_of_year_league_probabilities,
    out_of_year_probabilities,
)
from prometheus.types import INTERNATIONAL_LEAGUES

ev, em, enp = glicko.ev, glicko.em, glicko.enp
LAMBDAS = (0.25, 0.5, 1, 2, 4)
COMBINATIONS = ("both", "independent")


def attenuation(variance, lam, combination):
    """Glicko g on the sum of team RMS variances (independent divides by five)."""
    divisor = 5 if combination == "independent" else 1
    return 1 / np.sqrt(
        1 + 3 * (np.log(10) / 400) ** 2 * lam * variance / divisor / np.pi**2
    )


def attenuated(records, lam, combination):
    """Synthetic pair-centered ratings carry only changed gaps into the harness."""
    r = records.set_index(["gameid", "teamid"])
    mean = r.pre_match_elo.groupby(level="gameid").transform("mean")
    variance = r.pre_match_rd.pow(2).groupby(level="gameid").transform("sum")
    if lam == 0:
        return r.pre_match_elo.copy()
    return mean + (r.pre_match_elo - mean) * attenuation(variance, lam, combination)


def predictions(inputs, pairs, pre, years, states):
    """Same seven harness sections; published Form inputs, refitted forecast curves."""
    frame = inputs.frame[inputs.frame.year.isin(years)].reset_index(drop=True)
    frame = em.add_form(ev._with_elo(frame, pre), states)
    out = {}
    for label, p in (
        ("Elo", out_of_year_probabilities(frame, "elo_live")),
        ("FORGE", em.forge_probabilities(frame)),
    ):
        for subset in ev.TEST_SETS:
            mask = (frame.test_set == subset).to_numpy()
            part = frame.loc[mask]
            out[f"{label}, {subset.lower()}"] = (
                part.gameid.to_numpy(),
                np.asarray(p)[mask],
                part.won.to_numpy(),
            )
    pair = enp.pair_games(pairs, pre)
    pair = pair[pair.year.isin(years)].reset_index(drop=True)
    other = other_league_games(pair, INTERNATIONAL_LEAGUES, em.MAJORS).reset_index(
        drop=True
    )
    cross = cross_league_games(pair, INTERNATIONAL_LEAGUES, em.MAJORS).reset_index(
        drop=True
    )
    out["Elo, other leagues"] = (
        other.gameid.to_numpy(),
        np.asarray(out_of_year_league_probabilities(other)),
        other.won.to_numpy(),
    )
    out["Elo, cross-league"] = (
        cross.gameid.to_numpy(),
        np.asarray(out_of_year_probabilities(cross, "elo_live")),
        cross.won.to_numpy(),
    )
    # Match other_forge_losses: Form weights on all other major-league years.
    relative = em.out_of_year_form(ev._with_elo(inputs.frame, pre), states)
    other = other.assign(
        form=em.form_gap(relative, other.gameid, other.teamid, other.opponent_teamid)
    )
    other = other[other.form.notna()].reset_index(drop=True)
    out["FORGE, other leagues"] = (
        other.gameid.to_numpy(),
        np.asarray(out_of_year_probabilities(other, ["elo_live", "form"])),
        other.won.to_numpy(),
    )
    return out


def losses(preds):
    return {
        k: (ids, game_losses(p, y).log_loss.to_numpy())
        for k, (ids, p, y) in preds.items()
    }


def calibration(base, selected, changed):
    lines = [
        "## Roster-change calibration\n",
        "Deciles are equal-count groups ordered by published probability within each section; selected uses identical games. Entries are probabilities (not percentages). Full-section fits are sliced after scoring.\n",
        "| Section | Decile | Games | Published predicted | Selected predicted | Actual |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for label, (ids, p, y) in base.items():
        keep = np.flatnonzero(np.isin(ids, list(changed)))
        order = keep[np.argsort(p[keep], kind="stable")]
        for i, group in enumerate(np.array_split(order, min(10, len(order))), 1):
            lines.append(
                f"| {label} | {i} | {len(group)} | {p[group].mean():.4f} | {selected[label][1][group].mean():.4f} | {y[group].mean():.4f} |"
            )
    return lines


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("docs/research/elo_grd.md"))
    args = ap.parse_args()
    audit = Path("data/research/elo_grd")
    audit.mkdir(parents=True, exist_ok=True)
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    train, test = ev.split_years(inputs.frame.year.unique())
    protocol = {
        "lambda": LAMBDAS,
        "combination": COMBINATIONS,
        "extension": "once at winning lambda edge: .125 or 8, both combinations",
        "train": train,
        "test": test,
        "objective": "games-weighted domestic + other-league Elo",
        "form": "unchanged published opponent adjustment",
    }
    (audit / "protocol.json").write_text(json.dumps(protocol, indent=2))
    short = glicko.tuning_inputs(inputs, train)
    short_records = ev.replay(
        short, ev.game_length_margin(), records=True, record_rd=True
    )
    tuning = []

    def tune(grid):
        for lam, combo in grid:
            pre = attenuated(short_records, lam, combo)
            loss = float(enp.objective(short, pairs, pre, train))
            tuning.append((loss, lam, combo))
            print(f"tune lambda={lam} {combo}: {loss:.8f}", flush=True)
        return min(tuning)

    base_objective = float(
        enp.objective(short, pairs, attenuated(short_records, 0, "both"), train)
    )
    initial = tune([(lam, c) for lam in LAMBDAS for c in COMBINATIONS])
    extra = (
        0.125 if initial[1] == LAMBDAS[0] else 8 if initial[1] == LAMBDAS[-1] else None
    )
    winner = tune([(extra, c) for c in COMBINATIONS]) if extra else initial
    (audit / "selection.json").write_text(
        json.dumps(
            {
                "protocol": protocol,
                "baseline_objective": base_objective,
                "tuning": tuning,
                "initial": initial,
                "selected": winner,
            },
            indent=2,
        )
    )
    print(f"Frozen selection: {winner}", flush=True)
    # No held-out scores before the frozen selection above.
    records = ev.replay(inputs, ev.game_length_margin(), records=True, record_rd=True)
    pre = attenuated(records, 0, "both")
    np.testing.assert_allclose(
        pre.sort_index(), inputs.db_pre_match.sort_index(), rtol=0, atol=1e-10
    )
    pd.testing.assert_frame_equal(
        short_records.reset_index(drop=True),
        records.iloc[: len(short_records)].reset_index(drop=True),
    )
    selected = attenuated(records, winner[1], winner[2])
    states = ev.variant_form_states(inputs, pre)
    print("Scoring held-out sections", flush=True)
    baseline = predictions(inputs, pairs, pre, test, states)
    variant = predictions(inputs, pairs, selected, test, states)
    changed = glicko.roster_changes(inputs)
    rows = glicko.comparison(losses(baseline), losses(variant))
    roster = glicko.comparison(losses(baseline), losses(variant), changed)
    guarded = rows + roster
    verdict = (
        "Worth it"
        if any(r[5] < 0 for r in rows) and not any(r[4] > 0 for r in guarded)
        else "Not worth it"
    )
    print(f"{verdict}: {rows}", flush=True)
    # Three paired full replays: only RD recording adds engine work.
    timing = {"published": [], "record_rd": []}
    for order in ((False, True), (True, False), (False, True)):
        for record_rd in order:
            tick = time.perf_counter()
            ev.replay(inputs, ev.game_length_margin(), record_rd=record_rd)
            timing["record_rd" if record_rd else "published"].append(
                time.perf_counter() - tick
            )
    lines = [
        f"# Elo forecast g(RD) ({datetime.date.today()})\n",
        "Research only. Ratings, player moves, league offsets and published forecasts remain unchanged. Base: main `00237c0`; opt-in RD telemetry only. Negative Δ log loss is better.\n",
        f"Tune {train[0]}–{train[-1]} on chronological prefixes; held out {test[0]}–{test[-1]}. Fixed grid λ ∈ {{.25,.5,1,2,4}} × {{both,independent}}. One lambda-edge extension to .125 or 8 (both combinations), no further extension. λ=0 is published. Combination both sums team RMS starter RD²; independent divides that sum by five. Gap multiplied by 1/sqrt(1+3(ln(10)/400)²λφ²/π²). Only the gap changes, with all curves/blends refit. Form's opponent adjustment and stat weights stay tied to published Elo.\n",
        f"Selected λ={winner[1]}, {winner[2]}; initial {initial[1:]} ; extension {extra}. Selection frozen in gitignored data/research/elo_grd/selection.json before held-out scoring. Baseline tuning objective {base_objective:.8f}. Both parameterizations depend only on λ/divisor, so overlapping effective settings are mathematically identical.\n",
        "Harness caveats: leave-one-year-out curves/blends within each partition, not expanding-year deployment fits. Other-league Form stat weights use all other major-league years, including tuning years, matching the existing harness. Paired individual-game bootstrap 95% CIs (no series clustering or multiplicity correction). Historical holdouts have already been viewed in prior research. Exact prefix/full record parity and DB rating parity checked.\n",
        "## Tuning\n",
        "| λ | Combination | Objective |",
        "|---:|---|---:|",
    ]
    lines += [f"| {lam} | {combo} | {loss:.8f} |" for loss, lam, combo in tuning]
    lines += ["\n## Held-out sections\n"] + glicko.table(rows)
    lines += [
        "\n## Roster-change slices\n",
        "Either team changed its known five starters since its last game; first appearances excluded. Full-section fits sliced after scoring.\n",
    ] + glicko.table(roster)
    lines += ["\n"] + calibration(baseline, variant, changed)
    lines += [
        "\n## Verdict\n",
        f"**{verdict}.** Requires a significant held-out targeted-section gain and no significantly worse section; roster slices also guarded conservatively. Every section is a target of forecast attenuation. No production forecast change. An optimum still at the extension boundary is unresolved, not bracketed.\n",
        "## Runtime and checks\n",
        f"Three paired full replays (AB/BA/AB): published median {np.median(timing['published']):.2f}s; RD recording median {np.median(timing['record_rd']):.2f}s. Samples: {timing}. Forecast attenuation is vectorized after replay and does not change the replay. No CI job/build work added; tests cover the small opt-in telemetry.\n",
        "Native evaluation and market evidence: see [elo_grd_native.md](elo_grd_native.md).\n",
    ]
    args.out.write_text("\n".join(lines) + "\n")
    (audit / "results.json").write_text(
        json.dumps(
            {
                "selected": winner,
                "rows": rows,
                "roster": roster,
                "timings": timing,
                "verdict": verdict,
            },
            indent=2,
        )
    )
    pd.to_pickle((inputs, pairs, records, states, selected), audit / "research.pkl")
    print(f"Wrote {args.out}", flush=True)


if __name__ == "__main__":
    main()
