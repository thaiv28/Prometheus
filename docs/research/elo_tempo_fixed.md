# Fixed-center duration curve follow-up

Historical research before integration, on production baseline a2f7d37. Reproduce these original results from commit 99f3d6a; see the subsequent [fixed-curve adoption comparison](duration_curve_adoption.md) and the baseline-independent [completion gates](duration_curve_gates.md).

This candidate was noticed in the conditional-tempo attribution ablation after inspecting historical 2022+ results. It is retrospectively explored, not a new prospective confirmation. Exact constants stay frozen (.825, .175, 1800 seconds, 300 seconds); no grid or new tuning. Published defaults remain unchanged.

Development domestic Elo (2014–2021, no tuning): 0.639133.

## All-season guards

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 16,810 | 0.631553 | 0.631283 | -0.000270 [-0.000871, +0.000326] |
| Domestic | FORGE | 16,810 | 0.629051 | 0.628901 | -0.000150 [-0.000519, +0.000209] |
| International | Elo | 1,024 | 0.628278 | 0.623765 | -0.004513 [-0.007541, -0.001674] |
| International | FORGE | 1,024 | 0.628278 | 0.623765 | -0.004513 [-0.007541, -0.001674] |
| Cross-league | Elo | 10,184 | 0.601504 | 0.599913 | -0.001591 [-0.002498, -0.000641] |
| Within other leagues | Elo | 69,736 | 0.612731 | 0.610989 | -0.001742 [-0.002075, -0.001405] |
| Within other leagues | FORGE | 69,736 | 0.610065 | 0.609021 | -0.001044 [-0.001317, -0.000777] |

## Nested chronological sensitivity, 2022 onward

All first-stage Form and outer calibration use strictly earlier years as in the preceding validation; no constants were refit on the held-out years.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622729 | 0.622403 | -0.000326 [-0.001238, +0.000640] |
| Domestic | FORGE | 7,728 | 0.621464 | 0.621181 | -0.000283 [-0.001081, +0.000556] |
| International | Elo | 556 | 0.615319 | 0.610221 | -0.005098 [-0.008978, -0.000848] |
| International | FORGE | 556 | 0.615319 | 0.610221 | -0.005098 [-0.008978, -0.000848] |
| Cross-league | Elo | 5,385 | 0.582041 | 0.580610 | -0.001431 [-0.002637, -0.000183] |
| Within other leagues | Elo | 37,248 | 0.607333 | 0.604961 | -0.002372 [-0.002844, -0.001940] |
| Within other leagues | FORGE | 37,248 | 0.604780 | 0.603079 | -0.001702 [-0.002111, -0.001315] |

## Frozen-through-2024 market evidence

The preceding conditional validation reproduced current routing to 1.87e-14; that equality pass is reused, not rerun here. Cached ours are unused; cached prices/cohort only. Both Form and forecast weights are frozen through 2024; the cutoff is exactly the day before start, main roster with carried regional offsets, and current series rho.

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| All | Series | 2,398 | 0.571227 | 0.570194 | -0.001033 [-0.002711, +0.000659] |
| Same major league FORGE | Series | 788 | 0.590233 | 0.588368 | -0.001865 [-0.003965, +0.000290] |
| Same other league FORGE | Series | 1,263 | 0.555773 | 0.555036 | -0.000737 [-0.002967, +0.001481] |
| Cross-league Elo | Series | 347 | 0.584319 | 0.584096 | -0.000223 [-0.006506, +0.006141] |

Fixed curve versus conditional curve on the same market cohort:

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| All | Series | 2,398 | 0.570622 | 0.570194 | -0.000427 [-0.001414, +0.000568] |
| Same major league FORGE | Series | 788 | 0.587792 | 0.588368 | +0.000575 [-0.000564, +0.001796] |
| Same other league FORGE | Series | 1,263 | 0.556147 | 0.555036 | -0.001111 [-0.002197, -0.000005] |
| Cross-league Elo | Series | 347 | 0.584312 | 0.584096 | -0.000217 [-0.005080, +0.004914] |

## Decision and remaining checks

The fixed curve is the strongest candidate from this experiment, but remains research-only. Its chronological gains survive fair earlier-only fitting, and no scored game or cached-series slice significantly worsens. This does not establish a market improvement: the market-series intervals include zero. The fixed constants were inherited from an attribution ablation inspected after historical results; this is retrospective evidence rather than a newly untouched holdout.

The state pipeline inherits annual-file mean imputation and initial-year warmup limitations. Fixed-curve confidence intervals resample games; clustering was reported for the conditional candidate, not separately for the fixed curve. Before adoption, check fixed-curve dependence sensitivity and map-1 market outcomes, refresh production weights and run the standard production benchmark/build comparisons. Published computation and weights remain unchanged.

Rerun the frozen follow-up with `uv run python scripts/research/elo_tempo_validation.py --fixed-only --out docs/research/elo_tempo_fixed.md`. Its market input is a private copy of `data/markets/frames.pkl`; no price fetching is performed.
