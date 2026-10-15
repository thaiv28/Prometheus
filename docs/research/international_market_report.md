# International calls against Kalshi

## Scope and limitations

Base commit `36a1e6e`, generated 2026-10-14T22:13:48.708868+00:00. Current published ratings rebuilt from a private DB; saved odds, methods and home leagues are discarded. Prices/outcomes come from a fixed copied frames.pkl cohort. No new market fetching or forecast refitting.

Price cohort: 2025-12-11 05:00:00+00:00 to 2026-09-30 18:00:00+00:00; DB through 2026-10-11 15:58:23. Matched 2345 / 2398 series and 1383 / 1444 map-1 contracts. International non-qualifier sample: 104 series, 48 maps. No Worlds fixture is in this price cohort.

International means an OE INTERNATIONAL_LEAGUES event, excluding Kalshi titles containing ‘qualifier’ or ‘regional finals’ (three LPL regional-final series are labelled Worlds in OE). Same-home-region fixtures at these events are reported separately. Regional home leagues are as known at the forecast cutoff.

At both the close and 12h, our call uses only games before the UTC calendar day of that cutoff, as production does. This matches the day-level information policy, not Kalshi's hour-level freshness: same-day games/news are omitted. Untimed starts are excluded from lead-time comparisons. Map-1 early quotes are unavailable in the saved frames.

Series format is reconstructed from completed scores and checked against the saved best-of; this is a retrospective format assumption, not proof the format was available before start. Published fitted weights/rho include evaluated periods and prior experiments viewed these outcomes. This is a diagnostic, not held-out model selection or a trading result.

LL is log loss (lower is better). Elo LL removes Form but retains the published forecast curve and series correlation; on cross-region fixtures it is exactly the published Elo forecast. Intervals resample paired series, 4,000 draws, fixed seed; maps are map 1 only. Small slices and multiple comparisons are descriptive; intervals are withheld below 10 fixtures. Event-cluster intervals below are especially weak with few events.

## Series at the close

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| All international events | 104 | 0.5875 | 0.5844 | 0.5462 | +0.0413 [-0.0325, +0.1101] | +0.0382 [-0.0367, +0.1073] |
| Cross-region | 95 | 0.5716 | 0.5716 | 0.5269 | +0.0447 [-0.0389, +0.1192] | +0.0447 [-0.0389, +0.1192] |
| Same-region at international events | 9 | 0.7544 | 0.7190 | 0.7497 | +0.0047 (n < 10) | -0.0307 (n < 10) |

## Same series, close versus 12 hours

84 exactly timed series priced at both cutoffs.

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Close | 84 | 0.5750 | 0.5693 | 0.5358 | +0.0393 [-0.0488, +0.1189] | +0.0336 [-0.0556, +0.1146] |
| Close: either team's first appearance | 27 | 0.5381 | 0.5375 | 0.3783 | +0.1598 [+0.0703, +0.2663] | +0.1592 [+0.0710, +0.2650] |
| Close: later appearances | 57 | 0.5926 | 0.5844 | 0.6103 | -0.0178 [-0.1358, +0.0871] | -0.0259 [-0.1445, +0.0781] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| 12h, rebuilt at that cutoff | 84 | 0.5755 | 0.5703 | 0.5670 | +0.0085 [-0.0830, +0.0923] | +0.0034 [-0.0894, +0.0878] |
| 12h: either team's first appearance | 27 | 0.5345 | 0.5339 | 0.4218 | +0.1127 [-0.0433, +0.2476] | +0.1121 [-0.0403, +0.2455] |
| 12h: later appearances | 57 | 0.5949 | 0.5876 | 0.6358 | -0.0409 [-0.1500, +0.0590] | -0.0482 [-0.1578, +0.0528] |

## Senior events versus academy invitational

WSCI is an academy event; report separately from MSI/First Stand/EWC.

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Senior events | 59 | 0.6417 | 0.6388 | 0.6009 | +0.0407 [-0.0428, +0.1141] | +0.0378 [-0.0456, +0.1125] |
| Academy WSCI | 45 | 0.5164 | 0.5131 | 0.4744 | +0.0420 [-0.0986, +0.1603] | +0.0387 [-0.0990, +0.1565] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Cross-region, close | 76 | 0.5496 | 0.5496 | 0.5058 | +0.0438 [-0.0549, +0.1318] | +0.0438 [-0.0549, +0.1318] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Cross-region, 12h | 76 | 0.5510 | 0.5510 | 0.5349 | +0.0162 [-0.0841, +0.1059] | +0.0162 [-0.0841, +0.1059] |

## Events at the close

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Esports World Cup 2026 | 26 | 0.6979 | 0.6852 | 0.6709 | +0.0271 [-0.0504, +0.1021] | +0.0143 [-0.0686, +0.0935] |
| First Stand 2026 | 13 | 0.5605 | 0.5729 | 0.5385 | +0.0220 [-0.1461, +0.1641] | +0.0344 [-0.1372, +0.1785] |
| Mid-Season Invitational 2026 | 20 | 0.6212 | 0.6212 | 0.5506 | +0.0706 [-0.1311, +0.2367] | +0.0706 [-0.1311, +0.2367] |
| World Star Challengers Invitational 2026 | 45 | 0.5164 | 0.5131 | 0.4744 | +0.0420 [-0.0986, +0.1603] | +0.0387 [-0.0990, +0.1565] |

## Region pairs at the close

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| AM / LCKC | 2 | 0.2744 | 0.2744 | 0.1894 | +0.0850 (n < 10) | +0.0850 (n < 10) |
| AM / LES | 2 | 1.0326 | 1.0326 | 0.8539 | +0.1787 (n < 10) | +0.1787 (n < 10) |
| AM / PCS | 1 | 1.2408 | 1.2408 | 0.2712 | +0.9697 (n < 10) | +0.9697 (n < 10) |
| CBLOL / LCK | 3 | 0.1054 | 0.1054 | 0.0580 | +0.0474 (n < 10) | +0.0474 (n < 10) |
| CBLOL / LCS | 3 | 0.8920 | 0.8920 | 0.8837 | +0.0083 (n < 10) | +0.0083 (n < 10) |
| CBLOL / LEC | 1 | 0.2826 | 0.2826 | 0.2326 | +0.0500 (n < 10) | +0.0500 (n < 10) |
| CBLOL / LPL | 2 | 0.1431 | 0.1431 | 0.0824 | +0.0606 (n < 10) | +0.0606 (n < 10) |
| CD / LCKC | 2 | 0.2396 | 0.2396 | 0.1441 | +0.0955 (n < 10) | +0.0955 (n < 10) |
| CD / LJL | 2 | 0.9735 | 0.9735 | 0.6073 | +0.3662 (n < 10) | +0.3662 (n < 10) |
| CD / NACL | 2 | 0.3230 | 0.3230 | 0.4660 | -0.1430 (n < 10) | -0.1430 (n < 10) |
| LCK / LCP | 2 | 0.1018 | 0.1018 | 0.0463 | +0.0555 (n < 10) | +0.0555 (n < 10) |
| LCK / LCS | 5 | 0.0713 | 0.0713 | 0.0713 | +0.0000 (n < 10) | +0.0000 (n < 10) |
| LCK / LEC | 9 | 0.9918 | 0.9918 | 1.1100 | -0.1182 (n < 10) | -0.1182 (n < 10) |
| LCK / LPL | 10 | 0.7561 | 0.7561 | 0.6067 | +0.1494 [-0.0077, +0.3178] | +0.1494 [-0.0077, +0.3178] |
| LCKC / LES | 2 | 0.7584 | 0.7584 | 0.5426 | +0.2157 (n < 10) | +0.2157 (n < 10) |
| LCKC / LFL | 3 | 0.4788 | 0.4788 | 0.5724 | -0.0936 (n < 10) | -0.0936 (n < 10) |
| LCKC / LJL | 2 | 0.2742 | 0.2742 | 0.0672 | +0.2070 (n < 10) | +0.2070 (n < 10) |
| LCKC / LRN | 4 | 0.5031 | 0.5031 | 0.7813 | -0.2782 (n < 10) | -0.2782 (n < 10) |
| LCKC / NACL | 3 | 0.5755 | 0.5755 | 0.6320 | -0.0565 (n < 10) | -0.0565 (n < 10) |
| LCKC / PCS | 2 | 0.4050 | 0.4050 | 0.0879 | +0.3172 (n < 10) | +0.3172 (n < 10) |
| LCP / LCS | 2 | 0.5547 | 0.5547 | 0.0579 | +0.4967 (n < 10) | +0.4967 (n < 10) |
| LCP / LEC | 3 | 0.7362 | 0.7362 | 0.4797 | +0.2566 (n < 10) | +0.2566 (n < 10) |
| LCP / LPL | 1 | 1.5117 | 1.5117 | 2.9004 | -1.3887 (n < 10) | -1.3887 (n < 10) |
| LCS / LEC | 3 | 1.0866 | 1.0866 | 1.0517 | +0.0348 (n < 10) | +0.0348 (n < 10) |
| LCS / LPL | 3 | 0.3355 | 0.3355 | 0.2275 | +0.1080 (n < 10) | +0.1080 (n < 10) |
| LCS / VCS | 1 | 0.8572 | 0.8572 | 0.9289 | -0.0717 (n < 10) | -0.0717 (n < 10) |
| LEC / LPL | 6 | 0.6172 | 0.6172 | 0.4871 | +0.1301 (n < 10) | +0.1301 (n < 10) |
| LEC / VCS | 1 | 0.5673 | 0.5673 | 0.3857 | +0.1817 (n < 10) | +0.1817 (n < 10) |
| LES / LFL | 1 | 0.3059 | 0.3059 | 0.3181 | -0.0123 (n < 10) | -0.0123 (n < 10) |
| LES / PCS | 2 | 0.3309 | 0.3309 | 0.3296 | +0.0014 (n < 10) | +0.0014 (n < 10) |
| LFL / VCS | 3 | 0.1592 | 0.1592 | 0.3150 | -0.1558 (n < 10) | -0.1558 (n < 10) |
| LFL / WLRQ | 4 | 0.2451 | 0.2451 | 0.3808 | -0.1357 (n < 10) | -0.1357 (n < 10) |
| LJL / NACL | 2 | 0.5321 | 0.5321 | 0.2259 | +0.3062 (n < 10) | +0.3062 (n < 10) |
| VCS / WLRQ | 1 | 1.0061 | 1.0061 | 0.9742 | +0.0319 (n < 10) | +0.0319 (n < 10) |

## Best-of at the close

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Bo1 | 50 | 0.5075 | 0.5077 | 0.4461 | +0.0614 [-0.0570, +0.1643] | +0.0616 [-0.0576, +0.1647] |
| Bo3 | 14 | 0.9070 | 0.8833 | 0.9050 | +0.0020 [-0.1328, +0.1334] | -0.0217 [-0.1644, +0.1197] |
| Bo5 | 40 | 0.5756 | 0.5756 | 0.5457 | +0.0299 [-0.0878, +0.1422] | +0.0299 [-0.0880, +0.1444] |

## Tournament entry versus later appearances

Proxy only: either team has no earlier game day in the OE event since its first matched fixture. Prior games need no market price. Same-day earlier fixtures are excluded, matching the forecast's day cutoff. Bracket round/stage labels are unavailable; this cannot distinguish Swiss/group/playoff rounds.

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| either team's first appearance | 35 | 0.5799 | 0.5794 | 0.4288 | +0.1511 [+0.0734, +0.2427] | +0.1507 [+0.0754, +0.2414] |
| later appearances | 69 | 0.5913 | 0.5869 | 0.6058 | -0.0145 [-0.1163, +0.0745] | -0.0189 [-0.1234, +0.0716] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Esports World Cup 2026: either team's first appearance | 11 | 0.6984 | 0.6984 | 0.6057 | +0.0927 [-0.0212, +0.2128] | +0.0927 [-0.0212, +0.2128] |
| Esports World Cup 2026: later appearances | 15 | 0.6976 | 0.6756 | 0.7187 | -0.0210 [-0.1241, +0.0697] | -0.0431 [-0.1530, +0.0577] |
| First Stand 2026: either team's first appearance | 4 | 0.3577 | 0.3577 | 0.2459 | +0.1118 (n < 10) | +0.1118 (n < 10) |
| First Stand 2026: later appearances | 9 | 0.6507 | 0.6686 | 0.6686 | -0.0179 (n < 10) | +0.0000 (n < 10) |
| Mid-Season Invitational 2026: either team's first appearance | 6 | 0.4554 | 0.4554 | 0.1974 | +0.2580 (n < 10) | +0.2580 (n < 10) |
| Mid-Season Invitational 2026: later appearances | 14 | 0.6923 | 0.6923 | 0.7020 | -0.0097 [-0.2695, +0.1953] | -0.0097 [-0.2695, +0.1953] |
| World Star Challengers Invitational 2026: either team's first appearance | 14 | 0.6036 | 0.6025 | 0.4411 | +0.1625 [+0.0196, +0.3310] | +0.1613 [+0.0265, +0.3258] |
| World Star Challengers Invitational 2026: later appearances | 31 | 0.4770 | 0.4727 | 0.4894 | -0.0124 [-0.1970, +0.1433] | -0.0167 [-0.1999, +0.1393] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Cross-region: either team's first appearance | 33 | 0.5737 | 0.5737 | 0.4204 | +0.1533 [+0.0695, +0.2490] | +0.1533 [+0.0695, +0.2490] |
| Cross-region: later appearances | 62 | 0.5705 | 0.5705 | 0.5836 | -0.0131 [-0.1268, +0.0896] | -0.0131 [-0.1268, +0.0896] |

## Map 1 at the close

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| All international maps | 48 | 0.5697 | 0.5659 | 0.5703 | -0.0006 [-0.0624, +0.0600] | -0.0044 [-0.0675, +0.0574] |
| Cross-region maps | 43 | 0.5452 | 0.5452 | 0.5392 | +0.0060 [-0.0632, +0.0697] | +0.0060 [-0.0632, +0.0697] |
| Same-region maps | 5 | 0.7809 | 0.7444 | 0.8380 | -0.0571 (n < 10) | -0.0936 (n < 10) |

## Series and map 1 on matched fixtures

47 fixtures have both contracts.

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Series | 47 | 0.6335 | 0.6264 | 0.6162 | +0.0173 [-0.0846, +0.1108] | +0.0102 [-0.0958, +0.1066] |

| Slice | n | Published LL | Elo LL | Kalshi LL | Published − Kalshi (95%) | Elo − Kalshi (95%) |
|---|---:|---:|---:|---:|---|---|
| Map 1 | 47 | 0.5609 | 0.5570 | 0.5696 | -0.0087 [-0.0705, +0.0497] | -0.0125 [-0.0765, +0.0483] |

## Favourite calibration at entry

Each cross-region series oriented toward Elo's favourite. This separates underconfidence from overconfidence; these selected slices are descriptive and do not choose a recalibration curve.

| Appearance | n | Favourite won | Elo mean chance | Kalshi mean chance | Elo picked | Kalshi picked |
|---|---:|---:|---:|---:|---:|---:|
| either team's first appearance | 33 | 66.7% | 72.8% | 71.3% | 66.7% | 78.8% |
| later appearances | 62 | 69.4% | 75.1% | 76.6% | 69.4% | 76.6% |

## Cross-region residuals

Series probabilities oriented toward each region/team. Positive won − ours means underestimated observed wins; positive Kalshi − ours means the market rated it higher. Overlapping rows, selected representatives, tiny samples: these do not identify a regional effect independently of team strength.

| Region/team | n | Won | Our mean chance | Kalshi mean chance | Won − ours | Kalshi − ours |
|---|---:|---:|---:|---:|---:|---:|
| AM | 5 | 40.0% | 21.8% | 39.3% | +18.2% | +17.5% |
| CBLOL | 9 | 11.1% | 18.1% | 12.2% | -7.0% | -5.8% |
| CD | 6 | 33.3% | 29.0% | 35.5% | +4.3% | +6.5% |
| LCK | 29 | 69.0% | 78.0% | 78.3% | -9.0% | +0.4% |
| LCKC | 20 | 75.0% | 60.1% | 78.5% | +14.9% | +18.4% |
| LCP | 8 | 25.0% | 22.8% | 9.9% | +2.2% | -12.9% |
| LCS | 17 | 41.2% | 33.6% | 37.5% | +7.6% | +3.9% |
| LEC | 23 | 47.8% | 45.8% | 43.2% | +2.0% | -2.7% |
| LES | 7 | 57.1% | 65.6% | 55.2% | -8.4% | -10.4% |
| LFL | 11 | 90.9% | 80.1% | 65.3% | +10.8% | -14.9% |
| LJL | 6 | 0.0% | 42.3% | 23.2% | -42.3% | -19.1% |
| LPL | 22 | 63.6% | 53.0% | 59.8% | +10.6% | +6.8% |
| LRN | 4 | 25.0% | 36.3% | 10.7% | -11.3% | -25.6% |
| NACL | 7 | 71.4% | 50.2% | 47.5% | +21.2% | -2.7% |
| PCS | 5 | 0.0% | 38.7% | 19.3% | -38.7% | -19.5% |
| VCS | 6 | 16.7% | 30.2% | 35.2% | -13.6% | +4.9% |
| WLRQ | 5 | 0.0% | 29.9% | 37.5% | -29.9% | +7.6% |

| Region/team | n | Won | Our mean chance | Kalshi mean chance | Won − ours | Kalshi − ours |
|---|---:|---:|---:|---:|---:|---:|
| Anyone's Legend | 3 | 66.7% | 50.1% | 61.8% | +16.6% | +11.8% |
| BNK FEARX | 3 | 33.3% | 72.5% | 69.7% | -39.2% | -2.9% |
| Bilibili Gaming | 10 | 80.0% | 55.3% | 65.3% | +24.7% | +10.0% |
| Bilibili Gaming Junior | 5 | 40.0% | 21.8% | 39.3% | +18.2% | +17.5% |
| CTBC Flying Oyster Academy | 5 | 0.0% | 38.7% | 19.3% | -38.7% | -19.5% |
| Cupid Esports | 7 | 71.4% | 50.2% | 47.5% | +21.2% | -2.7% |
| DN SOOPers Challengers | 3 | 33.3% | 37.6% | 68.1% | -4.3% | +30.4% |
| Deep Cross Gaming | 2 | 0.0% | 24.7% | 4.5% | -24.7% | -20.2% |
| Dplus Kia | 5 | 80.0% | 62.0% | 59.1% | +18.0% | -2.9% |
| Dplus Kia Challengers | 6 | 83.3% | 72.3% | 87.0% | +11.1% | +14.8% |
| FENNEL | 6 | 0.0% | 42.3% | 23.2% | -42.3% | -19.1% |
| FURIA | 4 | 0.0% | 22.3% | 13.3% | -22.3% | -9.0% |
| Fuego | 4 | 25.0% | 36.3% | 10.7% | -11.3% | -25.6% |
| G2 Esports | 12 | 50.0% | 47.3% | 42.1% | +2.7% | -5.2% |
| GAM Esports | 1 | 100.0% | 17.2% | 30.5% | +82.8% | +13.3% |
| Galions | 6 | 83.3% | 82.3% | 62.8% | +1.1% | -19.4% |
| Gen.G | 6 | 83.3% | 90.5% | 93.1% | -7.1% | +2.6% |
| Hanwha Life Esports | 7 | 85.7% | 76.3% | 80.8% | +9.4% | +4.5% |
| JD Gaming | 7 | 57.1% | 50.7% | 54.3% | +6.4% | +3.5% |
| KT Rolster Challengers | 7 | 71.4% | 54.4% | 72.3% | +17.0% | +17.9% |
| Karmine Corp | 9 | 55.6% | 42.5% | 44.6% | +13.1% | +2.2% |
| LOUD | 2 | 0.0% | 15.8% | 14.1% | -15.8% | -1.7% |
| LYON | 10 | 40.0% | 38.2% | 43.0% | +1.8% | +4.8% |
| LØS | 3 | 33.3% | 14.0% | 9.5% | +19.4% | -4.5% |
| Movistar KOI | 2 | 0.0% | 52.1% | 43.0% | -52.1% | -9.1% |
| Movistar KOI Fénix | 7 | 57.1% | 65.6% | 55.2% | -8.4% | -10.4% |
| Saigon Warriors | 4 | 25.0% | 20.1% | 29.6% | +4.9% | +9.5% |
| Sentinels | 3 | 33.3% | 28.9% | 25.1% | +4.5% | -3.8% |
| Solary | 5 | 100.0% | 77.5% | 68.2% | +22.5% | -9.4% |
| T1 | 8 | 50.0% | 82.1% | 80.4% | -32.1% | -1.7% |
| T1 Esports Academy | 4 | 100.0% | 68.7% | 84.1% | +31.3% | +15.4% |
| Team Liquid | 4 | 50.0% | 25.8% | 33.3% | +24.2% | +7.5% |
| Team Secret | 2 | 0.0% | 50.4% | 46.2% | -50.4% | -4.2% |
| Team Secret Whales | 5 | 20.0% | 23.2% | 8.0% | -3.2% | -15.3% |
| Top Esports | 2 | 0.0% | 54.2% | 48.4% | -54.2% | -5.8% |
| Vivo Keyd Stars Academy | 6 | 33.3% | 29.0% | 35.5% | +4.3% | +6.5% |
| ZSK | 5 | 0.0% | 29.9% | 37.5% | -29.9% | +7.6% |

## Event-cluster sensitivity

Paired series LL differences resampled by complete Kalshi tournament title. With very few tournaments these intervals do not establish future-event generalization.

- All international: 4 events; Δ +0.0413, event-cluster 95% [+0.0254, +0.0583].
- Cross-region: 4 events; Δ +0.0447, event-cluster 95% [+0.0306, +0.0618].
