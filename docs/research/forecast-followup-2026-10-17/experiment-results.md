# Prometheus experiment results — before any merge

Research date: October 17, 2026. No production source edits, commit, PR creation, or merge. No reusable skill was created.

The strongest measured signal is **post-draft professional champion information**, including the features in the still-unmerged draft research branch. The new pre-draft families do not establish a broadly safe improvement over current FORGE. External patch champion win rates remain a plausible input, but the unrestricted addition worsens held-out loss. A well-covered post-draft subgroup shows a small incremental gain; pre-draft and 2026 evidence remain insufficient.

These are completed minimum experiments and feasibility probes, not a claim that full implementations of every paper have been exhaustively optimized. Full fearless draft simulation, full BOCPD run-length inference with patch-conditioned hazards, and the published hypergraph graph-regularized model were not implemented. Their tested prerequisites and simpler nested comparisons are reported explicitly below.

## 1. What was actually audited and rebuilt

**Verified current main:** [`ac5745ca1982d7347d7caee2f98f70f7f1832c53`](https://github.com/thaiv28/Prometheus/tree/ac5745ca1982d7347d7caee2f98f70f7f1832c53). A final remote-head check still returned this revision. **Draft research head:** [`dd84749b364d4580b41e7236ca98188f6a6d6596`](https://github.com/thaiv28/Prometheus/tree/dd84749b364d4580b41e7236ca98188f6a6d6596), also checked remotely. [PR #78](https://github.com/thaiv28/Prometheus/pull/78) was inspected but not merged.

The audit covered AGENTS.md; product, current state, technical, deployment, and UI steering; README, PRODUCT.md and DESIGN.md; research history and conclusions; and the Elo, Form, FORGE, regional calibration, series and market implementations. The earlier detailed research report supplies the literature review and novelty audit. This report supplies newly executed experiments.

The unmodified ingestion, Elo bootstrap and Form functions were run on pinned public copies of Oracle’s Elixir CSVs. Official Drive downloads hit quota. Sources and SHA256 values are in `mirror-manifest.json`: 2014–2024 from [LouisPoutrain/Lol-ML](https://github.com/LouisPoutrain/Lol-ML/tree/69a2856df3a6e566af49473f801b9ad7af8c85ad/raw_data); 2025–2026 from [chrisvu1007/league-of-legends-match-predictor](https://github.com/chrisvu1007/league-of-legends-match-predictor/tree/29838abc074d60a83c7a9638a456a2d366b5546d/data).

**Important limitation:** this reconstructs production algorithms on a historical mirror, not the exact October deployment database. Coverage ends **May 22, 2026**. A first scratch-local database failed integrity while building; a fresh rebuild in `/tmp` passed SQLite `quick_check`. Only the healthy rebuild was scored. It contains 196,108 team rows; 98,026 maps pair blue and red; 93,958 maps have both prior-day team states. Missing prior-state maps were excluded, rather than assigned invented ratings.

The vectorized production forecast was checked against `schedule.RatingsBefore` and `schedule.game_probability` on 21 fixed-sample maps across major, minor, international, same-home international and other cross-league routes. Maximum absolute probability error: **4.44 × 10⁻¹⁶**. This validates those routing examples; it is not an exhaustive proof for every team-name alias or missing-Form fallback.

## 2. Evaluation protocol and controls

- Training through 2021: **47,258 maps**. Hyperparameter selection in 2022–2023: **22,744**. Final retrospective evaluation in 2024 through the mirror cutoff: **23,956**.
- Main pre-match features use strictly prior UTC-day histories and the last observed roster. Current picks and current actual starters are excluded. Online strength and performance states update after the day’s forecasts.
- The draft comparison is explicitly post-draft and requires all ten picks plus player snapshot coverage. Its professional-history features use earlier OE timestamps, so earlier maps on the same day can enter. This is a different information horizon from a morning/12-hour forecast.
- The current packaged FORGE coefficients are the production reference. A three-route temperature control, fitted through 2023, prevents a new feature from receiving credit merely for rescaling major, minor or cross-league probabilities. Post-draft controls also fit the common blue-side intercept. Every candidate is compared on identical maps.
- A second control refits Form’s scoring weights and the FORGE/Elo curves from earlier years only. International regional calibration uses the packaged earlier-available, event-frozen snapshot. Current Elo heuristics and this study’s historical years have already been examined in repository research: this is **retrospective chronological evaluation, not prospective confirmation**.
- Primary metric is paired map log loss. Negative Δ is better. Intervals below are nominal 95% paired bootstrap intervals from 1,500 samples of league/team-pair/UTC-day clusters, approximating series. International sensitivity resamples event/year clusters 10,000 times. Brier, ECE, and calibration intercept/slope are in the JSON results.
- Penalties and small parameter grids were selected only on 2022–2023, using an equal-weight average over major domestic, minor domestic and international loss. Final feature coefficients fit through 2023; test outcomes may update allowed historical states but do not refit those coefficients.
- Confidence intervals condition on the fitted models and omit some training and selection uncertainty. Many families were examined. A nominal interval excluding zero alone does not constitute a production shipping decision.

### Production and calibration control

| Test slice | Maps | Packaged production log loss | Calibration control log loss | Control Δ [95% CI] |
|---|---:|---:|---:|---:|
| all | 23,956 | 0.61127 | 0.61097 | -0.00030 [-0.00061, +0.00000] |
| major_domestic | 4,756 | 0.62565 | 0.62528 | -0.00037 [-0.00102, +0.00028] |
| minor_domestic | 16,465 | 0.60768 | 0.60736 | -0.00032 [-0.00070, +0.00005] |
| international | 449 | 0.60882 | 0.60790 | -0.00093 [-0.00237, +0.00047] |
| intl_entry | 139 | 0.57522 | 0.57459 | -0.00064 [-0.00283, +0.00171] |


“International entry” here means a team’s first cross-home international appearance day in that event/year; 139 maps meet that proxy. It is **not** a validated tournament-entry forecast issued before the entire event. Same-home international maps are separately labeled. “Other cross-league” games are not silently counted as domestic or international.

## 3. Ranked findings — predictive evidence, feasibility and upside

### First: professional draft information — strongest measured signal, available after draft

**Mechanism and failure mode.** FORGE knows team performance and player-carried Elo, but does not price the actual ten-champion composition. The draft model adds player champion experience; wins above Elo on that champion; player-relative lane gold performance; 60-day champion-role professional wins above Elo; and, in the full version, champion matchup and teammate-champion pair effects.

**Nearest existing work.** These are the inspected PR #78 research features, not a newly discovered capability or a shipped pre-match feature. The original PR report compared chiefly with fitted Elo. This experiment instead adds its features to current FORGE plus regional calibration and a matched side/temperature control. Its train/development/test dates and corpus also differ from the PR report, so the numbers need not reproduce that report exactly.

**Measured result.** This cohort has 21,361 test maps: 2,874 major domestic, 15,887 minor domestic, 371 cross-home international, and other separately labeled maps. Major coverage is materially smaller than in the primary cohort because the draft script requires player snapshots, excluding substantial historical LPL coverage.


| Experiment | All maps Δ log loss [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| pr78_meta | -0.00236 [-0.00307, -0.00166] | -0.00320 [-0.00513, -0.00137] | -0.00641 [-0.01207, -0.00090] |
| pr78_draft | -0.00387 [-0.00482, -0.00295] | -0.00395 [-0.00643, -0.00154] | -0.00812 [-0.01674, -0.00022] |
| pr78_full | -0.00535 [-0.00645, -0.00430] | -0.00580 [-0.00872, -0.00287] | -0.00855 [-0.01888, +0.00138] |


The full model’s all-map log loss is **0.59978**, versus **0.60513** for the matched post-draft control. Its additional gain beyond the four-feature draft model is -0.00148 [-0.00200, -0.00095]. On the earlier-only fitted baseline, the full-model gain remains -0.00534 [-0.00644, -0.00430].

International evidence is weaker than the pooled headline. Its event-cluster sensitivity is -0.00855 [-0.01936, +0.00584], 8 event/year clusters. The entry-proxy delta is -0.00235 [-0.02255, +0.01672], with only 114 maps. This does not resolve the original tournament-entry concern.

**Risks and next experiment.** The champion pair features were already developed after earlier repository test years had been viewed. Champion identity is confounded by player skill, teams’ draft preferences and patch selection. A new untouched period and full current-data rerun are required. Compare incremental gains over the production market blend on a chronologically held-out priced cohort; do not infer market value from beating FORGE alone. Live adoption also requires actual draft availability before the intended forecast timestamp. Priority: highest for a separate post-draft forecast, conditional on those checks.

### Second: your patch champion win-rate idea — tested at two forecast horizons

The idea is feasible in principle: use the **competition patch**, whose ranked games may already have been played, rather than automatically using the latest live patch. The important exposure is whose usable champions benefit on that patch, not just the patch number.

**Pre-draft experiment.** Each player’s last 40 observed professional champion appearances form a role-specific pool. Before the day’s games, the last known five-player roster yields an appearance-weighted patch win-rate level, a change from the preceding archived patch, coverage, and a top-three available-champion value. No actual current picks are used. Level-only, shift-only, combined and comfort/experience controls were tested. The top-three score is a pool-value screen, not a full draft optimizer.

**Post-draft experiment.** Average current champion-role ranked win rate is added after picks are known. A second comparison adds it to the full professional draft model, which is the stronger and more relevant baseline for incremental draft value.

**Data and repair.** Source: [HakimT/lol-champion-ranked-stats](https://huggingface.co/datasets/HakimT/lol-champion-ranked-stats), 53,370 rows. It supplies champion, role, nominal date, patch, pick rate, win rate and ban rate, but no game counts, original provider identity or independently verified historical publication timestamps. 2,657 records have both zero win rate and zero pick rate, including 2,352 in 2026. These were conservatively treated as missing placeholders. Initial runs that treated them as observations were invalidated, retained as diagnostics, and excluded from this report’s substantive comparisons. This was a data repair, not a test-driven model selection change.

For each map, only a matching-patch record dated at least one day earlier is admitted. A 14-day delay is a sensitivity check. The archive’s date is an assumption about availability, not proof that it was accessible then. Competition-patch knowledge before the forecast is also assumed. There is no sample-count-based beta-binomial shrinkage, because the source does not supply counts.


| Experiment | All maps Δ log loss [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| patch_level_1 | +0.00026 [-0.00005, +0.00055] | +0.00034 [-0.00028, +0.00091] | +0.00035 [-0.00089, +0.00155] |
| patch_shift_1 | +0.00001 [-0.00007, +0.00008] | -0.00005 [-0.00028, +0.00016] | +0.00031 [-0.00010, +0.00072] |
| patch_pre_1 | +0.00029 [-0.00004, +0.00060] | +0.00022 [-0.00038, +0.00075] | +0.00053 [-0.00075, +0.00178] |
| patch_pre_14 | +0.00010 [-0.00006, +0.00027] | +0.00016 [-0.00023, +0.00056] | +0.00034 [-0.00024, +0.00098] |
| patch_options_1 | -0.00055 [-0.00102, -0.00011] | -0.00007 [-0.00083, +0.00067] | -0.00012 [-0.00268, +0.00210] |
| patch_options_14 | -0.00083 [-0.00123, -0.00043] | -0.00017 [-0.00069, +0.00034] | -0.00073 [-0.00261, +0.00110] |


The pool-value variants also contain familiarity/experience controls. Their incremental comparison must therefore use those same controls, rather than attributing all of the combined model’s performance to patch information:


- patch_options_1 beyond pool controls: +0.00028 [+0.00001, +0.00053] all maps; +0.00005 [-0.00048, +0.00059] major domestic.

- patch_options_14 beyond pool controls: -0.00001 [-0.00008, +0.00007] all maps; -0.00004 [-0.00025, +0.00016] major domestic.


| External ranked win-rate addition | All-map Δ [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| After draft, 1-day delay; vs side/calibration control | +0.00438 [+0.00295, +0.00571] | +0.00410 [+0.00084, +0.00767] | +0.00443 [-0.00487, +0.01574] |
| Added to full professional draft model, 1-day delay | +0.00374 [+0.00252, +0.00507] | +0.00278 [-0.00098, +0.00687] | +0.00621 [-0.00390, +0.01759] |
| After draft, 14-day delay; vs side/calibration control | +0.00141 [+0.00060, +0.00230] | +0.00118 [-0.00115, +0.00366] | -0.00248 [-0.00585, +0.00073] |
| Added to full professional draft model, 14-day delay | +0.00056 [+0.00012, +0.00102] | +0.00047 [-0.00092, +0.00204] | -0.00097 [-0.00272, +0.00061] |


Coverage is material, not a footnote. The next table shows the average fraction of historical pool exposure with an admissible ranked observation. Missing champions contribute neutral values plus explicit coverage-difference features; they are not counted as 0% winners.

| Slice | Pre-draft pool coverage, 1 day | Pre-draft pool coverage, 14 days | Actual-pick coverage, 1 day |
|---|---:|---:|---:|
| international | 73.0% | 26.2% | 75.5% |
| international_same_home | 86.9% | 50.8% | 89.2% |
| major_domestic | 62.9% | 18.9% | 63.3% |
| minor_domestic | 66.3% | 23.4% | 66.8% |
| other_cross | 62.1% | 17.2% | 62.7% |


On all test maps, 16,097 have at least 80% *average* pool coverage under a one-day delay, versus 5,602 under 14 days. Full covered-subset scores are in `results-static.json`; that subset is selected by information availability, not randomly sampled.

**Coverage-conditioned result.** On the already-reported availability slice (at least 80% average actual-pick coverage), adding one-day ranked features to the full professional draft model gives **-0.00066 [-0.00126, -0.00015]**, on **13,075 maps**. Major domestic: -0.00122 [-0.00292, +0.00058]; international: -0.00389 [-0.00792, -0.00008]. Those maps are entirely in 2024–2025; **zero 2026 maps** meet this coverage condition. The 14-day covered increment is -0.00048 [-0.00132, +0.00038], on 4,232 maps.

The same coverage check for the pre-draft combined exposure gives -0.00015 [-0.00031, +0.00000]; major domestic remains +0.00017 [-0.00015, +0.00047]. Thus the observed positive subgroup signal concerns known picks, not a confirmed improvement to morning or tournament-entry forecasts.

A transparent follow-up routes to the existing professional draft model when coverage is insufficient. This routing was evaluated **after viewing coverage results**, so it is exploratory even though the 80% diagnostic threshold was already specified in the analysis code. The one-day routed increment is -0.00041 [-0.00077, -0.00008]. It earns no untouched-validation claim. For the covered international subgroup, the event-cluster interval is [-0.01048768674574022, 0.0008020693810297759], based on only 7 events.

**Conclusion and relative upside.** The unrestricted archive feature fails, while better-covered post-draft maps show a modest incremental signal worth confirming. This is mixed evidence, not grounds to discard the patch idea or deploy it broadly. In particular, adding its one-day ranked features to that full model changes loss by +0.00374 [+0.00252, +0.00507]. This pooled result argues against an unrestricted rollout; the covered subgroup motivates testing an availability-gated version on untouched data. Solo-queue champion strength transfers imperfectly to coordinated pro play; sample size, rank, role, hotfix handling and pool selection all matter. Priority: obtain a trustworthy timestamped archive with counts, then run the same frozen exposure tests. Expected general benefit remains uncertain; the measured covered-subgroup gain must not be generalized to unsupported patches, 2026, or pre-draft forecasts.

### Third: opponent-style matchups — small, cohort-dependent signal

Lagged team EWMAs summarize kills per minute, objective rate and lane gold differential. Linear differences control for ordinary team performance. The novel test adds antisymmetric cross-products, so reversing opponents reverses the effect. These target non-transitive stylistic advantages that additive FORGE cannot express.


| Experiment | All maps Δ log loss [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| style_linear | -0.00046 [-0.00065, -0.00027] | -0.00011 [-0.00045, +0.00021] | -0.00009 [-0.00156, +0.00132] |
| style_interactions | -0.00058 [-0.00086, -0.00032] | +0.00004 [-0.00041, +0.00050] | -0.00008 [-0.00226, +0.00201] |


Interactions beyond linear style differences: -0.00013 [-0.00023, -0.00003] all maps; +0.00015 [-0.00002, +0.00033] major domestic. On the earlier-only control, the combined interaction model’s all-map delta is -0.00104 [-0.00163, -0.00049].

This remains a small exploratory specification. Lane coverage and play-style stats are confounded with strength; EWMA values are computed from past results, not the current map. This is materially different from simply re-adding early-game stats to Form, which the repository already tried. Priority: retain only if the interaction-specific gain, rather than the linear control, survives an untouched cohort and major/minor checks. No large universal effect is established.

### Fourth: transfer bridges — estimable in part, no demonstrated international improvement

The broad movement audit found 14,003 home-league transition observations before 2024, but many are academy moves, recurring players or league transitions, not independent cross-region bridges. A stricter test requires 20 same-role maps in one of twelve prespecified top leagues, followed by ten stable-role destination maps; at least 15/8 have valid lane-gold observations. It admits an episode only after the final destination observation.

This yields **275 episodes from 199 players**, 224 available before 2024. A ridge graph estimates origin/destination difficulty from changes in lane gold differential; its coefficients are frozen by year and tested as a cross-league residual beyond FORGE plus existing regional calibration. International delta: -0.00061 [-0.00439, +0.00318]; entry-proxy delta: -0.00033 [-0.00625, +0.00531]. Event sensitivity: -0.00061 [-0.00330, +0.00219], 9 event/year clusters.

A separate lagged player-relative performance probe gives +0.00002 [-0.00014, +0.00016] all maps. This is not a validated AURA replacement or a full cross-league translation system.

The graph has sparse directions, limited snapshot coverage, endogenous recruitment, adaptation and changing teammates. The same player can contribute correlated episodes. The bridge’s lane-performance endpoint is not match win probability. Its measurement fit is a prototype, not a causal estimate of region strength. Priority: below better timestamped patch data and draft confirmation; no adoption based on this test.

### Fifth: likelihood-based changes and abrupt breaks — baseline already absorbs most simple residuals

A bounded latent residual grid is layered on FORGE. Stable residuals are compared with resets triggered by already-observed roster changes and a Bayesian state transition that mixes retained strength with a fresh prior at each active day. The change-point grid tests hazards 0.01/0.05 and prior scales 0.35/0.70; stable/reset comparators use a 0.001 hazard. Team posteriors are factorized and updated with opponent posterior means, while forecasts integrate independent team uncertainties.

This is a tractable Bayesian reset-mixture prototype inspired by [Adams & MacKay](https://arxiv.org/abs/0710.3742). It is **not** a full BOCPD run-length implementation and does not test patch-dependent hazards or known announced rosters. It differs from shipped inactivity/roster heuristics by using predictive evidence for latent strength resets, but that distinction did not translate into a useful broad gain here.


| Experiment | All maps Δ log loss [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| bayes_stable | +0.00000 [+0.00000, +0.00000] | +0.00000 [-0.00000, +0.00000] | -0.00000 [-0.00001, +0.00000] |
| bayes_roster_reset | +0.00000 [-0.00000, +0.00001] | -0.00000 [-0.00001, +0.00001] | -0.00001 [-0.00003, +0.00002] |
| bayes_change_point | +0.00001 [+0.00000, +0.00001] | -0.00001 [-0.00002, +0.00000] | -0.00000 [-0.00004, +0.00004] |
| score_binary | +0.00001 [-0.00000, +0.00001] | -0.00000 [-0.00002, +0.00002] | -0.00003 [-0.00010, +0.00005] |
| score_joint | -0.00032 [-0.00048, -0.00015] | +0.00039 [+0.00004, +0.00072] | +0.00000 [-0.00148, +0.00132] |


Change-point versus stable residual directly: +0.00001 [+0.00000, +0.00001]. For score-driven models, the binary score is proportional to `y − p`, making the simplest Bernoulli version an Elo-like update rather than a fundamentally new observation. The joint prototype adds a robustly bounded, standardized gold-at-15 innovation using an earlier-year observation regression. It improves minor-domestic loss by -0.00050 [-0.00069, -0.00030], but worsens major-domestic loss by +0.00039 [+0.00004, +0.00072]. Joint versus binary directly: -0.00033 [-0.00049, -0.00015].

The joint observation prototype is not the full correctly specified joint latent-outcome likelihood from the [GAS literature](https://doi.org/10.1002/jae.1279). Gold differential is noisy, role/patch dependent, correlated with winning, and missing in some leagues. The broader methodology is not disproved. Priority: low until a measured, identifiable observation model justifies a more expensive filter; do not ship the mixed cohort result.

### Sixth: higher-order player interactions — identifiable subsets exist, no added forecast value established

Use last-observed rosters only. The nested sparse logistic residual designs contain individuals, then all pairs, then all triples. Pair/triple penalties are 4×/16× the individual penalty, and the penalty grid is selected in development. Current lineups are not treated as known before announcement. This is an interaction identifiability probe inspired by [hypergraph adjusted plus-minus](https://doi.org/10.1515/jqas-2024-0057), not that paper’s complete estimator or graph regularizer.

Among training-period features, individuals/pairs/triples have 9,972/66,281/89,344 distinct terms. Only 5,923/13,658/7,107 appear with at least three distinct complementary configurations. This is a basic variation diagnostic, not a sufficient-rank proof or a count of independent natural experiments.


| Experiment | All maps Δ log loss [95% CI] | Major domestic Δ [95% CI] | International Δ [95% CI] |
|---|---:|---:|---:|
| player_residual | -0.00003 [-0.00019, +0.00012] | -0.00062 [-0.00109, -0.00014] | -0.00004 [-0.00162, +0.00148] |
| pair_residual | -0.00002 [-0.00019, +0.00015] | -0.00062 [-0.00117, -0.00009] | -0.00007 [-0.00178, +0.00153] |
| trio_residual | -0.00001 [-0.00019, +0.00016] | -0.00062 [-0.00118, -0.00007] | -0.00010 [-0.00183, +0.00150] |


Pair effects beyond individuals: +0.00002 [-0.00001, +0.00005]. Triple effects beyond pairs: +0.00000 [-0.00000, +0.00001]. The individual residual’s major-domestic gain coexists with minor-domestic harm, +0.00018 [+0.00003, +0.00032]; it does not establish a safe all-league replacement. Player Elo already exists in Prometheus, so an individual-effect gain must not be mislabeled new synergy.

Stable rosters confound players with their teammates; transfer selection is endogenous; many test players/groups are unseen by the frozen fit. Ridge makes coefficients numerically estimable without making them causally identifiable. Priority: low for higher-order modeling on this evidence; investigate substitutes or within-team role variation before scaling the full hypergraph method.

### Seventh: fearless draft option value — prerequisite tested, full simulation not completed

The pool-control and patch top-three-option screens test whether usable role depth contains forecast signal beyond familiarity and experience. Their results appear in the patch tables. They do **not** encode actual series-specific fearless availability, earlier picks/bans, pick order, or opponent drafting strategy. A positive combined pool result would not demonstrate fearless value.

A full test needs historically correct tournament/series format flags and pre-map available champion sets, and must compare against the already-shipped beta-binomial series update. The OE corpus alone did not supply a verified format/availability table for every series. Consequently, no full fearless simulator result or claimed log-loss gain is reported. Priority: collect and validate that table before implementing a large simulator; the simpler screens do not justify a forecast uplift claim.

## 4. Market and calibration checks

The released [live benchmark archive](https://github.com/thaiv28/Prometheus/releases/tag/live-bench-data) was downloaded and hash-checked (`77df40cd869115150d33ae093acde59955e69c89e55d8e2072d10e8293a7e716`). Price comparisons below use exact OE game and team-name matches, the archive’s game-start price, and no market-outcome coefficient fitting. This is a selected 2026 overlap, not the earlier 33-series tournament-entry comparison. All maps in a series share a bootstrap cluster.

| Forecast | Matched maps | Log loss | Market-only log loss | Δ vs market [95% CI] |
|---|---:|---:|---:|---:|
| p_prod | 1,088 | 0.62927 | 0.61993 | +0.00934 [-0.00424, +0.02177] |
| postdraft_control | 1,088 | 0.62656 | 0.61993 | +0.00663 [-0.00666, +0.01946] |
| pr78_meta | 1,088 | 0.62288 | 0.61993 | +0.00295 [-0.01129, +0.01658] |
| pr78_draft | 1,088 | 0.62262 | 0.61993 | +0.00269 [-0.01139, +0.01587] |
| pr78_full | 1,088 | 0.62040 | 0.61993 | +0.00047 [-0.01396, +0.01412] |


These are pure-model comparisons, not a test of adding the new signal to a market blend. The game-start market may observe draft and other news. Earlier-only development data is insufficient here to fit and fairly select a new market blend, so that incremental market claim remains untested.

Brier and calibration estimates accompany every scored slice in the machine-readable outputs. Calibration should be assessed on sufficiently large samples; ten-bin ECE is unstable internationally. Score differences can be tiny yet have narrow conditional intervals after a residual coefficient shrinks almost to zero. Practical size and held-out robustness matter alongside significance.

### Computational cost of the prototypes

All runs used one BLAS/OMP thread per process, with independent jobs sometimes run concurrently. These are observed local wall times, not production CI budgets: healthy ingestion/bootstrap about 62 seconds; preparation 39 seconds; corrected patch/history features 84 seconds; static selection/scoring about 80 seconds per baseline; sparse player/pair/triple suite about 70 seconds for a 93,958 × 165,597 design; strict transfer bridge probe 17 seconds; draft feature preparation plus first scoring roughly 54 seconds, and cached scoring 39 seconds. Bootstrap and reporting are included in the scoring timings. The Bayesian grid sweep completed its forecasts/results but its ancillary serialization error prevented a trustworthy final timer; no exact dynamic-suite runtime is claimed. Peak-memory profiling and deployment latency were not measured. Full BOCPD, draft simulation and graph-regularized hypergraph costs remain unmeasured.

## 5. Already implemented or tested — do not rediscover as novel

Verified mechanisms include opponent-adjusted Form/GLORY; FORGE’s domestic Elo–Form blend; player-carried team Elo; rookie, inactivity and roster-aware adjustments; persistent international regional calibration; minor-league forecast handling; beta-binomial series probabilities; and market blending. These serve as controls, not new proposals.

The research history already tested higher K, alternative margins of victory, early-game Form additions, some champion features, and recency-weighted regional corrections without convincing incremental gains. Pairwise familiarity/synergy and predictive AURA had appeared in future work. PR #78 already contains professional champion-role and draft interaction research, although its features were not merged into the inspected main revision. The novelty of this execution is the explicit FORGE-controlled comparisons, patch-ranked exposure tests, and feasibility/ablation results; it is not authorship of those existing ideas.

The native repository’s out-of-year fitting can include future years in a historical fold. That is why this report also supplies an earlier-only control. Previously published benchmark numbers, including the 1,006-map regional-calibration result, must not be substituted for scores on this different mirror, period and forecast horizon.

## 6. Recommended sequence and merge position

1. **Do not merge from this report alone.** Restore the exact current deployment corpus and rerun the frozen experiments and regional slices. Preserve a new untouched evaluation period; do not retune on the results reported here.
2. **Confirm the professional draft model against FORGE and production market blending.** Keep it a distinct post-draft forecast. Resolve live pick availability and the historical LPL coverage gap; use series and event intervals. It is the most promising measured extension in this run, but it does not solve pre-draft tournament-entry forecasting.
3. **Acquire a trustworthy patch archive with counts and publication timestamps.** Preserve competition-patch IDs/hotfixes, role/rank/region, daily cumulative counts and rates. Reuse the frozen pre-draft exposure and post-draft conditional tests; validate metadata before outcomes. Confirm the covered-draft signal and availability gate on untouched data, then revisit pre-draft pool exposure. The lag between live and competition patches creates an information opportunity, not automatic predictive value.
4. **Keep only interaction-specific style evidence.** Recheck the small antisymmetric effect against linear controls on new data. Treat familiarity and player residuals as existing-backlog refinements with cohort harms to resolve, not novel universal wins.
5. **Defer costly full models until prerequisites improve.** More independent transfer bridges, format-correct fearless availability, and lineup variation would justify richer translation, draft optimization or hypergraph work. A fully specified patch-aware change-point/joint-observation model remains untested; current simpler prototypes give it low immediate priority.

Results precede any merge decision. No measured speculative gain is assigned to the unimplemented full models, no background Work task or automation is claimed, and no reusable research skill was created.

## 7. Reproducibility and files

The accompanying archive contains research scripts outside the repository; the frozen protocol; source pins and hashes; corrected derived analysis features; scored forecast files; machine-readable cohort results; nominal series/event confidence intervals; source-quality diagnostics; the invalidated placeholder runs; the pinned draft source reference; and reproduction instructions. It excludes the raw 833 MB CSV collection, rebuilt database and credentials. The scripts do not commit, open PRs, merge or edit production source.

An ancillary NumPy-key JSON serialization failed after the first dynamic run had already saved its forecasts and scores. That metadata file was regenerated, and the source serialization was corrected. Initial placeholder-data scores remain explicitly invalidated. Repeated runs corrected data/serialization issues and added the stated earlier-only baseline check. The availability-gated routing is separately labeled as a follow-up after inspecting the covered-subgroup result; it is not presented as an untouched test.
