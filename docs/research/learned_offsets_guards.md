# Single-offset replay: native forecast checks

The saved full replays use the same raw games/rosters, current player update rules and duration curve. This runner checks downstream domestic, international, cross-league and other-league effects, including refitted Form/FORGE. It uses existing native out-of-year curves and Form fitting, not the separate earlier-event cross-region scale. Thus it tests rating-table effects, not proof that a scaled candidate passes every production gate. No production DB/weights changed. Previously viewed data; this is not a prospective confirmation.

## scale_only

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622282 | 0.622282 | +0.000000 [+0.000000, +0.000000] |
| Domestic | FORGE | 7,728 | 0.620028 | 0.620028 | +0.000000 [+0.000000, +0.000000] |
| International | Elo | 556 | 0.610921 | 0.610921 | +0.000000 [+0.000000, +0.000000] |
| International | FORGE | 556 | 0.610921 | 0.610921 | +0.000000 [+0.000000, +0.000000] |
| Cross-league | Elo | 5,385 | 0.572427 | 0.572427 | +0.000000 [+0.000000, +0.000000] |
| Within other leagues | Elo | 37,248 | 0.604105 | 0.604105 | +0.000000 [+0.000000, +0.000000] |
| Within other leagues | FORGE | 37,248 | 0.601519 | 0.601519 | +0.000000 [+0.000000, +0.000000] |

Paired dependence sensitivity: team-pair/day clusters.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | +0.000000 [+0.000000, +0.000000] |
| Domestic | FORGE | 3,367 | +0.000000 [+0.000000, +0.000000] |
| International | Elo | 250 | +0.000000 [+0.000000, +0.000000] |
| International | FORGE | 250 | +0.000000 [+0.000000, +0.000000] |
| Cross-league | Elo | 3,134 | +0.000000 [+0.000000, +0.000000] |
| Within other leagues | Elo | 22,599 | +0.000000 [+0.000000, +0.000000] |
| Within other leagues | FORGE | 22,599 | +0.000000 [+0.000000, +0.000000] |

## replacement_fixed

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622282 | 0.622475 | +0.000193 [-0.000219, +0.000627] |
| Domestic | FORGE | 7,728 | 0.620028 | 0.620274 | +0.000246 [-0.000033, +0.000537] |
| International | Elo | 556 | 0.610921 | 0.614426 | +0.003505 [-0.003336, +0.010377] |
| International | FORGE | 556 | 0.610921 | 0.614426 | +0.003505 [-0.003336, +0.010377] |
| Cross-league | Elo | 5,385 | 0.572427 | 0.571784 | -0.000643 [-0.002006, +0.000613] |
| Within other leagues | Elo | 37,248 | 0.604105 | 0.604017 | -0.000088 [-0.000246, +0.000059] |
| Within other leagues | FORGE | 37,248 | 0.601519 | 0.601449 | -0.000070 [-0.000193, +0.000050] |

Paired dependence sensitivity: team-pair/day clusters.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | +0.000193 [-0.000254, +0.000637] |
| Domestic | FORGE | 3,367 | +0.000246 [-0.000039, +0.000528] |
| International | Elo | 250 | +0.003505 [-0.002877, +0.010369] |
| International | FORGE | 250 | +0.003505 [-0.002877, +0.010369] |
| Cross-league | Elo | 3,134 | -0.000643 [-0.001994, +0.000688] |
| Within other leagues | Elo | 22,599 | -0.000088 [-0.000239, +0.000060] |
| Within other leagues | FORGE | 22,599 | -0.000070 [-0.000191, +0.000054] |

## replacement_scaled

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622282 | 0.623628 | +0.001346 [-0.000023, +0.002726] |
| Domestic | FORGE | 7,728 | 0.620028 | 0.620023 | -0.000005 [-0.000957, +0.000899] |
| International | Elo | 556 | 0.610921 | 0.609379 | -0.001542 [-0.014878, +0.012181] |
| International | FORGE | 556 | 0.610921 | 0.609379 | -0.001542 [-0.014878, +0.012181] |
| Cross-league | Elo | 5,385 | 0.572427 | 0.573854 | +0.001427 [-0.002533, +0.005208] |
| Within other leagues | Elo | 37,248 | 0.604105 | 0.605628 | +0.001523 [+0.001023, +0.002034] |
| Within other leagues | FORGE | 37,248 | 0.601519 | 0.602666 | +0.001147 [+0.000734, +0.001570] |

Paired dependence sensitivity: team-pair/day clusters.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | +0.001346 [+0.000055, +0.002636] |
| Domestic | FORGE | 3,367 | -0.000005 [-0.000908, +0.000948] |
| International | Elo | 250 | -0.001542 [-0.015317, +0.012771] |
| International | FORGE | 250 | -0.001542 [-0.015317, +0.012771] |
| Cross-league | Elo | 3,134 | +0.001427 [-0.002943, +0.005886] |
| Within other leagues | Elo | 22,599 | +0.001523 [+0.001024, +0.002007] |
| Within other leagues | FORGE | 22,599 | +0.001147 [+0.000724, +0.001542] |

## recalibrated_fixed

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622282 | 0.622731 | +0.000450 [-0.000106, +0.001019] |
| Domestic | FORGE | 7,728 | 0.620028 | 0.620314 | +0.000286 [-0.000089, +0.000673] |
| International | Elo | 556 | 0.610921 | 0.609219 | -0.001702 [-0.006722, +0.003218] |
| International | FORGE | 556 | 0.610921 | 0.609219 | -0.001702 [-0.006722, +0.003218] |
| Cross-league | Elo | 5,385 | 0.572427 | 0.568672 | -0.003755 [-0.005280, -0.002201] |
| Within other leagues | Elo | 37,248 | 0.604105 | 0.604492 | +0.000387 [+0.000059, +0.000710] |
| Within other leagues | FORGE | 37,248 | 0.601519 | 0.601721 | +0.000203 [-0.000054, +0.000449] |

Paired dependence sensitivity: team-pair/day clusters.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | +0.000450 [-0.000095, +0.001038] |
| Domestic | FORGE | 3,367 | +0.000286 [-0.000089, +0.000666] |
| International | Elo | 250 | -0.001702 [-0.006352, +0.003052] |
| International | FORGE | 250 | -0.001702 [-0.006352, +0.003052] |
| Cross-league | Elo | 3,134 | -0.003755 [-0.005452, -0.002169] |
| Within other leagues | Elo | 22,599 | +0.000387 [+0.000045, +0.000703] |
| Within other leagues | FORGE | 22,599 | +0.000203 [-0.000059, +0.000458] |

## Other-league regression: roster slices

Descriptive only: either team has a starter within 10 appearances of a known home-league change; otherwise a starter with fewer than 25 prior appearances; otherwise neither. Groups are disjoint. Homes and rosters are the actual game's, from the baseline DB. This includes promotions/home relabelling as well as transfers. It cannot establish which mechanism caused the regression or identify a remedy.

| Slice | Games | Mean Δ LL | Sum of Δ LL |
|---|---:|---:|---:|
| Recent home-league move | 19751 | +0.000700 | +13.826 |
| Rookie, no recent move | 7976 | +0.000292 | +2.327 |
| Neither | 9521 | -0.000182 | -1.737 |

Runtime: 37.33 s.
