# Fixed duration curve completion gates

Current-model baseline b4e3681: roster-aware Form, time-away updates, move-down bonus and log rookie discount are retained on both sides. The exact power baseline and fixed tanh candidate are frozen in this runner, independent of production defaults. No tuning is performed. These are retrospective checks on previously examined years. Negative loss deltas improve forecasts.

## 2022+ game clustering

League × unordered team pair × calendar day clusters preserve maps from the same series together.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | -0.000632 [-0.001499, +0.000206] |
| Domestic | FORGE | 3,367 | -0.000295 [-0.000845, +0.000247] |
| International | Elo | 250 | -0.004746 [-0.008404, -0.000785] |
| International | FORGE | 250 | -0.004746 [-0.008404, -0.000785] |
| Cross-league | Elo | 3,134 | -0.000663 [-0.002016, +0.000608] |
| Within other leagues | Elo | 22,599 | -0.002044 [-0.002487, -0.001616] |
| Within other leagues | FORGE | 22,599 | -0.001406 [-0.001753, -0.001064] |

## Earlier-only 2022+ clustering

Inner Form scores and outer calibrators use earlier years only. Raw-data imputation and first-year state limitations are inherited equally.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | -0.000450 [-0.001389, +0.000465] |
| Domestic | FORGE | 3,367 | -0.000434 [-0.001302, +0.000403] |
| International | Elo | 250 | -0.004998 [-0.009286, -0.000445] |
| International | FORGE | 250 | -0.004998 [-0.009286, -0.000445] |
| Cross-league | Elo | 3,134 | -0.000746 [-0.002075, +0.000569] |
| Within other leagues | Elo | 22,599 | -0.002181 [-0.002640, -0.001713] |
| Within other leagues | FORGE | 22,599 | -0.001673 [-0.002097, -0.001244] |

## Cached map-1 markets, 2025 onward

Both models' weights are fitted through 2024 only. Calls use the day-before cutoff and latest main roster. Cached old predictions are unused; no prices are fetched.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| All map 1 | Map 1 | 1,444 | 0.615105 | 0.615027 | -0.000078 [-0.001726, +0.001570] |
| Same major league map 1 | Map 1 | 656 | 0.625770 | 0.625784 | +0.000014 [-0.001706, +0.001710] |
| Same other league map 1 | Map 1 | 651 | 0.611098 | 0.612390 | +0.001292 [-0.001426, +0.003925] |
| Cross-league map 1 | Map 1 | 137 | 0.583076 | 0.576050 | -0.007025 [-0.015437, +0.001270] |
