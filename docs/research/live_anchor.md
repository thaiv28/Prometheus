# Live anchor research

Local OE out-of-year FORGE/Elo backtests, feed timelines and priced live benchmark; train 2024 feed, calibration 2025 H1, test from 2025-07-01. The test chronology was already viewed by earlier studies, so results are retrospective. Fixed C=1 and map weights; 2,000 paired series-bootstrap draws, seed 42. Negative log-loss deltas favor the candidate. B1 replaces Elo with logit(FORGE); B2 adds it. C removes global calibration only.

A candidate passes when its primary delta's 95% interval is entirely below 0 and no reported slice's interval is entirely above 0.

FORGE table: 17867 maps. A kept/dropped 1271/2075 maps; 567 series.

## A: pregame

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| forge−current/all|1271|-0.0111|[-0.0209, -0.0019] |
| forge−current/map1|539|-0.0033|[-0.0149, +0.0082] |
| forge−current/map2+|732|-0.0168|[-0.0298, -0.0034] |
| forge−current/Majors|1190|-0.0104|[-0.0210, -0.0001] |
| forge−current/International|71|-0.0179|[-0.0685, +0.0292] |
| forge−current/Other|10|-0.0437|[-0.1244, +0.0370] |
| elo−current/all|1271|-0.0082|[-0.0177, +0.0013] |
| elo−current/map1|539|+0.0018|[-0.0101, +0.0136] |
| elo−current/map2+|732|-0.0155|[-0.0282, -0.0022] |
| elo−current/Majors|1190|-0.0073|[-0.0173, +0.0028] |
| elo−current/International|71|-0.0179|[-0.0685, +0.0292] |
| elo−current/Other|10|-0.0437|[-0.1244, +0.0370] |
| current+shift−current/all|1271|-0.0044|[-0.0077, -0.0013] |
| current+shift−current/map1|539|+0.0000|[-0.0000, +0.0000] |
| current+shift−current/map2+|732|-0.0077|[-0.0135, -0.0025] |
| current+shift−current/Majors|1190|-0.0035|[-0.0064, -0.0006] |
| current+shift−current/International|71|-0.0226|[-0.0486, -0.0005] |
| current+shift−current/Other|10|+0.0085|[-0.0131, +0.0278] |
| forge−current+shift/all|1271|-0.0066|[-0.0147, +0.0012] |
| forge unshifted−current/all|1271|-0.0091|[-0.0180, -0.0005] |
| current−Kalshi/all|1221|+0.0021|[-0.0105, +0.0151] |
| forge−Kalshi/all|1221|-0.0086|[-0.0172, +0.0003] |
| elo−Kalshi/all|1221|-0.0051|[-0.0141, +0.0039] |
| Kalshi−current/all|1221|-0.0021|[-0.0151, +0.0105] |
| Kalshi−current/map1|505|+0.0052|[-0.0133, +0.0233] |
| Kalshi−current/map2+|716|-0.0072|[-0.0240, +0.0098] |
| Kalshi−current/Majors|1141|-0.0026|[-0.0167, +0.0104] |
| Kalshi−current/International|70|+0.0146|[-0.0308, +0.0622] |
| Kalshi−current/Other|10|-0.0628|[-0.1576, +0.0139] |

Current: LL 0.6384, Brier 0.2227, ECE10 0.0566.
FORGE: LL 0.6274, Brier 0.2189, ECE10 0.0290.
Elo: LL 0.6302, Brier 0.2202, ECE10 0.0279.
Kalshi (valid subset): LL 0.6362, Brier 0.2226, ECE10 0.0499.
Verdict A: PASS.

## B: anchor

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| B1−prod/all|2266|+0.0023|[-0.0014, +0.0060] |
| B1−prod/0–5|2266|+0.0009|[-0.0046, +0.0059] |
| B1−prod/5–10|2266|+0.0007|[-0.0046, +0.0055] |
| B1−prod/10–20|2265|+0.0010|[-0.0034, +0.0049] |
| B1−prod/20–30|2264|+0.0028|[-0.0005, +0.0060] |
| B1−prod/30+|1282|+0.0075|[+0.0031, +0.0124] |
| B1−prod/Majors|2098|+0.0026|[-0.0010, +0.0063] |
| B1−prod/International|168|-0.0019|[-0.0182, +0.0139] |
| B1−prod/Other|0|—|— |
| B1−control/all|2266|-0.0006|[-0.0034, +0.0021] |
| B1−control/0–5|2266|-0.0000|[-0.0043, +0.0040] |
| B1−control/5–10|2266|-0.0008|[-0.0048, +0.0029] |
| B1−control/10–20|2265|-0.0012|[-0.0043, +0.0018] |
| B1−control/20–30|2264|-0.0007|[-0.0028, +0.0013] |
| B1−control/30+|1282|+0.0009|[-0.0014, +0.0031] |
| B1−control/Majors|2098|-0.0004|[-0.0030, +0.0022] |
| B1−control/International|168|-0.0032|[-0.0219, +0.0158] |
| B1−control/Other|0|—|— |
| B2−prod/all|2266|+0.0025|[-0.0022, +0.0070] |
| B2−prod/0–5|2266|+0.0012|[-0.0047, +0.0065] |
| B2−prod/5–10|2266|+0.0010|[-0.0052, +0.0064] |
| B2−prod/10–20|2265|+0.0012|[-0.0041, +0.0063] |
| B2−prod/20–30|2264|+0.0027|[-0.0018, +0.0070] |
| B2−prod/30+|1282|+0.0079|[+0.0019, +0.0142] |
| B2−prod/Majors|2098|+0.0027|[-0.0019, +0.0073] |
| B2−prod/International|168|-0.0002|[-0.0230, +0.0224] |
| B2−prod/Other|0|—|— |

B kept/dropped maps: train 1520/1237; calibration 877/942; test 2266/1627.
B1: LL 0.4853, Brier 0.1613, ECE10 0.0351.
B2: LL 0.4856, Brier 0.1614, ECE10 0.0366.
Control: LL 0.4860, Brier 0.1617, ECE10 0.0294.
Production: LL 0.4831, Brier 0.1606, ECE10 0.0234.
Verdict B: FAIL.

## C: calibration

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| raw−cal/all|3893|-0.0015|[-0.0030, -0.0002] |
| raw−cal/0–5|3893|-0.0045|[-0.0063, -0.0027] |
| raw−cal/5–10|3893|-0.0037|[-0.0055, -0.0019] |
| raw−cal/10–20|3892|-0.0019|[-0.0036, -0.0003] |
| raw−cal/20–30|3886|-0.0011|[-0.0026, +0.0003] |
| raw−cal/30+|2158|+0.0013|[-0.0004, +0.0029] |
| raw−cal/Majors|3100|-0.0014|[-0.0030, +0.0000] |
| raw−cal/International|305|+0.0012|[-0.0032, +0.0051] |
| raw−cal/Other|488|-0.0038|[-0.0078, -0.0001] |
| live raw−cal/all|1657|-0.0004|[-0.0026, +0.0018] |
| live raw−cal/5m|1551|-0.0028|[-0.0060, +0.0003] |
| live raw−cal/10m|1574|-0.0018|[-0.0046, +0.0011] |
| live raw−cal/15m|1590|-0.0011|[-0.0039, +0.0017] |
| live raw−cal/20m|1589|-0.0019|[-0.0047, +0.0007] |
| live raw−cal/25m|1572|+0.0000|[-0.0024, +0.0025] |
| live raw−cal/30m|1193|+0.0030|[+0.0002, +0.0055] |

Feed calibrated: LL 0.4655, Brier 0.1542, ECE10 0.0193.
Feed raw: LL 0.4639, Brier 0.1538, ECE10 0.0089.
Live calibrated: LL 0.4622, Brier 0.1527, ECE10 0.0307.
Live raw: LL 0.4618, Brier 0.1529, ECE10 0.0277.
Verdict C: FAIL (needs the feed rule and no significantly worse live checkpoint).

B1 + raw skipped: B and C did not both pass.

Reproduce: `uv run python scripts/research/live_anchor.py`.
