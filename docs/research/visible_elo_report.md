# 2026 validation and broadcast-visible Elo models

Fixed settings: C=1, three-year training, next-year sigmoid calibration, next-year test; no 2026-driven tuning. The 2026 baseline outcomes were viewed previously, so this is retrospective validation, not an untouched holdout.

## Finding

Elo improves both gold-only and full-stats models at all three checkpoints, with paired 95% intervals below zero. Adding kills to gold+Elo shows no reliable improvement at any checkpoint. Keep gold+Elo as the simplest broadcast-compatible candidate. Calibration remains imperfect; rounded or delayed broadcast inputs have not been validated.

## Input availability

Historical snapshots support team gold and kills, summed across five players per side. Towers, dragons, Baron, Herald and Atakhan in local OE files are final-game totals, with no checkpoint counts. They are excluded to avoid future information. Future objective features need timestamped events or archived screenshots; Baron buff status, dragon type/soul and timers may require more than a count. Game time is represented by separate 10/15/20-minute models, not a continuously validated model.

## Evaluation

Train 2022–2024, calibrate 2025, test available 2026 matches. Historical Elo updates after each finished game in archive order; current-match results do not enter its own pre-match rating. Existing Elo constants remain fixed. The common cohort compares rich stats, gold and gold+kills fairly on identical complete-rich games; the visible cohort only requires gold/kills/Elo and therefore has its own training population. Draft completeness is not required. Do not compare scores across cohorts as if they use the same games.

The full-stats+Elo candidate uses the original C=1 protocol. All visible models also use C=1, fixed before scoring this run. Elo gains compare gold+Elo vs gold and rich+Elo vs rich. The extra-kills comparison is scoreboard+Elo vs gold+Elo. Paired league/day-cluster 95% intervals use 2,000 draws, seed 42, without multiplicity adjustment. Raw and calibrated scores are both retained; no selecting calibration from 2026 results. 2023–2025 development folds for visible features are also shown.

Elo replay includes 100312 games through 2026 and reproduces stored pre-match ratings with max difference 0. 223 archive games share timestamps (existing game-ID tie ordering). Game/team/side joins require matching raw timestamp, duration and outcome. Result-availability timing and existing Elo parameter selection limit causal timing claims.

## 2026 common-cohort log loss

| minute | gold | gold_elo | rich | rich_elo | scoreboard | scoreboard_elo |
| --- | --- | --- | --- | --- | --- | --- |
| 10 | 0.6239 | 0.5868 | 0.6178 | 0.5867 | 0.6236 | 0.5877 |
| 15 | 0.5620 | 0.5371 | 0.5563 | 0.5364 | 0.5630 | 0.5395 |
| 20 | 0.4982 | 0.4803 | 0.4859 | 0.4707 | 0.4981 | 0.4806 |

## 2026 scores and paired differences

| minute | year | cohort | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2026 | common | gold | 2037 | 0.6239 | 0.2170 | 0.6514 | 0.0339 | 0.6213 | gold | 0 | 0 | 0 |
| 10 | 2026 | common | gold_elo | 2037 | 0.5868 | 0.2011 | 0.6942 | 0.0410 | 0.5824 | gold | -0.0372 | -0.0511 | -0.0226 |
| 10 | 2026 | common | rich | 2037 | 0.6178 | 0.2147 | 0.6559 | 0.0292 | 0.6185 | rich | 0 | 0 | 0 |
| 10 | 2026 | common | rich_elo | 2037 | 0.5867 | 0.2011 | 0.6853 | 0.0350 | 0.5855 | rich | -0.0311 | -0.0444 | -0.0177 |
| 10 | 2026 | common | scoreboard | 2037 | 0.6236 | 0.2168 | 0.6519 | 0.0361 | 0.6204 | gold | -0.0003 | -0.0012 | 0.0007 |
| 10 | 2026 | common | scoreboard_elo | 2037 | 0.5877 | 0.2014 | 0.6956 | 0.0371 | 0.5839 | gold_elo | 0.0009 | -0.0014 | 0.0032 |
| 10 | 2026 | visible | gold | 2037 | 0.6239 | 0.2170 | 0.6514 | 0.0339 | 0.6213 | gold | 0 | 0 | 0 |
| 10 | 2026 | visible | gold_elo | 2037 | 0.5868 | 0.2011 | 0.6942 | 0.0410 | 0.5824 | gold | -0.0372 | -0.0511 | -0.0226 |
| 10 | 2026 | visible | scoreboard | 2037 | 0.6236 | 0.2168 | 0.6519 | 0.0361 | 0.6204 | gold | -0.0003 | -0.0012 | 0.0007 |
| 10 | 2026 | visible | scoreboard_elo | 2037 | 0.5877 | 0.2014 | 0.6956 | 0.0371 | 0.5839 | gold_elo | 0.0009 | -0.0014 | 0.0032 |
| 15 | 2026 | common | gold | 2038 | 0.5620 | 0.1895 | 0.7134 | 0.0281 | 0.5593 | gold | 0 | 0 | 0 |
| 15 | 2026 | common | gold_elo | 2038 | 0.5371 | 0.1798 | 0.7203 | 0.0450 | 0.5323 | gold | -0.0249 | -0.0370 | -0.0124 |
| 15 | 2026 | common | rich | 2038 | 0.5563 | 0.1875 | 0.7134 | 0.0287 | 0.5568 | rich | 0 | 0 | 0 |
| 15 | 2026 | common | rich_elo | 2038 | 0.5364 | 0.1796 | 0.7355 | 0.0452 | 0.5369 | rich | -0.0199 | -0.0307 | -0.0083 |
| 15 | 2026 | common | scoreboard | 2038 | 0.5630 | 0.1904 | 0.7095 | 0.0244 | 0.5627 | gold | 0.0010 | -0.0022 | 0.0041 |
| 15 | 2026 | common | scoreboard_elo | 2038 | 0.5395 | 0.1813 | 0.7272 | 0.0352 | 0.5372 | gold_elo | 0.0024 | -0.0033 | 0.0077 |
| 15 | 2026 | visible | gold | 2038 | 0.5620 | 0.1895 | 0.7134 | 0.0281 | 0.5593 | gold | 0 | 0 | 0 |
| 15 | 2026 | visible | gold_elo | 2038 | 0.5371 | 0.1798 | 0.7203 | 0.0450 | 0.5323 | gold | -0.0249 | -0.0370 | -0.0124 |
| 15 | 2026 | visible | scoreboard | 2038 | 0.5630 | 0.1904 | 0.7095 | 0.0244 | 0.5627 | gold | 0.0010 | -0.0022 | 0.0041 |
| 15 | 2026 | visible | scoreboard_elo | 2038 | 0.5395 | 0.1813 | 0.7272 | 0.0352 | 0.5372 | gold_elo | 0.0024 | -0.0033 | 0.0077 |
| 20 | 2026 | common | gold | 2035 | 0.4982 | 0.1647 | 0.7582 | 0.0473 | 0.4880 | gold | 0 | 0 | 0 |
| 20 | 2026 | common | gold_elo | 2035 | 0.4803 | 0.1583 | 0.7690 | 0.0474 | 0.4718 | gold | -0.0180 | -0.0279 | -0.0078 |
| 20 | 2026 | common | rich | 2035 | 0.4859 | 0.1594 | 0.7671 | 0.0402 | 0.4843 | rich | 0 | 0 | 0 |
| 20 | 2026 | common | rich_elo | 2035 | 0.4707 | 0.1541 | 0.7774 | 0.0330 | 0.4721 | rich | -0.0152 | -0.0241 | -0.0060 |
| 20 | 2026 | common | scoreboard | 2035 | 0.4981 | 0.1646 | 0.7538 | 0.0501 | 0.4913 | gold | -0.0001 | -0.0050 | 0.0047 |
| 20 | 2026 | common | scoreboard_elo | 2035 | 0.4806 | 0.1582 | 0.7686 | 0.0428 | 0.4758 | gold_elo | 0.0003 | -0.0066 | 0.0071 |
| 20 | 2026 | visible | gold | 2035 | 0.4982 | 0.1647 | 0.7582 | 0.0473 | 0.4880 | gold | 0 | 0 | 0 |
| 20 | 2026 | visible | gold_elo | 2035 | 0.4803 | 0.1583 | 0.7690 | 0.0474 | 0.4718 | gold | -0.0180 | -0.0279 | -0.0078 |
| 20 | 2026 | visible | scoreboard | 2035 | 0.4981 | 0.1646 | 0.7538 | 0.0501 | 0.4913 | gold | -0.0001 | -0.0050 | 0.0047 |
| 20 | 2026 | visible | scoreboard_elo | 2035 | 0.4806 | 0.1582 | 0.7686 | 0.0428 | 0.4758 | gold_elo | 0.0003 | -0.0066 | 0.0071 |

## Development scores

| minute | year | cohort | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | 2023 | common | gold | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5899 | gold | 0 | 0 | 0 |
| 10 | 2023 | common | gold_elo | 1239 | 0.5490 | 0.1862 | 0.7215 | 0.0330 | 0.5508 | gold | -0.0405 | -0.0571 | -0.0250 |
| 10 | 2023 | common | rich | 1239 | 0.5866 | 0.2004 | 0.6949 | 0.0236 | 0.5867 | rich | 0 | 0 | 0 |
| 10 | 2023 | common | rich_elo | 1239 | 0.5466 | 0.1849 | 0.7280 | 0.0418 | 0.5484 | rich | -0.0400 | -0.0562 | -0.0247 |
| 10 | 2023 | common | scoreboard | 1239 | 0.5902 | 0.2015 | 0.6836 | 0.0323 | 0.5905 | gold | 0.0006 | 0.0001 | 0.0011 |
| 10 | 2023 | common | scoreboard_elo | 1239 | 0.5503 | 0.1865 | 0.7207 | 0.0246 | 0.5520 | gold_elo | 0.0012 | -0.0013 | 0.0039 |
| 10 | 2023 | visible | gold | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5899 | gold | 0 | 0 | 0 |
| 10 | 2023 | visible | gold_elo | 1239 | 0.5490 | 0.1862 | 0.7215 | 0.0330 | 0.5508 | gold | -0.0405 | -0.0571 | -0.0250 |
| 10 | 2023 | visible | scoreboard | 1239 | 0.5902 | 0.2015 | 0.6836 | 0.0323 | 0.5905 | gold | 0.0006 | 0.0001 | 0.0011 |
| 10 | 2023 | visible | scoreboard_elo | 1239 | 0.5503 | 0.1865 | 0.7207 | 0.0246 | 0.5520 | gold_elo | 0.0012 | -0.0013 | 0.0039 |
| 10 | 2024 | common | gold | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6104 | gold | 0 | 0 | 0 |
| 10 | 2024 | common | gold_elo | 1106 | 0.5595 | 0.1906 | 0.7089 | 0.0217 | 0.5614 | gold | -0.0497 | -0.0674 | -0.0327 |
| 10 | 2024 | common | rich | 1106 | 0.6062 | 0.2098 | 0.6646 | 0.0252 | 0.6072 | rich | 0 | 0 | 0 |
| 10 | 2024 | common | rich_elo | 1106 | 0.5560 | 0.1894 | 0.7043 | 0.0365 | 0.5577 | rich | -0.0502 | -0.0674 | -0.0330 |
| 10 | 2024 | common | scoreboard | 1106 | 0.6096 | 0.2113 | 0.6637 | 0.0334 | 0.6108 | gold | 0.0004 | -0.0005 | 0.0012 |
| 10 | 2024 | common | scoreboard_elo | 1106 | 0.5578 | 0.1902 | 0.7134 | 0.0234 | 0.5596 | gold_elo | -0.0017 | -0.0047 | 0.0014 |
| 10 | 2024 | visible | gold | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6104 | gold | 0 | 0 | 0 |
| 10 | 2024 | visible | gold_elo | 1106 | 0.5595 | 0.1906 | 0.7089 | 0.0217 | 0.5614 | gold | -0.0497 | -0.0674 | -0.0327 |
| 10 | 2024 | visible | scoreboard | 1106 | 0.6096 | 0.2113 | 0.6637 | 0.0334 | 0.6108 | gold | 0.0004 | -0.0005 | 0.0012 |
| 10 | 2024 | visible | scoreboard_elo | 1106 | 0.5578 | 0.1902 | 0.7134 | 0.0234 | 0.5596 | gold_elo | -0.0017 | -0.0047 | 0.0014 |
| 10 | 2025 | common | gold | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6163 | gold | 0 | 0 | 0 |
| 10 | 2025 | common | gold_elo | 1309 | 0.5610 | 0.1901 | 0.7173 | 0.0355 | 0.5591 | gold | -0.0558 | -0.0700 | -0.0421 |
| 10 | 2025 | common | rich | 1309 | 0.6171 | 0.2147 | 0.6532 | 0.0307 | 0.6169 | rich | 0 | 0 | 0 |
| 10 | 2025 | common | rich_elo | 1309 | 0.5633 | 0.1917 | 0.6960 | 0.0344 | 0.5621 | rich | -0.0538 | -0.0679 | -0.0403 |
| 10 | 2025 | common | scoreboard | 1309 | 0.6169 | 0.2146 | 0.6539 | 0.0170 | 0.6164 | gold | 0.0001 | 0.0000 | 0.0002 |
| 10 | 2025 | common | scoreboard_elo | 1309 | 0.5611 | 0.1903 | 0.7059 | 0.0225 | 0.5597 | gold_elo | 0.0001 | -0.0025 | 0.0026 |
| 10 | 2025 | visible | gold | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6163 | gold | 0 | 0 | 0 |
| 10 | 2025 | visible | gold_elo | 1309 | 0.5610 | 0.1901 | 0.7173 | 0.0355 | 0.5591 | gold | -0.0558 | -0.0700 | -0.0421 |
| 10 | 2025 | visible | scoreboard | 1309 | 0.6169 | 0.2146 | 0.6539 | 0.0170 | 0.6164 | gold | 0.0001 | 0.0000 | 0.0002 |
| 10 | 2025 | visible | scoreboard_elo | 1309 | 0.5611 | 0.1903 | 0.7059 | 0.0225 | 0.5597 | gold_elo | 0.0001 | -0.0025 | 0.0026 |
| 15 | 2023 | common | gold | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5135 | gold | 0 | 0 | 0 |
| 15 | 2023 | common | gold_elo | 1239 | 0.4885 | 0.1622 | 0.7603 | 0.0281 | 0.4881 | gold | -0.0261 | -0.0386 | -0.0144 |
| 15 | 2023 | common | rich | 1239 | 0.5028 | 0.1673 | 0.7490 | 0.0319 | 0.5017 | rich | 0 | 0 | 0 |
| 15 | 2023 | common | rich_elo | 1239 | 0.4756 | 0.1575 | 0.7627 | 0.0319 | 0.4754 | rich | -0.0272 | -0.0395 | -0.0157 |
| 15 | 2023 | common | scoreboard | 1239 | 0.5134 | 0.1710 | 0.7458 | 0.0229 | 0.5126 | gold | -0.0013 | -0.0052 | 0.0027 |
| 15 | 2023 | common | scoreboard_elo | 1239 | 0.4838 | 0.1608 | 0.7546 | 0.0174 | 0.4839 | gold_elo | -0.0048 | -0.0100 | 0.0004 |
| 15 | 2023 | visible | gold | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5135 | gold | 0 | 0 | 0 |
| 15 | 2023 | visible | gold_elo | 1239 | 0.4885 | 0.1622 | 0.7603 | 0.0281 | 0.4881 | gold | -0.0261 | -0.0386 | -0.0144 |
| 15 | 2023 | visible | scoreboard | 1239 | 0.5134 | 0.1710 | 0.7458 | 0.0229 | 0.5126 | gold | -0.0013 | -0.0052 | 0.0027 |
| 15 | 2023 | visible | scoreboard_elo | 1239 | 0.4838 | 0.1608 | 0.7546 | 0.0174 | 0.4839 | gold_elo | -0.0048 | -0.0100 | 0.0004 |
| 15 | 2024 | common | gold | 1106 | 0.5504 | 0.1867 | 0.7052 | 0.0301 | 0.5497 | gold | 0 | 0 | 0 |
| 15 | 2024 | common | gold_elo | 1106 | 0.5136 | 0.1720 | 0.7505 | 0.0331 | 0.5132 | gold | -0.0368 | -0.0523 | -0.0217 |
| 15 | 2024 | common | rich | 1106 | 0.5424 | 0.1833 | 0.7116 | 0.0420 | 0.5414 | rich | 0 | 0 | 0 |
| 15 | 2024 | common | rich_elo | 1106 | 0.5029 | 0.1684 | 0.7450 | 0.0419 | 0.5025 | rich | -0.0395 | -0.0549 | -0.0242 |
| 15 | 2024 | common | scoreboard | 1106 | 0.5496 | 0.1866 | 0.6971 | 0.0402 | 0.5491 | gold | -0.0008 | -0.0060 | 0.0046 |
| 15 | 2024 | common | scoreboard_elo | 1106 | 0.5064 | 0.1698 | 0.7450 | 0.0308 | 0.5064 | gold_elo | -0.0072 | -0.0145 | 0.0004 |
| 15 | 2024 | visible | gold | 1106 | 0.5504 | 0.1867 | 0.7052 | 0.0301 | 0.5497 | gold | 0 | 0 | 0 |
| 15 | 2024 | visible | gold_elo | 1106 | 0.5136 | 0.1720 | 0.7505 | 0.0331 | 0.5132 | gold | -0.0368 | -0.0523 | -0.0217 |
| 15 | 2024 | visible | scoreboard | 1106 | 0.5496 | 0.1866 | 0.6971 | 0.0402 | 0.5491 | gold | -0.0008 | -0.0060 | 0.0046 |
| 15 | 2024 | visible | scoreboard_elo | 1106 | 0.5064 | 0.1698 | 0.7450 | 0.0308 | 0.5064 | gold_elo | -0.0072 | -0.0145 | 0.0004 |
| 15 | 2025 | common | gold | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5658 | gold | 0 | 0 | 0 |
| 15 | 2025 | common | gold_elo | 1309 | 0.5233 | 0.1760 | 0.7242 | 0.0420 | 0.5228 | gold | -0.0426 | -0.0544 | -0.0310 |
| 15 | 2025 | common | rich | 1309 | 0.5609 | 0.1914 | 0.7021 | 0.0186 | 0.5606 | rich | 0 | 0 | 0 |
| 15 | 2025 | common | rich_elo | 1309 | 0.5221 | 0.1765 | 0.7227 | 0.0214 | 0.5217 | rich | -0.0388 | -0.0504 | -0.0268 |
| 15 | 2025 | common | scoreboard | 1309 | 0.5698 | 0.1949 | 0.6990 | 0.0191 | 0.5698 | gold | 0.0039 | 0.0002 | 0.0076 |
| 15 | 2025 | common | scoreboard_elo | 1309 | 0.5236 | 0.1767 | 0.7349 | 0.0277 | 0.5235 | gold_elo | 0.0003 | -0.0054 | 0.0062 |
| 15 | 2025 | visible | gold | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5658 | gold | 0 | 0 | 0 |
| 15 | 2025 | visible | gold_elo | 1309 | 0.5233 | 0.1760 | 0.7242 | 0.0420 | 0.5228 | gold | -0.0426 | -0.0544 | -0.0310 |
| 15 | 2025 | visible | scoreboard | 1309 | 0.5698 | 0.1949 | 0.6990 | 0.0191 | 0.5698 | gold | 0.0039 | 0.0002 | 0.0076 |
| 15 | 2025 | visible | scoreboard_elo | 1309 | 0.5236 | 0.1767 | 0.7349 | 0.0277 | 0.5235 | gold_elo | 0.0003 | -0.0054 | 0.0062 |
| 20 | 2023 | common | gold | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4425 | gold | 0 | 0 | 0 |
| 20 | 2023 | common | gold_elo | 1233 | 0.4279 | 0.1383 | 0.8013 | 0.0255 | 0.4281 | gold | -0.0150 | -0.0257 | -0.0050 |
| 20 | 2023 | common | rich | 1233 | 0.4280 | 0.1375 | 0.8086 | 0.0334 | 0.4273 | rich | 0 | 0 | 0 |
| 20 | 2023 | common | rich_elo | 1233 | 0.4128 | 0.1322 | 0.8167 | 0.0229 | 0.4127 | rich | -0.0152 | -0.0259 | -0.0051 |
| 20 | 2023 | common | scoreboard | 1233 | 0.4389 | 0.1422 | 0.7989 | 0.0273 | 0.4383 | gold | -0.0041 | -0.0089 | 0.0008 |
| 20 | 2023 | common | scoreboard_elo | 1233 | 0.4200 | 0.1354 | 0.8045 | 0.0293 | 0.4202 | gold_elo | -0.0079 | -0.0138 | -0.0019 |
| 20 | 2023 | visible | gold | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4425 | gold | 0 | 0 | 0 |
| 20 | 2023 | visible | gold_elo | 1233 | 0.4279 | 0.1383 | 0.8013 | 0.0255 | 0.4281 | gold | -0.0150 | -0.0257 | -0.0050 |
| 20 | 2023 | visible | scoreboard | 1233 | 0.4389 | 0.1422 | 0.7989 | 0.0273 | 0.4383 | gold | -0.0041 | -0.0089 | 0.0008 |
| 20 | 2023 | visible | scoreboard_elo | 1233 | 0.4200 | 0.1354 | 0.8045 | 0.0293 | 0.4202 | gold_elo | -0.0079 | -0.0138 | -0.0019 |
| 20 | 2024 | common | gold | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | gold | 0 | 0 | 0 |
| 20 | 2024 | common | gold_elo | 1106 | 0.4555 | 0.1503 | 0.7749 | 0.0232 | 0.4552 | gold | -0.0244 | -0.0359 | -0.0131 |
| 20 | 2024 | common | rich | 1106 | 0.4733 | 0.1554 | 0.7694 | 0.0409 | 0.4716 | rich | 0 | 0 | 0 |
| 20 | 2024 | common | rich_elo | 1106 | 0.4443 | 0.1460 | 0.7749 | 0.0345 | 0.4433 | rich | -0.0290 | -0.0413 | -0.0171 |
| 20 | 2024 | common | scoreboard | 1106 | 0.4764 | 0.1582 | 0.7541 | 0.0413 | 0.4760 | gold | -0.0036 | -0.0096 | 0.0027 |
| 20 | 2024 | common | scoreboard_elo | 1106 | 0.4441 | 0.1470 | 0.7749 | 0.0217 | 0.4439 | gold_elo | -0.0115 | -0.0193 | -0.0036 |
| 20 | 2024 | visible | gold | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | gold | 0 | 0 | 0 |
| 20 | 2024 | visible | gold_elo | 1106 | 0.4555 | 0.1503 | 0.7749 | 0.0232 | 0.4552 | gold | -0.0244 | -0.0359 | -0.0131 |
| 20 | 2024 | visible | scoreboard | 1106 | 0.4764 | 0.1582 | 0.7541 | 0.0413 | 0.4760 | gold | -0.0036 | -0.0096 | 0.0027 |
| 20 | 2024 | visible | scoreboard_elo | 1106 | 0.4441 | 0.1470 | 0.7749 | 0.0217 | 0.4439 | gold_elo | -0.0115 | -0.0193 | -0.0036 |
| 20 | 2025 | common | gold | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4676 | gold | 0 | 0 | 0 |
| 20 | 2025 | common | gold_elo | 1309 | 0.4428 | 0.1452 | 0.7846 | 0.0291 | 0.4426 | gold | -0.0246 | -0.0337 | -0.0155 |
| 20 | 2025 | common | rich | 1309 | 0.4542 | 0.1504 | 0.7693 | 0.0251 | 0.4535 | rich | 0 | 0 | 0 |
| 20 | 2025 | common | rich_elo | 1309 | 0.4336 | 0.1425 | 0.7861 | 0.0374 | 0.4329 | rich | -0.0207 | -0.0303 | -0.0112 |
| 20 | 2025 | common | scoreboard | 1309 | 0.4694 | 0.1562 | 0.7693 | 0.0282 | 0.4691 | gold | 0.0020 | -0.0031 | 0.0071 |
| 20 | 2025 | common | scoreboard_elo | 1309 | 0.4397 | 0.1448 | 0.7914 | 0.0213 | 0.4394 | gold_elo | -0.0031 | -0.0100 | 0.0042 |
| 20 | 2025 | visible | gold | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4676 | gold | 0 | 0 | 0 |
| 20 | 2025 | visible | gold_elo | 1309 | 0.4428 | 0.1452 | 0.7846 | 0.0291 | 0.4426 | gold | -0.0246 | -0.0337 | -0.0155 |
| 20 | 2025 | visible | scoreboard | 1309 | 0.4694 | 0.1562 | 0.7693 | 0.0282 | 0.4691 | gold | 0.0020 | -0.0031 | 0.0071 |
| 20 | 2025 | visible | scoreboard_elo | 1309 | 0.4397 | 0.1448 | 0.7914 | 0.0213 | 0.4394 | gold_elo | -0.0031 | -0.0100 | 0.0042 |

## Coverage

| minute | cohort | year | games |
| --- | --- | --- | --- |
| 10 | common | 2014 | 735 |
| 10 | common | 2015 | 628 |
| 10 | common | 2016 | 1369 |
| 10 | common | 2017 | 1657 |
| 10 | common | 2018 | 1887 |
| 10 | common | 2019 | 1806 |
| 10 | common | 2020 | 1835 |
| 10 | common | 2021 | 1633 |
| 10 | common | 2022 | 1237 |
| 10 | common | 2023 | 1239 |
| 10 | common | 2024 | 1106 |
| 10 | common | 2025 | 1309 |
| 10 | common | 2026 | 2037 |
| 10 | visible | 2014 | 735 |
| 10 | visible | 2015 | 628 |
| 10 | visible | 2016 | 1369 |
| 10 | visible | 2017 | 1657 |
| 10 | visible | 2018 | 1887 |
| 10 | visible | 2019 | 1806 |
| 10 | visible | 2020 | 1835 |
| 10 | visible | 2021 | 1633 |
| 10 | visible | 2022 | 1237 |
| 10 | visible | 2023 | 1239 |
| 10 | visible | 2024 | 1106 |
| 10 | visible | 2025 | 1309 |
| 10 | visible | 2026 | 2037 |
| 15 | common | 2014 | 735 |
| 15 | common | 2015 | 628 |
| 15 | common | 2016 | 1369 |
| 15 | common | 2017 | 1657 |
| 15 | common | 2018 | 1887 |
| 15 | common | 2019 | 1806 |
| 15 | common | 2020 | 1833 |
| 15 | common | 2021 | 1633 |
| 15 | common | 2022 | 1237 |
| 15 | common | 2023 | 1239 |
| 15 | common | 2024 | 1106 |
| 15 | common | 2025 | 1309 |
| 15 | common | 2026 | 2038 |
| 15 | visible | 2014 | 735 |
| 15 | visible | 2015 | 628 |
| 15 | visible | 2016 | 1369 |
| 15 | visible | 2017 | 1657 |
| 15 | visible | 2018 | 1887 |
| 15 | visible | 2019 | 1806 |
| 15 | visible | 2020 | 1833 |
| 15 | visible | 2021 | 1633 |
| 15 | visible | 2022 | 1237 |
| 15 | visible | 2023 | 1239 |
| 15 | visible | 2024 | 1106 |
| 15 | visible | 2025 | 1309 |
| 15 | visible | 2026 | 2038 |
| 20 | common | 2014 | 735 |
| 20 | common | 2015 | 628 |
| 20 | common | 2016 | 1366 |
| 20 | common | 2017 | 1657 |
| 20 | common | 2018 | 1886 |
| 20 | common | 2019 | 1798 |
| 20 | common | 2020 | 1828 |
| 20 | common | 2021 | 1626 |
| 20 | common | 2022 | 1233 |
| 20 | common | 2023 | 1233 |
| 20 | common | 2024 | 1106 |
| 20 | common | 2025 | 1309 |
| 20 | common | 2026 | 2035 |
| 20 | visible | 2014 | 735 |
| 20 | visible | 2015 | 628 |
| 20 | visible | 2016 | 1366 |
| 20 | visible | 2017 | 1657 |
| 20 | visible | 2018 | 1886 |
| 20 | visible | 2019 | 1798 |
| 20 | visible | 2020 | 1828 |
| 20 | visible | 2021 | 1626 |
| 20 | visible | 2022 | 1233 |
| 20 | visible | 2023 | 1233 |
| 20 | visible | 2024 | 1106 |
| 20 | visible | 2025 | 1309 |
| 20 | visible | 2026 | 2035 |

## Model export and live use

Fitted parameters, source hashes, predictions and scores are saved in data/visible_elo/. predict_visible() uses the exported visible-cohort 2026 model weights and calibrator without refitting. Provide blue/red gold in actual units (32.1k → 32100), kills and pre-match Elo at an exact trained checkpoint. It returns blue map-win probability. These snapshots are historical totals; broadcast rounding, extraction errors and display delay are not simulated. Gold+Elo can omit kill features. Objective features and interpolation between checkpoints are not trained yet. No live integration, DB changes, published metric changes or profitable trading claim.
