# Fixed duration curve completion gates

The exact power baseline and fixed tanh candidate are frozen in this runner, independent of production defaults. No tuning is performed. These are retrospective checks on previously examined years. Negative loss deltas improve forecasts.

## 2022+ game clustering

League × unordered team pair × calendar day clusters preserve maps from the same series together.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | -0.000493 [-0.001341, +0.000327] |
| Domestic | FORGE | 3,367 | -0.000272 [-0.000796, +0.000262] |
| International | Elo | 250 | -0.004806 [-0.008478, -0.000827] |
| International | FORGE | 250 | -0.004806 [-0.008478, -0.000827] |
| Cross-league | Elo | 3,134 | -0.001290 [-0.002632, -0.000046] |
| Within other leagues | Elo | 22,599 | -0.002158 [-0.002588, -0.001729] |
| Within other leagues | FORGE | 22,599 | -0.001545 [-0.001899, -0.001188] |

## Earlier-only 2022+ clustering

Inner Form scores and outer calibrators use earlier years only. Raw-data imputation and first-year state limitations are inherited equally.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | -0.000326 [-0.001238, +0.000565] |
| Domestic | FORGE | 3,367 | -0.000283 [-0.001073, +0.000484] |
| International | Elo | 250 | -0.005098 [-0.009340, -0.000582] |
| International | FORGE | 250 | -0.005098 [-0.009340, -0.000582] |
| Cross-league | Elo | 3,134 | -0.001431 [-0.002715, -0.000225] |
| Within other leagues | Elo | 22,599 | -0.002372 [-0.002810, -0.001937] |
| Within other leagues | FORGE | 22,599 | -0.001702 [-0.002084, -0.001312] |

## Cached map-1 markets, 2025 onward

Both models' weights are fitted through 2024 only. Calls use the day-before cutoff and latest main roster. Cached old predictions are unused; no prices are fetched.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| All map 1 | Map 1 | 1,444 | 0.614627 | 0.614666 | +0.000039 [-0.001540, +0.001648] |
| Same major league map 1 | Map 1 | 656 | 0.627754 | 0.627676 | -0.000078 [-0.001776, +0.001570] |
| Same other league map 1 | Map 1 | 651 | 0.606443 | 0.607861 | +0.001418 [-0.001174, +0.003995] |
| Cross-league map 1 | Map 1 | 137 | 0.590664 | 0.584713 | -0.005950 [-0.013934, +0.002247] |
