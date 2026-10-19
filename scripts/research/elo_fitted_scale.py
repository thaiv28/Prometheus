"""Frozen: runs against `prometheus/elo.py` at commit 00237c0 (options since removed).

elo_fitted_scale.py: Elo's update curve on the fitted forecast scale, with K retuned.

Fixed before scoring: update slope in {ln(10)/400, .0070, .0085, .0100}
by K in {12, 16, 20, 24, 28}; additionally one tier design (.0085 in
majors/international events, .0103 in other domestic leagues), with the same K grid.
All published rookie, duration, league-offset and time-away rules stay on.
Tune on <=2021, minimizing games-weighted domestic + other-league Elo log loss,
then compare the chosen configurations on 2022+ only. Third design: only
non-major domestic updates change, slope {ln(10)/400, .0070, .0085, .0103}
x K {20,24,28,32}. Majors/international retain published slope and K; offset
rules are unchanged. One extension, selected using training only: add .0045 or
.0121 if the slope optimum is at its lower/upper edge, and K 16 or 36 if K is
at its lower/upper edge; score the expanded Cartesian grid's new cells once.

Uses elo_variants.load_inputs/replay/pregame_elos through the shared scoring
helpers. Forecast curves, Form opponent adjustment/weights and FORGE blends are
refit for each replay, following elo_k_tier/elo_new_players. Calibration is
out-of-year within each requested partition, not earlier-only deployment testing.
No DB, published weights, site or default behavior is changed.

Usage:
    VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_fitted_scale.py --out docs/research/elo_fitted_scale.md
"""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import elo_new_players as enp
import elo_variants as ev
import evaluate_metrics as em

from prometheus import elo
from prometheus.evaluation import (
    fit_win_curve,
    other_league_games,
    paired_bootstrap,
    shrunk_league_slopes,
)
from prometheus.types import INTERNATIONAL_LEAGUES

SLOPES = (elo.EXPECTED_SLOPE, 0.0070, 0.0085, 0.0100)
KS = (12, 16, 20, 24, 28)
OTHER_SLOPES = (elo.EXPECTED_SLOPE, 0.0070, 0.0085, 0.0103)
OTHER_KS = (20, 24, 28, 32)
TRAIN_LAST = 2021


def other_config(leagues, slope, k):
    """Keep major/international updates native; scale only domestic player moves."""
    other = set(leagues) - set(INTERNATIONAL_LEAGUES) - set(em.MAJORS)
    return {
        "league_slopes": dict.fromkeys(other, slope),
        "league_factors": dict.fromkeys(other, k / 20),
    }


def other_grid(leagues, slopes=OTHER_SLOPES, ks=OTHER_KS):
    return [
        (f"other slope {s:.8f}, K {k}", other_config(leagues, s, k))
        for s in slopes
        for k in ks
    ]


def extension_grid(leagues, best):
    """One predeclared boundary extension; no held-out losses enter this choice."""
    slope = next(iter(best[2]["league_slopes"].values()))
    k = 20 * next(iter(best[2]["league_factors"].values()))
    slopes, ks = list(OTHER_SLOPES), list(OTHER_KS)
    if slope == slopes[0]:
        slopes.insert(0, 0.0045)
    elif slope == slopes[-1]:
        slopes.append(0.0121)
    if k == ks[0]:
        ks.insert(0, 16)
    elif k == ks[-1]:
        ks.append(36)
    return [
        (label, kw)
        for label, kw in other_grid(leagues, slopes, ks)
        if label not in {label for label, _ in other_grid(leagues)}
    ]


def designs(leagues):
    tier = {
        league: 0.0103
        for league in leagues
        if league not in INTERNATIONAL_LEAGUES and league not in em.MAJORS
    }
    return {
        "Non-major only": other_grid(leagues),
        "Uniform": [
            (f"slope {s:.8f}, K {k}", {"expected_slope": s, "K": k})
            for s in SLOPES
            for k in KS
        ],
        "Tier": [
            (
                f"slopes .0085/.0103, K {k}",
                {"expected_slope": 0.0085, "league_slopes": tier, "K": k},
            )
            for k in KS
        ],
    }


def losses(inputs, pairs, pre, years):
    with mock.patch.dict(os.environ, {"REGIONAL_CALIBRATION": "0"}):
        scores = ev.score(inputs, pre, years=years)
    out = {}
    for metric in ("elo_live", "forge"):
        for section in ("Domestic", "International", "Roster change (<5 games)"):
            mask = (
                scores.mask(section)
                if section != "Roster change (<5 games)"
                else inputs.frame[inputs.frame.year.isin(years)]
                .reset_index(drop=True)
                .since_change.lt(5)
                .to_numpy()
            )
            out[(metric, section)] = (
                scores.games.loc[mask, ["gameid"]].reset_index(drop=True),
                scores.losses[metric]["log_loss"].to_numpy()[mask],
            )
    for key, fn in (
        (("elo_live", "Other leagues"), enp.other_losses),
        (("forge", "Other leagues"), enp.other_forge_losses),
        (("elo_live", "Cross-league"), enp.cross_losses),
    ):
        games, loss = (
            fn(inputs, pairs, pre, years)
            if fn is enp.other_forge_losses
            else fn(pairs, pre, years)
        )
        out[key] = (games[["gameid"]], loss)
    return out


def slope_diagnostics(inputs, pairs, pre, years):
    """Descriptive refits only; these fits never select a config or score a game."""
    frame = ev._with_elo(inputs.frame, pre)
    frame = frame[frame.year.isin(years)]
    curve = fit_win_curve(frame.elo_live, frame.won)
    p = curve(np.array([0.0, 1.0]))
    logits = np.log(p / (1 - p))
    other = other_league_games(
        enp.pair_games(pairs, pre), INTERNATIONAL_LEAGUES, em.MAJORS
    )
    other = other[other.year.isin(years)]
    pooled, slopes = shrunk_league_slopes(other.elo_live, other.won, other.league)
    return (
        float(logits[1] - logits[0]),
        pooled,
        min(slopes.values()),
        max(slopes.values()),
    )


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_fitted_scale.md")
    )
    args = ap.parse_args()
    started = time.perf_counter()
    inputs = ev.load_inputs()
    pairs = em.load_pair_games()
    years = sorted(inputs.frame.year.unique())
    train = [y for y in years if y <= TRAIN_LAST]
    test = [y for y in years if y > TRAIN_LAST]
    margin = ev.game_length_margin()
    tick = time.perf_counter()
    base, reproduction = ev.reproduction_check(inputs)
    reproduction_time = time.perf_counter() - tick
    print(reproduction, flush=True)
    # The DB may use an older international classification; baseline is current code.
    if inputs.db_domestic:
        base = ev.replay(inputs, margin)
    base_obj = enp.objective(inputs, pairs, base, train)
    lines = [
        f"# Elo fitted scale ({datetime.date.today().isoformat()})\n",
        "Generated by `scripts/research/elo_fitted_scale.py`. Research only; "
        "published Elo, DB and weight artifacts unchanged.\n",
        f"Tune {train[0]}–{train[-1]}; report {test[0]}–{test[-1]}. Fixed grid: "
        "slope {ln(10)/400, .0070, .0085, .0100} × K {12,16,20,24,28}; "
        "tier {.0085 majors/international, .0103 other domestic} × the same K grid. "
        "Third design: non-major domestic slope {ln(10)/400,.0070,.0085,.0103} "
        "× K {20,24,28,32}; major/international slope ln(10)/400 and K 20. "
        "One training-only edge extension: slope .0045/.0121, K 16/36 on the "
        "selected lower/upper edge, scoring all new Cartesian cells once. "
        "league_factors = K_other/20 scales only players; international callbacks "
        "and offset rules stay native (offset values can differ through prior ratings). "
        "The published slope is exactly ln(10)/400, not the rounded .00576. "
        "Tuning minimizes games-weighted domestic + within-other-league Elo log loss.\n",
        "All forecast curves are refit per replay: out-of-year Elo, shrunk "
        "per-league slopes, variant-adjusted Form and FORGE blends. As in the "
        "prior harness, held-out curves use other 2022+ seasons; these are "
        "rating-design comparisons, not an earlier-only deployment simulation. "
        "Other-league FORGE's Form weights follow the existing helper (all "
        "other years, including tuning years). International regional calibration "
        "is disabled only inside this experiment: its frozen artifact replaces "
        "the refitted probability with an old-scale slope. Both Elo and FORGE "
        "therefore use refitted curves, as the original research protocol did. "
        "The baseline means published Elo ratings with refitted forecast curves, "
        "not today's calibrated international calls.\n",
        "## Reproduction\n",
        reproduction + "\n",
        "## Fixed-grid tuning\n",
        "| Design | Configuration | Train log loss | Replay seconds |",
        "|---|---|---:|---:|",
        f"| Published | slope {elo.EXPECTED_SLOPE:.8f}, K 20 | {base_obj:.6f} | — |",
    ]
    chosen = {}
    runtimes = []
    for design, grid in designs(inputs.games.league.unique()).items():
        candidates = []
        for label, kw in grid:
            tick = time.perf_counter()
            pre = ev.replay(inputs, margin, **kw)
            elapsed = time.perf_counter() - tick
            runtimes.append(elapsed)
            obj = enp.objective(inputs, pairs, pre, train)
            candidates.append((obj, label, kw, pre))
            print(f"{design}: {label}: {obj:.6f}; replay {elapsed:.2f}s", flush=True)
            lines.append(f"| {design} | {label} | {obj:.6f} | {elapsed:.2f} |")
        if design == "Non-major only":
            best = min(candidates, key=lambda x: x[0])
            extension = extension_grid(inputs.games.league.unique(), best)
            lines.append(
                f"| Extension trigger | {best[1]}; {len(extension)} new cells | — | — |"
            )
            for label, kw in extension:
                tick = time.perf_counter()
                pre = ev.replay(inputs, margin, **kw)
                elapsed = time.perf_counter() - tick
                runtimes.append(elapsed)
                obj = enp.objective(inputs, pairs, pre, train)
                candidates.append((obj, label, kw, pre))
                print(
                    f"{design} extension: {label}: {obj:.6f}; replay {elapsed:.2f}s",
                    flush=True,
                )
                lines.append(
                    f"| {design} extension | {label} | {obj:.6f} | {elapsed:.2f} |"
                )
            # Predeclared K-only comparison: earlier report's k_major=20/k_other=28.
            # Reuse its replay when it was in the initial grid.
            k28_label = other_grid(
                inputs.games.league.unique(), [elo.EXPECTED_SLOPE], [28]
            )[0][0]
            k28 = next(c for c in candidates if c[1] == k28_label)
            k_only = min(
                (
                    c
                    for c in candidates
                    if next(iter(c[2]["league_slopes"].values())) == elo.EXPECTED_SLOPE
                ),
                key=lambda x: x[0],
            )
        chosen[design] = min(candidates, key=lambda x: x[0])
    winner = min(chosen, key=lambda d: chosen[d][0])
    lines += [
        f"\nOverall training winner: **{winner}: {chosen[winner][1]}**. "
        "All three design winners below were selected without held-out scores.\n",
        "## Held out\n",
        "Δ log loss = variant − published; negative is better. Paired game "
        "bootstrap, 95% intervals (shared helper, fixed seed, 2,000 replicates). "
        "Game IDs and ordering are asserted equal before comparison.\n",
        "| Section | Games | Published LL | Non-major only Δ (95% CI) | Uniform Δ (95% CI) | Tier Δ (95% CI) |",
        "|---|---:|---:|---|---|---|",
    ]
    baseline = losses(inputs, pairs, base, test)
    variants = {
        d: losses(inputs, pairs, result[3], test) for d, result in chosen.items()
    }
    guards = {d: [] for d in chosen}
    for key, (games, loss) in baseline.items():
        cells = []
        for design in chosen:
            vg, vl = variants[design][key]
            pd.testing.assert_frame_equal(
                games.reset_index(drop=True), vg.reset_index(drop=True)
            )
            delta = paired_bootstrap(vl, loss)
            guards[design].append((key, delta))
            cells.append(f"{delta[0]:+.6f} ({delta[1]:+.6f} to {delta[2]:+.6f})")
        lines.append(
            f"| {'Elo' if key[0] == 'elo_live' else 'FORGE'}, {key[1]} "
            f"| {len(loss):,} | {loss.mean():.6f} | " + " | ".join(cells) + " |"
        )
    lines += [
        "\n## Does slope add to K alone?\n",
        "Earlier [K by tier](elo_k_tier.md) includes k_major 20 / k_other 28 in "
        "its tuning grid, but its held-out table reports the selected 28/28 arm, "
        "not 20/28. Re-evaluate 20/28 here on identical games/current defaults "
        "rather than comparing losses across baseline versions. Also compare "
        "the best training-selected K-only arm from this grid.\n",
        f"K-only training winner: **{k_only[1]}**, objective {k_only[0]:.6f}; "
        f"20/28 control objective {k28[0]:.6f}.\n",
        "| Section | K20/28 − published (95% CI) | Non-major winner − K20/28 (95% CI) | Non-major winner − tuned K-only (95% CI) |",
        "|---|---|---|---|",
    ]
    k28_losses = losses(inputs, pairs, k28[3], test)
    konly_losses = (
        k28_losses if k_only[1] == k28[1] else losses(inputs, pairs, k_only[3], test)
    )
    for key, (games, loss) in baseline.items():
        cg, cl = k28_losses[key]
        kg, kl = konly_losses[key]
        pd.testing.assert_frame_equal(
            games.reset_index(drop=True), cg.reset_index(drop=True)
        )
        pd.testing.assert_frame_equal(
            games.reset_index(drop=True), kg.reset_index(drop=True)
        )
        nl = variants["Non-major only"][key][1]
        cells = [paired_bootstrap(a, b) for a, b in ((cl, loss), (nl, cl), (nl, kl))]
        lines.append(
            f"| {'Elo' if key[0] == 'elo_live' else 'FORGE'}, {key[1]} | "
            + " | ".join(f"{d:+.6f} ({lo:+.6f} to {hi:+.6f})" for d, lo, hi in cells)
            + " |"
        )
    lines.append(
        "\nRoster-change slice: either team's lineup changed fewer than five games ago, "
        "using existing backtest context, pooled domestic/international games. "
        "It reuses each section's refitted predictions; no extra replay or DB read.\n"
    )
    lines += [
        "\n## Refit scale diagnostics\n",
        "Descriptive pooled refits, not scoring curves: majors plus international "
        "Elo logistic coefficient with blue intercept; other-league pooled "
        "no-intercept slope and range of shrunk league slopes. The annual scoring "
        "curves above are fit out of year. Test-partition diagnostics see test "
        "labels and are never used to choose configurations.\n",
        "| Configuration | Partition | Major/international slope | Other pooled | Other shrunk range |",
        "|---|---|---:|---:|---|",
    ]
    for label, pre in [("Published", base)] + [
        (f"{d}: {r[1]}", r[3]) for d, r in chosen.items()
    ]:
        for partition, ys in (("Train", train), ("Test (descriptive)", test)):
            major, other, low, high = slope_diagnostics(inputs, pairs, pre, ys)
            lines.append(
                f"| {label} | {partition} | {major:.8f} | {other:.8f} | {low:.8f}–{high:.8f} |"
            )
    passes = [
        d
        for d, ds in guards.items()
        if all(
            any(key == target and delta[2] < 0 for key, delta in ds)
            for target in (("elo_live", "Other leagues"), ("elo_live", "Cross-league"))
        )
        and all(delta[1] <= 0 for _, delta in ds)
    ]
    lines += [
        "\n## Interpretation and limits\n",
        "Significance gate (significant Elo gains within other leagues AND cross-league, no significant regression in "
        f"any reported section): {', '.join(passes) if passes else 'no design passes'}. "
        "No shipping in this research change. Intervals spanning zero are inside "
        "the noise; individual game resampling does not account for series clusters "
        "or repeated historical research.\n",
        (
            "Recommendation: **drop these proposed update-scale changes**. "
            "No tuned design passes the significance rule.\n"
            if not passes
            else "Recommendation: **iterate** with earlier-only calibration and native "
            "release guards before considering a production change.\n"
        ),
        "The update targets duration-weighted actual scores, not binary wins: a "
        "30-minute winner scores .825. Its expected-score slope need not equal "
        "the forecast slope for binary wins, even at equilibrium. Increasing the "
        "update slope compresses ratings and can steepen the refitted forecast "
        "slope; matching the old forecast coefficient is not self-consistency. "
        "Rookie discounts and league-move bonuses also remain in fixed rating "
        "points, so changing slope/K is not a pure change of units.\n",
        f"Replay wall time: median {np.median(runtimes):.2f}s, range "
        f"{min(runtimes):.2f}–{max(runtimes):.2f}s ({len(runtimes)} grid replays, "
        f"{len(inputs.games):,} games each). Reproduction {reproduction_time:.2f}s. "
        f"Whole experiment {time.perf_counter() - started:.1f}s. "
        "Single process, VECLIB_MAXIMUM_THREADS=1; shared-machine load affects timing. "
        "No CI/publish/hourly work added.\n",
    ]
    text = "\n".join(lines) + "\n"
    args.out.write_text(text)
    print(text, flush=True)


if __name__ == "__main__":
    main()
