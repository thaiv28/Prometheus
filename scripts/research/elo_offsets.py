"""Fixed-protocol offset-evidence research; never writes DB tables or weights."""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit, logit

sys.path.insert(0, str(Path(__file__).resolve().parent))
import elo_one_scale as eos

from prometheus import regional_calibration
from prometheus.evaluation import (
    FORWARD_START,
    cross_league_games,
    fit_win_curve,
    game_losses,
    other_league_games,
    out_of_year_probabilities,
    paired_bootstrap,
    series_ids,
)
from prometheus.types import INTERNATIONAL_LEAGUES

enp, ev, em = eos.enp, eos.ev, eos.em
PROTOCOL = """## Protocol (fixed before scoring)

Train <=2021, held out 2022+; every input date must precede 2026-10-20.
No held-out result selects an arm. Published duration, RD, rookie discount,
home rules, international league share and move-down bonus (25) stay fixed.
Calibration is off (`REGIONAL_CALIBRATION=0`) in every replay/refit.

Stage 1: link mode {plain, team} × link share {0,.125,.25,.5} × transfer
share {0,.1,.25,.5}, transfer games 20; share zero is replayed once per
transfer share (28 unique cells). Minimize train cross-league refit Elo log
loss (`elo_new_players.cross_losses`) among cells whose train domestic +
within-other Elo objective (`objective`) is within +.0005 of published.
Plain links move league offsets, including player conversion. Team links
move separate offsets included in team/main and stored player ratings and
history, but excluded from player conversion in seat(). Transfers learn from
scaled player updates for the next 20 games played in the destination home
league, including international appearances; a subsequent home change resets
the window. Only known non-international source/destination leagues qualify.
A gain in B moves A's offset up and B's down. The original transfer arm
had a feedback bug: lowering B also lowered the mover's effective rating.
Corrected evidence adds the same adjustment to the mover's own rating,
canceling their own evidence offset move, for every mover in the game.

Stage 1b (predeclared before corrected scoring): team link share
{0,.5,.75,1} × compensated transfer share {0,.02,.05,.1}, transfer_games=20.
Use the same training-only selection rule above. If the selected link share
is 1, score 1.5 once at its selected transfer share, then reselect across
all Stage-1b cells. Original Stage 1/2 results below are frozen history;
only Stage 1b selects the new Stage 2 configuration.

Level bias: fit a win curve on the partition's cross-league Elo gaps, freeze
its log-odds as an offset, then fit zero-sum home-league effects (+1 team,
−1 opponent) by logistic likelihood with ridge 4 (penalty 4/2 × sum(effect²)).
Report unweighted RMS and max absolute log-odds effect for leagues with >=30
cross-league games; all observed leagues enter the fit. Held-out diagnostics
refit on held-out games only; they do not select a configuration.

Stage 2 arms: P published, P+cal published with today's native regional
calibration (`apply_frame`, native default), C chosen, C−bonus chosen with
move_down_bonus=0, P−bonus published with move_down_bonus=0. P+cal changes only
eligible international-event, different-known-home probabilities, using the
artifact's frozen event snapshots/windows; non-international cross-league
probabilities stay unchanged. Apply it to refit native probabilities, never
recalibrate or refit after application.

Reuse `elo_one_scale.held_losses`: domestic and international Elo/FORGE,
cross-league Elo, within-other per-league Elo/FORGE. Curves refit out of year
within each train/held-out partition; Form opponent adjustments use each
replay. Within-other FORGE's Form helper also uses training years. This is
not earlier-only deployment testing. Paired 95% intervals: 2,000 bootstrap
replicates, seed 0, whole series from `evaluation.series_ids` (unordered pairs,
12-hour gaps). Negative differences favor the first arm.

(a) C−P: pass if a target (cross-league or international) gains significantly
with mean gain >=.0005 (added-parameter rule), with no section significantly
worse. Fail if any section significantly worsens, otherwise inconclusive.
(b) C−P+cal: pass if International (Elo and FORGE) and Cross-league Elo all
have upper CI <+.0005. (c) C−bonus−C and P−bonus−P separately: pass if every
section has upper CI <+.0005. For (b)/(c), fail if any lower CI >=+.0005;
otherwise inconclusive. No multiplicity adjustment.
"""


# Frozen results from the original, uncompensated run; never replay as corrected.
ORIGINAL_RESULTS = """## Stage 1 (original; transfer arm had a feedback bug)

Published replay vs DB: max |Δ| 9.09e-13, 205,858 team-games. Train 2014–2021, held out 2022–2026. Latest input 2026-10-17 11:38:16. Training guard: 9,082 domestic and 32,488 within-other games.

| Link mode | Link share | Transfer share | Cross LL | Guard objective | Bias RMS | Max effect | Eligible | Replay seconds |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| either | 0 | 0 | 0.614169 | 0.619996 | 0.399528 | 0.810182 | True | 4.22 |
| either | 0 | 0.1 | 0.647183 | 0.622183 | 0.444822 | 0.855584 | False | 4.44 |
| either | 0 | 0.25 | 0.692543 | 0.646224 | 0.540907 | 1.208959 | False | 4.35 |
| either | 0 | 0.5 | 0.693519 | 0.683172 | 0.546149 | 1.234939 | False | 4.27 |
| plain | 0.125 | 0 | 0.612687 | 0.620015 | 0.386778 | 0.800228 | True | 4.23 |
| plain | 0.125 | 0.1 | 0.634949 | 0.621375 | 0.421588 | 0.844816 | False | 4.93 |
| plain | 0.125 | 0.25 | 0.691485 | 0.641805 | 0.535358 | 1.195243 | False | 4.58 |
| plain | 0.125 | 0.5 | 0.693397 | 0.682112 | 0.545558 | 1.237035 | False | 5.43 |
| plain | 0.25 | 0 | 0.611857 | 0.620095 | 0.376266 | 0.791566 | True | 4.44 |
| plain | 0.25 | 0.1 | 0.627539 | 0.620923 | 0.404237 | 0.825584 | False | 4.36 |
| plain | 0.25 | 0.25 | 0.690908 | 0.637001 | 0.530735 | 1.180760 | False | 4.35 |
| plain | 0.25 | 0.5 | 0.693678 | 0.678649 | 0.545277 | 1.238654 | False | 4.37 |
| plain | 0.5 | 0 | 0.611287 | 0.620353 | 0.360432 | 0.777823 | True | 4.05 |
| plain | 0.5 | 0.1 | 0.620155 | 0.620594 | 0.380182 | 0.768616 | False | 4.61 |
| plain | 0.5 | 0.25 | 0.685619 | 0.631710 | 0.517385 | 1.139719 | False | 4.34 |
| plain | 0.5 | 0.5 | 0.695515 | 0.673323 | 0.545137 | 1.238696 | False | 4.34 |
| team | 0.125 | 0 | 0.612109 | 0.619974 | 0.379763 | 0.787967 | True | 4.13 |
| team | 0.125 | 0.1 | 0.634922 | 0.621787 | 0.415217 | 0.841730 | False | 4.33 |
| team | 0.125 | 0.25 | 0.690363 | 0.645239 | 0.533486 | 1.188691 | False | 4.34 |
| team | 0.125 | 0.5 | 0.693345 | 0.682680 | 0.545086 | 1.236470 | False | 4.63 |
| team | 0.25 | 0 | 0.611244 | 0.620003 | 0.365543 | 0.774037 | True | 4.29 |
| team | 0.25 | 0.1 | 0.632140 | 0.621728 | 0.397932 | 0.793348 | False | 4.32 |
| team | 0.25 | 0.25 | 0.704722 | 0.647379 | 0.536419 | 1.210323 | False | 4.34 |
| team | 0.25 | 0.5 | 0.693663 | 0.681584 | 0.544908 | 1.236279 | False | 4.31 |
| team | 0.5 | 0 | 0.610735 | 0.620087 | 0.346051 | 0.757333 | True | 4.08 |
| team | 0.5 | 0.1 | 0.627116 | 0.621591 | 0.373579 | 0.704488 | False | 4.58 |
| team | 0.5 | 0.25 | 0.708759 | 0.645512 | 0.535241 | 1.211043 | False | 4.46 |
| team | 0.5 | 0.5 | 0.693618 | 0.681505 | 0.545051 | 1.235580 | False | 4.43 |

Selected {'link_mode': 'team', 'link_share': 0.5, 'transfer_share': 0}, transfer_games=20. Published guard 0.619996; selected guard 0.620087, cross loss 0.610735. Train bias diagnostic: 4,799 games; eligible league counts are reported below for P/C.


## Stage 2 (original; team link_share=0.5, transfer_share=0)

Losses and paired differences (95% series-clustered intervals).

| Section | Games | Series | P LL | P+cal LL | C LL | C−bonus LL | P−bonus LL | (a) C−P | (b) C−P+cal | (c) C−bonus−C | (c) P−bonus−P |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Domestic, Elo | 7,728 | 3,351 | 0.621465 | 0.621465 | 0.621474 | 0.621523 | 0.621545 | +0.000009 (-0.000305, +0.000327) | — | +0.000049 (-0.000488, +0.000577) | +0.000081 (-0.000460, +0.000596) |
| Domestic, FORGE | 7,728 | 3,351 | 0.620046 | 0.620046 | 0.620078 | 0.620113 | 0.620114 | +0.000032 (-0.000191, +0.000277) | — | +0.000036 (-0.000337, +0.000395) | +0.000068 (-0.000283, +0.000418) |
| International, Elo | 589 | 251 | 0.618576 | 0.611533 | 0.619320 | 0.618903 | 0.618572 | +0.000744 (-0.001790, +0.003398) | +0.007787 (-0.005286, +0.021047) | -0.000417 (-0.002003, +0.001071) | -0.000005 (-0.001340, +0.001257) |
| International, FORGE | 589 | 251 | 0.618576 | 0.611533 | 0.619320 | 0.618903 | 0.618572 | +0.000744 (-0.001790, +0.003398) | +0.007787 (-0.005286, +0.021047) | -0.000417 (-0.002003, +0.001071) | -0.000005 (-0.001340, +0.001257) |
| Cross-league, Elo | 5,442 | 3,106 | 0.570774 | 0.568047 | 0.559079 | 0.561176 | 0.576065 | -0.011696 (-0.015574, -0.007970) | -0.008968 (-0.013335, -0.004771) | +0.002097 (+0.001296, +0.002956) | +0.005291 (+0.004207, +0.006446) |
| Other leagues, Elo | 37,272 | 22,185 | 0.600935 | 0.600935 | 0.601321 | 0.601748 | 0.601275 | +0.000387 (+0.000127, +0.000639) | — | +0.000427 (+0.000215, +0.000628) | +0.000340 (+0.000135, +0.000536) |
| Other leagues, FORGE | 37,272 | 22,185 | 0.599740 | 0.599740 | 0.599854 | 0.600155 | 0.599993 | +0.000114 (-0.000115, +0.000336) | — | +0.000300 (+0.000109, +0.000485) | +0.000253 (+0.000064, +0.000438) |

## Level-bias diagnostics (original)

Effects are log-odds; top five are among leagues with >=30 games.

| Partition | Arm | Games | Eligible leagues | RMS | Max absolute effect | Top five (league: effect; games) |
|---|---|---:|---:|---:|---:|---|
| Train | P | 4,799 | 51 | 0.399528 | 0.810182 | LJLCS: -0.8102; 48, EUM: +0.7776; 135, LPLOL: -0.7582; 47, KeSPA Cup: +0.7151; 47, SLO: +0.6957; 136 |
| Train | C | 4,799 | 51 | 0.346051 | 0.757333 | LJLCS: -0.7573; 48, BM: -0.6209; 57, EUM: +0.5990; 135, LPLOL: -0.5972; 47, KeSPA Cup: +0.5945; 47 |
| Held out | P | 5,442 | 62 | 0.430785 | 1.120312 | LCKC: +1.1203; 163, AM: +0.9648; 104, LJLA: -0.9553; 35, HW: -0.8158; 102, LCO: -0.8151; 69 |
| Held out | C | 5,442 | 62 | 0.326123 | 0.834026 | LJLA: -0.8340; 35, HW: -0.6940; 102, AM: +0.6672; 104, LCKC: +0.6239; 163, LCO: -0.6048; 69 |

## Mechanical verdicts (original)

(a) Metric change: **fail**. Significant target gains >=.0005: [('Cross-league', 'elo_live')]; significant regressions: [('Other leagues', 'elo_live')].

(b) Calibration removal: **inconclusive**: 1/3 upper CIs <+.0005; lower CI >=+.0005: none.

(c) Bonus removal from C: **fail**: 2/7 upper CIs <+.0005; lower CI >=+.0005: [('Cross-league', 'elo_live')].

(c) Bonus removal from P: **fail**: 2/7 upper CIs <+.0005; lower CI >=+.0005: [('Cross-league', 'elo_live')].

"""


def level_bias(pairs, pre, years):
    games = cross_league_games(
        enp.pair_games(pairs, pre), INTERNATIONAL_LEAGUES, em.MAJORS
    )
    games = games[games.year.isin(years)]
    leagues = sorted(set(games.home) | set(games.opponent_home))
    lookup = {league: i for i, league in enumerate(leagues)}
    a = games.home.map(lookup).to_numpy()
    b = games.opponent_home.map(lookup).to_numpy()
    counts = np.bincount(np.r_[a, b], minlength=len(leagues))
    native = fit_win_curve(games.elo_live, games.won)(games.elo_live)
    offset = logit(np.clip(native, 1e-12, 1 - 1e-12))
    y = games.won.to_numpy()

    def objective(effect):
        z = offset + effect[a] - effect[b]
        residual = expit(z) - y
        gradient = (
            np.bincount(a, weights=residual, minlength=len(leagues))
            - np.bincount(b, weights=residual, minlength=len(leagues))
            + 4 * effect
        )
        return np.sum(np.logaddexp(0, z) - y * z) + 2 * effect @ effect, gradient

    fit = minimize(
        objective,
        np.zeros(len(leagues)),
        jac=True,
        method="L-BFGS-B",
        options={"ftol": 1e-12, "gtol": 1e-7, "maxiter": 1000},
    )
    assert fit.success, fit.message
    effects = fit.x - fit.x.mean()
    eligible = [
        (league, int(n), float(e))
        for league, n, e in zip(leagues, counts, effects)
        if n >= 30
    ]
    values = np.array([e for _, _, e in eligible])
    return {
        "games": len(games),
        "leagues": len(values),
        "rms": np.sqrt(np.mean(values**2)),
        "max": np.abs(values).max(),
        "top": sorted(eligible, key=lambda r: -abs(r[2]))[:5],
    }


def calibrated_losses(inputs, pairs, pre, years, native):
    """Apply production calibration to the exact native refit games/probabilities."""
    frame = ev._with_elo(inputs.frame, pre)
    frame = frame[frame.year.isin(years)].reset_index(drop=True)
    with mock.patch.dict(os.environ, {"REGIONAL_CALIBRATION": "0"}):
        probabilities = out_of_year_probabilities(frame, "elo_live")
        forge_frame = em.add_form(frame, ev.variant_form_states(inputs, pre))
        forge_probabilities = em.forge_probabilities(forge_frame)
    result = dict(native)
    with mock.patch.dict(os.environ, {"REGIONAL_CALIBRATION": "1"}):
        for metric, p in (("elo_live", probabilities), ("forge", forge_probabilities)):
            mask = frame.test_set.eq("International").to_numpy()
            games = result[("International", metric)][0]
            np.testing.assert_allclose(
                game_losses(np.asarray(p)[mask], games.won).log_loss,
                native[("International", metric)][1],
                rtol=0,
                atol=1e-12,
            )
            calibrated = regional_calibration.apply_frame(frame, p)
            assert np.array_equal(games.gameid, frame.loc[mask, "gameid"])
            result[("International", metric)] = (
                games,
                game_losses(calibrated[mask], games.won).log_loss.to_numpy(),
                None,
            )
        games = result[("Cross-league", "elo_live")][0]
        p = out_of_year_probabilities(games, "elo_live")
        np.testing.assert_allclose(
            game_losses(p, games.won).log_loss,
            native[("Cross-league", "elo_live")][1],
            rtol=0,
            atol=1e-12,
        )
        p = regional_calibration.apply_frame(games, p, homes=("home", "opponent_home"))
        result[("Cross-league", "elo_live")] = (
            games,
            game_losses(p, games.won).log_loss.to_numpy(),
            None,
        )
    return result


def noninferiority(deltas):
    passes = [key for key, d in deltas if d[2] < 0.0005]
    fails = [key for key, d in deltas if d[1] >= 0.0005]
    verdict = (
        "pass" if len(passes) == len(deltas) else "fail" if fails else "inconclusive"
    )
    return f"**{verdict}**: {len(passes)}/{len(deltas)} upper CIs <+.0005; lower CI >=+.0005: {fails or 'none'}."


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out", type=Path, default=Path("docs/research/elo_offsets.md")
    )
    args = parser.parse_args()
    started = time.perf_counter()
    inputs = ev.load_inputs(verbose=False)
    pairs = em.load_pair_games()
    for frame in (inputs.games, inputs.frame, inputs.form_games, pairs):
        assert pd.to_datetime(frame.date).max() < pd.Timestamp(FORWARD_START)
    train, test = ev.split_years(inputs.frame.year.unique())
    timings = []

    def replay(**params):
        tick = time.perf_counter()
        pre = ev.replay(inputs, ev.game_length_margin(), **params)
        timings.append(time.perf_counter() - tick)
        return pre

    lines = [
        f"# More Elo offset evidence ({datetime.date.today().isoformat()})\n",
        PROTOCOL,
        ORIGINAL_RESULTS,
    ]
    with mock.patch.dict(os.environ, {"REGIONAL_CALIBRATION": "0"}):
        base = replay()
        diff = (base - inputs.db_pre_match.reindex(base.index)).abs()
        assert not inputs.db_domestic
        assert diff.max() < 1e-6
        baseline_obj = enp.objective(inputs, pairs, base, train)
        train_domestic = inputs.frame.year.isin(train) & inputs.frame.test_set.eq(
            "Domestic"
        )
        other = other_league_games(pairs, INTERNATIONAL_LEAGUES, em.MAJORS)
        train_other = int(other.year.isin(train).sum())
        lines += [
            "\n## Stage 1b: corrected training selection\n",
            f"Published replay vs DB: max |Δ| {diff.max():.3g}, {len(base):,} team-games. "
            f"Train {min(train)}–{max(train)}, held out {min(test)}–{max(test)}. "
            f"Latest input {pd.to_datetime(inputs.games.date).max()}. "
            f"Training guard: {int(train_domestic.sum()):,} domestic and "
            f"{train_other:,} within-other games.\n",
            "| Link mode | Link share | Transfer share | Cross LL | Guard objective | Bias RMS | Max effect | Eligible | Replay seconds |",
            "|---|---:|---:|---:|---:|---:|---:|---|---:|",
        ]
        candidates = []

        def score(share, transfer):
            mode = "team"
            params = {
                "link_mode": mode,
                "link_share": share,
                "transfer_share": transfer,
            }
            pre = base if not share and not transfer else replay(**params)
            seconds = timings[0] if not share and not transfer else timings[-1]
            cross = enp.cross_losses(pairs, pre, train)[1].mean()
            obj = (
                baseline_obj
                if not share and not transfer
                else enp.objective(inputs, pairs, pre, train)
            )
            bias = level_bias(pairs, pre, train)
            eligible = obj <= baseline_obj + 0.0005
            row = {
                "params": params,
                "pre": pre,
                "cross": cross,
                "obj": obj,
                "eligible": eligible,
                "bias": bias,
            }
            candidates.append(row)
            lines.append(
                f"| {mode if share else 'either'} | {share:g} | {transfer:g} | {cross:.6f} | {obj:.6f} | {bias['rms']:.6f} | {bias['max']:.6f} | {eligible} | {seconds:.2f} |"
            )
            print(
                f"Train {params}: cross {cross:.6f}, guard {obj:.6f}, eligible {eligible}; replay {seconds:.2f}s",
                flush=True,
            )

        for share in (0, 0.5, 0.75, 1.0):
            for transfer in (0, 0.02, 0.05, 0.1):
                score(share, transfer)
        provisional = min(
            (r for r in candidates if r["eligible"]), key=lambda r: r["cross"]
        )
        if provisional["params"]["link_share"] == 1.0:
            score(1.5, provisional["params"]["transfer_share"])
        chosen = min((r for r in candidates if r["eligible"]), key=lambda r: r["cross"])
        params = chosen["params"]
        lines += [
            f"\nSelected {params}, transfer_games=20. Published guard {baseline_obj:.6f}; "
            f"selected guard {chosen['obj']:.6f}, cross loss {chosen['cross']:.6f}. "
            f"Train bias diagnostic: {chosen['bias']['games']:,} games; eligible league counts are reported below for P/C.\n"
        ]
        print(f"Selected {params}; scoring held out", flush=True)
        pres = {
            "P": base,
            "C": chosen["pre"],
            "C−bonus": replay(**params, move_down_bonus=0),
            "P−bonus": replay(move_down_bonus=0),
        }
        losses = {}
        for arm, pre in pres.items():
            losses[arm] = eos.held_losses(inputs, pairs, pre, test)
            print(f"Scored {arm}", flush=True)
        losses["P+cal"] = calibrated_losses(inputs, pairs, base, test, losses["P"])
        lines += [
            f"\n## Stage 2 (Stage-1b choice: {params})\n",
            "Losses and paired differences (95% series-clustered intervals).\n",
            "| Section | Games | Series | P LL | P+cal LL | C LL | C−bonus LL | P−bonus LL | (a) C−P | (b) C−P+cal | (c) C−bonus−C | (c) P−bonus−P |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|",
        ]
        gates = {name: [] for name in ("a", "b", "cC", "cP")}
        identity = ["gameid", "date", "teamid", "opponent_teamid", "won"]
        for key, (games, _, _) in losses["P"].items():
            for arm in losses:
                pd.testing.assert_frame_equal(
                    games[identity], losses[arm][key][0][identity]
                )
            clusters = series_ids(games.date, games.teamid, games.opponent_teamid)
            ll = {arm: value[key][1] for arm, value in losses.items()}
            comparisons = [
                ("a", "C", "P"),
                ("b", "C", "P+cal"),
                ("cC", "C−bonus", "C"),
                ("cP", "P−bonus", "P"),
            ]
            cells = []
            for gate, a, b in comparisons:
                if gate == "b" and key[0] not in ("International", "Cross-league"):
                    cells.append("—")
                    continue
                delta = paired_bootstrap(ll[a], ll[b], clusters=clusters)
                gates[gate].append((key, delta))
                cells.append(eos.fmt(delta))
            lines.append(
                f"| {key[0]}, {'Elo' if key[1] == 'elo_live' else 'FORGE'} | {len(games):,} | {len(set(clusters)):,} | "
                + " | ".join(
                    f"{ll[arm].mean():.6f}"
                    for arm in ("P", "P+cal", "C", "C−bonus", "P−bonus")
                )
                + " | "
                + " | ".join(cells)
                + " |"
            )
        lines += [
            "\n## Level-bias diagnostics\n",
            "Effects are log-odds; top five are among leagues with >=30 games.\n",
            "| Partition | Arm | Games | Eligible leagues | RMS | Max absolute effect | Top five (league: effect; games) |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
        for partition, years in (("Train", train), ("Held out", test)):
            for arm in ("P", "C"):
                bias = level_bias(pairs, pres[arm], years)
                top = ", ".join(
                    f"{league}: {e:+.4f}; {n}" for league, n, e in bias["top"]
                )
                lines.append(
                    f"| {partition} | {arm} | {bias['games']:,} | {bias['leagues']} | {bias['rms']:.6f} | {bias['max']:.6f} | {top} |"
                )
        gains = [
            k
            for k, d in gates["a"]
            if k[0] in ("International", "Cross-league")
            and d[2] < 0
            and d[0] <= -0.0005
        ]
        worse = [k for k, d in gates["a"] if d[1] > 0]
        verdict_a = (
            "pass" if gains and not worse else "fail" if worse else "inconclusive"
        )
        lines += [
            "\n## Mechanical verdicts\n",
            f"(a) Metric change: **{verdict_a}**. Significant target gains >=.0005: {gains or 'none'}; significant regressions: {worse or 'none'}.\n",
            "(b) Calibration removal: " + noninferiority(gates["b"]) + "\n",
            "(c) Bonus removal from C: " + noninferiority(gates["cC"]) + "\n",
            "(c) Bonus removal from P: " + noninferiority(gates["cP"]) + "\n",
            "The [earlier link test](league_moves_report.md) found team-only links helped cross-league forecasts "
            "but hurt FORGE-major market series (the prior rejection motivating this retest). Market checks "
            "are not part of this script, so these gates cannot establish market safety. "
            "The [offset-RD study](elo_offset_rd.md) likewise improved cross-league loss but failed native "
            "non-inferiority and calibration removal. Historical held-out years have been viewed in prior research.\n",
        ]
    total = time.perf_counter() - started
    lines.append(
        f"Runtime: {len(timings)} replays, {sum(timings):.2f}s replay total "
        f"({min(timings):.2f}–{max(timings):.2f}s each); total {total:.2f}s. "
        "No DB writes, weight/default changes or CI additions.\n"
    )
    args.out.write_text("\n".join(lines) + "\n")
    print(f"Report {args.out}; total {total:.2f}s", flush=True)


if __name__ == "__main__":
    main()
