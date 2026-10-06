# Champion × game-state interaction experiment

Exploratory development only: 2023–2025 folds, with the already-viewed 2026 holdout excluded. Exact lane-matchup features are absent from every model in this experiment.

## Finding

No interaction variant improves pooled log loss over champion identities alone with a paired 95% interval below zero. Keep the simpler models as the benchmark. Every pooled interaction comparison has worse point-estimate log loss than its champion-only control.

## Richer model comparison

Log loss on the identical AURA-feature development cohorts; lower is better.

| minute | champions | gold_interactions | state_interactions |
| --- | --- | --- | --- |
| 10 | 0.6027 | 0.6060 | 0.6150 |
| 15 | 0.5327 | 0.5335 | 0.5409 |
| 20 | 0.4498 | 0.4518 | 0.4600 |

## Features

Start with the champion-by-role main effects. For each champion, add separate slopes when its team is ahead or behind in total gold. Thus the same gold gap may have different effects depending on the draft and which team is leading. The richer state variant additionally uses each champion's own-role gold, XP, CS and kill gaps. This is a piecewise-linear response with a fixed knot at zero; it is not an unrestricted team-composition or causal champion-value model.

Each interaction slope needs 20 training-game observations with a nonzero relevant gap. Champion main effects retain the prior 10-occurrence cutoff. Missing/unseen/rare slopes have zero learned adjustment and rely on the generic game-state and supported main effects. Gap scaling uses training standard deviation only, without centering, so zero stays an even state. Blue contributions are added and red contributions subtracted; swapping teams and negating all gaps negates the draft/state features. Separate minute models capture stage differences.

## Evaluation

Same complete-draft/snapshot games, leagues and chronological folds as the earlier champion experiment. Three years train, the next year calibrates, and the following year evaluates. No hyperparameter search; C=0.1 for all champion/interaction models. Retain original C=1 and same-C stats-only controls. The interaction comparison uses champion-only as its control, isolating the new slopes; delta_original also compares with the original stats-only model. Paired league/day-cluster bootstrap intervals use 2,000 resamples, seed 42, with no multiple-comparison correction. Raw log loss before calibration is retained. Older viewed folds remain development evidence; no fresh holdout or market edge is established.

## Pooled results

| minute | base | variant | n | log_loss | brier | accuracy | ece10 | control | delta_original | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | champions | 3654 | 0.6027 | 0.2080 | 0.6730 | 0.0143 | stats_shrunk | -0.0007 | -0.0006 | -0.0064 | 0.0050 |
| 10 | aura_features | gold_interactions | 3654 | 0.6060 | 0.2093 | 0.6678 | 0.0157 | champions | 0.0026 | 0.0033 | 0.0008 | 0.0060 |
| 10 | aura_features | state_interactions | 3654 | 0.6150 | 0.2133 | 0.6541 | 0.0161 | champions | 0.0116 | 0.0123 | 0.0071 | 0.0177 |
| 10 | aura_features | stats | 3654 | 0.6035 | 0.2084 | 0.6708 | 0.0115 | stats | 0 | 0 | 0 | 0 |
| 10 | aura_features | stats_shrunk | 3654 | 0.6033 | 0.2083 | 0.6708 | 0.0130 | stats_shrunk | -0.0001 | 0 | 0 | 0 |
| 10 | gold | champions | 3654 | 0.6065 | 0.2096 | 0.6667 | 0.0107 | stats_shrunk | 0.0012 | 0.0012 | -0.0042 | 0.0065 |
| 10 | gold | gold_interactions | 3654 | 0.6110 | 0.2115 | 0.6626 | 0.0177 | champions | 0.0057 | 0.0046 | 0.0020 | 0.0073 |
| 10 | gold | stats | 3654 | 0.6053 | 0.2090 | 0.6653 | 0.0138 | stats | 0 | 0 | 0 | 0 |
| 10 | gold | stats_shrunk | 3654 | 0.6053 | 0.2090 | 0.6653 | 0.0138 | stats_shrunk | 0.0000 | 0 | 0 | 0 |
| 15 | aura_features | champions | 3654 | 0.5327 | 0.1793 | 0.7219 | 0.0193 | stats_shrunk | -0.0028 | -0.0027 | -0.0085 | 0.0031 |
| 15 | aura_features | gold_interactions | 3654 | 0.5335 | 0.1794 | 0.7206 | 0.0233 | champions | -0.0021 | 0.0008 | -0.0015 | 0.0030 |
| 15 | aura_features | state_interactions | 3654 | 0.5409 | 0.1825 | 0.7173 | 0.0151 | champions | 0.0053 | 0.0082 | 0.0019 | 0.0142 |
| 15 | aura_features | stats | 3654 | 0.5356 | 0.1808 | 0.7209 | 0.0174 | stats | 0 | 0 | 0 | 0 |
| 15 | aura_features | stats_shrunk | 3654 | 0.5354 | 0.1807 | 0.7225 | 0.0164 | stats_shrunk | -0.0002 | 0 | 0 | 0 |
| 15 | gold | champions | 3654 | 0.5423 | 0.1830 | 0.7184 | 0.0135 | stats_shrunk | -0.0015 | -0.0015 | -0.0075 | 0.0043 |
| 15 | gold | gold_interactions | 3654 | 0.5443 | 0.1836 | 0.7198 | 0.0149 | champions | 0.0005 | 0.0020 | -0.0005 | 0.0043 |
| 15 | gold | stats | 3654 | 0.5438 | 0.1838 | 0.7184 | 0.0121 | stats | 0 | 0 | 0 | 0 |
| 15 | gold | stats_shrunk | 3654 | 0.5438 | 0.1838 | 0.7184 | 0.0121 | stats_shrunk | 0.0000 | 0 | 0 | 0 |
| 20 | aura_features | champions | 3648 | 0.4498 | 0.1474 | 0.7851 | 0.0101 | stats_shrunk | -0.0014 | -0.0010 | -0.0067 | 0.0049 |
| 20 | aura_features | gold_interactions | 3648 | 0.4518 | 0.1477 | 0.7884 | 0.0147 | champions | 0.0006 | 0.0020 | 0.0002 | 0.0040 |
| 20 | aura_features | state_interactions | 3648 | 0.4600 | 0.1511 | 0.7771 | 0.0148 | champions | 0.0089 | 0.0102 | 0.0048 | 0.0155 |
| 20 | aura_features | stats | 3648 | 0.4511 | 0.1475 | 0.7826 | 0.0119 | stats | 0 | 0 | 0 | 0 |
| 20 | aura_features | stats_shrunk | 3648 | 0.4508 | 0.1474 | 0.7840 | 0.0114 | stats_shrunk | -0.0004 | 0 | 0 | 0 |
| 20 | gold | champions | 3648 | 0.4615 | 0.1519 | 0.7771 | 0.0155 | stats_shrunk | -0.0015 | -0.0015 | -0.0073 | 0.0046 |
| 20 | gold | gold_interactions | 3648 | 0.4655 | 0.1529 | 0.7749 | 0.0079 | champions | 0.0025 | 0.0040 | 0.0020 | 0.0061 |
| 20 | gold | stats | 3648 | 0.4630 | 0.1523 | 0.7766 | 0.0166 | stats | 0 | 0 | 0 | 0 |
| 20 | gold | stats_shrunk | 3648 | 0.4629 | 0.1523 | 0.7766 | 0.0171 | stats_shrunk | -0.0000 | 0 | 0 | 0 |

## Annual results

| minute | year | base | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_original | delta_base | delta_low | delta_high | draft_features | interaction_features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2023 | gold | stats | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5899 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | gold | stats_shrunk | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5897 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | gold | champions | 1239 | 0.5877 | 0.2009 | 0.6877 | 0.0418 | 0.5909 | stats_shrunk | -0.0018 | -0.0018 | -0.0112 | 0.0079 | 232 | 0 |
| 10 | 2023 | gold | gold_interactions | 1239 | 0.5939 | 0.2029 | 0.6820 | 0.0460 | 0.6059 | champions | 0.0044 | 0.0062 | 0.0015 | 0.0110 | 548 | 316 |
| 10 | 2023 | aura_features | stats | 1239 | 0.5866 | 0.2004 | 0.6949 | 0.0236 | 0.5867 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | aura_features | stats_shrunk | 1239 | 0.5870 | 0.2006 | 0.6949 | 0.0272 | 0.5871 | stats_shrunk | 0.0004 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2023 | aura_features | champions | 1239 | 0.5851 | 0.1998 | 0.6917 | 0.0244 | 0.5888 | stats_shrunk | -0.0015 | -0.0019 | -0.0118 | 0.0082 | 232 | 0 |
| 10 | 2023 | aura_features | gold_interactions | 1239 | 0.5889 | 0.2009 | 0.6836 | 0.0425 | 0.6036 | champions | 0.0023 | 0.0038 | -0.0009 | 0.0085 | 548 | 316 |
| 10 | 2023 | aura_features | state_interactions | 1239 | 0.5970 | 0.2040 | 0.6868 | 0.0314 | 0.6276 | champions | 0.0104 | 0.0119 | 0.0041 | 0.0197 | 1702 | 1470 |
| 10 | 2024 | gold | stats | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6104 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | gold | stats_shrunk | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6101 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | gold | champions | 1106 | 0.6096 | 0.2109 | 0.6637 | 0.0267 | 0.6142 | stats_shrunk | 0.0003 | 0.0003 | -0.0082 | 0.0091 | 207 | 0 |
| 10 | 2024 | gold | gold_interactions | 1106 | 0.6124 | 0.2122 | 0.6618 | 0.0229 | 0.6211 | champions | 0.0031 | 0.0028 | -0.0020 | 0.0074 | 508 | 301 |
| 10 | 2024 | aura_features | stats | 1106 | 0.6062 | 0.2098 | 0.6646 | 0.0252 | 0.6072 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | aura_features | stats_shrunk | 1106 | 0.6058 | 0.2096 | 0.6646 | 0.0223 | 0.6067 | stats_shrunk | -0.0004 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2024 | aura_features | champions | 1106 | 0.6052 | 0.2090 | 0.6618 | 0.0276 | 0.6106 | stats_shrunk | -0.0009 | -0.0006 | -0.0092 | 0.0089 | 207 | 0 |
| 10 | 2024 | aura_features | gold_interactions | 1106 | 0.6075 | 0.2101 | 0.6609 | 0.0234 | 0.6188 | champions | 0.0014 | 0.0023 | -0.0023 | 0.0066 | 508 | 301 |
| 10 | 2024 | aura_features | state_interactions | 1106 | 0.6123 | 0.2125 | 0.6528 | 0.0302 | 0.6381 | champions | 0.0061 | 0.0071 | -0.0046 | 0.0181 | 1600 | 1393 |
| 10 | 2025 | gold | stats | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6163 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | gold | stats_shrunk | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6164 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | gold | champions | 1309 | 0.6216 | 0.2168 | 0.6494 | 0.0245 | 0.6216 | stats_shrunk | 0.0048 | 0.0048 | -0.0045 | 0.0147 | 199 | 0 |
| 10 | 2025 | gold | gold_interactions | 1309 | 0.6261 | 0.2189 | 0.6448 | 0.0360 | 0.6249 | champions | 0.0093 | 0.0045 | 0.0002 | 0.0087 | 485 | 286 |
| 10 | 2025 | aura_features | stats | 1309 | 0.6171 | 0.2147 | 0.6532 | 0.0307 | 0.6169 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | aura_features | stats_shrunk | 1309 | 0.6167 | 0.2145 | 0.6532 | 0.0309 | 0.6165 | stats_shrunk | -0.0004 | 0 | 0 | 0 | 0 | 0 |
| 10 | 2025 | aura_features | champions | 1309 | 0.6173 | 0.2148 | 0.6646 | 0.0312 | 0.6181 | stats_shrunk | 0.0002 | 0.0006 | -0.0086 | 0.0103 | 199 | 0 |
| 10 | 2025 | aura_features | gold_interactions | 1309 | 0.6210 | 0.2167 | 0.6585 | 0.0372 | 0.6217 | champions | 0.0039 | 0.0037 | -0.0005 | 0.0079 | 485 | 286 |
| 10 | 2025 | aura_features | state_interactions | 1309 | 0.6345 | 0.2227 | 0.6241 | 0.0228 | 0.6484 | champions | 0.0174 | 0.0172 | 0.0089 | 0.0254 | 1525 | 1326 |
| 15 | 2023 | gold | stats | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5135 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | gold | stats_shrunk | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5137 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | gold | champions | 1239 | 0.5087 | 0.1687 | 0.7450 | 0.0328 | 0.5076 | stats_shrunk | -0.0059 | -0.0059 | -0.0151 | 0.0039 | 232 | 0 |
| 15 | 2023 | gold | gold_interactions | 1239 | 0.5103 | 0.1687 | 0.7506 | 0.0251 | 0.5111 | champions | -0.0043 | 0.0016 | -0.0020 | 0.0053 | 545 | 313 |
| 15 | 2023 | aura_features | stats | 1239 | 0.5028 | 0.1673 | 0.7490 | 0.0319 | 0.5017 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | aura_features | stats_shrunk | 1239 | 0.5027 | 0.1673 | 0.7490 | 0.0320 | 0.5016 | stats_shrunk | -0.0001 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2023 | aura_features | champions | 1239 | 0.4982 | 0.1650 | 0.7603 | 0.0475 | 0.4972 | stats_shrunk | -0.0046 | -0.0045 | -0.0136 | 0.0053 | 232 | 0 |
| 15 | 2023 | aura_features | gold_interactions | 1239 | 0.4989 | 0.1648 | 0.7554 | 0.0317 | 0.5012 | champions | -0.0039 | 0.0007 | -0.0027 | 0.0041 | 545 | 313 |
| 15 | 2023 | aura_features | state_interactions | 1239 | 0.5097 | 0.1687 | 0.7554 | 0.0271 | 0.5234 | champions | 0.0069 | 0.0115 | 0.0036 | 0.0198 | 1741 | 1509 |
| 15 | 2024 | gold | stats | 1106 | 0.5504 | 0.1867 | 0.7052 | 0.0301 | 0.5497 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | gold | stats_shrunk | 1106 | 0.5503 | 0.1867 | 0.7052 | 0.0301 | 0.5496 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | gold | champions | 1106 | 0.5502 | 0.1867 | 0.7125 | 0.0449 | 0.5503 | stats_shrunk | -0.0001 | -0.0001 | -0.0106 | 0.0107 | 207 | 0 |
| 15 | 2024 | gold | gold_interactions | 1106 | 0.5510 | 0.1871 | 0.7152 | 0.0487 | 0.5531 | champions | 0.0007 | 0.0008 | -0.0036 | 0.0050 | 508 | 301 |
| 15 | 2024 | aura_features | stats | 1106 | 0.5424 | 0.1833 | 0.7116 | 0.0420 | 0.5414 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | aura_features | stats_shrunk | 1106 | 0.5422 | 0.1833 | 0.7143 | 0.0404 | 0.5411 | stats_shrunk | -0.0001 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2024 | aura_features | champions | 1106 | 0.5434 | 0.1836 | 0.7071 | 0.0488 | 0.5446 | stats_shrunk | 0.0011 | 0.0012 | -0.0089 | 0.0128 | 207 | 0 |
| 15 | 2024 | aura_features | gold_interactions | 1106 | 0.5423 | 0.1834 | 0.7080 | 0.0453 | 0.5470 | champions | -0.0001 | -0.0011 | -0.0054 | 0.0029 | 508 | 301 |
| 15 | 2024 | aura_features | state_interactions | 1106 | 0.5454 | 0.1852 | 0.7170 | 0.0447 | 0.5610 | champions | 0.0030 | 0.0019 | -0.0116 | 0.0147 | 1630 | 1423 |
| 15 | 2025 | gold | stats | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5658 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | gold | stats_shrunk | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5663 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | gold | champions | 1309 | 0.5673 | 0.1935 | 0.6982 | 0.0301 | 0.5670 | stats_shrunk | 0.0014 | 0.0014 | -0.0089 | 0.0126 | 199 | 0 |
| 15 | 2025 | gold | gold_interactions | 1309 | 0.5707 | 0.1947 | 0.6944 | 0.0287 | 0.5701 | champions | 0.0048 | 0.0033 | -0.0007 | 0.0076 | 485 | 286 |
| 15 | 2025 | aura_features | stats | 1309 | 0.5609 | 0.1914 | 0.7021 | 0.0186 | 0.5606 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | aura_features | stats_shrunk | 1309 | 0.5606 | 0.1913 | 0.7044 | 0.0168 | 0.5604 | stats_shrunk | -0.0003 | 0 | 0 | 0 | 0 | 0 |
| 15 | 2025 | aura_features | champions | 1309 | 0.5563 | 0.1891 | 0.6982 | 0.0330 | 0.5569 | stats_shrunk | -0.0045 | -0.0042 | -0.0137 | 0.0059 | 199 | 0 |
| 15 | 2025 | aura_features | gold_interactions | 1309 | 0.5588 | 0.1899 | 0.6982 | 0.0415 | 0.5594 | champions | -0.0020 | 0.0025 | -0.0013 | 0.0065 | 485 | 286 |
| 15 | 2025 | aura_features | state_interactions | 1309 | 0.5666 | 0.1932 | 0.6814 | 0.0481 | 0.5706 | champions | 0.0057 | 0.0103 | 0.0010 | 0.0195 | 1545 | 1346 |
| 20 | 2023 | gold | stats | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4425 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | gold | stats_shrunk | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4427 | stats_shrunk | 0.0000 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | gold | champions | 1233 | 0.4371 | 0.1421 | 0.7948 | 0.0285 | 0.4370 | stats_shrunk | -0.0059 | -0.0059 | -0.0165 | 0.0050 | 232 | 0 |
| 20 | 2023 | gold | gold_interactions | 1233 | 0.4409 | 0.1426 | 0.7932 | 0.0267 | 0.4413 | champions | -0.0020 | 0.0038 | -0.0001 | 0.0082 | 546 | 314 |
| 20 | 2023 | aura_features | stats | 1233 | 0.4280 | 0.1375 | 0.8086 | 0.0334 | 0.4273 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | aura_features | stats_shrunk | 1233 | 0.4286 | 0.1377 | 0.8110 | 0.0328 | 0.4280 | stats_shrunk | 0.0007 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2023 | aura_features | champions | 1233 | 0.4260 | 0.1378 | 0.8078 | 0.0258 | 0.4261 | stats_shrunk | -0.0020 | -0.0026 | -0.0133 | 0.0077 | 232 | 0 |
| 20 | 2023 | aura_features | gold_interactions | 1233 | 0.4286 | 0.1376 | 0.8078 | 0.0234 | 0.4304 | champions | 0.0006 | 0.0026 | -0.0011 | 0.0065 | 546 | 314 |
| 20 | 2023 | aura_features | state_interactions | 1233 | 0.4376 | 0.1411 | 0.8029 | 0.0243 | 0.4475 | champions | 0.0096 | 0.0116 | 0.0024 | 0.0210 | 1744 | 1512 |
| 20 | 2024 | gold | stats | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | gold | stats_shrunk | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | gold | champions | 1106 | 0.4800 | 0.1591 | 0.7694 | 0.0367 | 0.4805 | stats_shrunk | 0.0000 | 0.0000 | -0.0107 | 0.0115 | 207 | 0 |
| 20 | 2024 | gold | gold_interactions | 1106 | 0.4847 | 0.1602 | 0.7667 | 0.0299 | 0.4861 | champions | 0.0047 | 0.0047 | 0.0009 | 0.0085 | 511 | 304 |
| 20 | 2024 | aura_features | stats | 1106 | 0.4733 | 0.1554 | 0.7694 | 0.0409 | 0.4716 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | aura_features | stats_shrunk | 1106 | 0.4722 | 0.1550 | 0.7694 | 0.0419 | 0.4704 | stats_shrunk | -0.0012 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2024 | aura_features | champions | 1106 | 0.4744 | 0.1566 | 0.7613 | 0.0375 | 0.4756 | stats_shrunk | 0.0011 | 0.0022 | -0.0089 | 0.0142 | 207 | 0 |
| 20 | 2024 | aura_features | gold_interactions | 1106 | 0.4764 | 0.1570 | 0.7649 | 0.0338 | 0.4807 | champions | 0.0031 | 0.0020 | -0.0014 | 0.0055 | 511 | 304 |
| 20 | 2024 | aura_features | state_interactions | 1106 | 0.4840 | 0.1611 | 0.7577 | 0.0274 | 0.4982 | champions | 0.0107 | 0.0096 | -0.0009 | 0.0206 | 1650 | 1443 |
| 20 | 2025 | gold | stats | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4676 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | gold | stats_shrunk | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4691 | stats_shrunk | -0.0000 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | gold | champions | 1309 | 0.4688 | 0.1551 | 0.7670 | 0.0342 | 0.4664 | stats_shrunk | 0.0014 | 0.0014 | -0.0090 | 0.0122 | 199 | 0 |
| 20 | 2025 | gold | gold_interactions | 1309 | 0.4724 | 0.1564 | 0.7647 | 0.0370 | 0.4698 | champions | 0.0050 | 0.0036 | 0.0007 | 0.0064 | 485 | 286 |
| 20 | 2025 | aura_features | stats | 1309 | 0.4542 | 0.1504 | 0.7693 | 0.0251 | 0.4535 | stats | 0 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | aura_features | stats_shrunk | 1309 | 0.4535 | 0.1501 | 0.7708 | 0.0203 | 0.4530 | stats_shrunk | -0.0007 | 0 | 0 | 0 | 0 | 0 |
| 20 | 2025 | aura_features | champions | 1309 | 0.4513 | 0.1487 | 0.7838 | 0.0304 | 0.4501 | stats_shrunk | -0.0029 | -0.0022 | -0.0108 | 0.0073 | 199 | 0 |
| 20 | 2025 | aura_features | gold_interactions | 1309 | 0.4528 | 0.1493 | 0.7899 | 0.0336 | 0.4513 | champions | -0.0014 | 0.0015 | -0.0010 | 0.0040 | 485 | 286 |
| 20 | 2025 | aura_features | state_interactions | 1309 | 0.4609 | 0.1522 | 0.7693 | 0.0353 | 0.4612 | champions | 0.0066 | 0.0095 | 0.0013 | 0.0172 | 1573 | 1374 |

## Coverage

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

## Limits and next decision

Additional slopes can overfit sparse champions and stale patch relationships. Team gold is available from scoreboards, but role gold/XP requires a richer live source. No player identity, team-strength prior, patch-specific fit, arbitrary draft synergy or market-price data is added. Require a consistent gain before freezing a candidate for newly collected matches; keep an inconclusive design out of production.
