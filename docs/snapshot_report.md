# Snapshot audit and chronological win-probability baseline

Research only; estimates current-map outcomes, not series outcomes or trading profitability.

## Findings: 2026 calendar holdout

- 10 minutes: gold alone 65.1% accuracy / 0.6239 log loss; AURA features 65.6% / 0.6178. Rich-minus-gold log loss -0.0061 (95% interval -0.0122 to -0.0001).
- 15 minutes: gold alone 71.3% accuracy / 0.5620 log loss; AURA features 71.3% / 0.5563. Rich-minus-gold log loss -0.0057 (95% interval -0.0119 to +0.0006).
- 20 minutes: gold alone 75.8% accuracy / 0.4982 log loss; AURA features 76.7% / 0.4859. Rich-minus-gold log loss -0.0123 (95% interval -0.0218 to -0.0029).

These are retrospective prediction benchmarks, not a demonstrated market edge. The complete-case cohort and league mix can change between years; consult league scores below. Calibration fitted on the preceding year may worsen next-year log loss; both raw and calibrated scores are retained. Do not choose a recalibration method using this final holdout.

## Method

Raw CSVs are audited before database filtering. A complete game has ten unique side/role pairs, consistent league/timestamp/duration, two teams and exactly one winner. Missing or negative/nonfinite snapshot values are unavailable, never imputed. Gaps are blue minus red. Calendar year comes from the match timestamp, not the season label. A game must last strictly beyond the target minute.

Each test year uses the three years ending two years earlier for training, and the immediately preceding year for sigmoid calibration. Example: 2026 uses 2022–2024 training and 2025 calibration. The scaler and logistic regression (C=1) see training only. The 2023–2025 folds are development diagnostics; 2026 is the final calendar holdout, scored with fixed features/settings. No tuning follows these holdout results. 2026 is partial through the last locally downloaded game.

All models share the complete AURA-feature cohort for paired comparisons, restricted to LCK, LPL, LEC, LCS, Worlds, MSI, EWC, FST. One row per game per minute; each minute has its own model. Whole calendar years separate training/calibration/test. Explicit series identifiers are unavailable; a series crossing New Year cannot be guaranteed to stay in one split. Intervals resample league/day clusters, an approximate series grouping, 2,000 times with seed 42. ECE uses ten equal-width bins and is descriptive.

## Source inventory

13 files; 0 player rows missing game IDs; 0 game IDs repeated across files excluded entirely. Latest evaluated match timestamp: 2026-09-27T22:30:06+00:00.

File hashes, full coverage, fitted parameters, per-game predictions, calibration bins, and league-specific scores are in `data/snapshot_audit` (gitignored).

## Recent coverage

Counts are games, not player rows. Reached includes malformed games; invalid overlaps other columns. Gold requires all ten players’ gold; AURA requires all six stats for all ten. Ended games are excluded from the minute's prediction population, not treated as missing live observations.

| year | league | minute | games | ended_by_minute | invalid_roster_or_metadata | reached_minute | gold | scoreboard | aura_features |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2024 | EWC | 10 | 19 | 0 | 0 | 19 | 19 | 19 | 19 |
| 2024 | LCK | 10 | 482 | 0 | 0 | 482 | 482 | 482 | 482 |
| 2024 | LCS | 10 | 192 | 0 | 0 | 192 | 192 | 192 | 192 |
| 2024 | LEC | 10 | 294 | 0 | 0 | 294 | 294 | 294 | 294 |
| 2024 | LPL | 10 | 717 | 0 | 0 | 717 | 0 | 0 | 0 |
| 2024 | MSI | 10 | 78 | 0 | 0 | 78 | 0 | 0 | 0 |
| 2024 | Worlds | 10 | 132 | 0 | 0 | 132 | 119 | 119 | 119 |
| 2025 | EWC | 10 | 33 | 0 | 0 | 33 | 33 | 33 | 33 |
| 2025 | FST | 10 | 35 | 0 | 0 | 35 | 35 | 35 | 35 |
| 2025 | LCK | 10 | 555 | 0 | 0 | 555 | 555 | 555 | 555 |
| 2025 | LCS | 10 | 214 | 0 | 0 | 214 | 214 | 214 | 214 |
| 2025 | LEC | 10 | 308 | 0 | 0 | 308 | 308 | 308 | 308 |
| 2025 | LPL | 10 | 805 | 0 | 0 | 805 | 0 | 0 | 0 |
| 2025 | MSI | 10 | 80 | 0 | 0 | 80 | 80 | 80 | 80 |
| 2025 | Worlds | 10 | 96 | 0 | 0 | 96 | 84 | 84 | 84 |
| 2026 | EWC | 10 | 232 | 0 | 0 | 232 | 232 | 232 | 232 |
| 2026 | FST | 10 | 45 | 0 | 0 | 45 | 45 | 45 | 45 |
| 2026 | LCK | 10 | 502 | 0 | 0 | 502 | 502 | 502 | 502 |
| 2026 | LCS | 10 | 252 | 0 | 0 | 252 | 252 | 252 | 252 |
| 2026 | LEC | 10 | 383 | 0 | 0 | 383 | 382 | 382 | 382 |
| 2026 | LPL | 10 | 674 | 0 | 0 | 674 | 541 | 541 | 541 |
| 2026 | MSI | 10 | 71 | 0 | 0 | 71 | 71 | 71 | 71 |
| 2026 | Worlds | 10 | 12 | 0 | 0 | 12 | 12 | 12 | 12 |
| 2024 | EWC | 15 | 19 | 0 | 0 | 19 | 19 | 19 | 19 |
| 2024 | LCK | 15 | 482 | 0 | 0 | 482 | 482 | 482 | 482 |
| 2024 | LCS | 15 | 192 | 0 | 0 | 192 | 192 | 192 | 192 |
| 2024 | LEC | 15 | 294 | 0 | 0 | 294 | 294 | 294 | 294 |
| 2024 | LPL | 15 | 717 | 0 | 0 | 717 | 0 | 0 | 0 |
| 2024 | MSI | 15 | 78 | 0 | 0 | 78 | 0 | 0 | 0 |
| 2024 | Worlds | 15 | 132 | 0 | 0 | 132 | 119 | 119 | 119 |
| 2025 | EWC | 15 | 33 | 0 | 0 | 33 | 33 | 33 | 33 |
| 2025 | FST | 15 | 35 | 0 | 0 | 35 | 35 | 35 | 35 |
| 2025 | LCK | 15 | 555 | 0 | 0 | 555 | 555 | 555 | 555 |
| 2025 | LCS | 15 | 214 | 0 | 0 | 214 | 214 | 214 | 214 |
| 2025 | LEC | 15 | 308 | 0 | 0 | 308 | 308 | 308 | 308 |
| 2025 | LPL | 15 | 805 | 0 | 0 | 805 | 0 | 0 | 0 |
| 2025 | MSI | 15 | 80 | 0 | 0 | 80 | 80 | 80 | 80 |
| 2025 | Worlds | 15 | 96 | 0 | 0 | 96 | 84 | 84 | 84 |
| 2026 | EWC | 15 | 232 | 0 | 0 | 232 | 232 | 232 | 232 |
| 2026 | FST | 15 | 45 | 0 | 0 | 45 | 45 | 45 | 45 |
| 2026 | LCK | 15 | 502 | 0 | 0 | 502 | 502 | 502 | 502 |
| 2026 | LCS | 15 | 252 | 0 | 0 | 252 | 252 | 252 | 252 |
| 2026 | LEC | 15 | 383 | 0 | 0 | 383 | 382 | 382 | 382 |
| 2026 | LPL | 15 | 674 | 0 | 0 | 674 | 542 | 542 | 542 |
| 2026 | MSI | 15 | 71 | 0 | 0 | 71 | 71 | 71 | 71 |
| 2026 | Worlds | 15 | 12 | 0 | 0 | 12 | 12 | 12 | 12 |
| 2024 | EWC | 20 | 19 | 0 | 0 | 19 | 19 | 19 | 19 |
| 2024 | LCK | 20 | 482 | 0 | 0 | 482 | 482 | 482 | 482 |
| 2024 | LCS | 20 | 192 | 0 | 0 | 192 | 192 | 192 | 192 |
| 2024 | LEC | 20 | 294 | 0 | 0 | 294 | 294 | 294 | 294 |
| 2024 | LPL | 20 | 717 | 0 | 0 | 717 | 0 | 0 | 0 |
| 2024 | MSI | 20 | 78 | 1 | 0 | 77 | 0 | 0 | 0 |
| 2024 | Worlds | 20 | 132 | 0 | 0 | 132 | 119 | 119 | 119 |
| 2025 | EWC | 20 | 33 | 0 | 0 | 33 | 33 | 33 | 33 |
| 2025 | FST | 20 | 35 | 0 | 0 | 35 | 35 | 35 | 35 |
| 2025 | LCK | 20 | 555 | 0 | 0 | 555 | 555 | 555 | 555 |
| 2025 | LCS | 20 | 214 | 0 | 0 | 214 | 214 | 214 | 214 |
| 2025 | LEC | 20 | 308 | 0 | 0 | 308 | 308 | 308 | 308 |
| 2025 | LPL | 20 | 805 | 0 | 0 | 805 | 0 | 0 | 0 |
| 2025 | MSI | 20 | 80 | 0 | 0 | 80 | 80 | 80 | 80 |
| 2025 | Worlds | 20 | 96 | 0 | 0 | 96 | 84 | 84 | 84 |
| 2026 | EWC | 20 | 232 | 1 | 0 | 231 | 231 | 231 | 231 |
| 2026 | FST | 20 | 45 | 0 | 0 | 45 | 45 | 45 | 45 |
| 2026 | LCK | 20 | 502 | 0 | 0 | 502 | 502 | 502 | 502 |
| 2026 | LCS | 20 | 252 | 0 | 0 | 252 | 252 | 252 | 252 |
| 2026 | LEC | 20 | 383 | 0 | 0 | 383 | 381 | 381 | 381 |
| 2026 | LPL | 20 | 674 | 1 | 0 | 673 | 541 | 541 | 541 |
| 2026 | MSI | 20 | 71 | 0 | 0 | 71 | 71 | 71 | 71 |
| 2026 | Worlds | 20 | 12 | 0 | 0 | 12 | 12 | 12 | 12 |

### Draft and identity coverage at 10 minutes

| year | league | games | complete_champions | complete_player_ids | complete_player_names |
| --- | --- | --- | --- | --- | --- |
| 2024 | EWC | 19 | 19 | 19 | 19 |
| 2024 | LCK | 482 | 482 | 482 | 482 |
| 2024 | LCS | 192 | 192 | 192 | 192 |
| 2024 | LEC | 294 | 294 | 294 | 294 |
| 2024 | LPL | 717 | 717 | 717 | 717 |
| 2024 | MSI | 78 | 78 | 78 | 78 |
| 2024 | Worlds | 132 | 132 | 132 | 132 |
| 2025 | EWC | 33 | 33 | 33 | 33 |
| 2025 | FST | 35 | 35 | 35 | 35 |
| 2025 | LCK | 555 | 555 | 555 | 555 |
| 2025 | LCS | 214 | 214 | 214 | 214 |
| 2025 | LEC | 308 | 308 | 308 | 308 |
| 2025 | LPL | 805 | 805 | 805 | 805 |
| 2025 | MSI | 80 | 80 | 80 | 80 |
| 2025 | Worlds | 96 | 96 | 96 | 96 |
| 2026 | EWC | 232 | 232 | 232 | 232 |
| 2026 | FST | 45 | 45 | 45 | 45 |
| 2026 | LCK | 502 | 502 | 502 | 502 |
| 2026 | LCS | 252 | 252 | 252 | 252 |
| 2026 | LEC | 383 | 383 | 383 | 383 |
| 2026 | LPL | 674 | 674 | 674 | 674 |
| 2026 | MSI | 71 | 71 | 71 | 71 |
| 2026 | Worlds | 12 | 12 | 12 | 12 |

## Chronological benchmark

Lower log loss/Brier is better. Negative delta means improvement over calibrated gold alone; delta_low/high are paired 95% cluster-bootstrap intervals. Raw log loss is before calibration.

| year | minute | model | train_n | calibration_n | n | log_loss | raw_log_loss | brier | accuracy | ece10 | delta_gold | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 2023 | 10 | gold | 5274 | 1237 | 1239 | 0.5896 | 0.5899 | 0.2013 | 0.6812 | 0.0360 | 0 | 0 | 0 |
| 2023 | 10 | scoreboard | 5274 | 1237 | 1239 | 0.5902 | 0.5905 | 0.2015 | 0.6836 | 0.0323 | 0.0006 | 0.0001 | 0.0011 |
| 2023 | 10 | lanes_no_xp | 5274 | 1237 | 1239 | 0.5876 | 0.5881 | 0.2006 | 0.7006 | 0.0355 | -0.0020 | -0.0088 | 0.0052 |
| 2023 | 10 | aura_features | 5274 | 1237 | 1239 | 0.5866 | 0.5867 | 0.2004 | 0.6949 | 0.0236 | -0.0030 | -0.0113 | 0.0053 |
| 2024 | 10 | gold | 4705 | 1239 | 1106 | 0.6093 | 0.6104 | 0.2111 | 0.6609 | 0.0362 | 0 | 0 | 0 |
| 2024 | 10 | scoreboard | 4705 | 1239 | 1106 | 0.6096 | 0.6108 | 0.2113 | 0.6637 | 0.0334 | 0.0004 | -0.0005 | 0.0012 |
| 2024 | 10 | lanes_no_xp | 4705 | 1239 | 1106 | 0.6082 | 0.6099 | 0.2107 | 0.6664 | 0.0250 | -0.0011 | -0.0059 | 0.0038 |
| 2024 | 10 | aura_features | 4705 | 1239 | 1106 | 0.6062 | 0.6072 | 0.2098 | 0.6646 | 0.0252 | -0.0031 | -0.0085 | 0.0024 |
| 2025 | 10 | gold | 4109 | 1106 | 1309 | 0.6168 | 0.6163 | 0.2146 | 0.6539 | 0.0171 | 0 | 0 | 0 |
| 2025 | 10 | scoreboard | 4109 | 1106 | 1309 | 0.6169 | 0.6164 | 0.2146 | 0.6539 | 0.0170 | 0.0001 | 0.0000 | 0.0002 |
| 2025 | 10 | lanes_no_xp | 4109 | 1106 | 1309 | 0.6159 | 0.6154 | 0.2141 | 0.6593 | 0.0263 | -0.0009 | -0.0063 | 0.0049 |
| 2025 | 10 | aura_features | 4109 | 1106 | 1309 | 0.6171 | 0.6169 | 0.2147 | 0.6532 | 0.0307 | 0.0003 | -0.0059 | 0.0070 |
| 2026 | 10 | gold | 3582 | 1309 | 2037 | 0.6239 | 0.6213 | 0.2170 | 0.6514 | 0.0339 | 0 | 0 | 0 |
| 2026 | 10 | scoreboard | 3582 | 1309 | 2037 | 0.6236 | 0.6204 | 0.2168 | 0.6519 | 0.0361 | -0.0003 | -0.0012 | 0.0007 |
| 2026 | 10 | lanes_no_xp | 3582 | 1309 | 2037 | 0.6197 | 0.6202 | 0.2155 | 0.6549 | 0.0317 | -0.0042 | -0.0099 | 0.0015 |
| 2026 | 10 | aura_features | 3582 | 1309 | 2037 | 0.6178 | 0.6185 | 0.2147 | 0.6559 | 0.0292 | -0.0061 | -0.0122 | -0.0001 |
| 2023 | 15 | gold | 5272 | 1237 | 1239 | 0.5146 | 0.5135 | 0.1714 | 0.7522 | 0.0309 | 0 | 0 | 0 |
| 2023 | 15 | scoreboard | 5272 | 1237 | 1239 | 0.5134 | 0.5126 | 0.1710 | 0.7458 | 0.0229 | -0.0013 | -0.0052 | 0.0027 |
| 2023 | 15 | lanes_no_xp | 5272 | 1237 | 1239 | 0.5093 | 0.5088 | 0.1695 | 0.7417 | 0.0256 | -0.0054 | -0.0150 | 0.0040 |
| 2023 | 15 | aura_features | 5272 | 1237 | 1239 | 0.5028 | 0.5017 | 0.1673 | 0.7490 | 0.0319 | -0.0118 | -0.0220 | -0.0015 |
| 2024 | 15 | gold | 4703 | 1239 | 1106 | 0.5504 | 0.5497 | 0.1867 | 0.7052 | 0.0301 | 0 | 0 | 0 |
| 2024 | 15 | scoreboard | 4703 | 1239 | 1106 | 0.5496 | 0.5491 | 0.1866 | 0.6971 | 0.0402 | -0.0008 | -0.0060 | 0.0046 |
| 2024 | 15 | lanes_no_xp | 4703 | 1239 | 1106 | 0.5473 | 0.5472 | 0.1856 | 0.7080 | 0.0385 | -0.0031 | -0.0105 | 0.0045 |
| 2024 | 15 | aura_features | 4703 | 1239 | 1106 | 0.5424 | 0.5414 | 0.1833 | 0.7116 | 0.0420 | -0.0080 | -0.0168 | 0.0007 |
| 2025 | 15 | gold | 4109 | 1106 | 1309 | 0.5659 | 0.5658 | 0.1930 | 0.6975 | 0.0183 | 0 | 0 | 0 |
| 2025 | 15 | scoreboard | 4109 | 1106 | 1309 | 0.5698 | 0.5698 | 0.1949 | 0.6990 | 0.0191 | 0.0039 | 0.0002 | 0.0076 |
| 2025 | 15 | lanes_no_xp | 4109 | 1106 | 1309 | 0.5600 | 0.5594 | 0.1909 | 0.7044 | 0.0234 | -0.0059 | -0.0117 | -0.0004 |
| 2025 | 15 | aura_features | 4109 | 1106 | 1309 | 0.5609 | 0.5606 | 0.1914 | 0.7021 | 0.0186 | -0.0050 | -0.0124 | 0.0027 |
| 2026 | 15 | gold | 3582 | 1309 | 2038 | 0.5620 | 0.5593 | 0.1895 | 0.7134 | 0.0281 | 0 | 0 | 0 |
| 2026 | 15 | scoreboard | 3582 | 1309 | 2038 | 0.5630 | 0.5627 | 0.1904 | 0.7095 | 0.0244 | 0.0010 | -0.0022 | 0.0041 |
| 2026 | 15 | lanes_no_xp | 3582 | 1309 | 2038 | 0.5571 | 0.5563 | 0.1880 | 0.7110 | 0.0299 | -0.0049 | -0.0100 | -0.0000 |
| 2026 | 15 | aura_features | 3582 | 1309 | 2038 | 0.5563 | 0.5568 | 0.1875 | 0.7134 | 0.0287 | -0.0057 | -0.0119 | 0.0006 |
| 2023 | 20 | gold | 5252 | 1233 | 1233 | 0.4429 | 0.4425 | 0.1436 | 0.7981 | 0.0290 | 0 | 0 | 0 |
| 2023 | 20 | scoreboard | 5252 | 1233 | 1233 | 0.4389 | 0.4383 | 0.1422 | 0.7989 | 0.0273 | -0.0041 | -0.0089 | 0.0008 |
| 2023 | 20 | lanes_no_xp | 5252 | 1233 | 1233 | 0.4370 | 0.4365 | 0.1412 | 0.8029 | 0.0308 | -0.0060 | -0.0174 | 0.0051 |
| 2023 | 20 | aura_features | 5252 | 1233 | 1233 | 0.4280 | 0.4273 | 0.1375 | 0.8086 | 0.0334 | -0.0150 | -0.0269 | -0.0034 |
| 2024 | 20 | gold | 4687 | 1233 | 1106 | 0.4800 | 0.4795 | 0.1590 | 0.7649 | 0.0285 | 0 | 0 | 0 |
| 2024 | 20 | scoreboard | 4687 | 1233 | 1106 | 0.4764 | 0.4760 | 0.1582 | 0.7541 | 0.0413 | -0.0036 | -0.0096 | 0.0027 |
| 2024 | 20 | lanes_no_xp | 4687 | 1233 | 1106 | 0.4796 | 0.4791 | 0.1585 | 0.7613 | 0.0404 | -0.0004 | -0.0110 | 0.0111 |
| 2024 | 20 | aura_features | 4687 | 1233 | 1106 | 0.4733 | 0.4716 | 0.1554 | 0.7694 | 0.0409 | -0.0067 | -0.0184 | 0.0054 |
| 2025 | 20 | gold | 4092 | 1106 | 1309 | 0.4674 | 0.4676 | 0.1548 | 0.7662 | 0.0294 | 0 | 0 | 0 |
| 2025 | 20 | scoreboard | 4092 | 1106 | 1309 | 0.4694 | 0.4691 | 0.1562 | 0.7693 | 0.0282 | 0.0020 | -0.0031 | 0.0071 |
| 2025 | 20 | lanes_no_xp | 4092 | 1106 | 1309 | 0.4574 | 0.4552 | 0.1513 | 0.7785 | 0.0388 | -0.0100 | -0.0168 | -0.0027 |
| 2025 | 20 | aura_features | 4092 | 1106 | 1309 | 0.4542 | 0.4535 | 0.1504 | 0.7693 | 0.0251 | -0.0132 | -0.0225 | -0.0036 |
| 2026 | 20 | gold | 3572 | 1309 | 2035 | 0.4982 | 0.4880 | 0.1647 | 0.7582 | 0.0473 | 0 | 0 | 0 |
| 2026 | 20 | scoreboard | 3572 | 1309 | 2035 | 0.4981 | 0.4913 | 0.1646 | 0.7538 | 0.0501 | -0.0001 | -0.0050 | 0.0047 |
| 2026 | 20 | lanes_no_xp | 3572 | 1309 | 2035 | 0.4871 | 0.4807 | 0.1601 | 0.7661 | 0.0445 | -0.0111 | -0.0183 | -0.0044 |
| 2026 | 20 | aura_features | 3572 | 1309 | 2035 | 0.4859 | 0.4843 | 0.1594 | 0.7671 | 0.0402 | -0.0123 | -0.0218 | -0.0029 |

## 2026 holdout by league

Small international samples are descriptive only; do not interpret their calibration as stable.

| minute | model | league | n | log_loss | brier | accuracy | ece10 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | EWC | 232 | 0.5965 | 0.2066 | 0.6638 | 0.0360 |
| 10 | aura_features | FST | 45 | 0.6296 | 0.2197 | 0.6667 | 0.1243 |
| 10 | aura_features | LCK | 502 | 0.6077 | 0.2110 | 0.6594 | 0.0372 |
| 10 | aura_features | LCS | 252 | 0.6077 | 0.2114 | 0.6548 | 0.0457 |
| 10 | aura_features | LEC | 382 | 0.6625 | 0.2337 | 0.6178 | 0.0911 |
| 10 | aura_features | LPL | 541 | 0.6169 | 0.2136 | 0.6617 | 0.0535 |
| 10 | aura_features | MSI | 71 | 0.5173 | 0.1702 | 0.7887 | 0.1264 |
| 10 | aura_features | Worlds | 12 | 0.8309 | 0.2904 | 0.5000 | 0.3576 |
| 10 | gold | EWC | 232 | 0.6314 | 0.2199 | 0.6336 | 0.0735 |
| 10 | gold | FST | 45 | 0.6432 | 0.2249 | 0.6889 | 0.2215 |
| 10 | gold | LCK | 502 | 0.6083 | 0.2108 | 0.6653 | 0.0470 |
| 10 | gold | LCS | 252 | 0.6002 | 0.2077 | 0.6746 | 0.0649 |
| 10 | gold | LEC | 382 | 0.6735 | 0.2386 | 0.6099 | 0.1006 |
| 10 | gold | LPL | 541 | 0.6161 | 0.2130 | 0.6488 | 0.0410 |
| 10 | gold | MSI | 71 | 0.5320 | 0.1769 | 0.7746 | 0.1445 |
| 10 | gold | Worlds | 12 | 0.8798 | 0.3092 | 0.5000 | 0.2968 |
| 15 | aura_features | EWC | 232 | 0.5526 | 0.1863 | 0.7328 | 0.0727 |
| 15 | aura_features | FST | 45 | 0.5292 | 0.1788 | 0.7556 | 0.1751 |
| 15 | aura_features | LCK | 502 | 0.5601 | 0.1909 | 0.6992 | 0.0506 |
| 15 | aura_features | LCS | 252 | 0.5393 | 0.1827 | 0.7103 | 0.0651 |
| 15 | aura_features | LEC | 382 | 0.6039 | 0.2045 | 0.6885 | 0.0867 |
| 15 | aura_features | LPL | 542 | 0.5373 | 0.1786 | 0.7177 | 0.0533 |
| 15 | aura_features | MSI | 71 | 0.4823 | 0.1570 | 0.8310 | 0.1563 |
| 15 | aura_features | Worlds | 12 | 0.7119 | 0.2475 | 0.7500 | 0.3486 |
| 15 | gold | EWC | 232 | 0.5801 | 0.1954 | 0.7241 | 0.0749 |
| 15 | gold | FST | 45 | 0.5133 | 0.1744 | 0.7556 | 0.1661 |
| 15 | gold | LCK | 502 | 0.5623 | 0.1910 | 0.7191 | 0.0605 |
| 15 | gold | LCS | 252 | 0.5446 | 0.1833 | 0.7103 | 0.0385 |
| 15 | gold | LEC | 382 | 0.5993 | 0.2040 | 0.6780 | 0.0704 |
| 15 | gold | LPL | 542 | 0.5449 | 0.1816 | 0.7214 | 0.0468 |
| 15 | gold | MSI | 71 | 0.4832 | 0.1585 | 0.7606 | 0.1365 |
| 15 | gold | Worlds | 12 | 0.7986 | 0.2710 | 0.6667 | 0.3006 |
| 20 | aura_features | EWC | 231 | 0.4472 | 0.1432 | 0.8139 | 0.0791 |
| 20 | aura_features | FST | 45 | 0.4707 | 0.1557 | 0.7556 | 0.1665 |
| 20 | aura_features | LCK | 502 | 0.4685 | 0.1542 | 0.7749 | 0.0547 |
| 20 | aura_features | LCS | 252 | 0.4785 | 0.1615 | 0.7341 | 0.0687 |
| 20 | aura_features | LEC | 381 | 0.5519 | 0.1798 | 0.7402 | 0.0760 |
| 20 | aura_features | LPL | 541 | 0.4812 | 0.1579 | 0.7689 | 0.0476 |
| 20 | aura_features | MSI | 71 | 0.4564 | 0.1464 | 0.8169 | 0.1348 |
| 20 | aura_features | Worlds | 12 | 0.4618 | 0.1551 | 0.7500 | 0.1356 |
| 20 | gold | EWC | 231 | 0.4762 | 0.1581 | 0.7619 | 0.0714 |
| 20 | gold | FST | 45 | 0.4525 | 0.1562 | 0.7333 | 0.1625 |
| 20 | gold | LCK | 502 | 0.4756 | 0.1567 | 0.7669 | 0.0587 |
| 20 | gold | LCS | 252 | 0.4935 | 0.1666 | 0.7381 | 0.0578 |
| 20 | gold | LEC | 381 | 0.5593 | 0.1833 | 0.7507 | 0.0976 |
| 20 | gold | LPL | 541 | 0.4943 | 0.1627 | 0.7652 | 0.0413 |
| 20 | gold | MSI | 71 | 0.4735 | 0.1532 | 0.7606 | 0.0735 |
| 20 | gold | Worlds | 12 | 0.5216 | 0.1804 | 0.7500 | 0.2056 |

## Live feature availability

| Feature | Broadcast feasibility | Historical benchmark |
| --- | --- | --- |
| Team gold difference | Usually on scoreboard; rounded and delayed | Sum of player gold differences; validate against displayed team totals |
| Team kill difference | Usually on scoreboard | Sum of player kills |
| Lane CS and KDA | Often visible; layout/replays may hide them | lanes_no_xp model |
| Individual gold | Not continuously visible | Needed for lane models; requires structured feed or occasional overlay |
| Individual XP | Not consistently visible; level is not exact XP | AURA-feature model is a richer-data reference |
| Champions/players | Match metadata or draft; stable per game | Not fitted in this first benchmark |
| Towers/dragons/barons | Often on scoreboard | Final-game totals exist, but fixed-minute objective values are not used here |

Feasibility is a collection design assumption, not verified OCR or live feed access. Historical summed gold is more precise than rounded scoreboard reads; test rounding and extraction noise before deployment.

## Next work and limits

Start the collection pilot with team gold, kills, game clock, and match metadata. Use richer lane/XP models only where a live source supplies those fields. Investigate snapshot gaps by league; complete-case selection means these results do not establish performance on missing-data games. Add a strictly historical team-strength prior and draft features in a new development experiment, with a new untouched evaluation period. Do not substitute final-game objectives or season-level scores as live inputs. There are no synchronized market prices, executable fills, fees, or latency measurements here; this benchmark establishes prediction quality only.
