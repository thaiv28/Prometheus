# One learned regional offset: full Elo replay

Research only. Production compute_elo_records is unmodified; an iterator observes games and an isolated mapping factory exposes its single offset table. Replacement uses league_share=0 and overwrites that table with fitted offsets. Every player update, rookie baseline, transfer conversion and later team rating is replayed with the new offsets. No post-hoc regional term is added to probabilities.

Ridge 4 and persistent history are inherited from the <=2021 experiment; no new tuning/grid. Fixed-scale replacement holds the published cross-region slope constant. Scaled replacement fits that slope alongside offsets. Scale-only keeps ordinary offsets and learns probability scaling independently. Recalibrated-fixed retains ordinary game-by-game updates, then fits absolute offsets shrunk toward the current offset table, overwriting that same table at completed events. It is a single-state follow-up, fixed ridge 4 and fixed probability scale, specified after the replacement result; not an untouched confirmation or a new grid. Player update expectations retain the published 400-point curve in every arm.

Fits use only completed eligible older event blocks, at the end of a UTC day; new offsets/scales are available the next day. All historical fitting inputs are actual pre-game starter ratings. Evaluation uses production main-roster ratings before each UTC day; this distinction is common to the replay controls. Each finished pair/day contributes total weight one. Event provenance/coverage and inherited baseline hindsight limits are those of regional_correction.py. The same raw games/rosters and fixed priced cohort are used in every arm; Kalshi prices/results never enter fitting. No uncertainty/team-effect term.

Baseline native pre-game ratings reproduce the private DB within 1e-9. Every saved cross-region series/map call at both cutoffs reproduces the previous diagnostic within 1e-12. Intervals are paired by team-pair/day and by event for map results. Market intervals pair series; four events remain weak evidence. Research does not constitute a native production adoption-gate run or a prospective market edge.

## 2022+ day-before maps

## Forecast-only attribution controls

These preserve original player/offset histories and never feed corrections into updates. They isolate probability scale and distinguish an equivalent folded prediction from a replacement learning rule. The scaled overlay reproduces the previous persistent correction within 1e-8. Replacing offset learning also changes replay feedback and fits on native pre-game rather than day-start inputs; the difference cannot be attributed solely to replay feedback.

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 1006 | 0.5918 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| overlay_fixed | 1006 | 0.5789 | -0.0128 [-0.0232, -0.0023] | [-0.0229, -0.0012] |
| overlay_scaled | 1006 | 0.5743 | -0.0175 [-0.0272, -0.0075] | [-0.0276, -0.0065] |

### All

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 1006 | 0.5918 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 1006 | 0.5930 | +0.0012 [-0.0041, +0.0067] | [-0.0029, +0.0054] |
| replacement_fixed | 1006 | 0.5935 | +0.0017 [-0.0036, +0.0073] | [-0.0035, +0.0070] |
| replacement_scaled | 1006 | 0.5964 | +0.0046 [-0.0067, +0.0157] | [-0.0047, +0.0141] |
| recalibrated_fixed | 1006 | 0.5860 | -0.0058 [-0.0108, -0.0007] | [-0.0100, -0.0007] |

### Entry

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 267 | 0.5961 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 267 | 0.6029 | +0.0069 [-0.0041, +0.0182] | [-0.0021, +0.0160] |
| replacement_fixed | 267 | 0.5987 | +0.0026 [-0.0068, +0.0119] | [-0.0052, +0.0117] |
| replacement_scaled | 267 | 0.5880 | -0.0080 [-0.0324, +0.0157] | [-0.0294, +0.0123] |
| recalibrated_fixed | 267 | 0.5937 | -0.0024 [-0.0149, +0.0104] | [-0.0145, +0.0104] |

### Later

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 739 | 0.5902 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 739 | 0.5893 | -0.0009 [-0.0068, +0.0052] | [-0.0068, +0.0059] |
| replacement_fixed | 739 | 0.5916 | +0.0014 [-0.0052, +0.0077] | [-0.0062, +0.0085] |
| replacement_scaled | 739 | 0.5994 | +0.0092 [-0.0036, +0.0215] | [-0.0062, +0.0250] |
| recalibrated_fixed | 739 | 0.5832 | -0.0070 [-0.0121, -0.0021] | [-0.0120, -0.0019] |

### Major v major

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 556 | 0.6209 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 556 | 0.6264 | +0.0055 [-0.0015, +0.0128] | [+0.0001, +0.0112] |
| replacement_fixed | 556 | 0.6218 | +0.0008 [-0.0072, +0.0087] | [-0.0072, +0.0083] |
| replacement_scaled | 556 | 0.6207 | -0.0003 [-0.0149, +0.0143] | [-0.0106, +0.0097] |
| recalibrated_fixed | 556 | 0.6183 | -0.0026 [-0.0081, +0.0029] | [-0.0079, +0.0025] |

### 2022

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 193 | 0.5240 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 193 | 0.5158 | -0.0082 [-0.0156, -0.0002] | [-0.0105, -0.0049] |
| replacement_fixed | 193 | 0.5329 | +0.0089 [-0.0003, +0.0175] | [+0.0010, +0.0145] |
| replacement_scaled | 193 | 0.5376 | +0.0136 [-0.0019, +0.0280] | [+0.0118, +0.0162] |
| recalibrated_fixed | 193 | 0.5149 | -0.0091 [-0.0198, +0.0017] | [-0.0123, -0.0068] |

### 2023

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 151 | 0.6181 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 151 | 0.6205 | +0.0024 [-0.0106, +0.0161] | [-0.0006, +0.0042] |
| replacement_fixed | 151 | 0.6119 | -0.0062 [-0.0217, +0.0086] | [-0.0115, -0.0030] |
| replacement_scaled | 151 | 0.6015 | -0.0166 [-0.0456, +0.0115] | [-0.0235, -0.0124] |
| recalibrated_fixed | 151 | 0.5983 | -0.0198 [-0.0377, -0.0040] | [-0.0300, -0.0136] |

### 2024

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 185 | 0.6255 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 185 | 0.6326 | +0.0071 [-0.0037, +0.0175] | [+0.0035, +0.0191] |
| replacement_fixed | 185 | 0.6205 | -0.0049 [-0.0138, +0.0043] | [-0.0196, +0.0009] |
| replacement_scaled | 185 | 0.6188 | -0.0066 [-0.0252, +0.0125] | [-0.0386, +0.0046] |
| recalibrated_fixed | 185 | 0.6214 | -0.0041 [-0.0150, +0.0065] | [-0.0167, +0.0007] |

### 2025

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 222 | 0.6057 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 222 | 0.6061 | +0.0005 [-0.0092, +0.0103] | [-0.0064, +0.0096] |
| replacement_fixed | 222 | 0.6162 | +0.0106 [-0.0025, +0.0242] | [-0.0001, +0.0287] |
| replacement_scaled | 222 | 0.6201 | +0.0144 [-0.0048, +0.0338] | [+0.0037, +0.0228] |
| recalibrated_fixed | 222 | 0.6130 | +0.0073 [-0.0034, +0.0185] | [-0.0001, +0.0192] |

### 2026

| Model | n | LL | Δ vs existing Elo (series-cluster 95%) | Event-cluster sensitivity |
|---|---:|---:|---|---|
| baseline | 255 | 0.5909 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] |
| scale_only | 255 | 0.5948 | +0.0039 [-0.0094, +0.0189] | [-0.0063, +0.0111] |
| replacement_fixed | 255 | 0.5889 | -0.0020 [-0.0137, +0.0093] | [-0.0114, +0.0064] |
| replacement_scaled | 255 | 0.6010 | +0.0101 [-0.0227, +0.0408] | [-0.0119, +0.0352] |
| recalibrated_fixed | 255 | 0.5833 | -0.0076 [-0.0162, +0.0011] | [-0.0115, -0.0031] |

## Fixed market cohort

The 12h comparison is primary; common rows have prices at both cutoffs.

### 12h

| Model | n | LL | Δ vs existing Elo (paired series 95%) | Event-cluster sensitivity | Δ vs Kalshi (paired series 95%) |
|---|---:|---:|---|---|---|
| baseline | 76 | 0.5510 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] | +0.0162 [-0.0841, +0.1059] |
| scale_only | 76 | 0.5610 | +0.0100 [-0.0127, +0.0345] | [-0.0126, +0.0463] | +0.0261 [-0.0771, +0.1221] |
| replacement_fixed | 76 | 0.5442 | -0.0069 [-0.0262, +0.0120] | [-0.0362, +0.0100] | +0.0093 [-0.0954, +0.1057] |
| replacement_scaled | 76 | 0.5843 | +0.0333 [-0.0323, +0.0953] | [-0.0592, +0.1073] | +0.0495 [-0.0516, +0.1428] |
| recalibrated_fixed | 76 | 0.5442 | -0.0068 [-0.0229, +0.0090] | [-0.0262, +0.0011] | +0.0094 [-0.0846, +0.0946] |
| Kalshi | 76 | 0.5349 | -0.0162 [-0.1059, +0.0841] | [-0.0327, +0.0144] | +0.0000 [+0.0000, +0.0000] |

### Close, common

| Model | n | LL | Δ vs existing Elo (paired series 95%) | Event-cluster sensitivity | Δ vs Kalshi (paired series 95%) |
|---|---:|---:|---|---|---|
| baseline | 76 | 0.5496 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] | +0.0438 [-0.0549, +0.1318] |
| scale_only | 76 | 0.5584 | +0.0088 [-0.0135, +0.0327] | [-0.0124, +0.0413] | +0.0525 [-0.0503, +0.1485] |
| replacement_fixed | 76 | 0.5434 | -0.0062 [-0.0266, +0.0132] | [-0.0369, +0.0106] | +0.0376 [-0.0698, +0.1314] |
| replacement_scaled | 76 | 0.5847 | +0.0351 [-0.0285, +0.0959] | [-0.0537, +0.1079] | +0.0789 [-0.0232, +0.1698] |
| recalibrated_fixed | 76 | 0.5435 | -0.0061 [-0.0213, +0.0092] | [-0.0256, +0.0017] | +0.0377 [-0.0561, +0.1214] |
| Kalshi | 76 | 0.5058 | -0.0438 [-0.1318, +0.0549] | [-0.0706, -0.0149] | +0.0000 [+0.0000, +0.0000] |

### Close, all

| Model | n | LL | Δ vs existing Elo (paired series 95%) | Event-cluster sensitivity | Δ vs Kalshi (paired series 95%) |
|---|---:|---:|---|---|---|
| baseline | 95 | 0.5716 | +0.0000 [+0.0000, +0.0000] | [+0.0000, +0.0000] | +0.0447 [-0.0389, +0.1192] |
| scale_only | 95 | 0.5887 | +0.0171 [-0.0058, +0.0427] | [-0.0049, +0.0416] | +0.0618 [-0.0197, +0.1375] |
| replacement_fixed | 95 | 0.5520 | -0.0196 [-0.0421, +0.0012] | [-0.0670, +0.0038] | +0.0251 [-0.0670, +0.1096] |
| replacement_scaled | 95 | 0.5786 | +0.0070 [-0.0519, +0.0632] | [-0.0737, +0.0848] | +0.0517 [-0.0455, +0.1384] |
| recalibrated_fixed | 95 | 0.5533 | -0.0184 [-0.0346, -0.0020] | [-0.0577, -0.0022] | +0.0264 [-0.0540, +0.1010] |
| Kalshi | 95 | 0.5269 | -0.0447 [-0.1192, +0.0389] | [-0.0618, -0.0306] | +0.0000 [+0.0000, +0.0000] |

