# Series score and earlier drafts

Protocol fixed before scoring in `scripts/research/series_score.py`.
One primary posterior; existing rho is descriptive; one exploratory two-feature adaptation candidate. Negative is better.
Series grouping includes maps without draft coverage. p0 freezes the first production call; posterior uses earlier results only.

| Test year | Training-only rho |
|---|---:|
| 2021 | 0.0940 |
| 2022 | 0.0948 |
| 2023 | 0.0914 |
| 2024 | 0.0898 |
| 2025 | 0.0944 |
| 2026 | 0.0916 |

## posterior − constant

| Slice | Maps | Candidate LL | Control LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 26,885 | 0.6319 | 0.6374 | -0.0055 (-0.0067 to -0.0043) |
| major leagues | 5,807 | 0.6336 | 0.6340 | -0.0004 (-0.0028 to +0.0020) |
| LPL | 2,735 | 0.6413 | 0.6413 | -0.0000 (-0.0034 to +0.0035) |
| international | 865 | 0.6337 | 0.6375 | -0.0038 (-0.0110 to +0.0028) |
| other leagues | 20,213 | 0.6313 | 0.6383 | -0.0070 (-0.0085 to -0.0056) |
| before 2025 | 16,609 | 0.6396 | 0.6448 | -0.0052 (-0.0067 to -0.0037) |
| 2021 | 4,127 | 0.6468 | 0.6521 | -0.0053 (-0.0085 to -0.0021) |
| 2022 | 3,795 | 0.6451 | 0.6492 | -0.0041 (-0.0075 to -0.0009) |
| 2023 | 4,377 | 0.6390 | 0.6432 | -0.0042 (-0.0072 to -0.0015) |
| 2024 | 4,310 | 0.6285 | 0.6356 | -0.0071 (-0.0100 to -0.0041) |
| 2025 | 5,103 | 0.6299 | 0.6333 | -0.0034 (-0.0062 to -0.0006) |
| 2026 | 5,173 | 0.6090 | 0.6175 | -0.0085 (-0.0112 to -0.0057) |
| map 2 | 15,657 | 0.6184 | 0.6227 | -0.0043 (-0.0058 to -0.0029) |
| map 3+ | 11,228 | 0.6507 | 0.6578 | -0.0071 (-0.0092 to -0.0051) |
| repeat-free complete prefix | 11,062 | 0.6209 | 0.6265 | -0.0056 (-0.0077 to -0.0038) |
| repeated complete prefix | 15,823 | 0.6395 | 0.6450 | -0.0054 (-0.0069 to -0.0038) |

## fixed_rho − constant

| Slice | Maps | Candidate LL | Control LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 26,885 | 0.6316 | 0.6374 | -0.0058 (-0.0072 to -0.0043) |
| major leagues | 5,807 | 0.6327 | 0.6340 | -0.0013 (-0.0028 to +0.0002) |
| LPL | 2,735 | 0.6402 | 0.6413 | -0.0011 (-0.0032 to +0.0010) |
| international | 865 | 0.6345 | 0.6375 | -0.0031 (-0.0126 to +0.0057) |
| other leagues | 20,213 | 0.6312 | 0.6383 | -0.0072 (-0.0091 to -0.0053) |
| before 2025 | 16,609 | 0.6395 | 0.6448 | -0.0053 (-0.0072 to -0.0035) |
| 2021 | 4,127 | 0.6478 | 0.6521 | -0.0043 (-0.0082 to -0.0005) |
| 2022 | 3,795 | 0.6439 | 0.6492 | -0.0053 (-0.0093 to -0.0014) |
| 2023 | 4,377 | 0.6393 | 0.6432 | -0.0039 (-0.0076 to -0.0006) |
| 2024 | 4,310 | 0.6278 | 0.6356 | -0.0078 (-0.0115 to -0.0041) |
| 2025 | 5,103 | 0.6298 | 0.6333 | -0.0035 (-0.0069 to -0.0000) |
| 2026 | 5,173 | 0.6081 | 0.6175 | -0.0094 (-0.0128 to -0.0060) |
| map 2 | 15,657 | 0.6183 | 0.6227 | -0.0044 (-0.0062 to -0.0026) |
| map 3+ | 11,228 | 0.6502 | 0.6578 | -0.0077 (-0.0101 to -0.0053) |
| repeat-free complete prefix | 11,062 | 0.6205 | 0.6265 | -0.0060 (-0.0083 to -0.0037) |
| repeated complete prefix | 15,823 | 0.6393 | 0.6450 | -0.0056 (-0.0075 to -0.0037) |

## draft − forge_refit

| Slice | Maps | Candidate LL | Control LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 26,885 | 0.6277 | 0.6343 | -0.0066 (-0.0079 to -0.0053) |
| major leagues | 5,807 | 0.6264 | 0.6317 | -0.0053 (-0.0081 to -0.0026) |
| LPL | 2,735 | 0.6292 | 0.6393 | -0.0101 (-0.0142 to -0.0060) |
| international | 865 | 0.6285 | 0.6372 | -0.0087 (-0.0158 to -0.0013) |
| other leagues | 20,213 | 0.6280 | 0.6349 | -0.0069 (-0.0083 to -0.0054) |
| before 2025 | 16,609 | 0.6346 | 0.6416 | -0.0070 (-0.0087 to -0.0054) |
| 2021 | 4,127 | 0.6439 | 0.6494 | -0.0054 (-0.0087 to -0.0021) |
| 2022 | 3,795 | 0.6388 | 0.6457 | -0.0069 (-0.0102 to -0.0032) |
| 2023 | 4,377 | 0.6304 | 0.6394 | -0.0090 (-0.0124 to -0.0055) |
| 2024 | 4,310 | 0.6262 | 0.6328 | -0.0066 (-0.0098 to -0.0033) |
| 2025 | 5,103 | 0.6248 | 0.6299 | -0.0051 (-0.0079 to -0.0021) |
| 2026 | 5,173 | 0.6082 | 0.6150 | -0.0068 (-0.0099 to -0.0035) |
| map 2 | 15,657 | 0.6130 | 0.6202 | -0.0072 (-0.0089 to -0.0054) |
| map 3+ | 11,228 | 0.6481 | 0.6538 | -0.0058 (-0.0077 to -0.0035) |
| repeat-free complete prefix | 11,062 | 0.6174 | 0.6235 | -0.0061 (-0.0082 to -0.0040) |
| repeated complete prefix | 15,823 | 0.6348 | 0.6418 | -0.0070 (-0.0086 to -0.0052) |

## draft_score − draft

| Slice | Maps | Candidate LL | Control LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 26,885 | 0.6227 | 0.6277 | -0.0050 (-0.0062 to -0.0037) |
| major leagues | 5,807 | 0.6257 | 0.6264 | -0.0006 (-0.0030 to +0.0018) |
| LPL | 2,735 | 0.6291 | 0.6292 | -0.0001 (-0.0035 to +0.0034) |
| international | 865 | 0.6243 | 0.6285 | -0.0042 (-0.0114 to +0.0025) |
| other leagues | 20,213 | 0.6217 | 0.6280 | -0.0062 (-0.0077 to -0.0048) |
| before 2025 | 16,609 | 0.6299 | 0.6346 | -0.0047 (-0.0062 to -0.0033) |
| 2021 | 4,127 | 0.6395 | 0.6439 | -0.0045 (-0.0076 to -0.0014) |
| 2022 | 3,795 | 0.6357 | 0.6388 | -0.0031 (-0.0064 to -0.0000) |
| 2023 | 4,377 | 0.6267 | 0.6304 | -0.0037 (-0.0067 to -0.0011) |
| 2024 | 4,310 | 0.6188 | 0.6262 | -0.0073 (-0.0102 to -0.0044) |
| 2025 | 5,103 | 0.6206 | 0.6248 | -0.0042 (-0.0070 to -0.0014) |
| 2026 | 5,173 | 0.6017 | 0.6082 | -0.0065 (-0.0093 to -0.0038) |
| map 2 | 15,657 | 0.6083 | 0.6130 | -0.0047 (-0.0061 to -0.0032) |
| map 3+ | 11,228 | 0.6427 | 0.6481 | -0.0054 (-0.0074 to -0.0034) |
| repeat-free complete prefix | 11,062 | 0.6123 | 0.6174 | -0.0051 (-0.0071 to -0.0033) |
| repeated complete prefix | 15,823 | 0.6300 | 0.6348 | -0.0049 (-0.0064 to -0.0033) |

## adapt − adapt_control

| Slice | Maps | Candidate LL | Control LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 26,885 | 0.6229 | 0.6228 | +0.0000 (-0.0001 to +0.0002) |
| major leagues | 5,807 | 0.6260 | 0.6259 | +0.0000 (-0.0003 to +0.0004) |
| LPL | 2,735 | 0.6293 | 0.6291 | +0.0002 (-0.0004 to +0.0008) |
| international | 865 | 0.6235 | 0.6241 | -0.0005 (-0.0014 to +0.0003) |
| other leagues | 20,213 | 0.6219 | 0.6218 | +0.0001 (-0.0001 to +0.0003) |
| before 2025 | 16,609 | 0.6298 | 0.6297 | +0.0001 (-0.0002 to +0.0004) |
| 2021 | 4,127 | 0.6389 | 0.6388 | +0.0002 (-0.0006 to +0.0010) |
| 2022 | 3,795 | 0.6362 | 0.6360 | +0.0002 (-0.0003 to +0.0008) |
| 2023 | 4,377 | 0.6261 | 0.6262 | -0.0001 (-0.0005 to +0.0002) |
| 2024 | 4,310 | 0.6193 | 0.6190 | +0.0002 (-0.0002 to +0.0006) |
| 2025 | 5,103 | 0.6208 | 0.6208 | +0.0000 (-0.0002 to +0.0003) |
| 2026 | 5,173 | 0.6025 | 0.6027 | -0.0001 (-0.0003 to +0.0000) |
| map 2 | 15,657 | 0.6084 | 0.6085 | -0.0000 (-0.0003 to +0.0002) |
| map 3+ | 11,228 | 0.6430 | 0.6428 | +0.0002 (-0.0001 to +0.0004) |
| repeat-free complete prefix | 11,062 | 0.6126 | 0.6127 | -0.0001 (-0.0002 to +0.0001) |
| repeated complete prefix | 15,823 | 0.6300 | 0.6299 | +0.0001 (-0.0001 to +0.0004) |

## Limits

First-map production coverage and current-map full drafts required. Missing earlier drafts are zero in exploratory prior-shift means; all earlier map results count. No terminal-score filtering, avoiding conditioning predictors on future outcomes, but incomplete OE series may remain.
Fixed 0.054/0.127 uses event-major status (not home-league status) and constants fitted through 2024: descriptive only. The primary pooled rho always fits earlier years.
Repeat-free prefix is consistent with fearless play but is not proof of rules; no future maps are read for this label. Draft features were selected after 2025–26, so pre-2025 is separately shown. FORGE weights themselves inherit historical fitting limitations.
Adaptation is exploratory; no production changes or tradable-edge claims.
