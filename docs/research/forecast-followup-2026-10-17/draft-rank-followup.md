# Prometheus: rank-specific patch and professional draft follow-up

October 17, 2026. Research only. No production code changes, commits, PRs, merge, deployment or skill creation.

## Findings and recommendation

The professional draft model’s standalone forecasting evidence is stronger after these checks. Its gain survives expanding yearly/monthly fits, excluding every same-day observation from the feature history, and adding the previously missing LPL cohort. A simpler five-feature candidate is sufficient for the broader-coverage test. **This supports validating a separate post-draft forecast; it does not yet establish a tradable market edge or a night-before forecast improvement.**

Master+ patch win rates were actually compared with Diamond+ and Platinum+ on matched data, but the defensible test is too small to identify a winning rank filter. The higher-rank hypothesis remains open. The historical archive, rather than the total number of live Master+ games, limits this test.

No production merge recommendation yet: the dataset still ends May 22, 2026; exact current deployment data could not be obtained; current champions’ availability at the forecast/quote cutoff has not been verified; and the market result weakens after including coefficient-fitting uncertainty.

## 1. Scope, provenance and chronological controls

Both remote heads remained unchanged when checked at the start: main [`ac5745ca1982d7347d7caee2f98f70f7f1832c53`](https://github.com/thaiv28/Prometheus/tree/ac5745ca1982d7347d7caee2f98f70f7f1832c53) and draft research [`dd84749b364d4580b41e7236ca98188f6a6d6596`](https://github.com/thaiv28/Prometheus/tree/dd84749b364d4580b41e7236ca98188f6a6d6596). Repository guidance and the current technical/product/deployment state were checked against those revisions. The prior report and scored artifacts were restored and reused.

The follow-up protocol was written before follow-up scoring. Ridge penalty 0.1 was retained from the earlier development selection. The professional study uses 2019–2023 to fit its fixed model, then evaluates 2024–May 2026; expanding-year fits use only earlier years, and expanding-month fits use only earlier months. Both packaged production probabilities and earlier-only fitted Form/FORGE controls were tested. A common post-draft side/route-calibration control prevents the draft model receiving credit simply for knowing blue side or rescaling Elo.

These periods were already examined in the repository and prior research. **They are retrospective robustness checks, not new untouched confirmation.** The original fixed-model probabilities reproduced with maximum absolute error **0.0** on the shared evaluation cohort.

For the wider-roster test, the pinned 2014–2026 CSV corpus was recovered and its 2014–2025 hashes matched the original manifest. The native ingestion and Elo bootstrap were rerun unchanged; the resulting 196,108 team rows and latest match timestamp matched the prior rebuild. SQLite `quick_check` passed. The 2026 file remains the same 39,314,270-byte mirror through May 22. The newest official Drive file was listed but its download was quota-refused; an unauthenticated API probe was also refused. No third-party credentials were used. Therefore this study does not claim to reproduce the current October deployment database.

Primary uncertainty is a nominal paired bootstrap over league/team-pair/UTC-day clusters approximating series. International sensitivity groups by event/year. These intervals condition on fitted models unless explicitly labeled training-and-test bootstrap. They do not account for all historical model selection or multiple comparisons.

## 2. Professional draft model: temporal robustness

The original six inputs are player champion experience, player-champion wins above Elo, player-relative champion lane gold, 60-day champion-role professional meta, same-lane champion matchup effects and champion teammate-pair effects. All require the actual selected champions; histories use earlier observations. This is the existing draft branch’s research mechanism, not a newly invented feature family.

The original snapshot-complete cohort contains **21,361 test maps**, including 2,874 major domestic, 15,887 minor domestic and 371 cross-home international maps. The remaining maps are separately classified. LPL has no test maps in that original snapshot-dependent cohort.

| Fit strategy | All-map Δ log loss vs matched control [95% CI] | Major domestic | International |
|---|---:|---:|---:|
| Fixed through 2023 | -0.00535 [-0.00645, -0.00430] | -0.00580 [-0.00872, -0.00287] | -0.00855 [-0.01888, +0.00138] |
| Expanding prior years | -0.00532 [-0.00642, -0.00429] | -0.00578 [-0.00869, -0.00288] | -0.00866 [-0.01900, +0.00119] |
| Expanding prior months | -0.00529 [-0.00638, -0.00426] | -0.00577 [-0.00869, -0.00287] | -0.00860 [-0.01882, +0.00123] |


The annual refit also retains negative all-map deltas separately in each test year:

| Evaluation year | Maps | Δ log loss [95% CI] |
|---|---:|---:|
| 2024 | 8,078 | -0.00583 [-0.00751, -0.00412] |
| 2025 | 8,887 | -0.00458 [-0.00625, -0.00297] |
| 2026 | 4,396 | -0.00588 [-0.00813, -0.00338] |


The earlier-only baseline gives the following additional check:

| Strategy | Δ log loss [95% CI], all maps |
|---|---:|
| chrono_full | -0.00531 [-0.00641, -0.00427] |
| chrono_monthly_full | -0.00528 [-0.00638, -0.00425] |


These results make simple coefficient staleness an unlikely explanation for the pooled draft gain. They do not prove immunity to a new patch, roster population, data provider, or future season.

## 3. Which draft inputs matter?

The table compares the annual-refit full model with an otherwise identical model omitting one feature. Negative means the omitted feature helped. Each model was refit on earlier years, with the same fixed penalty and evaluation maps.

| Feature removed from comparator | Full model Δ vs ablation, all maps [95% CI] | Major domestic | International |
|---|---:|---:|---:|
| Champion experience | -0.00122 [-0.00174, -0.00069] | -0.00099 [-0.00230, +0.00039] | -0.00178 [-0.00710, +0.00345] |
| Player-champion wins above Elo | -0.00009 [-0.00023, +0.00005] | -0.00006 [-0.00046, +0.00037] | -0.00055 [-0.00187, +0.00071] |
| Champion lane-gold residual | -0.00004 [-0.00018, +0.00009] | +0.00025 [-0.00016, +0.00061] | +0.00071 [-0.00041, +0.00175] |
| Recent professional champion-role meta | -0.00080 [-0.00124, -0.00037] | -0.00115 [-0.00231, -0.00005] | -0.00308 [-0.00626, -0.00010] |
| Champion lane matchups | -0.00036 [-0.00061, -0.00010] | -0.00032 [-0.00103, +0.00037] | +0.00103 [-0.00102, +0.00298] |
| Champion teammate pairs | -0.00073 [-0.00110, -0.00040] | -0.00108 [-0.00209, -0.00007] | -0.00137 [-0.00449, +0.00139] |


The clearest pooled contributions are experience, professional meta, lane matchups and composition pairs. These are predictive associations; the pair effects do not establish causal synergy and can reflect team selection and patch preferences. Player-champion outcome residual and champion lane gold add little once the other inputs are present. Individual regional ablations are less certain; especially do not interpret the international column as a validated ranking of features.

A coefficient-transport check excluded one major league’s labeled matches from fitting. It still permitted earlier target-league observations when constructing historical inputs, so this is not an entirely unseen-league experiment:

| Excluded training league | Target test maps | Full model vs matched control [95% CI] |
|---|---:|---:|
| LCK | 1,321 | -0.00719 [-0.01143, -0.00304] |
| LPL | 0 | — |
| LEC | 812 | -0.00537 [-0.01070, +0.00041] |
| LCS | 530 | +0.00243 [-0.00404, +0.00938] |


LCK provides the clearest transport evidence. LEC is uncertain, LCS does not show a reliable gain in this particular coefficient-transport test, and the old snapshot cohort cannot assess LPL. This argues for league monitoring rather than assuming identical gains everywhere.

## 4. Wider coverage, including LPL, and strict prior-day features

Full-game champion/roster records exist even where lane snapshots are missing. The wider experiment reads `match_players` instead of requiring `player_stats` and drops lane gold. Its five inputs are **experience, player-champion wins above Elo, professional meta, lane matchup and champion teammate-pair effects**. The five-feature choice followed inspection of the ablations; it is a simplified candidate, not a new blind selection result.

Both candidate and side/route-calibrated FORGE control were refit on 2019–2023. The wider test contains **23,956 maps**: 4,756 major domestic, 16,465 minor domestic, 449 cross-home international, plus 2,175 other cross-league and 111 same-home international maps. Unlike the original cohort, it includes **1,907 LPL maps**.

One version uses only earlier timestamps. A stricter version excludes all observations from the current UTC day, including earlier maps in the same series. Both still know the current map’s champions: “prior day” describes historical feature updates, not the forecast horizon.

| Feature-history cutoff | All-map Δ vs control [95% CI] | Major domestic | International | LPL |
|---|---:|---:|---:|---:|
| timestamp_no_gd15 | -0.00608 [-0.00717, -0.00511] | -0.00749 [-0.01005, -0.00503] | -0.00695 [-0.01526, +0.00145] | -0.00789 [-0.01170, -0.00422] |
| prior_day_no_gd15 | -0.00599 [-0.00707, -0.00503] | -0.00737 [-0.00990, -0.00500] | -0.00699 [-0.01530, +0.00112] | -0.00758 [-0.01126, -0.00392] |


The strict prior-day model’s pooled log loss is **0.60357** versus **0.60956** for its matched control. Brier score is 0.20895 versus 0.21154. Its international event-cluster interval is **[-0.01530, +0.00369]**, from 9 events, so international superiority remains uncertain.

The strict-day versus timestamp difference is +0.00009 [-0.00002, +0.00022]. Thus the gain does not require reading earlier results from the same day. The old 21,361-map headline and the new wider result use different feature histories, training coverage and evaluation cohorts; their difference is not itself an ablation estimate.

A direct leakage sensitivity check used 5,180 real player rows. Flipping all results on 2025-01-21 changed that day’s or earlier features by at most 2.78e-17; later features changed, showing the intervention was effective. Removing all future games changed retained-prefix features by 0.0. This validates those feature computations, not every assumption in the inherited Elo pipeline.

## 5. Market comparison: stronger test, still no established edge

The released benchmark archive yields **906 maps from 496 series** with exact OE game/team matching and all three required prices: before draft, a minute before start, and game start. Requiring all those prices reduces the prior report’s 1,088-map start-price cohort. Results are not interchangeable across those samples.

For each test month, models fit only earlier completed data, with a one-day completion buffer. All use C=1 and symmetric logistic forms, following the production blend’s general architecture. The comparators are calibrated market alone, market + FORGE, and market + FORGE + the fixed professional draft component. The FORGE term includes the known series score through the existing tier-specific beta-binomial update, so draft is not simply receiving credit for earlier wins in the series. The added draft component excludes the professional model’s nuisance side and baseline-temperature coefficients.

**Unit limitation:** this is a **map-level chronological blend analogue**, not the exact production series-market blend. Applying the committed series-trained blend to map outcomes would not be a fair production comparison. No betting profit, executable edge, or performance improvement for the production trading system is claimed.

At the minute-before-start price:

| Minimum earlier training series | Test maps / series | Draft addition vs market + FORGE, conditional 95% CI | Training-and-test refit 95% CI | Full blend vs raw market, conditional 95% CI |
|---|---:|---:|---:|---:|
| 100 | 657 / 369 | -0.00311 [-0.00591, -0.00056] | [-0.00978, +0.00458] | +0.00435 [-0.00836, +0.01716] |
| 300 | 235 / 137 | -0.00925 [-0.01636, -0.00291] | [-0.02174, +0.00178] | -0.01152 [-0.02443, +0.00076] |


The 100-series threshold is explicitly exploratory; production uses at least 300. The 300-series threshold leaves only May’s 235 maps, with no international test maps. Map-one-only results are also uncertain: -0.00317 [-0.00725, +0.00094] with 100 earlier series, and -0.00907 [-0.01846, +0.00133] with 300.

The initial conditional intervals suggest additional draft signal over the fitted market + FORGE comparator. However, a **400-replicate series bootstrap that resamples training and test series and refits the monthly coefficients** includes zero for that increment at both thresholds. The first threshold’s full blend also trails the raw market on its point estimate. This prevents treating the conditional result as a proven market edge. Start-price sensitivity and regional slices are preserved in `market-results.json`; small slices remain noisy.

**Information availability is still unresolved.** The inspected live service gets champion participant metadata from Riot’s window feed, queries with a 30-second lag, and has no verified live pick/ban ingestion before game start. Historical chosen champions cannot establish that the model could have been computed a minute before a particular quote. Offline draft tests therefore assume a cutoff after picks and role assignments are known. An actual deployment must log the first valid receipt timestamp and score prices available after that receipt. This requirement also matters for flex picks whose lane assignment is initially ambiguous.

## 6. Master+ versus Diamond+ and Platinum+: what was actually tested

Source: [LoLalytics historical tier lists](https://lolalytics.com/lol/tierlist/?tier=master_plus&patch=16.1&lane=top). Requests explicitly selected Ranked Solo/Duo, global region, role, tier and patch; structured page state was checked against those requested fields. Snapshots and SHA256 hashes are retained. [Riot’s patch schedule](https://support-leagueoflegends.riotgames.com/hc/en-us/articles/360018987893-Patch-Schedule-League-of-Legends) supplied the next-patch release dates.

Thirty requested role/tier/patch pages succeeded for patches **16.1 and 16.2**, yielding **5,108 positive-count champion-role records**. The 105 requested pages for patches 16.3–16.9 returned 404. Alternative padded patch IDs and page routes did not recover those missing periods. Some later 2026 patch pages exist, but the professional corpus ends before their full-patch totals could have been available. MetaSRC returned 403 for tested historical endpoints. The original Hugging Face archive has only aggregated Platinum+ rates and cannot be relabeled as Master+.

Source validation also compared distinct historical/current page data: the inspected pages had different champion counts and win rates, rather than an unchanged current-data table with a historical URL. Nevertheless, retrieval now is not independent proof of the exact historical publication timestamp or rank-classification state.

**Normalization and sample size.** LoLalytics counts participants belonging to the selected bracket, so a bracket’s average win rate need not be 50%. Each champion-role estimate was shrunk toward its bracket average and expressed as a log-odds deviation from that average. The source supplies rounded rates and game counts, so wins are approximated by their product rather than taken from raw integer win/loss counts. This prevents a high Master+ bracket-wide win rate being mislabeled champion strength. Median champion-role sample size across the two patches is approximately 3,066 for Platinum+, 556 for Diamond+, and 206 for Master+. These medians include off-role picks; they are not all equally relevant to pro drafts.

**Avoiding full-patch leakage.** Only games at least one day after the following patch release were admitted. That leaves 75 maps on 16.1 for fitting the incremental rank coefficient and **97 maps / 48 clusters on 16.2** for evaluation. Only **13** evaluation maps are major domestic, **84** are minor domestic and none are international. A seven-day lag leaves nine training maps and zero test maps, so no meaningful seven-day rank comparison is possible.

This small sample is a limitation of historical full-patch archives. Your premise still makes sense: a timestamped daily snapshot could use the patch’s first several days of solo queue even before that patch ends. We cannot substitute its eventual full-patch win rate at that earlier cutoff.

The rank features score the actual five champions per team, after draft, beyond the fixed professional draft model. Shrinkage 500 is the declared primary setting, with 100 and 2,000 preserved as sensitivities; no setting was selected from the test outcomes. The incremental coefficient uses ridge 0.1 on patch 16.1 only.

| Rank cohort | Test log loss | Δ vs professional draft baseline [95% CI] |
|---|---:|---:|
| platinum_plus | 0.59989 | +0.00944 [-0.01764, +0.03507] |
| diamond_plus | 0.60046 | +0.01001 [-0.01553, +0.03526] |
| master_plus | 0.59745 | +0.00700 [-0.00903, +0.02370] |


Professional draft baseline on these 97 maps: **0.59045**. Master+ versus Platinum+ directly: **-0.00244 [-0.01694, +0.01305]**. Master+ versus Diamond+: **-0.00301 [-0.01305, +0.00770]**. The combined Platinum+ + Master+ residual comparison is also retained in the JSON.

**Conclusion:** the point estimates do not establish Master+ superiority, and none establishes incremental improvement over the professional baseline. The uncertainty is far too large to choose a production rank filter. A failure to win this tiny test does not disprove higher-rank data’s value. The next useful input is a multi-patch timestamped archive with counts for matching rank cohorts, preferably spanning enough independent events and patches for a genuinely new evaluation.

## 7. Concrete next decisions

1. **Professional draft:** prioritize the five-feature, full-roster candidate with strict prior-day historical inputs. It removes the lane-snapshot dependency and has favorable retrospective domestic/LPL results. Freeze it for a current-data and then prospective shadow test; do not retune on the periods reported here.
2. **Before production inference:** prove when complete picks/role assignments become available, log that timestamp, and use a market quote after that timestamp. Keep the output a distinct post-draft map forecast. It cannot silently replace forecasts issued before draft.
3. **Market use:** require a same-unit comparison against the actual production series blend, or explicitly define a separate map-market model. Preserve enough earlier priced series and include fitting uncertainty. Current results do not establish a market edge or live profitability.
4. **Patch ranks:** do not switch to Master+ solely because it sounds closer to pro play. Obtain daily counts/rates for all comparison cohorts on matching patches. Keep bracket normalization, count shrinkage, missing-data fallbacks, strict publication cutoffs and the professional draft baseline.
5. **Data refresh:** rerun frozen models on the actual current corpus once a verified export is available. The Drive quota and API refusal were documented rather than bypassed. No automatic task or data-collection schedule was started.

## 8. Files and reproducibility

The companion bundle contains the frozen protocol, new analysis scripts, scored probabilities, source manifests and successful compressed rank-page snapshots, failed-source diagnostics, cohort results, leakage checks, training-and-test bootstrap results, and minimal prior-study inputs needed to reproduce these comparisons. It excludes raw 833 MB Oracle’s Elixir CSVs, the rebuilt database, credentials, and unrelated repository source. The production checkout remains clean.

Run with the pinned repository environment (Python 3.12, pandas/numpy/scipy/scikit-learn, plus pyarrow/requests for research). See `followup/REPRODUCE.md`. All primary outcome intervals are nominal, and this repeatedly examined historical corpus cannot provide an untouched prospective claim. Initial script errors were corrected before final scoring: a missing local requests import environment and a missing market game-ID column. Scores were not selected on those failures. All corrected runs, including null and adverse rank results, are retained.
