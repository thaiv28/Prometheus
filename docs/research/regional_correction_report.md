# Regional Elo correction: first development experiment

Research only; no adoption, DB writes, published weights or live calls changed. Grid fixed in code before scoring (ridge 1/4/16; half-life 365/1460/infinite days); persistent and dynamic settings selected through 2021, then frozen for 2022+. Calibration and regional coefficients are re-fit before each event from completed earlier events only.

Baseline is the current published cross-region curve on production main-roster Elo before each UTC day. Current Elo's algorithm/hyperparameters and baseline slope have previously seen later periods. Candidates fit scale and regional effects on earlier events only; results remain retrospective development evidence.

Regional effects are ridge-shrunk to zero and sum to zero. Dynamic means an exponential half-life on older evidence, not a Bayesian uncertainty filter. No team residual or uncertainty integration is implemented. Map outcomes train a logistic likelihood; each unordered team-pair/day totals weight one to limit series dependence. One pooled positive scale multiplies Elo's logit; no intercept, so predictions reverse on swapping teams.

Event blocks are league/year with breaks longer than 21 days. Corrections are frozen at event start; existing Elo still learns from previous days inside that event. Same-day results never enter that day's forecasts. Known 2026 qualifier/regional-final days and EWC outside the matched main-event window are excluded using market metadata, never prices or market outcomes. Other historical event labels inherit OE limitations. Entry is based on first eligible cross-region game day, not bracket round or every same-region game.

Training is cross-region international-labelled maps. Same-home-region forecasts and all domestic/non-international routes are unchanged by construction; this is not a production benchmark-gate run. Series odds keep current rho. Series format and diagnostic fixture provenance retain their retrospective limitations. Kalshi fitting inputs are never used. Primary market endpoint is 12h on the fixed cohort; close is separate. 2026 prices cover four previously viewed events and no Worlds. No prospective market-beating claim.

Eligible maps: 2177; event blocks: 41; missing-home/same-region exclusions: 491.

## Settings chosen through 2021

| Variant | Ridge | Half-life (days) | Earlier-event tuning LL |
|---|---:|---:|---:|
| calibration | 4 | inf | 0.63126 |
| persistent | 4 | inf | 0.62288 |
| dynamic | 1 | 365 | 0.62091 |

## Chronological maps

| Slice | Maps | Events | Baseline LL | Candidate | Candidate LL | Δ vs published (series-cluster 95%; event sensitivity) | Δ vs calibration |
|---|---:|---:|---:|---|---:|---|---|
| 2022+ all | 1006 | 17 | 0.5918 | calibration | 0.5922 | +0.0004 [-0.0036, +0.0047]; event [-0.0025, +0.0036] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ all | 1006 | 17 | 0.5918 | persistent | 0.5743 | -0.0175 [-0.0272, -0.0075]; event [-0.0276, -0.0065] | -0.0179 [-0.0275, -0.0082]; event [-0.0275, -0.0080] |
| 2022+ all | 1006 | 17 | 0.5918 | dynamic | 0.5828 | -0.0090 [-0.0185, +0.0008]; event [-0.0198, +0.0037] | -0.0094 [-0.0180, -0.0010]; event [-0.0189, +0.0015] |
| 2022+ entry | 267 | 17 | 0.5961 | calibration | 0.6004 | +0.0044 [-0.0040, +0.0130]; event [-0.0024, +0.0114] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ entry | 267 | 17 | 0.5961 | persistent | 0.5623 | -0.0338 [-0.0569, -0.0122]; event [-0.0581, -0.0114] | -0.0381 [-0.0618, -0.0162]; event [-0.0628, -0.0149] |
| 2022+ entry | 267 | 17 | 0.5961 | dynamic | 0.5741 | -0.0219 [-0.0442, -0.0010]; event [-0.0530, +0.0049] | -0.0263 [-0.0475, -0.0067]; event [-0.0572, +0.0001] |
| 2022+ later | 739 | 17 | 0.5902 | calibration | 0.5892 | -0.0010 [-0.0055, +0.0037]; event [-0.0054, +0.0041] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ later | 739 | 17 | 0.5902 | persistent | 0.5786 | -0.0116 [-0.0228, -0.0006]; event [-0.0211, -0.0005] | -0.0106 [-0.0214, -0.0004]; event [-0.0208, -0.0002] |
| 2022+ later | 739 | 17 | 0.5902 | dynamic | 0.5859 | -0.0043 [-0.0149, +0.0064]; event [-0.0144, +0.0083] | -0.0033 [-0.0126, +0.0056]; event [-0.0133, +0.0070] |
| 2022+ senior | 941 | 16 | 0.5927 | calibration | 0.5932 | +0.0004 [-0.0037, +0.0047]; event [-0.0028, +0.0038] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ senior | 941 | 16 | 0.5927 | persistent | 0.5744 | -0.0184 [-0.0291, -0.0079]; event [-0.0290, -0.0061] | -0.0188 [-0.0289, -0.0090]; event [-0.0289, -0.0077] |
| 2022+ senior | 941 | 16 | 0.5927 | dynamic | 0.5837 | -0.0090 [-0.0191, +0.0010]; event [-0.0205, +0.0047] | -0.0095 [-0.0181, -0.0009]; event [-0.0199, +0.0026] |
| 2026 | 255 | 5 | 0.5909 | calibration | 0.5933 | +0.0024 [-0.0077, +0.0139]; event [-0.0050, +0.0078] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2026 | 255 | 5 | 0.5909 | persistent | 0.5839 | -0.0070 [-0.0272, +0.0133]; event [-0.0248, +0.0064] | -0.0094 [-0.0292, +0.0090]; event [-0.0287, +0.0014] |
| 2026 | 255 | 5 | 0.5909 | dynamic | 0.5954 | +0.0045 [-0.0140, +0.0236]; event [-0.0147, +0.0211] | +0.0021 [-0.0140, +0.0167]; event [-0.0137, +0.0156] |
| 2022+ major v major | 556 | 16 | 0.6209 | calibration | 0.6247 | +0.0038 [-0.0016, +0.0094]; event [-0.0003, +0.0081] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ major v major | 556 | 16 | 0.6209 | persistent | 0.6111 | -0.0099 [-0.0199, +0.0008]; event [-0.0189, -0.0008] | -0.0136 [-0.0227, -0.0038]; event [-0.0201, -0.0072] |
| 2022+ major v major | 556 | 16 | 0.6209 | dynamic | 0.6209 | -0.0001 [-0.0116, +0.0117]; event [-0.0106, +0.0118] | -0.0038 [-0.0131, +0.0056]; event [-0.0119, +0.0045] |
| 2022+ major v other | 308 | 15 | 0.5066 | calibration | 0.4981 | -0.0085 [-0.0157, -0.0014]; event [-0.0144, -0.0024] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ major v other | 308 | 15 | 0.5066 | persistent | 0.4865 | -0.0201 [-0.0404, -0.0008]; event [-0.0369, -0.0017] | -0.0116 [-0.0297, +0.0056]; event [-0.0286, +0.0064] |
| 2022+ major v other | 308 | 15 | 0.5066 | dynamic | 0.4902 | -0.0164 [-0.0355, +0.0017]; event [-0.0346, +0.0028] | -0.0079 [-0.0240, +0.0071]; event [-0.0253, +0.0097] |
| 2022+ other v other | 142 | 9 | 0.6622 | calibration | 0.6691 | +0.0069 [-0.0024, +0.0175]; event [+0.0009, +0.0200] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| 2022+ other v other | 142 | 9 | 0.6622 | persistent | 0.6207 | -0.0414 [-0.0810, -0.0057]; event [-0.1119, -0.0085] | -0.0484 [-0.0943, -0.0069]; event [-0.1299, -0.0104] |
| 2022+ other v other | 142 | 9 | 0.6622 | dynamic | 0.6346 | -0.0276 [-0.0565, -0.0002]; event [-0.0685, -0.0083] | -0.0345 [-0.0697, -0.0028]; event [-0.0832, -0.0119] |
| Year 2022 | 193 | 2 | 0.5240 | calibration | 0.5176 | -0.0064 [-0.0117, -0.0007]; event [-0.0080, -0.0041] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| Year 2022 | 193 | 2 | 0.5240 | persistent | 0.4962 | -0.0278 [-0.0504, -0.0061]; event [-0.0287, -0.0266] | -0.0215 [-0.0442, +0.0010]; event [-0.0225, -0.0207] |
| Year 2022 | 193 | 2 | 0.5240 | dynamic | 0.5014 | -0.0226 [-0.0437, -0.0027]; event [-0.0330, -0.0079] | -0.0162 [-0.0365, +0.0034]; event [-0.0250, -0.0038] |
| Year 2023 | 151 | 2 | 0.6181 | calibration | 0.6195 | +0.0014 [-0.0089, +0.0121]; event [-0.0010, +0.0029] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| Year 2023 | 151 | 2 | 0.6181 | persistent | 0.5705 | -0.0476 [-0.0774, -0.0206]; event [-0.0631, -0.0382] | -0.0490 [-0.0804, -0.0209]; event [-0.0621, -0.0411] |
| Year 2023 | 151 | 2 | 0.6181 | dynamic | 0.5814 | -0.0367 [-0.0651, -0.0094]; event [-0.0379, -0.0360] | -0.0381 [-0.0647, -0.0134]; event [-0.0389, -0.0369] |
| Year 2024 | 185 | 3 | 0.6255 | calibration | 0.6303 | +0.0049 [-0.0035, +0.0128]; event [+0.0020, +0.0143] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| Year 2024 | 185 | 3 | 0.6255 | persistent | 0.6089 | -0.0165 [-0.0420, +0.0059]; event [-0.0256, -0.0077] | -0.0214 [-0.0473, +0.0009]; event [-0.0310, -0.0097] |
| Year 2024 | 185 | 3 | 0.6255 | dynamic | 0.6166 | -0.0088 [-0.0347, +0.0146]; event [-0.0200, +0.0226] | -0.0137 [-0.0385, +0.0079]; event [-0.0253, +0.0083] |
| Year 2025 | 222 | 5 | 0.6057 | calibration | 0.6055 | -0.0002 [-0.0077, +0.0074]; event [-0.0056, +0.0068] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| Year 2025 | 222 | 5 | 0.6057 | persistent | 0.6049 | -0.0008 [-0.0176, +0.0175]; event [-0.0227, +0.0250] | -0.0006 [-0.0147, +0.0154]; event [-0.0176, +0.0188] |
| Year 2025 | 222 | 5 | 0.6057 | dynamic | 0.6120 | +0.0063 [-0.0112, +0.0248]; event [-0.0164, +0.0303] | +0.0065 [-0.0069, +0.0213]; event [-0.0112, +0.0241] |
| Year 2026 | 255 | 5 | 0.5909 | calibration | 0.5933 | +0.0024 [-0.0077, +0.0139]; event [-0.0050, +0.0078] | +0.0000 [+0.0000, +0.0000]; event [+0.0000, +0.0000] |
| Year 2026 | 255 | 5 | 0.5909 | persistent | 0.5839 | -0.0070 [-0.0272, +0.0133]; event [-0.0248, +0.0064] | -0.0094 [-0.0292, +0.0090]; event [-0.0287, +0.0014] |
| Year 2026 | 255 | 5 | 0.5909 | dynamic | 0.5954 | +0.0045 [-0.0140, +0.0236]; event [-0.0147, +0.0211] | +0.0021 [-0.0140, +0.0167]; event [-0.0137, +0.0156] |

## Fixed market cohort

| Slice | n | Candidate | LL | Δ vs current Elo (paired series 95%) | Δ vs Kalshi (paired series 95%) |
|---|---:|---|---:|---|---|
| 12h, common cohort (primary) | 76 | calibration | 0.5578 | +0.0068 [-0.0105, +0.0253] | +0.0229 [-0.0788, +0.1170] |
| 12h, common cohort (primary) | 76 | persistent | 0.5542 | +0.0031 [-0.0357, +0.0420] | +0.0193 [-0.0758, +0.1047] |
| 12h, common cohort (primary) | 76 | dynamic | 0.5661 | +0.0150 [-0.0150, +0.0446] | +0.0312 [-0.0661, +0.1192] |
| Close, common cohort | 76 | calibration | 0.5554 | +0.0058 [-0.0111, +0.0240] | +0.0496 [-0.0513, +0.1427] |
| Close, common cohort | 76 | persistent | 0.5528 | +0.0032 [-0.0359, +0.0422] | +0.0470 [-0.0471, +0.1285] |
| Close, common cohort | 76 | dynamic | 0.5635 | +0.0139 [-0.0161, +0.0433] | +0.0577 [-0.0393, +0.1413] |
| Close, all | 95 | calibration | 0.5838 | +0.0122 [-0.0052, +0.0319] | +0.0569 [-0.0236, +0.1318] |
| Close, all | 95 | persistent | 0.5730 | +0.0013 [-0.0347, +0.0377] | +0.0461 [-0.0300, +0.1143] |
| Close, all | 95 | dynamic | 0.5958 | +0.0242 [-0.0078, +0.0585] | +0.0689 [-0.0091, +0.1384] |
| Close: either team's first appearance | 33 | calibration | 0.5831 | +0.0094 [-0.0154, +0.0383] | +0.1627 [+0.0688, +0.2732] |
| Close: either team's first appearance | 33 | persistent | 0.5477 | -0.0261 [-0.0854, +0.0287] | +0.1273 [+0.0327, +0.2351] |
| Close: either team's first appearance | 33 | dynamic | 0.5779 | +0.0041 [-0.0431, +0.0560] | +0.1574 [+0.0661, +0.2628] |
| Close: later appearances | 62 | calibration | 0.5842 | +0.0137 [-0.0091, +0.0412] | +0.0006 [-0.1112, +0.1021] |
| Close: later appearances | 62 | persistent | 0.5864 | +0.0159 [-0.0301, +0.0619] | +0.0029 [-0.1008, +0.0901] |
| Close: later appearances | 62 | dynamic | 0.6054 | +0.0349 [-0.0085, +0.0797] | +0.0218 [-0.0841, +0.1140] |
| Close: Esports World Cup 2026 | 23 | calibration | 0.6934 | +0.0248 [-0.0124, +0.0687] | +0.0659 [-0.0222, +0.1710] |
| Close: Esports World Cup 2026 | 23 | persistent | 0.6191 | -0.0494 [-0.1149, +0.0230] | -0.0084 [-0.1001, +0.0879] |
| Close: Esports World Cup 2026 | 23 | dynamic | 0.6635 | -0.0051 [-0.0646, +0.0667] | +0.0360 [-0.0585, +0.1405] |
| Close: First Stand 2026 | 12 | calibration | 0.6177 | +0.0317 [-0.0306, +0.1237] | +0.0498 [-0.0621, +0.1738] |
| Close: First Stand 2026 | 12 | persistent | 0.6212 | +0.0352 [-0.0796, +0.1739] | +0.0534 [-0.0534, +0.1808] |
| Close: First Stand 2026 | 12 | dynamic | 0.6727 | +0.0868 [-0.0464, +0.2416] | +0.1049 [+0.0079, +0.2455] |
| Close: Mid-Season Invitational 2026 | 20 | calibration | 0.6519 | +0.0307 [-0.0072, +0.0733] | +0.1013 [-0.0788, +0.2641] |
| Close: Mid-Season Invitational 2026 | 20 | persistent | 0.6599 | +0.0387 [-0.0366, +0.1296] | +0.1093 [-0.0440, +0.2526] |
| Close: Mid-Season Invitational 2026 | 20 | dynamic | 0.6946 | +0.0734 [+0.0034, +0.1512] | +0.1440 [-0.0296, +0.3119] |
| Close: World Star Challengers Invitational 2026 | 40 | calibration | 0.4766 | -0.0102 [-0.0280, +0.0107] | +0.0317 [-0.1305, +0.1769] |
| Close: World Star Challengers Invitational 2026 | 40 | persistent | 0.4885 | +0.0017 [-0.0509, +0.0459] | +0.0436 [-0.1097, +0.1648] |
| Close: World Star Challengers Invitational 2026 | 40 | dynamic | 0.4845 | -0.0024 [-0.0373, +0.0272] | +0.0395 [-0.1106, +0.1593] |
| Map 1 close | 43 | calibration | 0.5406 | -0.0046 [-0.0216, +0.0152] | +0.0013 [-0.0664, +0.0664] |
| Map 1 close | 43 | persistent | 0.5346 | -0.0106 [-0.0463, +0.0269] | -0.0046 [-0.0589, +0.0492] |
| Map 1 close | 43 | dynamic | 0.5557 | +0.0105 [-0.0210, +0.0444] | +0.0165 [-0.0454, +0.0768] |

