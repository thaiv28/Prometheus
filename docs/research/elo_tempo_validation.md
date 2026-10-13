# Conditional tempo validation

Historical research before integration, on production baseline a2f7d37. Reproduce these original results from commit 99f3d6a; see the subsequent [fixed-curve adoption comparison](duration_curve_adoption.md) and the baseline-independent [completion gates](duration_curve_gates.md).

Frozen amplitude .175 selected only through 2021; no extra settings tuned. No defaults changed.

## Same residual curve, fixed 30-minute center versus published baseline

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622775 | 0.622281 | -0.000493 [-0.001317, +0.000406] |
| Domestic | FORGE | 7,728 | 0.620718 | 0.620445 | -0.000272 [-0.000815, +0.000290] |
| International | Elo | 556 | 0.615536 | 0.610730 | -0.004806 [-0.008186, -0.001171] |
| International | FORGE | 556 | 0.615536 | 0.610730 | -0.004806 [-0.008186, -0.001171] |
| Cross-league | Elo | 5,385 | 0.582025 | 0.580735 | -0.001290 [-0.002582, -0.000022] |
| Within other leagues | Elo | 37,248 | 0.607578 | 0.605420 | -0.002158 [-0.002605, -0.001745] |
| Within other leagues | FORGE | 37,248 | 0.604491 | 0.602945 | -0.001545 [-0.001927, -0.001200] |

## Conditional center versus fixed center

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622281 | 0.622173 | -0.000108 [-0.000541, +0.000311] |
| Domestic | FORGE | 7,728 | 0.620445 | 0.620365 | -0.000080 [-0.000364, +0.000197] |
| International | Elo | 556 | 0.610730 | 0.612370 | +0.001640 [-0.000112, +0.003303] |
| International | FORGE | 556 | 0.610730 | 0.612370 | +0.001640 [-0.000112, +0.003303] |
| Cross-league | Elo | 5,385 | 0.580735 | 0.581306 | +0.000571 [-0.000128, +0.001247] |
| Within other leagues | Elo | 37,248 | 0.605420 | 0.605891 | +0.000471 [+0.000259, +0.000694] |
| Within other leagues | FORGE | 37,248 | 0.602945 | 0.603668 | +0.000722 [+0.000532, +0.000913] |

## All-season guards (2014 onward, out-of-year fitting)

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 16,810 | 0.631553 | 0.630515 | -0.001038 [-0.001584, -0.000493] |
| Domestic | FORGE | 16,810 | 0.629051 | 0.628457 | -0.000594 [-0.000940, -0.000259] |
| International | Elo | 1,024 | 0.628278 | 0.624174 | -0.004104 [-0.006526, -0.001735] |
| International | FORGE | 1,024 | 0.628278 | 0.624174 | -0.004104 [-0.006526, -0.001735] |
| Cross-league | Elo | 10,184 | 0.601504 | 0.600280 | -0.001225 [-0.002192, -0.000267] |
| Within other leagues | Elo | 69,736 | 0.612731 | 0.611203 | -0.001529 [-0.001858, -0.001191] |
| Within other leagues | FORGE | 69,736 | 0.610065 | 0.609448 | -0.000617 [-0.000875, -0.000359] |

## Nested chronological sensitivity, 2022 onward

Each first-stage Form year uses only earlier domestic outcomes. Outer Elo/Forge/league curves train only on earlier years, using those chronological Form scores. The first year has zero Form as a warm-up; all 2022+ models have ample prior seasons. This is an integrity sensitivity, not another tuned variant.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622729 | 0.622113 | -0.000616 [-0.001337, +0.000203] |
| Domestic | FORGE | 7,728 | 0.621464 | 0.621118 | -0.000346 [-0.000975, +0.000357] |
| International | Elo | 556 | 0.615319 | 0.612713 | -0.002607 [-0.005887, +0.000627] |
| International | FORGE | 556 | 0.615319 | 0.612713 | -0.002607 [-0.005887, +0.000627] |
| Cross-league | Elo | 5,385 | 0.582041 | 0.581383 | -0.000658 [-0.001853, +0.000515] |
| Within other leagues | Elo | 37,248 | 0.607333 | 0.605666 | -0.001667 [-0.002103, -0.001245] |
| Within other leagues | FORGE | 37,248 | 0.604780 | 0.603983 | -0.000798 [-0.001171, -0.000440] |

## Offline market-series evidence

Current-code reconstruction max series probability difference: 1.87e-14. Cached ours are unused; cached prices/cohort only. Both Form and forecast weights are frozen through 2024; the cutoff is exactly the day before start, main roster with carried regional offsets, and current series rho.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| All | Series | 2,398 | 0.571227 | 0.570622 | -0.000606 [-0.002090, +0.000941] |
| Same major league FORGE | Series | 788 | 0.590233 | 0.587792 | -0.002441 [-0.004646, -0.000271] |
| Same other league FORGE | Series | 1,263 | 0.555773 | 0.556147 | +0.000374 [-0.001592, +0.002415] |
| Cross-league Elo | Series | 347 | 0.584319 | 0.584312 | -0.000006 [-0.004880, +0.004776] |

## Interpretation

Conditional centring does **not** improve the same steep curve: it significantly
worsens within-other-league Elo and FORGE relative to the fixed-centre control.
The strong gain over published Elo therefore supports investigating curve shape,
not attributing improvement to tempo surprise. Its conditional-only market result
cannot stand in for the fixed curve's market validation.

The fixed ablation was discovered after inspecting these historical comparisons;
[its follow-up](elo_tempo_fixed.md) uses exactly the same constants without a new
grid, and remains retrospective evidence. Defaults remain unchanged.
