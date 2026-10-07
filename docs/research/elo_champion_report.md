# Champions added to stats + Elo: matched regularization

Exploratory development folds: 2023–2025 only. The previously viewed 2026 data is excluded.

## Finding

No full-stats champion addition improves pooled log loss with a paired 95% interval below zero. Keep stats+Elo as the simpler development candidate.

## Full-stats comparison

Log loss (lower is better); both models use C=0.1.

| minute | champions_elo | stats_elo |
| --- | --- | --- |
| 10 | 0.5554 | 0.5553 |
| 15 | 0.4989 | 0.5003 |
| 20 | 0.4292 | 0.4293 |

## Protocol

Each gold or full-stats (30 lane features) base includes blue-minus-red pre-match Elo. Compare the same numeric model with and without signed champion-by-role main effects. Both use logistic C=0.1, fixed from the earlier champion protocol, with identical games, numeric scaling and temporal splits. No parameter search, exact lane-matchup features, champion×state terms or composition synergies. Unknown/rare champions receive zero draft adjustment; the 10-training-occurrence cutoff and vocabulary use training only.

Each fold trains on three calendar years, uses the following year for sigmoid calibration, and evaluates the next year. Calibration is fit separately for each model using only that preceding year. Report both calibrated and raw log loss. Candidate deltas compare champions+Elo directly with same-C stats+Elo; paired league/day-cluster 95% intervals use 2,000 resamples, seed 42, with no multiple-comparison correction. Gold is a secondary comparison; full stats is the primary requested comparison.

## Elo provenance and coverage

Existing roster-aware Elo replayed unchanged through 2025: 91370 games, maximum difference from stored pre-match ratings 0. Joins validate game/team/side IDs and raw timestamp/result/duration. All models share complete draft/snapshot/rating cohorts. 215 archive games share timestamps; the existing replay uses game-ID tie order. Archive ordering is not a verified result-availability feed. See the prior snapshot Elo report for broader Elo provenance.

## Pooled scores and paired differences

| minute | base | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | champions_elo | 3654 | 0.5554 | 0.1883 | 0.7083 | 0.0099 | 0.5579 | stats_elo | 0.0001 | -0.0054 | 0.0055 |
| 10 | aura_features | stats_elo | 3654 | 0.5553 | 0.1887 | 0.7085 | 0.0109 | 0.5559 | stats_elo | 0 | 0 | 0 |
| 10 | gold | champions_elo | 3654 | 0.5565 | 0.1888 | 0.7058 | 0.0129 | 0.5580 | stats_elo | 0.0000 | -0.0051 | 0.0052 |
| 10 | gold | stats_elo | 3654 | 0.5565 | 0.1889 | 0.7165 | 0.0203 | 0.5568 | stats_elo | 0 | 0 | 0 |
| 15 | aura_features | champions_elo | 3654 | 0.4989 | 0.1665 | 0.7485 | 0.0152 | 0.4992 | stats_elo | -0.0014 | -0.0067 | 0.0042 |
| 15 | aura_features | stats_elo | 3654 | 0.5003 | 0.1675 | 0.7447 | 0.0189 | 0.4999 | stats_elo | 0 | 0 | 0 |
| 15 | gold | champions_elo | 3654 | 0.5061 | 0.1690 | 0.7438 | 0.0166 | 0.5052 | stats_elo | -0.0024 | -0.0076 | 0.0033 |
| 15 | gold | stats_elo | 3654 | 0.5086 | 0.1701 | 0.7438 | 0.0195 | 0.5083 | stats_elo | 0 | 0 | 0 |
| 20 | aura_features | champions_elo | 3648 | 0.4292 | 0.1399 | 0.7955 | 0.0160 | 0.4295 | stats_elo | -0.0001 | -0.0053 | 0.0056 |
| 20 | aura_features | stats_elo | 3648 | 0.4293 | 0.1399 | 0.7933 | 0.0088 | 0.4287 | stats_elo | 0 | 0 | 0 |
| 20 | gold | champions_elo | 3648 | 0.4389 | 0.1433 | 0.7936 | 0.0143 | 0.4383 | stats_elo | -0.0027 | -0.0080 | 0.0028 |
| 20 | gold | stats_elo | 3648 | 0.4416 | 0.1444 | 0.7870 | 0.0131 | 0.4419 | stats_elo | 0 | 0 | 0 |

## Annual scores and paired differences

| minute | base | year | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | 2023 | champions_elo | 1239 | 0.5414 | 0.1825 | 0.7207 | 0.0294 | 0.5451 | stats_elo | -0.0056 | -0.0149 | 0.0042 |
| 10 | aura_features | 2023 | stats_elo | 1239 | 0.5470 | 0.1851 | 0.7264 | 0.0407 | 0.5486 | stats_elo | 0 | 0 | 0 |
| 10 | aura_features | 2024 | champions_elo | 1106 | 0.5557 | 0.1887 | 0.7107 | 0.0193 | 0.5603 | stats_elo | -0.0001 | -0.0088 | 0.0100 |
| 10 | aura_features | 2024 | stats_elo | 1106 | 0.5557 | 0.1893 | 0.7043 | 0.0328 | 0.5572 | stats_elo | 0 | 0 | 0 |
| 10 | aura_features | 2025 | champions_elo | 1309 | 0.5685 | 0.1936 | 0.6944 | 0.0265 | 0.5679 | stats_elo | 0.0056 | -0.0036 | 0.0150 |
| 10 | aura_features | 2025 | stats_elo | 1309 | 0.5629 | 0.1915 | 0.6952 | 0.0397 | 0.5618 | stats_elo | 0 | 0 | 0 |
| 10 | gold | 2023 | champions_elo | 1239 | 0.5424 | 0.1834 | 0.7175 | 0.0254 | 0.5457 | stats_elo | -0.0066 | -0.0153 | 0.0022 |
| 10 | gold | 2023 | stats_elo | 1239 | 0.5490 | 0.1862 | 0.7215 | 0.0339 | 0.5504 | stats_elo | 0 | 0 | 0 |
| 10 | gold | 2024 | champions_elo | 1106 | 0.5589 | 0.1899 | 0.7034 | 0.0207 | 0.5633 | stats_elo | -0.0006 | -0.0096 | 0.0093 |
| 10 | gold | 2024 | stats_elo | 1106 | 0.5595 | 0.1906 | 0.7089 | 0.0217 | 0.5609 | stats_elo | 0 | 0 | 0 |
| 10 | gold | 2025 | champions_elo | 1309 | 0.5679 | 0.1931 | 0.6967 | 0.0374 | 0.5653 | stats_elo | 0.0069 | -0.0022 | 0.0165 |
| 10 | gold | 2025 | stats_elo | 1309 | 0.5610 | 0.1901 | 0.7181 | 0.0346 | 0.5594 | stats_elo | 0 | 0 | 0 |
| 15 | aura_features | 2023 | champions_elo | 1239 | 0.4683 | 0.1542 | 0.7724 | 0.0241 | 0.4675 | stats_elo | -0.0072 | -0.0155 | 0.0019 |
| 15 | aura_features | 2023 | stats_elo | 1239 | 0.4755 | 0.1575 | 0.7627 | 0.0310 | 0.4752 | stats_elo | 0 | 0 | 0 |
| 15 | aura_features | 2024 | champions_elo | 1106 | 0.5058 | 0.1690 | 0.7459 | 0.0377 | 0.5064 | stats_elo | 0.0030 | -0.0074 | 0.0139 |
| 15 | aura_features | 2024 | stats_elo | 1106 | 0.5028 | 0.1684 | 0.7459 | 0.0407 | 0.5022 | stats_elo | 0 | 0 | 0 |
| 15 | aura_features | 2025 | champions_elo | 1309 | 0.5221 | 0.1761 | 0.7280 | 0.0274 | 0.5230 | stats_elo | 0.0005 | -0.0089 | 0.0101 |
| 15 | aura_features | 2025 | stats_elo | 1309 | 0.5217 | 0.1763 | 0.7265 | 0.0236 | 0.5213 | stats_elo | 0 | 0 | 0 |
| 15 | gold | 2023 | champions_elo | 1239 | 0.4790 | 0.1582 | 0.7619 | 0.0337 | 0.4781 | stats_elo | -0.0096 | -0.0178 | -0.0007 |
| 15 | gold | 2023 | stats_elo | 1239 | 0.4886 | 0.1622 | 0.7595 | 0.0268 | 0.4880 | stats_elo | 0 | 0 | 0 |
| 15 | gold | 2024 | champions_elo | 1106 | 0.5130 | 0.1716 | 0.7459 | 0.0391 | 0.5128 | stats_elo | -0.0005 | -0.0108 | 0.0105 |
| 15 | gold | 2024 | stats_elo | 1106 | 0.5135 | 0.1720 | 0.7505 | 0.0330 | 0.5130 | stats_elo | 0 | 0 | 0 |
| 15 | gold | 2025 | champions_elo | 1309 | 0.5260 | 0.1771 | 0.7250 | 0.0277 | 0.5245 | stats_elo | 0.0027 | -0.0072 | 0.0132 |
| 15 | gold | 2025 | stats_elo | 1309 | 0.5233 | 0.1760 | 0.7235 | 0.0421 | 0.5234 | stats_elo | 0 | 0 | 0 |
| 20 | aura_features | 2023 | champions_elo | 1233 | 0.4073 | 0.1306 | 0.8135 | 0.0207 | 0.4077 | stats_elo | -0.0060 | -0.0155 | 0.0037 |
| 20 | aura_features | 2023 | stats_elo | 1233 | 0.4133 | 0.1324 | 0.8151 | 0.0251 | 0.4133 | stats_elo | 0 | 0 | 0 |
| 20 | aura_features | 2024 | champions_elo | 1106 | 0.4477 | 0.1474 | 0.7857 | 0.0317 | 0.4482 | stats_elo | 0.0045 | -0.0064 | 0.0159 |
| 20 | aura_features | 2024 | stats_elo | 1106 | 0.4432 | 0.1457 | 0.7785 | 0.0322 | 0.4421 | stats_elo | 0 | 0 | 0 |
| 20 | aura_features | 2025 | champions_elo | 1309 | 0.4341 | 0.1422 | 0.7869 | 0.0278 | 0.4342 | stats_elo | 0.0016 | -0.0069 | 0.0108 |
| 20 | aura_features | 2025 | stats_elo | 1309 | 0.4325 | 0.1421 | 0.7853 | 0.0285 | 0.4320 | stats_elo | 0 | 0 | 0 |
| 20 | gold | 2023 | champions_elo | 1233 | 0.4180 | 0.1348 | 0.8078 | 0.0255 | 0.4183 | stats_elo | -0.0100 | -0.0195 | -0.0002 |
| 20 | gold | 2023 | stats_elo | 1233 | 0.4280 | 0.1383 | 0.8013 | 0.0255 | 0.4281 | stats_elo | 0 | 0 | 0 |
| 20 | gold | 2024 | champions_elo | 1106 | 0.4548 | 0.1498 | 0.7848 | 0.0288 | 0.4550 | stats_elo | -0.0006 | -0.0113 | 0.0108 |
| 20 | gold | 2024 | stats_elo | 1106 | 0.4555 | 0.1503 | 0.7740 | 0.0241 | 0.4550 | stats_elo | 0 | 0 | 0 |
| 20 | gold | 2025 | champions_elo | 1309 | 0.4452 | 0.1460 | 0.7876 | 0.0307 | 0.4429 | stats_elo | 0.0024 | -0.0076 | 0.0125 |
| 20 | gold | 2025 | stats_elo | 1309 | 0.4428 | 0.1452 | 0.7846 | 0.0312 | 0.4440 | stats_elo | 0 | 0 | 0 |

## Coverage

| minute | year | snapshot_draft_complete | elo_complete |
| --- | --- | --- | --- |
| 10 | 2014 | 739 | 735 |
| 10 | 2015 | 628 | 628 |
| 10 | 2016 | 1369 | 1369 |
| 10 | 2017 | 1657 | 1657 |
| 10 | 2018 | 1887 | 1887 |
| 10 | 2019 | 1806 | 1806 |
| 10 | 2020 | 1835 | 1835 |
| 10 | 2021 | 1633 | 1633 |
| 10 | 2022 | 1237 | 1237 |
| 10 | 2023 | 1239 | 1239 |
| 10 | 2024 | 1106 | 1106 |
| 10 | 2025 | 1309 | 1309 |
| 15 | 2014 | 739 | 735 |
| 15 | 2015 | 628 | 628 |
| 15 | 2016 | 1369 | 1369 |
| 15 | 2017 | 1657 | 1657 |
| 15 | 2018 | 1887 | 1887 |
| 15 | 2019 | 1806 | 1806 |
| 15 | 2020 | 1833 | 1833 |
| 15 | 2021 | 1633 | 1633 |
| 15 | 2022 | 1237 | 1237 |
| 15 | 2023 | 1239 | 1239 |
| 15 | 2024 | 1106 | 1106 |
| 15 | 2025 | 1309 | 1309 |
| 20 | 2014 | 739 | 735 |
| 20 | 2015 | 628 | 628 |
| 20 | 2016 | 1366 | 1366 |
| 20 | 2017 | 1657 | 1657 |
| 20 | 2018 | 1886 | 1886 |
| 20 | 2019 | 1798 | 1798 |
| 20 | 2020 | 1828 | 1828 |
| 20 | 2021 | 1626 | 1626 |
| 20 | 2022 | 1233 | 1233 |
| 20 | 2023 | 1233 | 1233 |
| 20 | 2024 | 1106 | 1106 |
| 20 | 2025 | 1309 | 1309 |

## Decision limits

These folds have already informed model development, and existing Elo settings were selected in prior work. A small lower point estimate does not establish a reliable benefit. Keep an inconclusive champion addition out of the chosen candidate; freeze the selected design before evaluating newly collected matches. Probability quality does not establish a betting edge without aligned executable prices and costs. This experiment changes no published metrics or live behavior.
