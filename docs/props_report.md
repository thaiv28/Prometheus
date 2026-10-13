# Prop projections: report

Generated 2026-10-12 by `scripts/evaluate_props.py`. Half-life and prior games per stat (kills 8 and 10, assists 16 and 10, deaths 32 and 3, cs 4 and 3), each the best on 2022-2023 (grid below); models fit on every league's games through 2023; scored on 64,050 player-maps of LCK, LPL, LEC, LCS and international events from 2024 on (6,405 games, 2,665 matches). Each projection uses the states before its series' first map. Lower is better; Δ is the model minus the other, with a 95% interval from a bootstrap over matches.

## One map

| Stat | Model log score | Model RPS | vs league-role avg | vs last 10 | vs season | vs player rate | vs no result term |
|---|---|---|---|---|---|---|---|
| kills | 2.000 | 1.201 | -0.025 (-0.028 to -0.021) | -0.055 (-0.059 to -0.052) | -0.031 (-0.034 to -0.027) | -0.017 (-0.020 to -0.014) | -0.013 (-0.016 to -0.011) |
| assists | 2.740 | 2.311 | -0.059 (-0.065 to -0.052) | -0.084 (-0.091 to -0.078) | -0.062 (-0.068 to -0.055) | -0.050 (-0.055 to -0.044) | -0.043 (-0.048 to -0.038) |
| deaths | 1.967 | 1.018 | -0.044 (-0.049 to -0.039) | -0.062 (-0.068 to -0.058) | -0.044 (-0.048 to -0.039) | -0.027 (-0.031 to -0.023) | -0.018 (-0.021 to -0.015) |
| cs | 5.186 | 25.756 | -0.027 (-0.030 to -0.024) | -0.025 (-0.029 to -0.021) | -0.012 (-0.015 to -0.008) | +0.001 (-0.001 to +0.003) | -0.003 (-0.004 to -0.003) |

Fantasy points (DraftKings Pick6 scoring: kill 3, assist 2, death −1, CS 0.02), CRPS:

| Model CRPS | vs league-role avg | vs last 10 | vs season | vs player rate |
|---|---|---|---|---|
| 7.292 | -0.458 (-0.515 to -0.396) | -0.577 (-0.632 to -0.521) | -0.417 (-0.469 to -0.362) | -0.369 (-0.420 to -0.316) |

## Calibration at a stand-in line (last-10 mean rounded down, plus a half)

| Stat | Model P(over) | Last-10 P(over) | Went over | Model ECE | Last-10 ECE |
|---|---|---|---|---|---|
| kills | 0.417 | 0.403 | 0.418 | 0.006 | 0.015 |
| assists | 0.437 | 0.424 | 0.451 | 0.016 | 0.027 |
| deaths | 0.443 | 0.431 | 0.470 | 0.027 | 0.039 |
| cs | 0.425 | 0.457 | 0.460 | 0.036 | 0.003 |

## Series totals

Bo3s in the training years went to a third map 35% of the time (the baseline's rate). Baseline: the last-10 mean per map, summed over the maps. Stand-in line: the baseline's mean rounded down plus a half.

| Maps | Stat | Player-series | Model log score | Δ log vs last 10 | Δ RPS vs last 10 | Model ECE | Last-10 ECE |
|---|---|---|---|---|---|---|---|
| 1-2 (Bo3) | kills | 16,741 | 2.441 | -0.113 (-0.123 to -0.104) | -0.184 (-0.202 to -0.169) | 0.004 | 0.029 |
| 1-2 (Bo3) | assists | 16,741 | 3.160 | -0.147 (-0.165 to -0.130) | -0.421 (-0.473 to -0.369) | 0.022 | 0.040 |
| 1-2 (Bo3) | deaths | 16,741 | 2.373 | -0.117 (-0.129 to -0.105) | -0.160 (-0.178 to -0.143) | 0.026 | 0.027 |
| 1-2 (Bo3) | cs | 16,741 | 5.613 | -0.042 (-0.052 to -0.033) | -2.047 (-2.444 to -1.642) | 0.061 | 0.018 |
| 1-2 (Bo3) | fantasy (CRPS) | 16,741 | 10.620 | -1.502 (-1.691 to -1.323) | | | |
| 1-2 (Bo5) | kills | 4,802 | 2.442 | -0.090 (-0.105 to -0.075) | -0.162 (-0.191 to -0.130) | 0.014 | 0.052 |
| 1-2 (Bo5) | assists | 4,802 | 3.190 | -0.099 (-0.126 to -0.074) | -0.296 (-0.391 to -0.205) | 0.048 | 0.016 |
| 1-2 (Bo5) | deaths | 4,802 | 2.382 | -0.145 (-0.171 to -0.121) | -0.192 (-0.226 to -0.160) | 0.044 | 0.098 |
| 1-2 (Bo5) | cs | 4,802 | 5.549 | -0.027 (-0.044 to -0.009) | -0.993 (-1.781 to -0.159) | 0.066 | 0.017 |
| 1-2 (Bo5) | fantasy (CRPS) | 4,802 | 10.707 | -1.215 (-1.576 to -0.860) | | | |
| 1-3 (Bo3, as played) | kills | 16,733 | 2.589 | -0.131 (-0.143 to -0.119) | -0.225 (-0.245 to -0.205) | 0.004 | 0.043 |
| 1-3 (Bo3, as played) | assists | 16,733 | 3.333 | -0.187 (-0.207 to -0.167) | -0.539 (-0.607 to -0.474) | 0.021 | 0.070 |
| 1-3 (Bo3, as played) | deaths | 16,733 | 2.539 | -0.150 (-0.164 to -0.137) | -0.214 (-0.235 to -0.193) | 0.017 | 0.043 |
| 1-3 (Bo3, as played) | cs | 16,733 | 6.140 | -0.044 (-0.054 to -0.034) | -3.139 (-3.890 to -2.406) | 0.017 | 0.019 |
| 1-3 (Bo3, as played) | fantasy (CRPS) | 16,733 | 12.988 | -1.821 (-2.053 to -1.590) | | | |
| 1-3 (Bo5) | kills | 4,792 | 2.699 | -0.146 (-0.164 to -0.127) | -0.315 (-0.357 to -0.270) | 0.019 | 0.039 |
| 1-3 (Bo5) | assists | 4,792 | 3.447 | -0.157 (-0.192 to -0.121) | -0.622 (-0.774 to -0.482) | 0.047 | 0.037 |
| 1-3 (Bo5) | deaths | 4,792 | 2.637 | -0.202 (-0.237 to -0.170) | -0.310 (-0.364 to -0.255) | 0.038 | 0.087 |
| 1-3 (Bo5) | cs | 4,792 | 5.784 | -0.048 (-0.069 to -0.027) | -2.499 (-3.685 to -1.248) | 0.054 | 0.008 |
| 1-3 (Bo5) | fantasy (CRPS) | 4,792 | 13.842 | -2.505 (-3.029 to -1.987) | | | |

## Tuning grid (2022-2023, one-map log score)

| halflife | prior_games | kills | assists | deaths | cs | sum |
|---|---|---|---|---|---|---|
| 4 | 3 | 1.926 | 2.6442 | 1.8982 | 5.1656 | 11.634 |
| 4 | 10 | 1.9258 | 2.6441 | 1.8981 | 5.1669 | 11.635 |
| 8 | 3 | 1.9257 | 2.6442 | 1.897 | 5.1674 | 11.6342 |
| 8 | 10 | 1.9256 | 2.6441 | 1.8971 | 5.1685 | 11.6352 |
| 16 | 3 | 1.9259 | 2.6441 | 1.8959 | 5.1726 | 11.6385 |
| 16 | 10 | 1.9259 | 2.644 | 1.896 | 5.1733 | 11.6392 |
| 32 | 3 | 1.9266 | 2.6443 | 1.8955 | 5.1785 | 11.6448 |
| 32 | 10 | 1.9266 | 2.6442 | 1.8955 | 5.179 | 11.6453 |

## Held out: per-stat settings against one half-life for every stat

Log score on 2024 on (models fit through 2023), one map and the series totals lines are set on. First row: the chosen settings; the others: the difference from them (below 0 beats them), with a 95% interval over matches.

| Half-life | kills | assists | deaths | cs | Bo3 1-2 kills | Bo3 1-2 assists | Bo5 1-3 kills | Bo5 1-3 assists |
|---|---|---|---|---|---|---|---|---|
| Chosen per stat | 1.9996 | 2.7403 | 1.9674 | 5.1860 | 2.4407 | 3.1604 | 2.6989 | 3.4471 |
| 4 for every stat | +0.0008 (+0.0005 to +0.0012) | +0.0009 (+0.0002 to +0.0018) | +0.0033 (+0.0023 to +0.0045) | +0.0000 (+0.0000 to +0.0000) | +0.0019 (+0.0011 to +0.0028) | +0.0012 (-0.0006 to +0.0030) | +0.0035 (+0.0014 to +0.0055) | +0.0029 (-0.0018 to +0.0076) |
| 8 for every stat | +0.0000 (-0.0001 to +0.0001) | +0.0002 (-0.0002 to +0.0006) | +0.0012 (+0.0004 to +0.0019) | +0.0041 (+0.0033 to +0.0049) | +0.0000 (-0.0002 to +0.0002) | -0.0001 (-0.0010 to +0.0008) | +0.0002 (-0.0002 to +0.0006) | +0.0003 (-0.0022 to +0.0029) |
| 16 for every stat | -0.0002 (-0.0006 to +0.0001) | +0.0001 (+0.0000 to +0.0003) | -0.0000 (-0.0004 to +0.0004) | +0.0124 (+0.0109 to +0.0140) | -0.0002 (-0.0011 to +0.0007) | -0.0001 (-0.0003 to +0.0002) | -0.0007 (-0.0026 to +0.0013) | +0.0015 (+0.0008 to +0.0022) |
| 32 for every stat | +0.0002 (-0.0004 to +0.0008) | +0.0008 (+0.0004 to +0.0012) | +0.0000 (+0.0000 to +0.0000) | +0.0217 (+0.0196 to +0.0239) | +0.0012 (-0.0004 to +0.0026) | +0.0013 (+0.0003 to +0.0023) | +0.0009 (-0.0025 to +0.0043) | +0.0055 (+0.0029 to +0.0081) |
| 64 for every stat | +0.0010 (+0.0002 to +0.0017) | +0.0020 (+0.0013 to +0.0026) | +0.0011 (+0.0008 to +0.0015) | +0.0291 (+0.0265 to +0.0317) | +0.0033 (+0.0012 to +0.0052) | +0.0038 (+0.0020 to +0.0056) | +0.0044 (-0.0000 to +0.0086) | +0.0112 (+0.0067 to +0.0156) |
