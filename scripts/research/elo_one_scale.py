"""Fixed-protocol research: one Elo scale with per-event-tier learning rates.

Run with UV_NO_SYNC=1 VECLIB_MAXIMUM_THREADS=1 uv run python
scripts/research/elo_one_scale.py. No published artifacts are changed.
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
    FORWARD_START,
    cross_league_games,
    fit_win_curve,
    game_losses,
    other_league_games,
    paired_bootstrap,
    series_ids,
    shrunk_league_slopes,
)
from prometheus.types import INTERNATIONAL_LEAGUES

S0 = elo.EXPECTED_SLOPE
PROTOCOL = """## Protocol (fixed before scoring)

M = domestic major events (`evaluate_metrics.MAJORS`), O = other domestic
events, I = `INTERNATIONAL_LEAGUES`; s0 = ln(10)/400. Published updates use
s0 in M/I and .0065 in O, K=20. One-scale updates and RD information use s0
in every event (`other_league_slope=None`); a row-ordered callback uses K_M
in M/I and K_O in O. Duration, RD, rookie discount, move-down bonus and home
rules remain published. `league_share` is passed to `compute_elo_records`.

Train <=2021, held out 2022+; assert every input date is before 2026-10-20.
Regional calibration is disabled (`REGIONAL_CALIBRATION=0`) throughout.
Stage 0 reproduces published DB pre-match ratings and measures train/held-out
c_M, c_O, c_X. These are fitted slopes divided by update slope: domestic-major
`fit_win_curve`, pooled `shrunk_league_slopes` within other leagues, and
`fit_win_curve` on `cross_league_games`, respectively (X denominator s0).
These descriptive partition-wide fits are separate from scoring curves.

Stage 1: K_M {16,20,24} × K_O {20,24,28,32,40,48}, share .5; minimize
`elo_new_players.objective` (games-weighted domestic + within-other Elo loss,
refitting curves). Report train objective and all three c ratios. If the initial
winner has K_O=48, score K_O {56,64} at its selected K_M once and reselect.
Stage 2: at the selected Ks, share {.5,.75,1,1.5,2}; minimize train cross-league
refit loss among settings within +.0005 of stage 1's best objective.

Stage 3 has three forecast arms: published refit (P), chosen one-scale refit
(C), and chosen one-scale no-curve. Also score published no-curve as a diagnostic.
Domestic majors and international: Elo and FORGE (`elo_variants.score`, refit
blend); cross-league: Elo (`cross_losses`); within other leagues: Elo per-league
refit (`other_losses`) and FORGE (`other_forge_losses`). No-curve Elo is
sigmoid(u × gap), without intercept, on exactly the refit games; C uses s0
throughout, P uses .0065 only within other leagues and s0 elsewhere.

Refit scoring is out-of-year within the requested partition, not earlier-only
deployment testing. Other-league FORGE's helper fits Form weights on all other
years, including training years. All Form opponent adjustments use replay ratings.
Differences: (a) C refit − P refit on every section; (b) C no-curve − P refit
on Elo sections; (c) C no-curve − C refit and P no-curve − P refit. Paired 95%
bootstrap intervals use 2,000 replicates, seed 0, clustered by `series_ids` from
the same games' dates and unordered team pairs (12-hour gaps).

Metric-change gate: a significant gain on a targeted section, no section
significantly worse; an added parameter also requires a mean gain >=.0005.
No-curve simplification: every Elo section's (b) upper interval <+.0005.
Verdicts are conclusive when the corresponding gate passes or a significant
regression establishes failure; otherwise inconclusive. No held-out result
selects a configuration.
"""


def replay(inputs, km, ko, share):
    """Consume exactly one event-tier K per engine input row; RD also uses s0."""
    games = inputs.games[ev.ELO_COLUMNS].assign(
        gamelength=ev.winner_scores(inputs, ev.game_length_margin())
    )
    major_or_event = games.league.isin([*em.MAJORS, *INTERNATIONAL_LEAGUES])
    ks = iter(np.where(major_or_event, km, ko))

    def change(**args):
        return ev.margin_elo_change(**args, K=next(ks), expected_slope=S0)

    out, _ = elo.compute_elo_records(
        games,
        change,
        rosters=inputs.rosters,
        other_league_slope=None,
        league_share=share,
    )
    assert next(ks, None) is None
    return out.set_index(["gameid", "teamid"])["pre_match_elo"]


def fitted_slope(frame):
    p = fit_win_curve(frame.elo_live, frame.won)(np.array([0.0, 1.0]))
    logits = np.log(p / (1 - p))
    return float(logits[1] - logits[0])


def calibration(inputs, pairs, pre, years, published=False):
    frame = ev._with_elo(inputs.frame, pre)
    domestic = frame[frame.year.isin(years) & frame.test_set.eq("Domestic")]
    paired = enp.pair_games(pairs, pre)
    other = other_league_games(paired, INTERNATIONAL_LEAGUES, em.MAJORS)
    other = other[other.year.isin(years)]
    cross = cross_league_games(paired, INTERNATIONAL_LEAGUES, em.MAJORS)
    cross = cross[cross.year.isin(years)]
    pooled, _ = shrunk_league_slopes(other.elo_live, other.won, other.league)
    return (
        fitted_slope(domestic) / S0,
        pooled / (elo.OTHER_LEAGUE_SLOPE if published else S0),
        fitted_slope(cross) / S0,
    )


def held_losses(inputs, pairs, pre, years, published=False):
    scored = ev.score(inputs, pre, years=years, forge=True)
    frame = ev._with_elo(inputs.frame, pre)
    frame = frame[frame.year.isin(years)].reset_index(drop=True)
    assert np.array_equal(frame.gameid, scored.games.gameid)
    out = {}
    for section in ("Domestic", "International"):
        mask = scored.mask(section)
        games = frame.loc[mask].rename(
            columns={"blue_id": "teamid", "red_id": "opponent_teamid"}
        )
        for metric in ("elo_live", "forge"):
            out[(section, metric)] = (
                games,
                scored.losses[metric].log_loss.to_numpy()[mask],
            )
    for section, metric, fn in (
        ("Cross-league", "elo_live", enp.cross_losses),
        ("Other leagues", "elo_live", enp.other_losses),
        ("Other leagues", "forge", enp.other_forge_losses),
    ):
        out[(section, metric)] = (
            fn(inputs, pairs, pre, years)
            if metric == "forge"
            else fn(pairs, pre, years)
        )
    result = {}
    for (section, metric), (games, loss) in out.items():
        assert np.isfinite(loss).all()
        u = elo.OTHER_LEAGUE_SLOPE if published and section == "Other leagues" else S0
        no_curve = (
            game_losses(
                1 / (1 + np.exp(-u * games.elo_live)), games.won
            ).log_loss.to_numpy()
            if metric == "elo_live"
            else None
        )
        result[(section, metric)] = (games.reset_index(drop=True), loss, no_curve)
    return result


def fmt(delta):
    return f"{delta[0]:+.6f} ({delta[1]:+.6f}, {delta[2]:+.6f})"


def ratios(values):
    return " | ".join(f"{v:.4f}" for v in values)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("docs/research/elo_one_scale.md"))
    args = ap.parse_args()
    started = time.perf_counter()
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    for frame in (inputs.games, inputs.frame, inputs.form_games, pairs):
        assert pd.to_datetime(frame.date).max() < pd.Timestamp(FORWARD_START)
    train, test = ev.split_years(inputs.frame.year.unique())
    timings = []
    lines = [f"# One Elo scale ({datetime.date.today().isoformat()})\n", PROTOCOL]
    with mock.patch.dict(os.environ, {"REGIONAL_CALIBRATION": "0"}):
        tick = time.perf_counter()
        base, reproduction = ev.reproduction_check(inputs)
        elapsed = time.perf_counter() - tick
        timings.append(elapsed)
        assert not inputs.db_domestic, "protocol requires today's DB classification"
        print(
            f"Published replay: {elapsed:.2f}s; " + reproduction.replace("\n", "; "),
            flush=True,
        )
        lines += [
            "\n## Stage 0: published diagnostics\n",
            reproduction + "\n",
            f"Train {min(train)}–{max(train)}; held out {min(test)}–{max(test)}. "
            f"Latest input: {pd.to_datetime(inputs.games.date).max()}.\n",
            "| Partition | c_M | c_O | c_X |",
            "|---|---:|---:|---:|",
        ]
        for name, years in (("Train", train), ("Held out", test)):
            lines.append(
                f"| {name} | {ratios(calibration(inputs, pairs, base, years, True))} |"
            )
        lines += [
            "\n## Stage 1: learning rates\n",
            "| K_M | K_O | Train objective | c_M | c_O | c_X | Replay seconds |",
            "|---:|---:|---:|---:|---:|---:|---:|",
        ]
        candidates = []

        def candidate(km, ko, share, stage):
            tick = time.perf_counter()
            pre = replay(inputs, km, ko, share)
            elapsed = time.perf_counter() - tick
            timings.append(elapsed)
            obj = enp.objective(inputs, pairs, pre, train)
            cal = calibration(inputs, pairs, pre, train)
            cross = (
                enp.cross_losses(pairs, pre, train)[1].mean() if stage == 2 else None
            )
            print(
                f"Stage {stage}: K_M={km}, K_O={ko}, share={share:g}; "
                f"objective={obj:.6f}; replay {elapsed:.2f}s",
                flush=True,
            )
            return {
                "km": km,
                "ko": ko,
                "share": share,
                "pre": pre,
                "obj": obj,
                "cal": cal,
                "cross": cross,
                "seconds": elapsed,
            }

        def stage1(km, ko):
            row = candidate(km, ko, 0.5, 1)
            candidates.append(row)
            lines.append(
                f"| {km} | {ko} | {row['obj']:.6f} | {ratios(row['cal'])} | {row['seconds']:.2f} |"
            )

        for km in (16, 20, 24):
            for ko in (20, 24, 28, 32, 40, 48):
                stage1(km, ko)
        best = min(candidates, key=lambda r: r["obj"])
        if best["ko"] == 48:
            extension_km = best["km"]
            for ko in (56, 64):
                stage1(extension_km, ko)
        best = min(candidates, key=lambda r: r["obj"])
        lines += [
            f"\nSelected K_M={best['km']}, K_O={best['ko']}; objective {best['obj']:.6f}.\n",
            "\n## Stage 2: offset learning\n",
            "| Share | Train cross loss | Train objective | c_X | Eligible | Replay seconds |",
            "|---:|---:|---:|---:|---|---:|",
        ]
        offsets = []
        for share in (0.5, 0.75, 1.0, 1.5, 2.0):
            row = candidate(best["km"], best["ko"], share, 2)
            row["eligible"] = row["obj"] <= best["obj"] + 0.0005
            offsets.append(row)
            lines.append(
                f"| {share:g} | {row['cross']:.6f} | {row['obj']:.6f} | "
                f"{row['cal'][2]:.4f} | {row['eligible']} | {row['seconds']:.2f} |"
            )
        chosen = min((r for r in offsets if r["eligible"]), key=lambda r: r["cross"])
        lines += [
            f"\nSelected share={chosen['share']:g} at K_M={chosen['km']}, K_O={chosen['ko']}.\n",
            "\n## Stage 3: held out\n",
            "Negative differences favor the first arm; parentheses are 95% intervals.\n",
            "| Section | Games | P refit LL | C refit LL | (a) C refit − P refit | (b) C native − P refit | (c) C native − C refit | (c) P native − P refit | (b) pass |",
            "|---|---:|---:|---:|---|---|---|---|---|",
        ]
        p_losses = held_losses(inputs, pairs, base, test, True)
        c_losses = held_losses(inputs, pairs, chosen["pre"], test)
        gate_a, gate_b = [], []
        for key, (pg, pl, pn) in p_losses.items():
            cg, cl, cn = c_losses[key]
            identity = ["gameid", "date", "teamid", "opponent_teamid", "won"]
            pd.testing.assert_frame_equal(pg[identity], cg[identity])
            clusters = series_ids(pg.date, pg.teamid, pg.opponent_teamid)

            def delta(a, b, clusters=clusters):
                return paired_bootstrap(a, b, clusters=clusters)

            a = delta(cl, pl)
            gate_a.append((key, a))
            cells = [fmt(a)]
            if cn is not None:
                b = delta(cn, pl)
                gate_b.append((key, b))
                cells += [
                    fmt(b),
                    fmt(delta(cn, cl)),
                    fmt(delta(pn, pl)),
                    str(b[2] < 0.0005),
                ]
            else:
                cells += ["—"] * 4
            lines.append(
                f"| {key[0]}, {'Elo' if key[1] == 'elo_live' else 'FORGE'} | {len(pl):,} | "
                f"{pl.mean():.6f} | {cl.mean():.6f} | " + " | ".join(cells) + " |"
            )
        lines += [
            "\n| Held-out replay | c_M | c_O | c_X |",
            "|---|---:|---:|---:|",
            f"| P | {ratios(calibration(inputs, pairs, base, test, True))} |",
            f"| C | {ratios(calibration(inputs, pairs, chosen['pre'], test))} |",
            "\n## Verdict\n",
        ]
        gains = [k for k, d in gate_a if d[2] < 0 and d[0] <= -0.0005]
        worse = [k for k, d in gate_a if d[1] > 0]
        passes_a = bool(gains) and not worse
        passes_b = all(d[2] < 0.0005 for _, d in gate_b)
        fails_b = [k for k, d in gate_b if d[1] >= 0.0005]
        lines += [
            f"Metric-change gate: **{'conclusive: passes' if passes_a else 'conclusive: fails' if worse else 'inconclusive'}**. "
            f"Significant gains >=.0005: {gains or 'none'}; significant regressions: {worse or 'none'}.\n",
            f"No-curve C non-inferiority: **{'conclusive: passes' if passes_b else 'conclusive: fails' if fails_b else 'inconclusive'}**. "
            f"{sum(d[2] < 0.0005 for _, d in gate_b)}/{len(gate_b)} Elo sections have upper CI <+.0005; "
            f"sections with lower CI >=+.0005: {fails_b or 'none'}.\n",
        ]
    total = time.perf_counter() - started
    lines.append(
        f"Runtime: {len(timings)} replays, total replay {sum(timings):.2f}s "
        f"(range {min(timings):.2f}–{max(timings):.2f}s); total {total:.2f}s. "
        "Existing helpers ran against today's engine without compatibility fixes. "
        "No published code, weights, defaults or CI changed.\n"
    )
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Report: {args.out}; total {total:.2f}s", flush=True)


if __name__ == "__main__":
    main()
