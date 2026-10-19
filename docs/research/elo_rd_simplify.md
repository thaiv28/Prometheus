# Elo RD slope and move-down simplifications

Fixed three-arm experiment against published Elo (base 00237c0). Defaults remain unchanged. Negative Δ log loss is better.

Training objective: games-weighted domestic + within-other-league Elo, 2014–2021. Held out: 2022–2026. No tuning, selection or boundary extension: all three mechanisms fixed in code before scoring. PLAYER_RD_INFORMATION remains .125, K 20 and all other settings published.

Own-game slope uses OTHER_LEAGUE_SLOPE (.0065) for non-major domestic games and ln(10)/400 otherwise, in both slope² and E of the RD information term. No move-down disables only the stored +25 transfer bonus.

Unchanged elo_glicko sections/comparison and elo_variants replay: leave-one-year-out forecast curves within each partition, replay-specific Form weights/opponent adjustment and FORGE refits. Other-league Form fits inherit other major-league years. This is a rating-design comparison, not an earlier-only deployment simulation. 95% paired individual-game bootstrap intervals, without series clustering or multiplicity adjustment; historical holdouts were viewed in earlier research. Published DB/replay equality and each variant's prefix/full equality checked.

| Fixed setting | ≤2021 objective |
|---|---:|
| Published | 0.61999453 |
| Game slope | 0.61999574 |
| No move-down | 0.62010845 |
| Both | 0.62010473 |

## Game slope

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | -0.00010 (-0.00019 to -0.00002) |
| Elo, international | 589 | 0.61877 | -0.00020 (-0.00046 to +0.00006) |
| FORGE, domestic | 7,728 | 0.62010 | -0.00005 (-0.00011 to +0.00001) |
| FORGE, international | 589 | 0.61154 | -0.00001 (-0.00017 to +0.00015) |
| Elo, other leagues | 37,272 | 0.60081 | +0.00012 (-0.00000 to +0.00025) |
| FORGE, other leagues | 37,272 | 0.59979 | -0.00005 (-0.00015 to +0.00006) |
| Elo, cross-league | 5,442 | 0.57070 | +0.00007 (-0.00026 to +0.00040) |

### Roster-change diagnostic

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | -0.00019 (-0.00057 to +0.00018) |
| Elo, international | 9 | 0.78976 | +0.00333 (+0.00115 to +0.00594) |
| FORGE, domestic | 703 | 0.58950 | -0.00001 (-0.00026 to +0.00024) |
| FORGE, international | 9 | 0.78809 | +0.00202 (+0.00046 to +0.00390) |
| Elo, other leagues | 6,814 | 0.58324 | -0.00017 (-0.00044 to +0.00013) |
| FORGE, other leagues | 6,814 | 0.58221 | -0.00025 (-0.00048 to -0.00000) |
| Elo, cross-league | 682 | 0.53321 | +0.00076 (-0.00031 to +0.00183) |

Held-out gate: **PASS**. Roster-change slices are diagnostic; the requested gate guards forecast sections.


## No move-down

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | +0.00008 (-0.00042 to +0.00060) |
| Elo, international | 589 | 0.61877 | +0.00001 (-0.00123 to +0.00124) |
| FORGE, domestic | 7,728 | 0.62010 | +0.00006 (-0.00027 to +0.00041) |
| FORGE, international | 589 | 0.61154 | -0.00025 (-0.00115 to +0.00066) |
| Elo, other leagues | 37,272 | 0.60081 | +0.00035 (+0.00015 to +0.00055) |
| FORGE, other leagues | 37,272 | 0.59979 | +0.00027 (+0.00008 to +0.00045) |
| Elo, cross-league | 5,442 | 0.57070 | +0.00521 (+0.00420 to +0.00628) |

### Roster-change diagnostic

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | +0.00038 (-0.00169 to +0.00251) |
| Elo, international | 9 | 0.78976 | -0.01150 (-0.02281 to +0.00014) |
| FORGE, domestic | 703 | 0.58950 | +0.00021 (-0.00116 to +0.00167) |
| FORGE, international | 9 | 0.78809 | -0.00778 (-0.01547 to -0.00015) |
| Elo, other leagues | 6,814 | 0.58324 | +0.00067 (+0.00019 to +0.00118) |
| FORGE, other leagues | 6,814 | 0.58221 | +0.00056 (+0.00010 to +0.00103) |
| Elo, cross-league | 682 | 0.53321 | +0.00630 (+0.00292 to +0.00950) |

Held-out gate: **FAIL**. Roster-change slices are diagnostic; the requested gate guards forecast sections.


## Both

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | -0.00002 (-0.00053 to +0.00050) |
| Elo, international | 589 | 0.61877 | -0.00020 (-0.00139 to +0.00098) |
| FORGE, domestic | 7,728 | 0.62010 | +0.00002 (-0.00031 to +0.00036) |
| FORGE, international | 589 | 0.61154 | -0.00026 (-0.00114 to +0.00064) |
| Elo, other leagues | 37,272 | 0.60081 | +0.00046 (+0.00022 to +0.00070) |
| FORGE, other leagues | 37,272 | 0.59979 | +0.00021 (-0.00001 to +0.00042) |
| Elo, cross-league | 5,442 | 0.57070 | +0.00536 (+0.00424 to +0.00644) |

### Roster-change diagnostic

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | +0.00019 (-0.00194 to +0.00236) |
| Elo, international | 9 | 0.78976 | -0.00792 (-0.01884 to +0.00454) |
| FORGE, domestic | 703 | 0.58950 | +0.00022 (-0.00121 to +0.00171) |
| FORGE, international | 9 | 0.78809 | -0.00552 (-0.01279 to +0.00266) |
| Elo, other leagues | 6,814 | 0.58324 | +0.00049 (-0.00006 to +0.00107) |
| FORGE, other leagues | 6,814 | 0.58221 | +0.00029 (-0.00021 to +0.00081) |
| Elo, cross-league | 682 | 0.53321 | +0.00711 (+0.00369 to +0.01048) |

Held-out gate: **FAIL**. Roster-change slices are diagnostic; the requested gate guards forecast sections.


## Runtime

Three interleaved full replays per setting, reverse order in round two; VECLIB_MAXIMUM_THREADS=1. Concurrent machine load can affect timings.

| Setting | Median seconds | Runs |
|---|---:|---|
| Published | 5.20 | 5.11, 5.20, 5.41 |
| Game slope | 5.66 | 5.33, 5.66, 6.17 |
| No move-down | 6.09 | 6.09, 5.35, 6.10 |
| Both | 6.34 | 6.34, 5.89, 6.67 |

## Decision rule

A simplification is worth it only if no forecast section (held-out and native) and no native markets series row is significantly worse. Significant gains are reported but not required. Run native for every held-out passer; see [native comparisons](elo_rd_simplify_native.md). No defaults or weights are promoted by this experiment.

