# One Elo scale (2026-10-19)

## Protocol (fixed before scoring)

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


## Stage 0: published diagnostics

Current code vs DB: max |Δ| = 9.09495e-13 over 205,858 team-games; 0 differ
Reproduction: OK (max |Δ| < 1e-6)

Train 2014–2021; held out 2022–2026. Latest input: 2026-10-17 11:38:16.

| Partition | c_M | c_O | c_X |
|---|---:|---:|---:|
| Train | 1.5189 | 1.5955 | 1.7678 |
| Held out | 1.4344 | 1.5568 | 1.8553 |

## Stage 1: learning rates

| K_M | K_O | Train objective | c_M | c_O | c_X | Replay seconds |
|---:|---:|---:|---:|---:|---:|---:|
| 16 | 20 | 0.620237 | 1.5574 | 1.6547 | 1.6754 | 4.26 |
| 16 | 24 | 0.620455 | 1.5322 | 1.5554 | 1.5960 | 4.23 |
| 16 | 28 | 0.620939 | 1.5071 | 1.4719 | 1.5253 | 4.24 |
| 16 | 32 | 0.621601 | 1.4823 | 1.3997 | 1.4615 | 4.42 |
| 16 | 40 | 0.623263 | 1.4336 | 1.2786 | 1.3503 | 4.47 |
| 16 | 48 | 0.625183 | 1.3866 | 1.1786 | 1.2553 | 4.31 |
| 20 | 20 | 0.620024 | 1.5000 | 1.6518 | 1.6535 | 4.21 |
| 20 | 24 | 0.620196 | 1.4824 | 1.5533 | 1.5809 | 4.68 |
| 20 | 28 | 0.620639 | 1.4647 | 1.4704 | 1.5156 | 4.20 |
| 20 | 32 | 0.621265 | 1.4468 | 1.3985 | 1.4564 | 4.20 |
| 20 | 40 | 0.622862 | 1.4111 | 1.2780 | 1.3519 | 4.36 |
| 20 | 48 | 0.624723 | 1.3752 | 1.1782 | 1.2617 | 4.41 |
| 24 | 20 | 0.620002 | 1.4457 | 1.6484 | 1.6286 | 4.37 |
| 24 | 24 | 0.620137 | 1.4327 | 1.5510 | 1.5617 | 4.35 |
| 24 | 28 | 0.620548 | 1.4195 | 1.4686 | 1.5011 | 4.17 |
| 24 | 32 | 0.621146 | 1.4060 | 1.3972 | 1.4457 | 4.52 |
| 24 | 40 | 0.622692 | 1.3788 | 1.2771 | 1.3473 | 4.32 |
| 24 | 48 | 0.624509 | 1.3509 | 1.1776 | 1.2615 | 4.29 |

Selected K_M=24, K_O=20; objective 0.620002.


## Stage 2: offset learning

| Share | Train cross loss | Train objective | c_X | Eligible | Replay seconds |
|---:|---:|---:|---:|---|---:|
| 0.5 | 0.614792 | 0.620002 | 1.6286 | True | 4.18 |
| 0.75 | 0.614158 | 0.620110 | 1.6006 | True | 4.18 |
| 1 | 0.613952 | 0.620243 | 1.5737 | True | 4.18 |
| 1.5 | 0.614235 | 0.620540 | 1.5232 | False | 4.53 |
| 2 | 0.615017 | 0.620855 | 1.4768 | False | 4.26 |

Selected share=1 at K_M=24, K_O=20.


## Stage 3: held out

Negative differences favor the first arm; parentheses are 95% intervals.

| Section | Games | P refit LL | C refit LL | (a) C refit − P refit | (b) C native − P refit | (c) C native − C refit | (c) P native − P refit | (b) pass |
|---|---:|---:|---:|---|---|---|---|---|
| Domestic, Elo | 7,728 | 0.621465 | 0.621917 | +0.000452 (-0.000190, +0.001093) | +0.007415 (+0.004844, +0.010159) | +0.006962 (+0.004489, +0.009602) | +0.008392 (+0.005691, +0.011286) | False |
| Domestic, FORGE | 7,728 | 0.620046 | 0.620414 | +0.000368 (-0.000064, +0.000816) | — | — | — | — |
| International, Elo | 589 | 0.618576 | 0.620825 | +0.002248 (-0.003237, +0.007277) | +0.006220 (-0.002915, +0.015117) | +0.003972 (-0.004988, +0.013270) | +0.007533 (-0.002155, +0.017379) | False |
| International, FORGE | 589 | 0.618576 | 0.620825 | +0.002248 (-0.003237, +0.007277) | — | — | — | — |
| Cross-league, Elo | 5,442 | 0.570774 | 0.570358 | -0.000416 (-0.001609, +0.000781) | +0.014692 (+0.010102, +0.019417) | +0.015108 (+0.010545, +0.019887) | +0.020780 (+0.015464, +0.026203) | False |
| Other leagues, Elo | 37,272 | 0.600935 | 0.601434 | +0.000499 (+0.000289, +0.000698) | +0.011428 (+0.010011, +0.012704) | +0.010929 (+0.009547, +0.012179) | +0.010308 (+0.008946, +0.011528) | False |
| Other leagues, FORGE | 37,272 | 0.599740 | 0.600240 | +0.000500 (+0.000327, +0.000660) | — | — | — | — |

| Held-out replay | c_M | c_O | c_X |
|---|---:|---:|---:|
| P | 1.4344 | 1.5568 | 1.8553 |
| C | 1.3544 | 1.5845 | 1.6614 |

## Verdict

Metric-change gate: **conclusive: fails**. Significant gains >=.0005: none; significant regressions: [('Other leagues', 'elo_live'), ('Other leagues', 'forge')].

No-curve C non-inferiority: **conclusive: fails**. 0/4 Elo sections have upper CI <+.0005; sections with lower CI >=+.0005: [('Domestic', 'elo_live'), ('Cross-league', 'elo_live'), ('Other leagues', 'elo_live')].

Runtime: 24 replays, total replay 103.12s (range 3.79–4.68s); total 151.69s. Existing helpers ran against today's engine without compatibility fixes. No published code, weights, defaults or CI changed.

