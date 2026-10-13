# Conditional tempo surprise Elo

Historical research before integration, on production baseline a2f7d37. Reproduce these original results from commit 99f3d6a; see the subsequent [fixed-curve adoption comparison](duration_curve_adoption.md) and the baseline-independent [completion gates](duration_curve_gates.md).

Opt-in research on base `a2f7d37`; no published defaults or DB scripts changed.
Source corpus: 205,701 team-match rows (102,857 distinct games), dated 2014-01-14
through 2026-10-11; 205,688 paired rated team-games enter the replay.

## Protocol

The frozen expectation model is online ridge on absolute candidate pregame Elo gap
(capped at 800 points) plus a shrunk league/year residual. Its prior is 30 minutes
with 100 pseudo-games; pooled forgetting is .999/game, league/year .99/game with
50-game shrinkage. Year resets use the current pooled prediction. It predicts
before observing duration, then updates. Expected durations are bounded at 15–60
minutes. Neither result nor a future game is a predictor. Winner/loser updates are
exact complements and K=20, rookie treatment and regional links are unchanged.

Winner score is `.825 + amplitude * tanh((expected_seconds - seconds)/300)`;
.825 is the published duration score midpoint. A fixed softened binary control
(amplitude zero) isolates replacing absolute duration from conditioning on tempo.
This is result evidence plus bounded conditional residual, not a predictive
feature taken from the completed game. The loser receives `1 - winner_score`.

Only amplitudes [0.05, 0.1, 0.175] were tried, selected on domestic Elo log loss
in 2014–2021. Choice: **0.175**, objective 0.637836.
Held-out score years: 2022–2026. The candidate and baseline are fairly
refit using the repository's out-of-year win curves and Form/FORGE fitting.
Within-other Elo uses the per-league curves; FORGE uses its pooled Elo+Form curve.
For the primary 2022+ table, calibrators and Form fit only other 2022+ seasons,
matching the existing margin harness held-out protocol rather than the stock
full-history benchmark. Do not compare its absolute losses with differently
calibrated experiments. The validation report includes full-history all-season
guards and an earlier-only sensitivity.
These fits follow the existing non-nested out-of-year protocol, not an earlier-only
calibration experiment. Earlier inspected years are historical development
evidence, not an untouched prospective test. Intervals resample paired game rows;
series/time dependence and multiple research comparisons limit interpretation.

Baseline reproduction: `Current code vs DB: max |Δ| = 0 over 205,688 team-games; 0 differ; Reproduction: OK (max |Δ| < 1e-6)`.

## Development scores

| Amplitude | Domestic Elo log loss (through 2021) |
|---:|---:|
| 0.05 | 0.639485 |
| 0.1 | 0.638588 |
| 0.175 | 0.637836 |

## Selected candidate, 2022 onward

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622775 | 0.622173 | -0.000601 [-0.001311, +0.000166] |
| Domestic | FORGE | 7,728 | 0.620718 | 0.620365 | -0.000353 [-0.000803, +0.000144] |
| International | Elo | 556 | 0.615536 | 0.612370 | -0.003166 [-0.006182, +0.000098] |
| International | FORGE | 556 | 0.615536 | 0.612370 | -0.003166 [-0.006182, +0.000098] |
| Cross-league | Elo | 5,385 | 0.582025 | 0.581306 | -0.000719 [-0.001996, +0.000554] |
| Within other leagues | Elo | 37,248 | 0.607578 | 0.605891 | -0.001688 [-0.002130, -0.001252] |
| Within other leagues | FORGE | 37,248 | 0.604491 | 0.603668 | -0.000823 [-0.001177, -0.000483] |

## Softened binary control, 2022 onward

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622775 | 0.623743 | +0.000968 [+0.000395, +0.001522] |
| Domestic | FORGE | 7,728 | 0.620718 | 0.621124 | +0.000406 [+0.000071, +0.000725] |
| International | Elo | 556 | 0.615536 | 0.619517 | +0.003981 [+0.001313, +0.006408] |
| International | FORGE | 556 | 0.615536 | 0.619517 | +0.003981 [+0.001313, +0.006408] |
| Cross-league | Elo | 5,385 | 0.582025 | 0.584188 | +0.002163 [+0.001259, +0.003034] |
| Within other leagues | Elo | 37,248 | 0.607578 | 0.610091 | +0.002513 [+0.002227, +0.002817] |
| Within other leagues | FORGE | 37,248 | 0.604491 | 0.606117 | +0.001626 [+0.001400, +0.001859] |

## Binary result control (winner score 1), 2022 onward

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.622775 | 0.623825 | +0.001050 [+0.000378, +0.001678] |
| Domestic | FORGE | 7,728 | 0.620718 | 0.620993 | +0.000276 [-0.000137, +0.000677] |
| International | Elo | 556 | 0.615536 | 0.619965 | +0.004429 [+0.001489, +0.007067] |
| International | FORGE | 556 | 0.615536 | 0.619965 | +0.004429 [+0.001489, +0.007067] |
| Cross-league | Elo | 5,385 | 0.582025 | 0.588827 | +0.006802 [+0.004970, +0.008670] |
| Within other leagues | Elo | 37,248 | 0.607578 | 0.611458 | +0.003880 [+0.003306, +0.004496] |
| Within other leagues | FORGE | 37,248 | 0.604491 | 0.608395 | +0.003905 [+0.003431, +0.004427] |

## Conditional residual versus softened binary control

| Slice | Metric | Games | Baseline | Candidate | Delta [paired 95% CI] |
|---|---|---:|---:|---:|---|
| Domestic | Elo | 7,728 | 0.623743 | 0.622173 | -0.001569 [-0.002757, -0.000256] |
| Domestic | FORGE | 7,728 | 0.621124 | 0.620365 | -0.000759 [-0.001490, +0.000015] |
| International | Elo | 556 | 0.619517 | 0.612370 | -0.007147 [-0.012264, -0.001502] |
| International | FORGE | 556 | 0.619517 | 0.612370 | -0.007147 [-0.012264, -0.001502] |
| Cross-league | Elo | 5,385 | 0.584188 | 0.581306 | -0.002882 [-0.004945, -0.000832] |
| Within other leagues | Elo | 37,248 | 0.610091 | 0.605891 | -0.004200 [-0.004917, -0.003497] |
| Within other leagues | FORGE | 37,248 | 0.606117 | 0.603668 | -0.002450 [-0.002993, -0.001914] |

Expectation MAE over all replay games: 276.5 seconds.

## Tempo diagnostics by era

| Year | Mean duration (s) | Expectation MAE (s) | Winners losing update points |
|---|---:|---:|---:|
| 2014 | 2281.9 | 404.3 | 3.2% |
| 2015 | 2249.3 | 358.5 | 3.5% |
| 2016 | 2181.4 | 361.3 | 3.4% |
| 2017 | 2127.6 | 357.5 | 4.3% |
| 2018 | 2027.4 | 319.9 | 3.5% |
| 2019 | 1937.7 | 274.3 | 2.6% |
| 2020 | 1939.2 | 268.1 | 3.0% |
| 2021 | 1881.3 | 255.6 | 2.9% |
| 2022 | 1895.2 | 260.2 | 2.9% |
| 2023 | 1874.8 | 258.6 | 3.2% |
| 2024 | 1890.1 | 262.3 | 3.9% |
| 2025 | 1921.7 | 251.6 | 3.3% |
| 2026 | 1884.6 | 254.6 | 3.5% |

A winning favorite can still lose Elo when its bounded soft result is below its pregame expected score, as in the published duration model. This is not a binary-only updater.

## Selected candidate annual log-loss differences

| Year | Slice | Metric | Delta |
|---|---|---|---:|
| 2022 | Domestic | Elo | -0.000230 |
| 2023 | Domestic | Elo | -0.000797 |
| 2024 | Domestic | Elo | -0.002016 |
| 2025 | Domestic | Elo | -0.000110 |
| 2026 | Domestic | Elo | +0.000038 |
| 2022 | Domestic | FORGE | -0.000080 |
| 2023 | Domestic | FORGE | -0.000588 |
| 2024 | Domestic | FORGE | -0.001272 |
| 2025 | Domestic | FORGE | +0.000153 |
| 2026 | Domestic | FORGE | -0.000063 |
| 2022 | International | Elo | +0.005582 |
| 2023 | International | Elo | -0.001640 |
| 2024 | International | Elo | -0.005032 |
| 2025 | International | Elo | -0.006466 |
| 2026 | International | Elo | -0.005262 |
| 2022 | International | FORGE | +0.005582 |
| 2023 | International | FORGE | -0.001640 |
| 2024 | International | FORGE | -0.005032 |
| 2025 | International | FORGE | -0.006466 |
| 2026 | International | FORGE | -0.005262 |
| 2022 | Cross-league | Elo | -0.000283 |
| 2023 | Cross-league | Elo | -0.003046 |
| 2024 | Cross-league | Elo | +0.001604 |
| 2025 | Cross-league | Elo | -0.001051 |
| 2026 | Cross-league | Elo | -0.001408 |
| 2022 | Within other leagues | Elo | -0.001857 |
| 2023 | Within other leagues | Elo | -0.001262 |
| 2024 | Within other leagues | Elo | -0.001452 |
| 2025 | Within other leagues | Elo | -0.002345 |
| 2026 | Within other leagues | Elo | -0.001540 |
| 2022 | Within other leagues | FORGE | -0.000868 |
| 2023 | Within other leagues | FORGE | -0.000808 |
| 2024 | Within other leagues | FORGE | -0.000694 |
| 2025 | Within other leagues | FORGE | -0.001181 |
| 2026 | Within other leagues | FORGE | -0.000545 |

## Team-pair/day cluster sensitivity

League × calendar day × unordered team pair is a conservative series proxy; distinct same-day series can be pooled.

| Slice | Metric | Clusters | Delta [cluster 95% CI] |
|---|---|---:|---|
| Domestic | Elo | 3,367 | -0.000601 [-0.001354, +0.000138] |
| Domestic | FORGE | 3,367 | -0.000353 [-0.000802, +0.000112] |
| International | Elo | 250 | -0.003166 [-0.006372, +0.000157] |
| International | FORGE | 250 | -0.003166 [-0.006372, +0.000157] |
| Cross-league | Elo | 3,134 | -0.000719 [-0.002044, +0.000625] |
| Within other leagues | Elo | 22,599 | -0.001688 [-0.002130, -0.001276] |
| Within other leagues | FORGE | 22,599 | -0.000823 [-0.001175, -0.000479] |

## Decision

**The conditional-tempo hypothesis is unsupported.** Its gain over published Elo
comes from the steeper bounded duration curve: keeping that curve centred at a
fixed 30 minutes performs better, significantly so within other leagues (Elo
+0.000471 and FORGE +0.000722 when conditional centring is added).
[Validation](elo_tempo_validation.md) shows the conditional variant's forecast gain
survives chronological and cluster checks and helps major-league market series,
but those facts do not establish value from conditional centring.

Keep production defaults unchanged. The exact fixed-centre curve is a promising
exploratory follow-up, discovered by this retrospective ablation; its dedicated
validation is in [elo_tempo_fixed.md](elo_tempo_fixed.md). No production metric,
tracked weight or DB build algorithm changed.
