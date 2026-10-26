# Live offset research

Follow-up to [anchor B1](live_anchor.md): logit(FORGE) as a fixed offset (weight 1 at 0:00), fitting only its fade beside production's state terms; no Elo, free side intercept, no global calibration. D fades linearly in time, D2 adds time². Train 2024 feed, test from 2025-07-01 on B's maps; retrospective. Negative deltas favor the candidate; 2,000 paired series-bootstrap draws, seed 42.

A candidate passes when its primary delta's 95% interval is entirely below 0 and no reported slice's interval is entirely above 0. Primary: D−prod.

Test maps: 2266.

## Results

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| D−prod/all|2266|-0.0024|[-0.0062, +0.0011] |
| D−prod/0–5|2266|-0.0091|[-0.0152, -0.0035] |
| D−prod/5–10|2266|-0.0075|[-0.0132, -0.0024] |
| D−prod/10–20|2265|-0.0042|[-0.0087, -0.0003] |
| D−prod/20–30|2264|-0.0013|[-0.0043, +0.0017] |
| D−prod/30+|1282|+0.0072|[+0.0034, +0.0112] |
| D−prod/Majors|2098|-0.0024|[-0.0060, +0.0012] |
| D−prod/International|168|-0.0034|[-0.0203, +0.0131] |
| D−prod/Other|0|—|— |
| D2−prod/all|2266|-0.0026|[-0.0064, +0.0008] |
| D2−prod/0–5|2266|-0.0091|[-0.0150, -0.0036] |
| D2−prod/5–10|2266|-0.0073|[-0.0127, -0.0023] |
| D2−prod/10–20|2265|-0.0040|[-0.0083, -0.0003] |
| D2−prod/20–30|2264|-0.0015|[-0.0045, +0.0014] |
| D2−prod/30+|1282|+0.0056|[+0.0020, +0.0093] |
| D2−prod/Majors|2098|-0.0026|[-0.0062, +0.0009] |
| D2−prod/International|168|-0.0033|[-0.0204, +0.0132] |
| D2−prod/Other|0|—|— |
| D−B1/all|2266|-0.0048|[-0.0079, -0.0016] |
| D−B1/0–5|2266|-0.0098|[-0.0143, -0.0051] |
| D−B1/5–10|2266|-0.0081|[-0.0125, -0.0037] |
| D−B1/10–20|2265|-0.0053|[-0.0089, -0.0017] |
| D−B1/20–30|2264|-0.0042|[-0.0072, -0.0011] |
| D−B1/30+|1282|-0.0001|[-0.0040, +0.0036] |
| D−B1/Majors|2098|-0.0051|[-0.0085, -0.0019] |
| D−B1/International|168|-0.0009|[-0.0107, +0.0088] |
| D−B1/Other|0|—|— |

## Diagnosis

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| Control−prod/all|2266|+0.0030|[+0.0010, +0.0051] |
| Control−prod/20–30|2264|+0.0036|[+0.0011, +0.0062] |
| Control−prod/30+|1282|+0.0070|[+0.0035, +0.0109] |
| Control−D/all|2266|+0.0055|[+0.0020, +0.0093] |
| Control−D/20–30|2264|+0.0048|[+0.0016, +0.0082] |
| Control−D/30+|1282|-0.0002|[-0.0043, +0.0037] |
| Control raw−prod/all|2266|-0.0010|[-0.0037, +0.0017] |
| Control raw−prod/20–30|2264|-0.0007|[-0.0035, +0.0020] |
| Control raw−prod/30+|1282|+0.0062|[+0.0032, +0.0094] |
| Control raw−D/all|2266|+0.0014|[-0.0009, +0.0038] |
| Control raw−D/20–30|2264|+0.0005|[-0.0013, +0.0024] |
| Control raw−D/30+|1282|-0.0011|[-0.0035, +0.0014] |
| D+cal−prod/all|2266|+0.0025|[-0.0012, +0.0061] |
| D+cal−prod/20–30|2264|+0.0039|[+0.0005, +0.0073] |
| D+cal−prod/30+|1282|+0.0089|[+0.0040, +0.0144] |
| D+cal−D/all|2266|+0.0050|[+0.0019, +0.0081] |
| D+cal−D/20–30|2264|+0.0051|[+0.0020, +0.0084] |
| D+cal−D/30+|1282|+0.0017|[-0.0022, +0.0059] |
| D+elo_time−prod/all|2266|-0.0023|[-0.0068, +0.0020] |
| D+elo_time−prod/20–30|2264|-0.0011|[-0.0052, +0.0028] |
| D+elo_time−prod/30+|1282|+0.0074|[+0.0019, +0.0130] |
| D+elo_time−D/all|2266|+0.0001|[-0.0009, +0.0011] |
| D+elo_time−D/20–30|2264|+0.0002|[-0.0012, +0.0015] |
| D+elo_time−D/30+|1282|+0.0002|[-0.0021, +0.0027] |
| D+elo−prod/all|2266|-0.0025|[-0.0068, +0.0017] |
| D+elo−prod/20–30|2264|-0.0013|[-0.0054, +0.0026] |
| D+elo−prod/30+|1282|+0.0064|[+0.0009, +0.0118] |
| D+elo−D/all|2266|-0.0001|[-0.0010, +0.0009] |
| D+elo−D/20–30|2264|-0.0001|[-0.0014, +0.0013] |
| D+elo−D/30+|1282|-0.0008|[-0.0033, +0.0017] |
| E−prod/all|2266|-0.0020|[-0.0052, +0.0011] |
| E−prod/20–30|2264|-0.0014|[-0.0043, +0.0014] |
| E−prod/30+|1282|+0.0062|[+0.0029, +0.0097] |
| E−D/all|2266|+0.0004|[-0.0010, +0.0019] |
| E−D/20–30|2264|-0.0001|[-0.0013, +0.0011] |
| E−D/30+|1282|-0.0010|[-0.0025, +0.0005] |

D+cal slope 1.124.
Control: LL 0.4861, Brier 0.1616, ECE10 0.0296.
Control raw: LL 0.4820, Brier 0.1606, ECE10 0.0098.
D+cal: LL 0.4855, Brier 0.1613, ECE10 0.0351.
D+elo_time: LL 0.4807, Brier 0.1599, ECE10 0.0099.
D+elo: LL 0.4805, Brier 0.1598, ECE10 0.0111.
E: LL 0.4810, Brier 0.1601, ECE10 0.0105.

D: LL 0.4806, Brier 0.1599, ECE10 0.0099.
D2: LL 0.4804, Brier 0.1598, ECE10 0.0103.
B1: LL 0.4853, Brier 0.1613, ECE10 0.0354.
Production: LL 0.4830, Brier 0.1606, ECE10 0.0237.

FORGE log-odds weight by minute (0, 10, 20, 30, 40):
- D: 1.00, 0.90, 0.80, 0.70, 0.60
- D2: 1.00, 0.94, 0.82, 0.64, 0.40
- D side intercept: +0.056 log-odds.

Verdict: FAIL.

## Full sample (F)

Declared after the diagnosis: D's design fit on all 2757 train maps, offset logit(FORGE) where the backtest has it, else the 400-scale Elo chance from the map's pre-match ratings. Primary F−prod on all 3893 test maps under the rule above; FORGE maps secondary. Retrospective on a viewed split: a pass marks F for prospective checks only.

| Comparison/slice|n maps|Delta LL|95% interval |
|---|---:|---:|---|
| F−prod/all|3893|-0.0008|[-0.0035, +0.0019] |
| F−prod/0–5|3893|-0.0039|[-0.0089, +0.0011] |
| F−prod/5–10|3893|-0.0040|[-0.0081, +0.0001] |
| F−prod/10–20|3892|-0.0024|[-0.0054, +0.0005] |
| F−prod/20–30|3886|-0.0011|[-0.0032, +0.0008] |
| F−prod/30+|2158|+0.0030|[+0.0006, +0.0054] |
| F−prod/Majors|3100|-0.0013|[-0.0041, +0.0015] |
| F−prod/International|305|+0.0038|[-0.0092, +0.0167] |
| F−prod/Other|488|-0.0005|[-0.0110, +0.0093] |
| F−prod FORGE maps/all|2266|-0.0037|[-0.0068, -0.0008] |
| F−prod FORGE maps/0–5|2266|-0.0079|[-0.0137, -0.0026] |
| F−prod FORGE maps/20–30|2264|-0.0022|[-0.0048, +0.0002] |
| F−prod FORGE maps/30+|1282|+0.0031|[-0.0002, +0.0063] |

F: LL 0.4645, Brier 0.1538, ECE10 0.0086.
Production (all maps): LL 0.4653, Brier 0.1541, ECE10 0.0194.
F prior weight by minute: 1.00, 0.94, 0.88, 0.82, 0.77; side intercept +0.120.
Verdict F: FAIL.

Reproduce: `uv run python scripts/research/live_offset.py` (needs `live_anchor.py`'s inputs).
