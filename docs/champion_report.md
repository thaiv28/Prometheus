# Champion and lane-matchup experiment

Exploratory only: evaluated on 2023–2025 chronological folds. The already-viewed 2026 baseline holdout is excluded from champion model selection and scoring. Confirm any candidate on a new period.

## Finding

No champion or matchup variant has a pooled log-loss improvement whose paired 95% interval excludes zero. Keep the stats-only model as the benchmark; these results do not justify adopting the champion variants.

## How champions enter the model

Each role has a champion effect, entered +1 for blue and −1 for red. These ten champion identities produce an additive team-composition score. The matchup variant adds signed, same-role champion-pair effects beyond those main effects. For example, top-lane Aatrox against Ornn has a different residual effect from either champion alone. Swapping drafts reverses every feature. Mirror matchups cancel.

Champion-role effects need at least 10 training occurrences; exact lane matchups need at least 20. Cutoffs and feature vocabularies use training only. Unseen/sparse matchups fall back to main effects; unseen champions have zero learned draft effect and rely on game-state stats. Stronger ridge regularization (C=0.1 for champion models) is fixed in advance. A stats-only C=0.1 control separates feature additions from a change in regularization; the original C=1 baseline is also retained.

Models are separate at 10/15/20 minutes, allowing champion effects to differ by game stage. This first experiment does not model champion×gold interactions, arbitrary five-champion synergies, player identity, pregame team strength, or patch-specific effects. An additive composition score is not a full composition model.

## Evaluation

Compare gold-only and AURA-feature baselines with champion and champion+matchup variants on identical complete-snapshot/draft cohorts. Each fold trains on three older calendar years, fits a sigmoid calibrator on the next year, and evaluates the following year. Numeric scaling and draft encoding see training only. Log loss and Brier judge probabilities; accuracy and ten-bin ECE are diagnostics. Paired 95% intervals resample league/day clusters (2,000 draws, seed 42), approximating series grouping. Intervals are not adjusted for multiple comparisons. These older folds have already been viewed; they are development evidence.

## Pooled development results

Negative delta_base means lower log loss than the indicated same-regularization control. delta_original compares with the original C=1 stats-only model.

| minute | base | variant | n | log_loss | brier | accuracy | ece10 | control | delta_original | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | champions | 3654 | 0.6027 | 0.2080 | 0.6730 | 0.0143 | stats_shrunk | -0.0007 | -0.0006 | -0.0064 | 0.0050 |
| 10 | aura_features | matchups | 3654 | 0.6024 | 0.2079 | 0.6762 | 0.0138 | stats_shrunk | -0.0010 | -0.0009 | -0.0064 | 0.0045 |
| 10 | aura_features | stats | 3654 | 0.6035 | 0.2084 | 0.6708 | 0.0115 | stats | 0 | 0 | 0 | 0 |
| 10 | aura_features | stats_shrunk | 3654 | 0.6033 | 0.2083 | 0.6708 | 0.0130 | stats_shrunk | -0.0001 | 0 | 0 | 0 |
| 10 | gold | champions | 3654 | 0.6065 | 0.2096 | 0.6667 | 0.0107 | stats_shrunk | 0.0012 | 0.0012 | -0.0042 | 0.0065 |
| 10 | gold | matchups | 3654 | 0.6065 | 0.2096 | 0.6658 | 0.0124 | stats_shrunk | 0.0012 | 0.0012 | -0.0043 | 0.0063 |
| 10 | gold | stats | 3654 | 0.6053 | 0.2090 | 0.6653 | 0.0138 | stats | 0 | 0 | 0 | 0 |
| 10 | gold | stats_shrunk | 3654 | 0.6053 | 0.2090 | 0.6653 | 0.0138 | stats_shrunk | 0.0000 | 0 | 0 | 0 |
| 15 | aura_features | champions | 3654 | 0.5327 | 0.1793 | 0.7219 | 0.0193 | stats_shrunk | -0.0028 | -0.0027 | -0.0085 | 0.0031 |
| 15 | aura_features | matchups | 3654 | 0.5330 | 0.1794 | 0.7228 | 0.0202 | stats_shrunk | -0.0026 | -0.0024 | -0.0081 | 0.0032 |
| 15 | aura_features | stats | 3654 | 0.5356 | 0.1808 | 0.7209 | 0.0174 | stats | 0 | 0 | 0 | 0 |
| 15 | aura_features | stats_shrunk | 3654 | 0.5354 | 0.1807 | 0.7225 | 0.0164 | stats_shrunk | -0.0002 | 0 | 0 | 0 |
| 15 | gold | champions | 3654 | 0.5423 | 0.1830 | 0.7184 | 0.0135 | stats_shrunk | -0.0015 | -0.0015 | -0.0075 | 0.0043 |
| 15 | gold | matchups | 3654 | 0.5422 | 0.1830 | 0.7178 | 0.0182 | stats_shrunk | -0.0016 | -0.0016 | -0.0074 | 0.0042 |
| 15 | gold | stats | 3654 | 0.5438 | 0.1838 | 0.7184 | 0.0121 | stats | 0 | 0 | 0 | 0 |
| 15 | gold | stats_shrunk | 3654 | 0.5438 | 0.1838 | 0.7184 | 0.0121 | stats_shrunk | 0.0000 | 0 | 0 | 0 |
| 20 | aura_features | champions | 3648 | 0.4498 | 0.1474 | 0.7851 | 0.0101 | stats_shrunk | -0.0014 | -0.0010 | -0.0067 | 0.0049 |
| 20 | aura_features | matchups | 3648 | 0.4504 | 0.1477 | 0.7826 | 0.0095 | stats_shrunk | -0.0007 | -0.0003 | -0.0060 | 0.0054 |
| 20 | aura_features | stats | 3648 | 0.4511 | 0.1475 | 0.7826 | 0.0119 | stats | 0 | 0 | 0 | 0 |
| 20 | aura_features | stats_shrunk | 3648 | 0.4508 | 0.1474 | 0.7840 | 0.0114 | stats_shrunk | -0.0004 | 0 | 0 | 0 |
| 20 | gold | champions | 3648 | 0.4615 | 0.1519 | 0.7771 | 0.0155 | stats_shrunk | -0.0015 | -0.0015 | -0.0073 | 0.0046 |
| 20 | gold | matchups | 3648 | 0.4620 | 0.1521 | 0.7747 | 0.0145 | stats_shrunk | -0.0009 | -0.0009 | -0.0067 | 0.0051 |
| 20 | gold | stats | 3648 | 0.4630 | 0.1523 | 0.7766 | 0.0166 | stats | 0 | 0 | 0 | 0 |
| 20 | gold | stats_shrunk | 3648 | 0.4629 | 0.1523 | 0.7766 | 0.0171 | stats_shrunk | -0.0000 | 0 | 0 | 0 |

## Annual results

| minute | year | base | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_original | delta_base | delta_low | delta_high | draft_features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2023 | gold | stats | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5899 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | gold | stats_shrunk | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5897 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 |
| 10 | 2023 | gold | champions | 1239 | 0.5877 | 0.2009 | 0.6877 | 0.0418 | 0.5909 | stats_shrunk | -0.0018 | -0.0018 | -0.0112 | 0.0079 | 232 |
| 10 | 2023 | gold | matchups | 1239 | 0.5906 | 0.2021 | 0.6844 | 0.0344 | 0.5952 | stats_shrunk | 0.0010 | 0.0010 | -0.0085 | 0.0111 | 561 |
| 10 | 2023 | aura_features | stats | 1239 | 0.5866 | 0.2004 | 0.6949 | 0.0236 | 0.5867 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | aura_features | stats_shrunk | 1239 | 0.5870 | 0.2006 | 0.6949 | 0.0272 | 0.5871 | stats_shrunk | 0.0004 | 0 | 0 | 0 | 0 |
| 10 | 2023 | aura_features | champions | 1239 | 0.5851 | 0.1998 | 0.6917 | 0.0244 | 0.5888 | stats_shrunk | -0.0015 | -0.0019 | -0.0118 | 0.0082 | 232 |
| 10 | 2023 | aura_features | matchups | 1239 | 0.5873 | 0.2008 | 0.6877 | 0.0267 | 0.5922 | stats_shrunk | 0.0007 | 0.0003 | -0.0094 | 0.0107 | 561 |
| 10 | 2024 | gold | stats | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6104 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | gold | stats_shrunk | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6101 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 |
| 10 | 2024 | gold | champions | 1106 | 0.6096 | 0.2109 | 0.6637 | 0.0267 | 0.6142 | stats_shrunk | 0.0003 | 0.0003 | -0.0082 | 0.0091 | 207 |
| 10 | 2024 | gold | matchups | 1106 | 0.6083 | 0.2103 | 0.6637 | 0.0282 | 0.6135 | stats_shrunk | -0.0010 | -0.0010 | -0.0088 | 0.0071 | 522 |
| 10 | 2024 | aura_features | stats | 1106 | 0.6062 | 0.2098 | 0.6646 | 0.0252 | 0.6072 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | aura_features | stats_shrunk | 1106 | 0.6058 | 0.2096 | 0.6646 | 0.0223 | 0.6067 | stats_shrunk | -0.0004 | 0 | 0 | 0 | 0 |
| 10 | 2024 | aura_features | champions | 1106 | 0.6052 | 0.2090 | 0.6618 | 0.0276 | 0.6106 | stats_shrunk | -0.0009 | -0.0006 | -0.0092 | 0.0089 | 207 |
| 10 | 2024 | aura_features | matchups | 1106 | 0.6033 | 0.2081 | 0.6691 | 0.0239 | 0.6091 | stats_shrunk | -0.0029 | -0.0025 | -0.0109 | 0.0062 | 522 |
| 10 | 2025 | gold | stats | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6163 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | gold | stats_shrunk | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6164 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 |
| 10 | 2025 | gold | champions | 1309 | 0.6216 | 0.2168 | 0.6494 | 0.0245 | 0.6216 | stats_shrunk | 0.0048 | 0.0048 | -0.0045 | 0.0147 | 199 |
| 10 | 2025 | gold | matchups | 1309 | 0.6199 | 0.2162 | 0.6501 | 0.0243 | 0.6200 | stats_shrunk | 0.0031 | 0.0031 | -0.0070 | 0.0139 | 476 |
| 10 | 2025 | aura_features | stats | 1309 | 0.6171 | 0.2147 | 0.6532 | 0.0307 | 0.6169 | stats | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | aura_features | stats_shrunk | 1309 | 0.6167 | 0.2145 | 0.6532 | 0.0309 | 0.6165 | stats_shrunk | -0.0004 | 0 | 0 | 0 | 0 |
| 10 | 2025 | aura_features | champions | 1309 | 0.6173 | 0.2148 | 0.6646 | 0.0312 | 0.6181 | stats_shrunk | 0.0002 | 0.0006 | -0.0086 | 0.0103 | 199 |
| 10 | 2025 | aura_features | matchups | 1309 | 0.6161 | 0.2144 | 0.6715 | 0.0416 | 0.6174 | stats_shrunk | -0.0010 | -0.0006 | -0.0109 | 0.0102 | 476 |
| 15 | 2023 | gold | stats | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5135 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | gold | stats_shrunk | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5137 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 |
| 15 | 2023 | gold | champions | 1239 | 0.5087 | 0.1687 | 0.7450 | 0.0328 | 0.5076 | stats_shrunk | -0.0059 | -0.0059 | -0.0151 | 0.0039 | 232 |
| 15 | 2023 | gold | matchups | 1239 | 0.5120 | 0.1699 | 0.7441 | 0.0397 | 0.5116 | stats_shrunk | -0.0026 | -0.0026 | -0.0119 | 0.0074 | 560 |
| 15 | 2023 | aura_features | stats | 1239 | 0.5028 | 0.1673 | 0.7490 | 0.0319 | 0.5017 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | aura_features | stats_shrunk | 1239 | 0.5027 | 0.1673 | 0.7490 | 0.0320 | 0.5016 | stats_shrunk | -0.0001 | 0 | 0 | 0 | 0 |
| 15 | 2023 | aura_features | champions | 1239 | 0.4982 | 0.1650 | 0.7603 | 0.0475 | 0.4972 | stats_shrunk | -0.0046 | -0.0045 | -0.0136 | 0.0053 | 232 |
| 15 | 2023 | aura_features | matchups | 1239 | 0.5014 | 0.1662 | 0.7482 | 0.0352 | 0.5010 | stats_shrunk | -0.0014 | -0.0013 | -0.0104 | 0.0084 | 560 |
| 15 | 2024 | gold | stats | 1106 | 0.5504 | 0.1867 | 0.7052 | 0.0301 | 0.5497 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | gold | stats_shrunk | 1106 | 0.5503 | 0.1867 | 0.7052 | 0.0301 | 0.5496 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 |
| 15 | 2024 | gold | champions | 1106 | 0.5502 | 0.1867 | 0.7125 | 0.0449 | 0.5503 | stats_shrunk | -0.0001 | -0.0001 | -0.0106 | 0.0107 | 207 |
| 15 | 2024 | gold | matchups | 1106 | 0.5473 | 0.1857 | 0.7170 | 0.0454 | 0.5484 | stats_shrunk | -0.0030 | -0.0030 | -0.0127 | 0.0069 | 522 |
| 15 | 2024 | aura_features | stats | 1106 | 0.5424 | 0.1833 | 0.7116 | 0.0420 | 0.5414 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | aura_features | stats_shrunk | 1106 | 0.5422 | 0.1833 | 0.7143 | 0.0404 | 0.5411 | stats_shrunk | -0.0001 | 0 | 0 | 0 | 0 |
| 15 | 2024 | aura_features | champions | 1106 | 0.5434 | 0.1836 | 0.7071 | 0.0488 | 0.5446 | stats_shrunk | 0.0011 | 0.0012 | -0.0089 | 0.0128 | 207 |
| 15 | 2024 | aura_features | matchups | 1106 | 0.5398 | 0.1825 | 0.7152 | 0.0380 | 0.5422 | stats_shrunk | -0.0026 | -0.0024 | -0.0122 | 0.0079 | 522 |
| 15 | 2025 | gold | stats | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5658 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | gold | stats_shrunk | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5663 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 |
| 15 | 2025 | gold | champions | 1309 | 0.5673 | 0.1935 | 0.6982 | 0.0301 | 0.5670 | stats_shrunk | 0.0014 | 0.0014 | -0.0089 | 0.0126 | 199 |
| 15 | 2025 | gold | matchups | 1309 | 0.5664 | 0.1930 | 0.6937 | 0.0422 | 0.5662 | stats_shrunk | 0.0006 | 0.0006 | -0.0110 | 0.0121 | 476 |
| 15 | 2025 | aura_features | stats | 1309 | 0.5609 | 0.1914 | 0.7021 | 0.0186 | 0.5606 | stats | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | aura_features | stats_shrunk | 1309 | 0.5606 | 0.1913 | 0.7044 | 0.0168 | 0.5604 | stats_shrunk | -0.0003 | 0 | 0 | 0 | 0 |
| 15 | 2025 | aura_features | champions | 1309 | 0.5563 | 0.1891 | 0.6982 | 0.0330 | 0.5569 | stats_shrunk | -0.0045 | -0.0042 | -0.0137 | 0.0059 | 199 |
| 15 | 2025 | aura_features | matchups | 1309 | 0.5571 | 0.1893 | 0.7051 | 0.0326 | 0.5583 | stats_shrunk | -0.0038 | -0.0035 | -0.0141 | 0.0073 | 476 |
| 20 | 2023 | gold | stats | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4425 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | gold | stats_shrunk | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4427 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 |
| 20 | 2023 | gold | champions | 1233 | 0.4371 | 0.1421 | 0.7948 | 0.0285 | 0.4370 | stats_shrunk | -0.0059 | -0.0059 | -0.0165 | 0.0050 | 232 |
| 20 | 2023 | gold | matchups | 1233 | 0.4403 | 0.1432 | 0.7940 | 0.0206 | 0.4407 | stats_shrunk | -0.0026 | -0.0026 | -0.0136 | 0.0085 | 558 |
| 20 | 2023 | aura_features | stats | 1233 | 0.4280 | 0.1375 | 0.8086 | 0.0334 | 0.4273 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | aura_features | stats_shrunk | 1233 | 0.4286 | 0.1377 | 0.8110 | 0.0328 | 0.4280 | stats_shrunk | 0.0007 | 0 | 0 | 0 | 0 |
| 20 | 2023 | aura_features | champions | 1233 | 0.4260 | 0.1378 | 0.8078 | 0.0258 | 0.4261 | stats_shrunk | -0.0020 | -0.0026 | -0.0133 | 0.0077 | 232 |
| 20 | 2023 | aura_features | matchups | 1233 | 0.4284 | 0.1386 | 0.8021 | 0.0240 | 0.4289 | stats_shrunk | 0.0004 | -0.0003 | -0.0106 | 0.0102 | 558 |
| 20 | 2024 | gold | stats | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | gold | stats_shrunk | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 |
| 20 | 2024 | gold | champions | 1106 | 0.4800 | 0.1591 | 0.7694 | 0.0367 | 0.4805 | stats_shrunk | 0.0000 | 0.0000 | -0.0107 | 0.0115 | 207 |
| 20 | 2024 | gold | matchups | 1106 | 0.4779 | 0.1583 | 0.7667 | 0.0188 | 0.4787 | stats_shrunk | -0.0020 | -0.0020 | -0.0120 | 0.0085 | 521 |
| 20 | 2024 | aura_features | stats | 1106 | 0.4733 | 0.1554 | 0.7694 | 0.0409 | 0.4716 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | aura_features | stats_shrunk | 1106 | 0.4722 | 0.1550 | 0.7694 | 0.0419 | 0.4704 | stats_shrunk | -0.0012 | 0 | 0 | 0 | 0 |
| 20 | 2024 | aura_features | champions | 1106 | 0.4744 | 0.1566 | 0.7613 | 0.0375 | 0.4756 | stats_shrunk | 0.0011 | 0.0022 | -0.0089 | 0.0142 | 207 |
| 20 | 2024 | aura_features | matchups | 1106 | 0.4717 | 0.1555 | 0.7649 | 0.0337 | 0.4735 | stats_shrunk | -0.0016 | -0.0005 | -0.0115 | 0.0109 | 521 |
| 20 | 2025 | gold | stats | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4676 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | gold | stats_shrunk | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4691 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 |
| 20 | 2025 | gold | champions | 1309 | 0.4688 | 0.1551 | 0.7670 | 0.0342 | 0.4664 | stats_shrunk | 0.0014 | 0.0014 | -0.0090 | 0.0122 | 199 |
| 20 | 2025 | gold | matchups | 1309 | 0.4690 | 0.1554 | 0.7632 | 0.0401 | 0.4665 | stats_shrunk | 0.0016 | 0.0016 | -0.0090 | 0.0127 | 474 |
| 20 | 2025 | aura_features | stats | 1309 | 0.4542 | 0.1504 | 0.7693 | 0.0251 | 0.4535 | stats | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | aura_features | stats_shrunk | 1309 | 0.4535 | 0.1501 | 0.7708 | 0.0203 | 0.4530 | stats_shrunk | -0.0007 | 0 | 0 | 0 | 0 |
| 20 | 2025 | aura_features | champions | 1309 | 0.4513 | 0.1487 | 0.7838 | 0.0304 | 0.4501 | stats_shrunk | -0.0029 | -0.0022 | -0.0108 | 0.0073 | 199 |
| 20 | 2025 | aura_features | matchups | 1309 | 0.4533 | 0.1495 | 0.7792 | 0.0304 | 0.4525 | stats_shrunk | -0.0009 | -0.0002 | -0.0098 | 0.0098 | 474 |

## Cohort coverage

| minute | year | snapshot_complete | draft_complete |
| --- | --- | --- | --- |
| 10 | 2014 | 739 | 739 |
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
| 15 | 2014 | 739 | 739 |
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
| 20 | 2014 | 739 | 739 |
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

## Next decision

Prefer a consistent log-loss improvement across years and minutes, rather than the best isolated row. An inconclusive or worse result is a reason to keep the simpler model. Exact champion pairs are sparse and the meta changes with patches; adding more interactions is not automatically an improvement. Any selected design must be frozen before collecting/evaluating new matches. There is no fresh untouched champion holdout in this report and no synchronized market-price or profitability evaluation.
