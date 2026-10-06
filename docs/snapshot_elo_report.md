# Pre-match Elo and in-game win probability

Exploratory 2023–2025 development folds; 2026 excluded. Lower log loss is better.

## Finding

Every Elo addition improves pooled log loss, with all paired 95% intervals below zero. Every annual comparison also improves in point estimate. Keep stats+Elo as a development candidate; champion additions remain exploratory. Calibration is not uniformly improved. No production adoption or fresh validation is claimed.

## Protocol

Add blue-minus-red pre-match Elo as one standardized numeric feature. Gold and 30-lane-stat bases each compare stats vs stats+Elo (C=1) and champions vs champions+Elo (C=0.1). Each pair has identical complete snapshot/draft/Elo games and regularization. Champion effects are by role, with no lane pairs or state interactions. Separate models at 10/15/20 minutes learn separate Elo weights. No hyperparameter search.

Three training calendar years, the next year for sigmoid calibration, then the evaluation year. Scaling, champion vocabulary and coefficients use training only. Report calibrated and raw scores. Paired 95% intervals resample league/day clusters, 2,000 draws, seed 42, without multiplicity adjustment.

## Elo provenance

Existing player/roster-aware, game-length-weighted Elo replayed unchanged in memory through 2025: 91370 games. Pre-match ratings reproduce all stored records with maximum difference 0. Ratings are captured before updating from the current game result or length. Joins use game/team IDs and blue/red sides; raw snapshot date, winner and duration must match DB metadata. Missing or mismatched ratings are excluded from every comparison, never imputed.

215 historical games share timestamps; the existing replay breaks ties by game ID. Match timestamps are the archive ordering, not a verified feed of result availability. Elo algorithm constants were established in prior research; these folds are not an untouched evaluation of their selection. No DB writes or published metric changes.

## Pooled results

| minute | base | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | champions | 3654 | 0.6027 | 0.2080 | 0.6730 | 0.0143 | 0.6059 | champions | 0 | 0 | 0 |
| 10 | aura_features | champions_elo | 3654 | 0.5554 | 0.1883 | 0.7083 | 0.0099 | 0.5579 | champions | -0.0473 | -0.0560 | -0.0389 |
| 10 | aura_features | stats | 3654 | 0.6035 | 0.2084 | 0.6708 | 0.0115 | 0.6037 | stats | 0 | 0 | 0 |
| 10 | aura_features | stats_elo | 3654 | 0.5554 | 0.1887 | 0.7094 | 0.0095 | 0.5561 | stats | -0.0480 | -0.0574 | -0.0391 |
| 10 | gold | champions | 3654 | 0.6065 | 0.2096 | 0.6667 | 0.0107 | 0.6089 | champions | 0 | 0 | 0 |
| 10 | gold | champions_elo | 3654 | 0.5565 | 0.1888 | 0.7058 | 0.0129 | 0.5580 | champions | -0.0499 | -0.0587 | -0.0410 |
| 10 | gold | stats | 3654 | 0.6053 | 0.2090 | 0.6653 | 0.0138 | 0.6056 | stats | 0 | 0 | 0 |
| 10 | gold | stats_elo | 3654 | 0.5565 | 0.1889 | 0.7162 | 0.0207 | 0.5570 | stats | -0.0488 | -0.0583 | -0.0395 |
| 15 | aura_features | champions | 3654 | 0.5327 | 0.1793 | 0.7219 | 0.0193 | 0.5329 | champions | 0 | 0 | 0 |
| 15 | aura_features | champions_elo | 3654 | 0.4989 | 0.1665 | 0.7485 | 0.0152 | 0.4992 | champions | -0.0338 | -0.0410 | -0.0269 |
| 15 | aura_features | stats | 3654 | 0.5356 | 0.1808 | 0.7209 | 0.0174 | 0.5348 | stats | 0 | 0 | 0 |
| 15 | aura_features | stats_elo | 3654 | 0.5005 | 0.1676 | 0.7430 | 0.0196 | 0.5002 | stats | -0.0351 | -0.0430 | -0.0277 |
| 15 | gold | champions | 3654 | 0.5423 | 0.1830 | 0.7184 | 0.0135 | 0.5418 | champions | 0 | 0 | 0 |
| 15 | gold | champions_elo | 3654 | 0.5061 | 0.1690 | 0.7438 | 0.0166 | 0.5052 | champions | -0.0361 | -0.0435 | -0.0289 |
| 15 | gold | stats | 3654 | 0.5438 | 0.1838 | 0.7184 | 0.0121 | 0.5432 | stats | 0 | 0 | 0 |
| 15 | gold | stats_elo | 3654 | 0.5086 | 0.1701 | 0.7444 | 0.0202 | 0.5081 | stats | -0.0352 | -0.0430 | -0.0275 |
| 20 | aura_features | champions | 3648 | 0.4498 | 0.1474 | 0.7851 | 0.0101 | 0.4497 | champions | 0 | 0 | 0 |
| 20 | aura_features | champions_elo | 3648 | 0.4292 | 0.1399 | 0.7955 | 0.0160 | 0.4295 | champions | -0.0206 | -0.0265 | -0.0149 |
| 20 | aura_features | stats | 3648 | 0.4511 | 0.1475 | 0.7826 | 0.0119 | 0.4501 | stats | 0 | 0 | 0 |
| 20 | aura_features | stats_elo | 3648 | 0.4298 | 0.1401 | 0.7930 | 0.0126 | 0.4292 | stats | -0.0213 | -0.0278 | -0.0148 |
| 20 | gold | champions | 3648 | 0.4615 | 0.1519 | 0.7771 | 0.0155 | 0.4607 | champions | 0 | 0 | 0 |
| 20 | gold | champions_elo | 3648 | 0.4389 | 0.1433 | 0.7936 | 0.0143 | 0.4383 | champions | -0.0226 | -0.0287 | -0.0167 |
| 20 | gold | stats | 3648 | 0.4630 | 0.1523 | 0.7766 | 0.0166 | 0.4627 | stats | 0 | 0 | 0 |
| 20 | gold | stats_elo | 3648 | 0.4416 | 0.1444 | 0.7873 | 0.0141 | 0.4415 | stats | -0.0213 | -0.0276 | -0.0152 |

## Annual results

| minute | base | year | variant | n | log_loss | brier | accuracy | ece10 | raw_log_loss | control | delta_base | delta_low | delta_high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | aura_features | 2023 | champions | 1239 | 0.5851 | 0.1998 | 0.6917 | 0.0244 | 0.5888 | champions | 0 | 0 | 0 |
| 10 | aura_features | 2023 | champions_elo | 1239 | 0.5414 | 0.1825 | 0.7207 | 0.0294 | 0.5451 | champions | -0.0437 | -0.0594 | -0.0296 |
| 10 | aura_features | 2023 | stats | 1239 | 0.5866 | 0.2004 | 0.6949 | 0.0236 | 0.5867 | stats | 0 | 0 | 0 |
| 10 | aura_features | 2023 | stats_elo | 1239 | 0.5466 | 0.1849 | 0.7280 | 0.0418 | 0.5484 | stats | -0.0400 | -0.0562 | -0.0247 |
| 10 | aura_features | 2024 | champions | 1106 | 0.6052 | 0.2090 | 0.6618 | 0.0276 | 0.6106 | champions | 0 | 0 | 0 |
| 10 | aura_features | 2024 | champions_elo | 1106 | 0.5557 | 0.1887 | 0.7107 | 0.0193 | 0.5603 | champions | -0.0496 | -0.0656 | -0.0343 |
| 10 | aura_features | 2024 | stats | 1106 | 0.6062 | 0.2098 | 0.6646 | 0.0252 | 0.6072 | stats | 0 | 0 | 0 |
| 10 | aura_features | 2024 | stats_elo | 1106 | 0.5560 | 0.1894 | 0.7043 | 0.0365 | 0.5577 | stats | -0.0502 | -0.0674 | -0.0330 |
| 10 | aura_features | 2025 | champions | 1309 | 0.6173 | 0.2148 | 0.6646 | 0.0312 | 0.6181 | champions | 0 | 0 | 0 |
| 10 | aura_features | 2025 | champions_elo | 1309 | 0.5685 | 0.1936 | 0.6944 | 0.0265 | 0.5679 | champions | -0.0489 | -0.0614 | -0.0369 |
| 10 | aura_features | 2025 | stats | 1309 | 0.6171 | 0.2147 | 0.6532 | 0.0307 | 0.6169 | stats | 0 | 0 | 0 |
| 10 | aura_features | 2025 | stats_elo | 1309 | 0.5633 | 0.1917 | 0.6960 | 0.0344 | 0.5621 | stats | -0.0538 | -0.0679 | -0.0403 |
| 10 | gold | 2023 | champions | 1239 | 0.5877 | 0.2009 | 0.6877 | 0.0418 | 0.5909 | champions | 0 | 0 | 0 |
| 10 | gold | 2023 | champions_elo | 1239 | 0.5424 | 0.1834 | 0.7175 | 0.0254 | 0.5457 | champions | -0.0453 | -0.0619 | -0.0307 |
| 10 | gold | 2023 | stats | 1239 | 0.5896 | 0.2013 | 0.6812 | 0.0360 | 0.5899 | stats | 0 | 0 | 0 |
| 10 | gold | 2023 | stats_elo | 1239 | 0.5490 | 0.1862 | 0.7215 | 0.0330 | 0.5508 | stats | -0.0405 | -0.0571 | -0.0250 |
| 10 | gold | 2024 | champions | 1106 | 0.6096 | 0.2109 | 0.6637 | 0.0267 | 0.6142 | champions | 0 | 0 | 0 |
| 10 | gold | 2024 | champions_elo | 1106 | 0.5589 | 0.1899 | 0.7034 | 0.0207 | 0.5633 | champions | -0.0507 | -0.0674 | -0.0347 |
| 10 | gold | 2024 | stats | 1106 | 0.6093 | 0.2111 | 0.6609 | 0.0362 | 0.6104 | stats | 0 | 0 | 0 |
| 10 | gold | 2024 | stats_elo | 1106 | 0.5595 | 0.1906 | 0.7089 | 0.0217 | 0.5614 | stats | -0.0497 | -0.0674 | -0.0327 |
| 10 | gold | 2025 | champions | 1309 | 0.6216 | 0.2168 | 0.6494 | 0.0245 | 0.6216 | champions | 0 | 0 | 0 |
| 10 | gold | 2025 | champions_elo | 1309 | 0.5679 | 0.1931 | 0.6967 | 0.0374 | 0.5653 | champions | -0.0537 | -0.0663 | -0.0412 |
| 10 | gold | 2025 | stats | 1309 | 0.6168 | 0.2146 | 0.6539 | 0.0171 | 0.6163 | stats | 0 | 0 | 0 |
| 10 | gold | 2025 | stats_elo | 1309 | 0.5610 | 0.1901 | 0.7173 | 0.0355 | 0.5591 | stats | -0.0558 | -0.0700 | -0.0421 |
| 15 | aura_features | 2023 | champions | 1239 | 0.4982 | 0.1650 | 0.7603 | 0.0475 | 0.4972 | champions | 0 | 0 | 0 |
| 15 | aura_features | 2023 | champions_elo | 1239 | 0.4683 | 0.1542 | 0.7724 | 0.0241 | 0.4675 | champions | -0.0299 | -0.0411 | -0.0197 |
| 15 | aura_features | 2023 | stats | 1239 | 0.5028 | 0.1673 | 0.7490 | 0.0319 | 0.5017 | stats | 0 | 0 | 0 |
| 15 | aura_features | 2023 | stats_elo | 1239 | 0.4756 | 0.1575 | 0.7627 | 0.0319 | 0.4754 | stats | -0.0272 | -0.0395 | -0.0157 |
| 15 | aura_features | 2024 | champions | 1106 | 0.5434 | 0.1836 | 0.7071 | 0.0488 | 0.5446 | champions | 0 | 0 | 0 |
| 15 | aura_features | 2024 | champions_elo | 1106 | 0.5058 | 0.1690 | 0.7459 | 0.0377 | 0.5064 | champions | -0.0376 | -0.0513 | -0.0243 |
| 15 | aura_features | 2024 | stats | 1106 | 0.5424 | 0.1833 | 0.7116 | 0.0420 | 0.5414 | stats | 0 | 0 | 0 |
| 15 | aura_features | 2024 | stats_elo | 1106 | 0.5029 | 0.1684 | 0.7450 | 0.0419 | 0.5025 | stats | -0.0395 | -0.0549 | -0.0242 |
| 15 | aura_features | 2025 | champions | 1309 | 0.5563 | 0.1891 | 0.6982 | 0.0330 | 0.5569 | champions | 0 | 0 | 0 |
| 15 | aura_features | 2025 | champions_elo | 1309 | 0.5221 | 0.1761 | 0.7280 | 0.0274 | 0.5230 | champions | -0.0342 | -0.0451 | -0.0233 |
| 15 | aura_features | 2025 | stats | 1309 | 0.5609 | 0.1914 | 0.7021 | 0.0186 | 0.5606 | stats | 0 | 0 | 0 |
| 15 | aura_features | 2025 | stats_elo | 1309 | 0.5221 | 0.1765 | 0.7227 | 0.0214 | 0.5217 | stats | -0.0388 | -0.0504 | -0.0268 |
| 15 | gold | 2023 | champions | 1239 | 0.5087 | 0.1687 | 0.7450 | 0.0328 | 0.5076 | champions | 0 | 0 | 0 |
| 15 | gold | 2023 | champions_elo | 1239 | 0.4790 | 0.1582 | 0.7619 | 0.0337 | 0.4781 | champions | -0.0298 | -0.0414 | -0.0188 |
| 15 | gold | 2023 | stats | 1239 | 0.5146 | 0.1714 | 0.7522 | 0.0309 | 0.5135 | stats | 0 | 0 | 0 |
| 15 | gold | 2023 | stats_elo | 1239 | 0.4885 | 0.1622 | 0.7603 | 0.0281 | 0.4881 | stats | -0.0261 | -0.0386 | -0.0144 |
| 15 | gold | 2024 | champions | 1106 | 0.5502 | 0.1867 | 0.7125 | 0.0449 | 0.5503 | champions | 0 | 0 | 0 |
| 15 | gold | 2024 | champions_elo | 1106 | 0.5130 | 0.1716 | 0.7459 | 0.0391 | 0.5128 | champions | -0.0372 | -0.0513 | -0.0236 |
| 15 | gold | 2024 | stats | 1106 | 0.5504 | 0.1867 | 0.7052 | 0.0301 | 0.5497 | stats | 0 | 0 | 0 |
| 15 | gold | 2024 | stats_elo | 1106 | 0.5136 | 0.1720 | 0.7505 | 0.0331 | 0.5132 | stats | -0.0368 | -0.0523 | -0.0217 |
| 15 | gold | 2025 | champions | 1309 | 0.5673 | 0.1935 | 0.6982 | 0.0301 | 0.5670 | champions | 0 | 0 | 0 |
| 15 | gold | 2025 | champions_elo | 1309 | 0.5260 | 0.1771 | 0.7250 | 0.0277 | 0.5245 | champions | -0.0413 | -0.0527 | -0.0304 |
| 15 | gold | 2025 | stats | 1309 | 0.5659 | 0.1930 | 0.6975 | 0.0183 | 0.5658 | stats | 0 | 0 | 0 |
| 15 | gold | 2025 | stats_elo | 1309 | 0.5233 | 0.1760 | 0.7242 | 0.0420 | 0.5228 | stats | -0.0426 | -0.0544 | -0.0310 |
| 20 | aura_features | 2023 | champions | 1233 | 0.4260 | 0.1378 | 0.8078 | 0.0258 | 0.4261 | champions | 0 | 0 | 0 |
| 20 | aura_features | 2023 | champions_elo | 1233 | 0.4073 | 0.1306 | 0.8135 | 0.0207 | 0.4077 | champions | -0.0186 | -0.0287 | -0.0090 |
| 20 | aura_features | 2023 | stats | 1233 | 0.4280 | 0.1375 | 0.8086 | 0.0334 | 0.4273 | stats | 0 | 0 | 0 |
| 20 | aura_features | 2023 | stats_elo | 1233 | 0.4128 | 0.1322 | 0.8167 | 0.0229 | 0.4127 | stats | -0.0152 | -0.0259 | -0.0051 |
| 20 | aura_features | 2024 | champions | 1106 | 0.4744 | 0.1566 | 0.7613 | 0.0375 | 0.4756 | champions | 0 | 0 | 0 |
| 20 | aura_features | 2024 | champions_elo | 1106 | 0.4477 | 0.1474 | 0.7857 | 0.0317 | 0.4482 | champions | -0.0267 | -0.0374 | -0.0167 |
| 20 | aura_features | 2024 | stats | 1106 | 0.4733 | 0.1554 | 0.7694 | 0.0409 | 0.4716 | stats | 0 | 0 | 0 |
| 20 | aura_features | 2024 | stats_elo | 1106 | 0.4443 | 0.1460 | 0.7749 | 0.0345 | 0.4433 | stats | -0.0290 | -0.0413 | -0.0171 |
| 20 | aura_features | 2025 | champions | 1309 | 0.4513 | 0.1487 | 0.7838 | 0.0304 | 0.4501 | champions | 0 | 0 | 0 |
| 20 | aura_features | 2025 | champions_elo | 1309 | 0.4341 | 0.1422 | 0.7869 | 0.0278 | 0.4342 | champions | -0.0172 | -0.0264 | -0.0082 |
| 20 | aura_features | 2025 | stats | 1309 | 0.4542 | 0.1504 | 0.7693 | 0.0251 | 0.4535 | stats | 0 | 0 | 0 |
| 20 | aura_features | 2025 | stats_elo | 1309 | 0.4336 | 0.1425 | 0.7861 | 0.0374 | 0.4329 | stats | -0.0207 | -0.0303 | -0.0112 |
| 20 | gold | 2023 | champions | 1233 | 0.4371 | 0.1421 | 0.7948 | 0.0285 | 0.4370 | champions | 0 | 0 | 0 |
| 20 | gold | 2023 | champions_elo | 1233 | 0.4180 | 0.1348 | 0.8078 | 0.0255 | 0.4183 | champions | -0.0191 | -0.0292 | -0.0095 |
| 20 | gold | 2023 | stats | 1233 | 0.4429 | 0.1436 | 0.7981 | 0.0290 | 0.4425 | stats | 0 | 0 | 0 |
| 20 | gold | 2023 | stats_elo | 1233 | 0.4279 | 0.1383 | 0.8013 | 0.0255 | 0.4281 | stats | -0.0150 | -0.0257 | -0.0050 |
| 20 | gold | 2024 | champions | 1106 | 0.4800 | 0.1591 | 0.7694 | 0.0367 | 0.4805 | champions | 0 | 0 | 0 |
| 20 | gold | 2024 | champions_elo | 1106 | 0.4548 | 0.1498 | 0.7848 | 0.0288 | 0.4550 | champions | -0.0252 | -0.0359 | -0.0153 |
| 20 | gold | 2024 | stats | 1106 | 0.4800 | 0.1590 | 0.7649 | 0.0285 | 0.4795 | stats | 0 | 0 | 0 |
| 20 | gold | 2024 | stats_elo | 1106 | 0.4555 | 0.1503 | 0.7749 | 0.0232 | 0.4552 | stats | -0.0244 | -0.0359 | -0.0131 |
| 20 | gold | 2025 | champions | 1309 | 0.4688 | 0.1551 | 0.7670 | 0.0342 | 0.4664 | champions | 0 | 0 | 0 |
| 20 | gold | 2025 | champions_elo | 1309 | 0.4452 | 0.1460 | 0.7876 | 0.0307 | 0.4429 | champions | -0.0237 | -0.0327 | -0.0147 |
| 20 | gold | 2025 | stats | 1309 | 0.4674 | 0.1548 | 0.7662 | 0.0294 | 0.4676 | stats | 0 | 0 | 0 |
| 20 | gold | 2025 | stats_elo | 1309 | 0.4428 | 0.1452 | 0.7846 | 0.0291 | 0.4426 | stats | -0.0246 | -0.0337 | -0.0155 |

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

## Limits and decision

Inspect annual consistency, raw versus calibrated scores and uncertainty before choosing a candidate. These viewed folds support development, not final validation or market profitability. Any candidate needs new untouched matches and synchronized live inputs/prices. Ratings reflect starters; live inference needs the confirmed lineup. Earlier series maps may inform later maps when results are available, but archive timestamps alone do not prove availability. Complete-case league coverage remains uneven.
