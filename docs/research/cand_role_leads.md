# Role leads phase A: exact OE checkpoints

Same chronological split; one C=1 calibrated model per minute. Primary adds role gold and CS gaps to the six-feature gold/Elo control. Secondary adds XP gaps; XP is a proxy for progression, not a level measurement. All models share complete ten-player rows. Pregame Elo is fixed at the series start. No feed participant data or interpolation is used. This is phase A evidence, not live validation.

| Minute | Train | Calibrate | Test | Control LL | Role gold/CS LL | Difference (95%) | +XP LL | Difference (95%) |
|---|---:|---:|---:|---:|---:|---|---:|---|
| 10 | 17,027 | 1,079 | 3,378 | 0.5754 | 0.5737 | -0.0017 (-0.0031 to -0.0004) | 0.5725 | -0.0029 (-0.0059 to +0.0001) |
| 15 | 17,027 | 1,079 | 3,378 | 0.5260 | 0.5228 | -0.0031 (-0.0050 to -0.0012) | 0.5225 | -0.0035 (-0.0076 to +0.0007) |
| 20 | 16,992 | 1,079 | 3,375 | 0.4622 | 0.4571 | -0.0051 (-0.0077 to -0.0024) | 0.4532 | -0.0090 (-0.0139 to -0.0041) |
| 25 | 16,085 | 1,053 | 3,226 | 0.3863 | 0.3841 | -0.0022 (-0.0051 to +0.0006) | 0.3741 | -0.0123 (-0.0180 to -0.0064) |

## Pooled, equal map weights

| Slice | Maps | Control LL | Role LL | Role − Control |
|---|---|---|---|---|
| All | 3,378 | 0.4850 | 0.4820 | -0.0030 (-0.0048 to -0.0012) |
| Minutes 10–20 | 3,378 | 0.5507 | 0.5483 | -0.0024 (-0.0039 to -0.0009) |
| Minutes 20–30 | 3,375 | 0.4168 | 0.4131 | -0.0037 (-0.0062 to -0.0012) |
| Major league | 2,842 | 0.4890 | 0.4857 | -0.0033 (-0.0053 to -0.0012) |
| International | 536 | 0.4638 | 0.4619 | -0.0018 (-0.0062 to +0.0028) |

## Secondary XP versus same-row control

| Slice | Maps | Control LL | XP LL | XP − Control |
|---|---|---|---|---|
| All | 3,378 | 0.4850 | 0.4782 | -0.0068 (-0.0100 to -0.0035) |
| Minutes 10–20 | 3,378 | 0.5507 | 0.5475 | -0.0032 (-0.0064 to +0.0001) |
| Minutes 20–30 | 3,375 | 0.4168 | 0.4064 | -0.0104 (-0.0148 to -0.0061) |
| Major league | 2,842 | 0.4890 | 0.4833 | -0.0057 (-0.0093 to -0.0022) |
| International | 536 | 0.4638 | 0.4510 | -0.0128 (-0.0214 to -0.0044) |

## Role gold/CS versus frozen v1 on exact checkpoints

| Slice | Maps | v1 LL | Role LL | Role − v1 |
|---|---|---|---|---|
| All | 3,378 | 0.4875 | 0.4820 | -0.0055 (-0.0082 to -0.0029) |
| Minutes 10–20 | 3,378 | 0.5544 | 0.5483 | -0.0061 (-0.0088 to -0.0033) |
| Minutes 20–30 | 3,375 | 0.4183 | 0.4131 | -0.0051 (-0.0086 to -0.0018) |
| Major league | 2,842 | 0.4911 | 0.4857 | -0.0053 (-0.0083 to -0.0023) |
| International | 536 | 0.4683 | 0.4619 | -0.0064 (-0.0131 to +0.0005) |

## Limits

Retrospective reused test and multiple comparisons. This pool differs from feed timelines and has substantial LPL snapshot missingness. The four-checkpoint result cannot establish gain over objectives or continuous-time performance. Checkpoint survival selects different populations at each minute. No participant recollection was started and no live model changed.
