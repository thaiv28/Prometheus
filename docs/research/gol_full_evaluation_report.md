# Completed-corpus win probability evaluation

The primary 15-minute objective comparison is inconclusive on this retrospective cohort: added-minus-gold+Elo log loss -0.02274, paired series-bootstrap 95% interval [-0.04554, +0.00093]. This evaluates map winners, not series contracts or profitability.

Post-run assessment: the historical-data/modeling route supports an automatic extraction and prospective paper-prediction pilot. Gold+Elo has the clearest evidence of useful signal. Towers/dragons are a reasonable fixed comparison for that pilot; their benefit across years remains uncertain and Herald contributes little in this benchmark. Keep gold+Elo as the control. No profitability conclusion follows from these results.

For the simpler towers/dragons variant, 2025 accuracy intervals are 66.8–76.9% at 10m, 69.9–80.2% at 15m, and 73.0–82.0% at 20m (whole-series bootstrap). At 15m its 60–70% favourite bucket averages 64.9% predicted confidence but only 56.25% wins (80 maps); 80–90% averages 85.6% versus 80% wins (75 maps). All 65 >90% favourites win, but this is 53 correlated series and does not establish certainty. A bootstrap of an all-success bin necessarily returns [1,1]: that degenerate empirical interval cannot bound the risk of future losses. The same limitation applies to the all-objectives confidence table below.

For that towers/dragons variant at 15m, rounding each team's gold to the nearest 100 shifts probabilities by 0.35 percentage points on average and 0.96 points at the 95th percentile. A one-tower gap error shifts them by roughly 7.3 points on average; a one-dragon gap error roughly 5.5 points. These hypothetical tests argue for strict objective-reading checks, not a claim that actual OCR has been validated.

## Data and fixed protocol

1451 verified games / 4308 checkpoint rows, selected LCK/LCS/LEC/Worlds events in 2022–2025. LPL and 2026 excluded. Train 2022–2023 / calibrate 2024 / test 2025 is primary. Train 2022 / calibrate 2023 / test 2024 is a secondary temporal stability check. Same games for every variant within a fold/minute; separate models at 10/15/20m, no pooling correlated checkpoints as independent games. Explicit series cannot cross partitions. Logistic C=1, training-only scaling, separate-year sigmoid C=1e6; fixed before scoring, no search or post-score recalibration. Constant baseline uses prior calibration-year blue win rate. 2,000 series-cluster bootstrap draws, seed 42, conditional on fitted models and this selected population.

Primary endpoint: calibrated 2025 15m all-objectives vs gold+Elo log loss. All other metrics, comparisons, subgroups and stress tests are descriptive/secondary; no multiple-testing-based model selection. 2025/2026 outcomes were viewed in earlier research, so these periods are not untouched prospective holdouts.

Scoreboard-objectives uses gold/Elo/tower/elemental-dragon gaps. All-objectives additionally requests Herald/Elder/Baron/grubs/Atakhan gaps; training-constant columns are omitted and recorded. Thus old-year training cannot learn grubs/Atakhan and Baron/Elder have no meaningful pre-20m examples. The live pilot must establish which counters are recoverable; absence in a frame cannot be assumed zero.

## Primary 2025 performance

Lower log loss/Brier/ECE is better; higher AUC/accuracy is better. Brier skill compares with the past-year constant prior. AUC measures ranking, not calibration or profit.

| minute | variant | train_games | calibration_games | n | series | log_loss | brier | roc_auc | accuracy | balanced_accuracy | mcc | brier_skill_prior | ece10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | constant_prior | 768 | 310 | 361 | 176 | 0.6916 | 0.2492 | 0.5000 | 0.5291 | 0.5000 | 0 | 0 | 0.0096 |
| 10 | elo | 768 | 310 | 361 | 176 | 0.5850 | 0.1996 | 0.7620 | 0.7036 | 0.7018 | 0.4044 | 0.1992 | 0.0611 |
| 10 | gold | 768 | 310 | 361 | 176 | 0.6182 | 0.2157 | 0.7072 | 0.6427 | 0.6368 | 0.2798 | 0.1344 | 0.0266 |
| 10 | gold_elo | 768 | 310 | 361 | 176 | 0.5380 | 0.1823 | 0.7989 | 0.7175 | 0.7152 | 0.4319 | 0.2685 | 0.0619 |
| 10 | scoreboard_objectives | 768 | 310 | 361 | 176 | 0.5328 | 0.1807 | 0.8038 | 0.7175 | 0.7155 | 0.4321 | 0.2751 | 0.0467 |
| 10 | all_objectives | 768 | 310 | 361 | 176 | 0.5331 | 0.1808 | 0.8037 | 0.7175 | 0.7155 | 0.4321 | 0.2747 | 0.0581 |
| 15 | constant_prior | 765 | 312 | 357 | 176 | 0.6919 | 0.2494 | 0.5000 | 0.5266 | 0.5000 | 0 | 0 | 0.0086 |
| 15 | elo | 765 | 312 | 357 | 176 | 0.5821 | 0.1982 | 0.7658 | 0.7059 | 0.7046 | 0.4096 | 0.2050 | 0.0720 |
| 15 | gold | 765 | 312 | 357 | 176 | 0.5988 | 0.2070 | 0.7406 | 0.6499 | 0.6469 | 0.2958 | 0.1701 | 0.0710 |
| 15 | gold_elo | 765 | 312 | 357 | 176 | 0.5310 | 0.1810 | 0.8029 | 0.7143 | 0.7129 | 0.4264 | 0.2742 | 0.0516 |
| 15 | scoreboard_objectives | 765 | 312 | 357 | 176 | 0.5076 | 0.1718 | 0.8234 | 0.7507 | 0.7501 | 0.5001 | 0.3111 | 0.0816 |
| 15 | all_objectives | 765 | 312 | 357 | 176 | 0.5083 | 0.1721 | 0.8234 | 0.7507 | 0.7501 | 0.5001 | 0.3098 | 0.0837 |
| 20 | constant_prior | 762 | 315 | 358 | 176 | 0.6923 | 0.2496 | 0.5000 | 0.5251 | 0.5000 | 0 | 0 | 0.0145 |
| 20 | elo | 762 | 315 | 358 | 176 | 0.5841 | 0.1993 | 0.7620 | 0.6955 | 0.6938 | 0.3886 | 0.2016 | 0.0725 |
| 20 | gold | 762 | 315 | 358 | 176 | 0.5155 | 0.1755 | 0.8181 | 0.7207 | 0.7160 | 0.4410 | 0.2967 | 0.0769 |
| 20 | gold_elo | 762 | 315 | 358 | 176 | 0.4718 | 0.1584 | 0.8499 | 0.7682 | 0.7652 | 0.5354 | 0.3652 | 0.0532 |
| 20 | scoreboard_objectives | 762 | 315 | 358 | 176 | 0.4401 | 0.1460 | 0.8727 | 0.7765 | 0.7743 | 0.5517 | 0.4151 | 0.0394 |
| 20 | all_objectives | 762 | 315 | 358 | 176 | 0.4399 | 0.1462 | 0.8729 | 0.7793 | 0.7767 | 0.5577 | 0.4143 | 0.0428 |

## Paired improvements and uncertainty

Deltas are added-minus-reference: negative is better for loss/Brier, positive for accuracy. Resampling whole series keeps maps correlated. These intervals do not include model-training uncertainty or unobserved selection/patch shifts.

| minute | variant | reference | n | series | delta | low | high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | gold_elo | gold | 361 | 176 | -0.0802 | -0.1127 | -0.0492 |
| 10 | gold_elo | elo | 361 | 176 | -0.0470 | -0.0741 | -0.0187 |
| 10 | scoreboard_objectives | gold_elo | 361 | 176 | -0.0052 | -0.0245 | 0.0132 |
| 10 | all_objectives | gold_elo | 361 | 176 | -0.0049 | -0.0249 | 0.0139 |
| 10 | all_objectives | scoreboard_objectives | 361 | 176 | 0.0003 | -0.0003 | 0.0008 |
| 15 | gold_elo | gold | 357 | 176 | -0.0678 | -0.0973 | -0.0397 |
| 15 | gold_elo | elo | 357 | 176 | -0.0510 | -0.0932 | -0.0051 |
| 15 | scoreboard_objectives | gold_elo | 357 | 176 | -0.0234 | -0.0462 | 0.0009 |
| 15 | all_objectives | gold_elo | 357 | 176 | -0.0227 | -0.0455 | 0.0009 |
| 15 | all_objectives | scoreboard_objectives | 357 | 176 | 0.0007 | -0.0006 | 0.0020 |
| 20 | gold_elo | gold | 358 | 176 | -0.0436 | -0.0639 | -0.0221 |
| 20 | gold_elo | elo | 358 | 176 | -0.1122 | -0.1605 | -0.0625 |
| 20 | scoreboard_objectives | gold_elo | 358 | 176 | -0.0317 | -0.0553 | -0.0078 |
| 20 | all_objectives | gold_elo | 358 | 176 | -0.0320 | -0.0547 | -0.0087 |
| 20 | all_objectives | scoreboard_objectives | 358 | 176 | -0.0002 | -0.0071 | 0.0071 |

Absolute log-loss/Brier/accuracy intervals and paired Brier/accuracy intervals are in metrics.csv and paired.csv. All individual predictions and model parameters are exported for inspection.

## Calibration and raw probabilities

Diagnostic calibration slope ideal=1, intercept ideal=0; they are estimated on evaluation outcomes only for diagnosis and never applied to predictions. A slope below 1 suggests overly extreme scores. Positive bias means blue win probabilities exceed blue win frequency. ECE depends on bins and sample size; it is not a guaranteed pointwise error bound.

| minute | variant | raw_log_loss | log_loss | raw_brier | brier | ece5 | ece10 | ece15 | calibration_bias | diagnostic_calibration_intercept | diagnostic_calibration_slope | sharpness_std |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | gold_elo | 0.5386 | 0.5380 | 0.1827 | 0.1823 | 0.0520 | 0.0619 | 0.0613 | -0.0085 | 0.0358 | 1.1757 | 0.2383 |
| 10 | scoreboard_objectives | 0.5333 | 0.5328 | 0.1811 | 0.1807 | 0.0338 | 0.0467 | 0.0812 | -0.0029 | 0.0029 | 1.1635 | 0.2434 |
| 10 | all_objectives | 0.5340 | 0.5331 | 0.1813 | 0.1808 | 0.0333 | 0.0581 | 0.0903 | -0.0029 | 0.0030 | 1.1625 | 0.2433 |
| 15 | gold_elo | 0.5308 | 0.5310 | 0.1805 | 0.1810 | 0.0435 | 0.0516 | 0.0697 | -0.0075 | 0.0473 | 0.9225 | 0.2794 |
| 15 | scoreboard_objectives | 0.5082 | 0.5076 | 0.1719 | 0.1718 | 0.0335 | 0.0816 | 0.0861 | -0.0086 | 0.0524 | 0.9838 | 0.2864 |
| 15 | all_objectives | 0.5086 | 0.5083 | 0.1721 | 0.1721 | 0.0359 | 0.0837 | 0.0931 | -0.0066 | 0.0412 | 0.9698 | 0.2881 |
| 20 | gold_elo | 0.4698 | 0.4718 | 0.1575 | 0.1584 | 0.0428 | 0.0532 | 0.0577 | 0.0215 | -0.1274 | 0.9257 | 0.3164 |
| 20 | scoreboard_objectives | 0.4402 | 0.4401 | 0.1457 | 0.1460 | 0.0220 | 0.0394 | 0.0508 | 0.0094 | -0.0688 | 1.0333 | 0.3202 |
| 20 | all_objectives | 0.4398 | 0.4399 | 0.1459 | 0.1462 | 0.0369 | 0.0428 | 0.0643 | 0.0097 | -0.0704 | 1.0233 | 0.3215 |

## Temporal stability

| year | minute | variant | n | log_loss | raw_log_loss | brier | accuracy | ece10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | 10 | gold_elo | 310 | 0.5509 | 0.5554 | 0.1859 | 0.7097 | 0.0383 |
| 2024 | 10 | scoreboard_objectives | 310 | 0.5399 | 0.5500 | 0.1819 | 0.7097 | 0.0310 |
| 2024 | 10 | all_objectives | 310 | 0.5402 | 0.5507 | 0.1820 | 0.7097 | 0.0333 |
| 2024 | 15 | gold_elo | 312 | 0.4847 | 0.4861 | 0.1581 | 0.7692 | 0.0535 |
| 2024 | 15 | scoreboard_objectives | 312 | 0.4791 | 0.4801 | 0.1579 | 0.7596 | 0.0607 |
| 2024 | 15 | all_objectives | 312 | 0.4779 | 0.4788 | 0.1576 | 0.7628 | 0.0595 |
| 2024 | 20 | gold_elo | 315 | 0.4200 | 0.4246 | 0.1375 | 0.7778 | 0.0613 |
| 2024 | 20 | scoreboard_objectives | 315 | 0.4291 | 0.4305 | 0.1413 | 0.7873 | 0.0600 |
| 2024 | 20 | all_objectives | 315 | 0.4264 | 0.4277 | 0.1405 | 0.7778 | 0.0530 |
| 2025 | 10 | gold_elo | 361 | 0.5380 | 0.5386 | 0.1823 | 0.7175 | 0.0619 |
| 2025 | 10 | scoreboard_objectives | 361 | 0.5328 | 0.5333 | 0.1807 | 0.7175 | 0.0467 |
| 2025 | 10 | all_objectives | 361 | 0.5331 | 0.5340 | 0.1808 | 0.7175 | 0.0581 |
| 2025 | 15 | gold_elo | 357 | 0.5310 | 0.5308 | 0.1810 | 0.7143 | 0.0516 |
| 2025 | 15 | scoreboard_objectives | 357 | 0.5076 | 0.5082 | 0.1718 | 0.7507 | 0.0816 |
| 2025 | 15 | all_objectives | 357 | 0.5083 | 0.5086 | 0.1721 | 0.7507 | 0.0837 |
| 2025 | 20 | gold_elo | 358 | 0.4718 | 0.4698 | 0.1584 | 0.7682 | 0.0532 |
| 2025 | 20 | scoreboard_objectives | 358 | 0.4401 | 0.4402 | 0.1460 | 0.7765 | 0.0394 |
| 2025 | 20 | all_objectives | 358 | 0.4399 | 0.4398 | 0.1462 | 0.7793 | 0.0428 |

Expanding chronological training-prefix learning curves use RAW predictions on the earlier calibration year, never fitting a calibrator to those curve scores. See learning_curves.csv. They are not tuning runs against 2025.

## LCS/LTA and other leagues

Small slices can move substantially with a few games; per-league point estimates are descriptive. Additional gold-state and Elo-versus-gold-disagreement slices are in subgroups.csv.

| minute | variant | value | n | log_loss | brier | roc_auc | accuracy | ece10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | gold_elo | LCK | 135 | 0.5080 | 0.1705 | 0.8276 | 0.7481 | 0.0833 |
| 10 | gold_elo | LCS | 64 | 0.4747 | 0.1560 | 0.8667 | 0.7500 | 0.1280 |
| 10 | gold_elo | LEC | 83 | 0.5906 | 0.2014 | 0.7591 | 0.7470 | 0.1466 |
| 10 | gold_elo | Worlds | 79 | 0.5853 | 0.2038 | 0.7571 | 0.6076 | 0.1489 |
| 10 | scoreboard_objectives | LCK | 135 | 0.5274 | 0.1796 | 0.8046 | 0.6963 | 0.0668 |
| 10 | scoreboard_objectives | LCS | 64 | 0.4498 | 0.1452 | 0.8853 | 0.7969 | 0.0991 |
| 10 | scoreboard_objectives | LEC | 83 | 0.5629 | 0.1900 | 0.7893 | 0.7470 | 0.1227 |
| 10 | scoreboard_objectives | Worlds | 79 | 0.5778 | 0.2015 | 0.7654 | 0.6582 | 0.1204 |
| 10 | all_objectives | LCK | 135 | 0.5285 | 0.1801 | 0.8041 | 0.6963 | 0.0670 |
| 10 | all_objectives | LCS | 64 | 0.4496 | 0.1451 | 0.8863 | 0.7969 | 0.0987 |
| 10 | all_objectives | LEC | 83 | 0.5624 | 0.1898 | 0.7925 | 0.7470 | 0.1248 |
| 10 | all_objectives | Worlds | 79 | 0.5777 | 0.2015 | 0.7647 | 0.6582 | 0.1207 |
| 15 | gold_elo | LCK | 134 | 0.4649 | 0.1550 | 0.8578 | 0.7612 | 0.0453 |
| 15 | gold_elo | LCS | 64 | 0.4995 | 0.1720 | 0.8373 | 0.7188 | 0.1383 |
| 15 | gold_elo | LEC | 81 | 0.6281 | 0.2146 | 0.7420 | 0.6914 | 0.1639 |
| 15 | gold_elo | Worlds | 78 | 0.5699 | 0.1981 | 0.7789 | 0.6538 | 0.1387 |
| 15 | scoreboard_objectives | LCK | 134 | 0.4580 | 0.1534 | 0.8598 | 0.7836 | 0.0608 |
| 15 | scoreboard_objectives | LCS | 64 | 0.4649 | 0.1541 | 0.8696 | 0.7812 | 0.0944 |
| 15 | scoreboard_objectives | LEC | 81 | 0.5845 | 0.2021 | 0.7752 | 0.7037 | 0.1960 |
| 15 | scoreboard_objectives | Worlds | 78 | 0.5482 | 0.1864 | 0.8072 | 0.7179 | 0.1104 |
| 15 | all_objectives | LCK | 134 | 0.4572 | 0.1530 | 0.8605 | 0.7836 | 0.0573 |
| 15 | all_objectives | LCS | 64 | 0.4670 | 0.1552 | 0.8686 | 0.7812 | 0.1086 |
| 15 | all_objectives | LEC | 81 | 0.5855 | 0.2026 | 0.7732 | 0.7037 | 0.1865 |
| 15 | all_objectives | Worlds | 78 | 0.5499 | 0.1872 | 0.8053 | 0.7179 | 0.1123 |
| 20 | gold_elo | LCK | 133 | 0.3959 | 0.1309 | 0.8946 | 0.8120 | 0.0788 |
| 20 | gold_elo | LCS | 64 | 0.4222 | 0.1439 | 0.8892 | 0.7500 | 0.1395 |
| 20 | gold_elo | LEC | 83 | 0.5932 | 0.2008 | 0.7547 | 0.7108 | 0.1235 |
| 20 | gold_elo | Worlds | 78 | 0.5129 | 0.1723 | 0.8513 | 0.7692 | 0.1305 |
| 20 | scoreboard_objectives | LCK | 133 | 0.3919 | 0.1263 | 0.9039 | 0.8271 | 0.0537 |
| 20 | scoreboard_objectives | LCS | 64 | 0.3909 | 0.1298 | 0.9078 | 0.7969 | 0.0964 |
| 20 | scoreboard_objectives | LEC | 83 | 0.5571 | 0.1918 | 0.7981 | 0.6627 | 0.1252 |
| 20 | scoreboard_objectives | Worlds | 78 | 0.4381 | 0.1441 | 0.8967 | 0.7949 | 0.1108 |
| 20 | all_objectives | LCK | 133 | 0.3914 | 0.1262 | 0.9016 | 0.8421 | 0.0659 |
| 20 | all_objectives | LCS | 64 | 0.3926 | 0.1297 | 0.9049 | 0.7969 | 0.1144 |
| 20 | all_objectives | LEC | 83 | 0.5619 | 0.1946 | 0.7981 | 0.6747 | 0.1995 |
| 20 | all_objectives | Worlds | 78 | 0.4315 | 0.1422 | 0.8987 | 0.7692 | 0.1053 |

## Confidence versus actual wins

Favourite confidence bins use the team the model favours; observed is how often that team wins. Intervals resample series within each bin, conditional on bin membership. Very small bins are weak evidence.

| bin | n | series | predicted | observed | gap | low | high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5–0.6 | 62 | 53 | 0.5517 | 0.6774 | -0.1257 | 0.5667 | 0.7903 |
| 0.6–0.7 | 81 | 65 | 0.6513 | 0.5802 | 0.0710 | 0.4800 | 0.6790 |
| 0.7–0.8 | 74 | 61 | 0.7569 | 0.7297 | 0.0271 | 0.6267 | 0.8359 |
| 0.8–0.9 | 72 | 66 | 0.8569 | 0.7917 | 0.0652 | 0.6957 | 0.8831 |
| 0.9–1.0 | 68 | 56 | 0.9440 | 1 | -0.0560 | 1 | 1 |

Reliability bins for BLUE probabilities at every checkpoint/model are in reliability.csv; confidence.csv contains all favourite bins. Metrics include counts, wrong calls and accuracy above 80%/90% confidence, mean confidence gap, precision/recall and average precision (blue-positive).

## Fixed old model on newly acquired series

The original 1,031-game experiment stays frozen. This check applies those exact saved weights/calibrators to newly acquired 2025 series, excluding every series in its original scored predictions. No refitting. This is a small retrospective extension, not a pristine new season; it complements the full-corpus refit.

| minute | n | series | control_log_loss | objective_log_loss | delta | low | high |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 66 | 28 | 0.5383 | 0.5699 | 0.0316 | -0.0022 | 0.0694 |
| 15 | 65 | 28 | 0.4720 | 0.5027 | 0.0308 | -0.0117 | 0.0781 |
| 20 | 65 | 28 | 0.4272 | 0.4595 | 0.0322 | -0.0192 | 0.0833 |

## Broadcast input robustness

Hypothetical rounding/error scenarios use the SAME fitted models and current checkpoint state. These are not measured OCR errors or full latency simulations; no missing objective is imputed zero. Delay can change gold/objectives and market quotes, which this static dataset cannot fully quantify.

| minute | scenario | mean_probability_shift | p95_probability_shift | max_probability_shift | log_loss_delta |
| --- | --- | --- | --- | --- | --- |
| 10 | round_each_gold_100 | 0.0043 | 0.0106 | 0.0157 | 0.0002 |
| 10 | round_each_gold_500 | 0.0213 | 0.0544 | 0.0693 | 0.0076 |
| 10 | round_each_gold_1000 | 0.0408 | 0.1174 | 0.1500 | 0.0047 |
| 10 | misread_tower_gap_-1 | 0.0203 | 0.0267 | 0.0268 | 0.0008 |
| 10 | misread_tower_gap_+1 | 0.0204 | 0.0267 | 0.0268 | 0.0014 |
| 10 | misread_dragon_gap_-1 | 0.0835 | 0.1093 | 0.1094 | 0.0196 |
| 10 | misread_dragon_gap_+1 | 0.0823 | 0.1092 | 0.1094 | 0.0169 |
| 10 | misread_herald_gap_-1 | 0.0130 | 0.0171 | 0.0171 | 0.0006 |
| 10 | misread_herald_gap_+1 | 0.0130 | 0.0171 | 0.0171 | 0.0002 |
| 15 | round_each_gold_100 | 0.0035 | 0.0097 | 0.0145 | -0.0013 |
| 15 | round_each_gold_500 | 0.0189 | 0.0491 | 0.0718 | 0.0009 |
| 15 | round_each_gold_1000 | 0.0352 | 0.1027 | 0.1537 | 0.0113 |
| 15 | misread_tower_gap_-1 | 0.0717 | 0.1081 | 0.1085 | 0.0128 |
| 15 | misread_tower_gap_+1 | 0.0726 | 0.1079 | 0.1085 | 0.0187 |
| 15 | misread_dragon_gap_-1 | 0.0536 | 0.0798 | 0.0801 | 0.0107 |
| 15 | misread_dragon_gap_+1 | 0.0531 | 0.0799 | 0.0801 | 0.0064 |
| 15 | misread_herald_gap_-1 | 0.0159 | 0.0239 | 0.0240 | 0.0001 |
| 15 | misread_herald_gap_+1 | 0.0160 | 0.0239 | 0.0240 | 0.0014 |
| 20 | round_each_gold_100 | 0.0023 | 0.0074 | 0.0103 | -0.0000 |
| 20 | round_each_gold_500 | 0.0109 | 0.0319 | 0.0458 | -0.0014 |
| 20 | round_each_gold_1000 | 0.0247 | 0.0777 | 0.1046 | 0.0062 |
| 20 | misread_tower_gap_-1 | 0.0005 | 0.0009 | 0.0009 | -0.0000 |
| 20 | misread_tower_gap_+1 | 0.0005 | 0.0009 | 0.0009 | 0.0000 |
| 20 | misread_dragon_gap_-1 | 0.0479 | 0.0816 | 0.0819 | 0.0047 |
| 20 | misread_dragon_gap_+1 | 0.0473 | 0.0810 | 0.0819 | 0.0110 |
| 20 | misread_herald_gap_-1 | 0.0241 | 0.0413 | 0.0416 | 0.0036 |
| 20 | misread_herald_gap_+1 | 0.0243 | 0.0415 | 0.0416 | 0.0004 |

Probability shifts are fractions (0.01 = 1 percentage point). Coefficients and conditional odds ratios are in coefficients.csv; correlated gold/objectives mean negative conditional coefficients do not prove an objective is harmful. No isolated objective attribution is claimed.

## What this establishes and what remains

The benchmark can support a live-data paper-prediction pilot if objectives improve on the same games with adequate calibration and robustness. Current limitations remain selected-event/name/roster exclusions, patch changes, no independent broadcast verification of every historical objective time, small league/confidence slices and previously viewed periods. A sigmoid fitted on 2024 does not guarantee 2026 calibration. All current-game inputs must be available when the system receives them; final totals are validation-only, winner labels/identity/date are not numeric predictors.

Profitability, ROI, market-relative incremental information and executable edge remain UNMEASURED: there are no synchronized in-game executable quotes, bid/ask spreads, depth, fees or broadcast receipt-delay records in this dataset. Map probabilities cannot be substituted for series probabilities. Automatic LCS/LTA extraction still needs labelled real frames, replay/overlay rejection, side/game identity, observable counters, rounding and latency measurements. Then freeze a pilot model and assess prospective paper predictions with synchronized quotes.

## Reproduction

Run `.venv/bin/python scripts/research/evaluate_gol_full.py`. First run freezes exact inputs, numeric parameters, predictions, source/helper hashes, diagnostics and plots under data/gol_full_evaluation/. Same-directory reruns are refused. Original experiment is never overwritten. Inspect diagnostics.png for calibration and the paired loss comparison. No published metric, DB or site changes.
