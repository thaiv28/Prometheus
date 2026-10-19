# Elo forecast g(RD) (2026-10-19)

Research only. Ratings, player moves, league offsets and published forecasts remain unchanged. Base: main `00237c0`; opt-in RD telemetry only. Negative Δ log loss is better.

Tune 2014–2021 on chronological prefixes; held out 2022–2026. Fixed grid λ ∈ {.25,.5,1,2,4} × {both,independent}. One lambda-edge extension to .125 or 8 (both combinations), no further extension. λ=0 is published. Combination both sums team RMS starter RD²; independent divides that sum by five. Gap multiplied by 1/sqrt(1+3(ln(10)/400)²λφ²/π²). Only the gap changes, with all curves/blends refit. Form's opponent adjustment and stat weights stay tied to published Elo.

Selected λ=0.125, independent; initial (0.25, 'independent') ; extension 0.125. Selection frozen in gitignored data/research/elo_grd/selection.json before held-out scoring. Baseline tuning objective 0.61999453. Both parameterizations depend only on λ/divisor, so overlapping effective settings are mathematically identical.

Harness caveats: leave-one-year-out curves/blends within each partition, not expanding-year deployment fits. Other-league Form stat weights use all other major-league years, including tuning years, matching the existing harness. Paired individual-game bootstrap 95% CIs (no series clustering or multiplicity correction). Historical holdouts have already been viewed in prior research. Exact prefix/full record parity and DB rating parity checked.

## Tuning

| λ | Combination | Objective |
|---:|---|---:|
| 0.25 | both | 0.62006610 |
| 0.25 | independent | 0.62000678 |
| 0.5 | both | 0.62014605 |
| 0.5 | independent | 0.62002044 |
| 1 | both | 0.62029025 |
| 1 | independent | 0.62005038 |
| 2 | both | 0.62049680 |
| 2 | independent | 0.62011422 |
| 4 | both | 0.62072174 |
| 4 | independent | 0.62023607 |
| 0.125 | both | 0.62002766 |
| 0.125 | independent | 0.62000045 |

## Held-out sections

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | -0.00000 (-0.00001 to +0.00001) |
| Elo, international | 589 | 0.61877 | +0.00000 (-0.00001 to +0.00002) |
| FORGE, domestic | 7,728 | 0.62010 | -0.00000 (-0.00000 to +0.00000) |
| FORGE, international | 589 | 0.61154 | -0.00006 (-0.00017 to +0.00004) |
| Elo, other leagues | 37,272 | 0.60081 | +0.00000 (-0.00001 to +0.00001) |
| Elo, cross-league | 5,442 | 0.57070 | -0.00004 (-0.00008 to -0.00001) |
| FORGE, other leagues | 37,272 | 0.59979 | +0.00003 (+0.00002 to +0.00004) |

## Roster-change slices

Either team changed its known five starters since its last game; first appearances excluded. Full-section fits sliced after scoring.

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | -0.00000 (-0.00003 to +0.00003) |
| Elo, international | 9 | 0.78976 | +0.00005 (-0.00001 to +0.00010) |
| FORGE, domestic | 703 | 0.58950 | +0.00000 (-0.00002 to +0.00002) |
| FORGE, international | 9 | 0.78809 | -0.00077 (-0.00166 to +0.00019) |
| Elo, other leagues | 6,814 | 0.58324 | +0.00000 (-0.00003 to +0.00003) |
| Elo, cross-league | 682 | 0.53321 | -0.00010 (-0.00025 to +0.00004) |
| FORGE, other leagues | 6,814 | 0.58221 | +0.00003 (+0.00000 to +0.00006) |


## Roster-change calibration

Deciles are equal-count groups ordered by published probability within each section; selected uses identical games. Entries are probabilities (not percentages). Full-section fits are sliced after scoring.

| Section | Decile | Games | Published predicted | Selected predicted | Actual |
|---|---:|---:|---:|---:|---:|
| Elo, domestic | 1 | 71 | 0.1777 | 0.1778 | 0.2113 |
| Elo, domestic | 2 | 71 | 0.3020 | 0.3021 | 0.2817 |
| Elo, domestic | 3 | 71 | 0.3936 | 0.3937 | 0.4507 |
| Elo, domestic | 4 | 70 | 0.4531 | 0.4531 | 0.3286 |
| Elo, domestic | 5 | 70 | 0.5163 | 0.5163 | 0.5000 |
| Elo, domestic | 6 | 70 | 0.5751 | 0.5751 | 0.5429 |
| Elo, domestic | 7 | 70 | 0.6344 | 0.6344 | 0.7571 |
| Elo, domestic | 8 | 70 | 0.6960 | 0.6959 | 0.7429 |
| Elo, domestic | 9 | 70 | 0.7705 | 0.7704 | 0.7857 |
| Elo, domestic | 10 | 70 | 0.8732 | 0.8732 | 0.8571 |
| Elo, international | 1 | 1 | 0.3150 | 0.3149 | 1.0000 |
| Elo, international | 2 | 1 | 0.3714 | 0.3714 | 1.0000 |
| Elo, international | 3 | 1 | 0.4107 | 0.4107 | 1.0000 |
| Elo, international | 4 | 1 | 0.4349 | 0.4350 | 0.0000 |
| Elo, international | 5 | 1 | 0.4723 | 0.4723 | 1.0000 |
| Elo, international | 6 | 1 | 0.6071 | 0.6070 | 0.0000 |
| Elo, international | 7 | 1 | 0.7190 | 0.7190 | 1.0000 |
| Elo, international | 8 | 1 | 0.7302 | 0.7303 | 0.0000 |
| Elo, international | 9 | 1 | 0.8379 | 0.8377 | 1.0000 |
| FORGE, domestic | 1 | 71 | 0.1743 | 0.1743 | 0.1831 |
| FORGE, domestic | 2 | 71 | 0.2989 | 0.2990 | 0.3662 |
| FORGE, domestic | 3 | 71 | 0.3884 | 0.3884 | 0.3662 |
| FORGE, domestic | 4 | 70 | 0.4516 | 0.4516 | 0.3714 |
| FORGE, domestic | 5 | 70 | 0.5112 | 0.5113 | 0.4429 |
| FORGE, domestic | 6 | 70 | 0.5763 | 0.5763 | 0.6286 |
| FORGE, domestic | 7 | 70 | 0.6396 | 0.6395 | 0.7143 |
| FORGE, domestic | 8 | 70 | 0.6974 | 0.6974 | 0.6857 |
| FORGE, domestic | 9 | 70 | 0.7736 | 0.7735 | 0.8286 |
| FORGE, domestic | 10 | 70 | 0.8739 | 0.8738 | 0.8714 |
| FORGE, international | 1 | 1 | 0.2892 | 0.2897 | 1.0000 |
| FORGE, international | 2 | 1 | 0.3525 | 0.3534 | 1.0000 |
| FORGE, international | 3 | 1 | 0.3742 | 0.3747 | 0.0000 |
| FORGE, international | 4 | 1 | 0.3977 | 0.3984 | 1.0000 |
| FORGE, international | 5 | 1 | 0.4898 | 0.4901 | 1.0000 |
| FORGE, international | 6 | 1 | 0.5006 | 0.5003 | 0.0000 |
| FORGE, international | 7 | 1 | 0.7274 | 0.7267 | 1.0000 |
| FORGE, international | 8 | 1 | 0.7754 | 0.7747 | 0.0000 |
| FORGE, international | 9 | 1 | 0.8192 | 0.8182 | 1.0000 |
| Elo, other leagues | 1 | 682 | 0.1258 | 0.1262 | 0.1188 |
| Elo, other leagues | 2 | 682 | 0.2495 | 0.2498 | 0.2713 |
| Elo, other leagues | 3 | 682 | 0.3372 | 0.3374 | 0.3446 |
| Elo, other leagues | 4 | 682 | 0.4091 | 0.4092 | 0.4047 |
| Elo, other leagues | 5 | 681 | 0.4757 | 0.4757 | 0.4626 |
| Elo, other leagues | 6 | 681 | 0.5390 | 0.5389 | 0.5316 |
| Elo, other leagues | 7 | 681 | 0.6063 | 0.6062 | 0.6138 |
| Elo, other leagues | 8 | 681 | 0.6809 | 0.6807 | 0.7078 |
| Elo, other leagues | 9 | 681 | 0.7652 | 0.7650 | 0.7651 |
| Elo, other leagues | 10 | 681 | 0.8870 | 0.8868 | 0.8634 |
| Elo, cross-league | 1 | 69 | 0.0648 | 0.0652 | 0.1014 |
| Elo, cross-league | 2 | 69 | 0.1654 | 0.1657 | 0.1304 |
| Elo, cross-league | 3 | 68 | 0.2614 | 0.2617 | 0.3088 |
| Elo, cross-league | 4 | 68 | 0.3538 | 0.3540 | 0.3824 |
| Elo, cross-league | 5 | 68 | 0.4374 | 0.4376 | 0.5882 |
| Elo, cross-league | 6 | 68 | 0.5440 | 0.5440 | 0.6618 |
| Elo, cross-league | 7 | 68 | 0.6469 | 0.6466 | 0.6471 |
| Elo, cross-league | 8 | 68 | 0.7277 | 0.7275 | 0.7206 |
| Elo, cross-league | 9 | 68 | 0.8233 | 0.8229 | 0.8676 |
| Elo, cross-league | 10 | 68 | 0.9271 | 0.9266 | 0.9118 |
| FORGE, other leagues | 1 | 682 | 0.1363 | 0.1366 | 0.1202 |
| FORGE, other leagues | 2 | 682 | 0.2516 | 0.2519 | 0.2654 |
| FORGE, other leagues | 3 | 682 | 0.3382 | 0.3384 | 0.3358 |
| FORGE, other leagues | 4 | 682 | 0.4121 | 0.4122 | 0.3900 |
| FORGE, other leagues | 5 | 681 | 0.4823 | 0.4823 | 0.4831 |
| FORGE, other leagues | 6 | 681 | 0.5458 | 0.5457 | 0.5419 |
| FORGE, other leagues | 7 | 681 | 0.6115 | 0.6114 | 0.6094 |
| FORGE, other leagues | 8 | 681 | 0.6856 | 0.6854 | 0.7181 |
| FORGE, other leagues | 9 | 681 | 0.7690 | 0.7688 | 0.7474 |
| FORGE, other leagues | 10 | 681 | 0.8841 | 0.8838 | 0.8722 |

## Verdict

**Not worth it.** Requires a significant held-out targeted-section gain and no significantly worse section; roster slices also guarded conservatively. Every section is a target of forecast attenuation. No production forecast change. An optimum still at the extension boundary is unresolved, not bracketed.

## Runtime and checks

Three paired full replays (AB/BA/AB): published median 5.34s; RD recording median 5.69s. Samples: {'published': [6.286338750040159, 5.335518916021101, 5.277509583975188], 'record_rd': [6.926990875042975, 5.694189750007354, 5.225695833098143]}. Forecast attenuation is vectorized after replay and does not change the replay. No CI job/build work added; tests cover the small opt-in telemetry.

Native evaluation and market evidence: see [elo_grd_native.md](elo_grd_native.md).

