# More Elo offset evidence (2026-10-19)

## Protocol (fixed before scoring)

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

## Stage 1 (original; transfer arm had a feedback bug)

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



## Stage 1b: corrected training selection

Published replay vs DB: max |Δ| 9.09e-13, 205,858 team-games. Train 2014–2021, held out 2022–2026. Latest input 2026-10-17 11:38:16. Training guard: 9,082 domestic and 32,488 within-other games.

| Link mode | Link share | Transfer share | Cross LL | Guard objective | Bias RMS | Max effect | Eligible | Replay seconds |
|---|---:|---:|---:|---:|---:|---:|---|---:|
| either | 0 | 0 | 0.614169 | 0.619996 | 0.399528 | 0.810182 | True | 4.99 |
| either | 0 | 0.02 | 0.614682 | 0.619578 | 0.393759 | 0.771112 | True | 5.01 |
| either | 0 | 0.05 | 0.620288 | 0.619791 | 0.399425 | 0.773938 | True | 4.73 |
| either | 0 | 0.1 | 0.644822 | 0.621875 | 0.441350 | 0.852563 | False | 4.85 |
| team | 0.5 | 0 | 0.610735 | 0.620087 | 0.346051 | 0.757333 | True | 4.52 |
| team | 0.5 | 0.02 | 0.610405 | 0.619646 | 0.338845 | 0.722185 | True | 4.97 |
| team | 0.5 | 0.05 | 0.612993 | 0.619767 | 0.341132 | 0.685177 | True | 4.79 |
| team | 0.5 | 0.1 | 0.625567 | 0.621329 | 0.371253 | 0.698085 | False | 5.34 |
| team | 0.75 | 0 | 0.610908 | 0.620177 | 0.333730 | 0.748679 | True | 5.07 |
| team | 0.75 | 0.02 | 0.610509 | 0.619722 | 0.326851 | 0.716144 | True | 5.19 |
| team | 0.75 | 0.05 | 0.612524 | 0.619818 | 0.328423 | 0.682111 | True | 4.79 |
| team | 0.75 | 0.1 | 0.621926 | 0.621218 | 0.353170 | 0.672029 | False | 4.73 |
| team | 1 | 0 | 0.611417 | 0.620268 | 0.325801 | 0.744527 | True | 4.62 |
| team | 1 | 0.02 | 0.610984 | 0.619799 | 0.319281 | 0.714351 | True | 4.90 |
| team | 1 | 0.05 | 0.612590 | 0.619869 | 0.320251 | 0.683062 | True | 5.06 |
| team | 1 | 0.1 | 0.619943 | 0.621141 | 0.340671 | 0.671571 | False | 4.39 |

Selected {'link_mode': 'team', 'link_share': 0.5, 'transfer_share': 0.02}, transfer_games=20. Published guard 0.619996; selected guard 0.619646, cross loss 0.610405. Train bias diagnostic: 4,799 games; eligible league counts are reported below for P/C.


## Stage 2 (Stage-1b choice: {'link_mode': 'team', 'link_share': 0.5, 'transfer_share': 0.02})

Losses and paired differences (95% series-clustered intervals).

| Section | Games | Series | P LL | P+cal LL | C LL | C−bonus LL | P−bonus LL | (a) C−P | (b) C−P+cal | (c) C−bonus−C | (c) P−bonus−P |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| Domestic, Elo | 7,728 | 3,351 | 0.621465 | 0.621465 | 0.621591 | 0.621684 | 0.621545 | +0.000127 (-0.000301, +0.000555) | — | +0.000092 (-0.000448, +0.000640) | +0.000081 (-0.000460, +0.000596) |
| Domestic, FORGE | 7,728 | 3,351 | 0.620046 | 0.620046 | 0.620243 | 0.620298 | 0.620114 | +0.000198 (-0.000095, +0.000501) | — | +0.000055 (-0.000313, +0.000420) | +0.000068 (-0.000283, +0.000418) |
| International, Elo | 589 | 251 | 0.618576 | 0.611533 | 0.618989 | 0.618916 | 0.618572 | +0.000413 (-0.002203, +0.003201) | +0.007456 (-0.005503, +0.020567) | -0.000073 (-0.001730, +0.001549) | -0.000005 (-0.001340, +0.001257) |
| International, FORGE | 589 | 251 | 0.618576 | 0.611533 | 0.618989 | 0.618916 | 0.618572 | +0.000413 (-0.002203, +0.003201) | +0.007456 (-0.005503, +0.020567) | -0.000073 (-0.001730, +0.001549) | -0.000005 (-0.001340, +0.001257) |
| Cross-league, Elo | 5,442 | 3,106 | 0.570774 | 0.568047 | 0.558340 | 0.560150 | 0.576065 | -0.012435 (-0.016476, -0.008520) | -0.009707 (-0.014186, -0.005409) | +0.001810 (+0.001032, +0.002649) | +0.005291 (+0.004207, +0.006446) |
| Other leagues, Elo | 37,272 | 22,185 | 0.600935 | 0.600935 | 0.601041 | 0.601381 | 0.601275 | +0.000106 (-0.000271, +0.000470) | — | +0.000340 (+0.000145, +0.000527) | +0.000340 (+0.000135, +0.000536) |
| Other leagues, FORGE | 37,272 | 22,185 | 0.599740 | 0.599740 | 0.599554 | 0.599776 | 0.599993 | -0.000186 (-0.000511, +0.000151) | — | +0.000223 (+0.000044, +0.000391) | +0.000253 (+0.000064, +0.000438) |

## Level-bias diagnostics

Effects are log-odds; top five are among leagues with >=30 games.

| Partition | Arm | Games | Eligible leagues | RMS | Max absolute effect | Top five (league: effect; games) |
|---|---|---:|---:|---:|---:|---|
| Train | P | 4,799 | 51 | 0.399528 | 0.810182 | LJLCS: -0.8102; 48, EUM: +0.7776; 135, LPLOL: -0.7582; 47, KeSPA Cup: +0.7151; 47, SLO: +0.6957; 136 |
| Train | C | 4,799 | 51 | 0.338845 | 0.722185 | LJLCS: -0.7222; 48, KeSPA Cup: +0.6093; 47, BM: -0.6063; 57, LPLOL: -0.5820; 47, SLO: +0.5720; 136 |
| Held out | P | 5,442 | 62 | 0.430785 | 1.120312 | LCKC: +1.1203; 163, AM: +0.9648; 104, LJLA: -0.9553; 35, HW: -0.8158; 102, LCO: -0.8151; 69 |
| Held out | C | 5,442 | 62 | 0.317342 | 0.800896 | LJLA: -0.8009; 35, AM: +0.7220; 104, HW: -0.6498; 102, LCKC: +0.5953; 163, GL: -0.5527; 40 |

## Mechanical verdicts

(a) Metric change: **pass**. Significant target gains >=.0005: [('Cross-league', 'elo_live')]; significant regressions: none.

(b) Calibration removal: **inconclusive**: 1/3 upper CIs <+.0005; lower CI >=+.0005: none.

(c) Bonus removal from C: **fail**: 2/7 upper CIs <+.0005; lower CI >=+.0005: [('Cross-league', 'elo_live')].

(c) Bonus removal from P: **fail**: 2/7 upper CIs <+.0005; lower CI >=+.0005: [('Cross-league', 'elo_live')].

The [earlier link test](league_moves_report.md) found team-only links helped cross-league forecasts but hurt FORGE-major market series (the prior rejection motivating this retest). Market checks are not part of this script, so these gates cannot establish market safety. The [offset-RD study](elo_offset_rd.md) likewise improved cross-league loss but failed native non-inferiority and calibration removal. Historical held-out years have been viewed in prior research.

Runtime: 18 replays, 86.27s replay total (3.99–5.34s each); total 155.80s. No DB writes, weight/default changes or CI additions.


## Published-default refit (2026-10-19)

The selected defaults now use team-only links .5 and compensated transfers .02 over 20 games. Regional calibration is unchanged: its frozen artifact was fitted on the old offsets; removal was inconclusive. Native and market guards remain for the PR benchmark check.

Regenerated native report versus committed `docs/metric_backtest.md` (all years, not the held-out research cohort):

| Section | Elo log loss before → after | FORGE log loss before → after |
|---|---:|---:|
| Domestic | .6303 → .6304 | .6285 → .6286 |
| International | .6252 → .6250 | .6252 → .6250 |
| Cross-league | .5893 → .5807 | same Elo routing |
| Other leagues (per-league curves) | .6070 → .6069 | .6065 → .6062 |

These aggregate differences do not replace paired native/market guards in the PR check.

All three forecast weight artifacts were refitted. The table records every changed serialized coefficient versus HEAD; fixed Form settings are unchanged.

| Artifact / coefficient | Before | After | Δ |
|---|---:|---:|---:|
| forge_weights.json: elo_weight | 0.005480 | 0.005564 | +0.000084 |
| forge_weights.json: form_weight | 0.409892 | 0.403264 | -0.006628 |
| forge_weights.json: cross_region_elo_weight | 0.008492 | 0.008518 | +0.000026 |
| forge_weights.json: other_league_elo_weight | 0.010227 | 0.010126 | -0.000101 |
| forge_weights.json: other_league_forge_elo_weight | 0.008389 | 0.008328 | -0.000061 |
| forge_weights.json: other_league_form_weight | 0.292506 | 0.292361 | -0.000145 |
| form_weights.json: gpm | 0.005226 | 0.005183 | -0.000043 |
| form_weights.json: kills_per_10 | -0.003292 | -0.002626 | +0.000666 |
| form_weights.json: turrets_per_10 | 0.728256 | 0.725190 | -0.003066 |
| form_weights.json: baron_per_10 | -1.284423 | -1.281108 | +0.003315 |
| form_weights.json: dragon_per_10 | 0.636051 | 0.643960 | +0.007909 |
| form_weights.json: atakhans | 0.612327 | 0.622252 | +0.009925 |
| form_weights.json: heralds_per_10 | 0.359409 | 0.355056 | -0.004353 |
| form_weights.json: firstherald | -0.434898 | -0.427974 | +0.006924 |
| form_weights.json: firstdragon | -0.406457 | -0.412854 | -0.006397 |
| form_weights.json: firstbaron | -0.090101 | -0.094238 | -0.004137 |
| form_weights.json: firsttower | 0.139661 | 0.133580 | -0.006081 |
| form_weights.json: visionscore_per_10 | 0.013822 | 0.013852 | +0.000030 |
| league_curves.json: AL | 0.010493 | 0.010392 | -0.000101 |
| league_curves.json: AM | 0.009585 | 0.009516 | -0.000069 |
| league_curves.json: ASCI | 0.010348 | 0.010238 | -0.000110 |
| league_curves.json: BIG | 0.009960 | 0.009784 | -0.000176 |
| league_curves.json: BL | 0.011151 | 0.010888 | -0.000263 |
| league_curves.json: BM | 0.010301 | 0.010049 | -0.000252 |
| league_curves.json: BRCC | 0.012168 | 0.011969 | -0.000199 |
| league_curves.json: CBLOL | 0.009258 | 0.009234 | -0.000024 |
| league_curves.json: CBLOLA | 0.009783 | 0.009696 | -0.000087 |
| league_curves.json: CD | 0.009635 | 0.009638 | +0.000003 |
| league_curves.json: CISC | 0.010247 | 0.010161 | -0.000086 |
| league_curves.json: CK | 0.009941 | 0.010003 | +0.000062 |
| league_curves.json: CLS | 0.011614 | 0.011518 | -0.000096 |
| league_curves.json: CT | 0.009501 | 0.009374 | -0.000127 |
| league_curves.json: CU | 0.010329 | 0.010233 | -0.000096 |
| league_curves.json: DCup | 0.009526 | 0.009448 | -0.000078 |
| league_curves.json: DDH | 0.012005 | 0.011887 | -0.000118 |
| league_curves.json: DL | 0.011526 | 0.011149 | -0.000377 |
| league_curves.json: EBL | 0.011510 | 0.011241 | -0.000269 |
| league_curves.json: EGL | 0.010290 | 0.010191 | -0.000099 |
| league_curves.json: EL | 0.011461 | 0.011267 | -0.000194 |
| league_curves.json: ESLOL | 0.008605 | 0.008560 | -0.000045 |
| league_curves.json: EU CS | 0.010814 | 0.010773 | -0.000041 |
| league_curves.json: EUM | 0.010576 | 0.010349 | -0.000227 |
| league_curves.json: GL | 0.010587 | 0.010444 | -0.000143 |
| league_curves.json: GLL | 0.009294 | 0.009042 | -0.000252 |
| league_curves.json: GLLPA | 0.010240 | 0.010081 | -0.000159 |
| league_curves.json: GPL | 0.010788 | 0.010690 | -0.000098 |
| league_curves.json: HC | 0.008993 | 0.008718 | -0.000275 |
| league_curves.json: HLL | 0.011367 | 0.011026 | -0.000341 |
| league_curves.json: HM | 0.011819 | 0.011416 | -0.000403 |
| league_curves.json: HW | 0.009761 | 0.009661 | -0.000100 |
| league_curves.json: IC | 0.010458 | 0.010327 | -0.000131 |
| league_curves.json: IGNIS | 0.011172 | 0.011004 | -0.000168 |
| league_curves.json: KeSPA | 0.010232 | 0.010129 | -0.000103 |
| league_curves.json: KeSPA Cup | 0.010228 | 0.010127 | -0.000101 |
| league_curves.json: LAS | 0.009820 | 0.009808 | -0.000012 |
| league_curves.json: LCKC | 0.007228 | 0.007279 | +0.000051 |
| league_curves.json: LCL | 0.011937 | 0.012022 | +0.000085 |
| league_curves.json: LCO | 0.011380 | 0.011160 | -0.000220 |
| league_curves.json: LCP | 0.011015 | 0.010709 | -0.000306 |
| league_curves.json: LCSA | 0.008577 | 0.008578 | +0.000001 |
| league_curves.json: LDL | 0.008195 | 0.008155 | -0.000040 |
| league_curves.json: LES | 0.011025 | 0.010647 | -0.000378 |
| league_curves.json: LFL | 0.008503 | 0.008713 | +0.000210 |
| league_curves.json: LFL2 | 0.009568 | 0.009534 | -0.000034 |
| league_curves.json: LHE | 0.010386 | 0.010339 | -0.000047 |
| league_curves.json: LIT | 0.012187 | 0.011914 | -0.000273 |
| league_curves.json: LJL | 0.012710 | 0.012562 | -0.000148 |
| league_curves.json: LJLA | 0.010612 | 0.010554 | -0.000058 |
| league_curves.json: LJLCS | 0.011701 | 0.011523 | -0.000178 |
| league_curves.json: LLA | 0.010853 | 0.010852 | -0.000001 |
| league_curves.json: LLN | 0.011708 | 0.011588 | -0.000120 |
| league_curves.json: LMF | 0.012306 | 0.012082 | -0.000224 |
| league_curves.json: LMS | 0.012466 | 0.012396 | -0.000070 |
| league_curves.json: LPLOL | 0.012213 | 0.011900 | -0.000313 |
| league_curves.json: LRN | 0.010796 | 0.010675 | -0.000121 |
| league_curves.json: LRS | 0.009752 | 0.009690 | -0.000062 |
| league_curves.json: LSPL | 0.009770 | 0.009814 | +0.000044 |
| league_curves.json: LTA S | 0.009301 | 0.009344 | +0.000043 |
| league_curves.json: LVP SL | 0.008653 | 0.008558 | -0.000095 |
| league_curves.json: NA CS | 0.011701 | 0.011627 | -0.000074 |
| league_curves.json: NACL | 0.008870 | 0.008650 | -0.000220 |
| league_curves.json: NASG | 0.007792 | 0.007742 | -0.000050 |
| league_curves.json: NEXO | 0.010448 | 0.010372 | -0.000076 |
| league_curves.json: NL | 0.011461 | 0.011094 | -0.000367 |
| league_curves.json: NLC | 0.009387 | 0.009266 | -0.000121 |
| league_curves.json: NLC Aurora Open | 0.010270 | 0.010102 | -0.000168 |
| league_curves.json: OCS | 0.010557 | 0.010356 | -0.000201 |
| league_curves.json: OGN | 0.012123 | 0.011975 | -0.000148 |
| league_curves.json: OPL | 0.012427 | 0.012216 | -0.000211 |
| league_curves.json: OTBLX | 0.009947 | 0.009933 | -0.000014 |
| league_curves.json: PCL | 0.013136 | 0.012866 | -0.000270 |
| league_curves.json: PCS | 0.010945 | 0.010926 | -0.000019 |
| league_curves.json: PGC | 0.011399 | 0.011054 | -0.000345 |
| league_curves.json: PGN | 0.011497 | 0.011298 | -0.000199 |
| league_curves.json: PRM | 0.008247 | 0.008170 | -0.000077 |
| league_curves.json: PRMP | 0.009571 | 0.009255 | -0.000316 |
| league_curves.json: RCL | 0.009131 | 0.008775 | -0.000356 |
| league_curves.json: RL | 0.009597 | 0.009394 | -0.000203 |
| league_curves.json: ROL | 0.011732 | 0.011504 | -0.000228 |
| league_curves.json: SL (LATAM) | 0.009984 | 0.009906 | -0.000078 |
| league_curves.json: SLO | 0.009079 | 0.009133 | +0.000054 |
| league_curves.json: TAL | 0.012604 | 0.012425 | -0.000179 |
| league_curves.json: TCL | 0.010367 | 0.010298 | -0.000069 |
| league_curves.json: TCS | 0.010293 | 0.010230 | -0.000063 |
| league_curves.json: TPL | 0.010304 | 0.010205 | -0.000099 |
| league_curves.json: TSC | 0.010053 | 0.009993 | -0.000060 |
| league_curves.json: UKLC | 0.011272 | 0.010987 | -0.000285 |
| league_curves.json: UL | 0.010261 | 0.010291 | +0.000030 |
| league_curves.json: UPL | 0.009662 | 0.009249 | -0.000413 |
| league_curves.json: USP | 0.010228 | 0.010127 | -0.000101 |
| league_curves.json: VCS | 0.009079 | 0.009010 | -0.000069 |
| league_curves.json: VL | 0.012027 | 0.011861 | -0.000166 |
| league_curves.json: WLRQ | 0.010228 | 0.010127 | -0.000101 |
