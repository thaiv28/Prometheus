# Objectives follow-up: draft, momentum and calibration

Retrospective reused test; unchanged split and C=1; equal-map losses and paired series-bootstrap intervals. Negative differences are better. No production model changes.

Train 2,757, calibration 1,733, test 3,857 feed maps. Draft gaps are zero when unavailable; all models keep all rows. Primary uses the original draft features; matchup/synergy is secondary because its selection overlaps the test.

## Primary: original draft versus objectives

| Slice | Maps | Objectives LL | Combined LL | Combined − Objectives |
|---|---|---|---|---|
| All | 3,857 | 0.4700 | 0.4682 | -0.0018 (-0.0035 to -0.0002) |
| Minutes 0–10 | 3,857 | 0.6106 | 0.6075 | -0.0031 (-0.0054 to -0.0007) |
| Minutes 10–20 | 3,856 | 0.4983 | 0.4967 | -0.0016 (-0.0035 to +0.0003) |
| Minutes 20–30 | 3,850 | 0.3383 | 0.3377 | -0.0006 (-0.0018 to +0.0007) |
| Minutes 30+ | 2,136 | 0.2876 | 0.2878 | +0.0002 (-0.0012 to +0.0017) |
| Major league | 3,084 | 0.4789 | 0.4775 | -0.0014 (-0.0032 to +0.0005) |
| International | 297 | 0.4480 | 0.4479 | -0.0001 (-0.0064 to +0.0066) |
| Other | 476 | 0.4261 | 0.4205 | -0.0056 (-0.0099 to -0.0010) |

Known draft: 3,447 maps; combined − objectives -0.0021 (-0.0040 to -0.0002).

Missing draft: 410 maps; combined − objectives +0.0002 (-0.0006 to +0.0012).

## Secondary: draft with interactions versus objectives

| Slice | Maps | Objectives LL | Combined LL | Combined − Objectives |
|---|---|---|---|---|
| All | 3,857 | 0.4700 | 0.4674 | -0.0026 (-0.0044 to -0.0009) |
| Minutes 0–10 | 3,857 | 0.6106 | 0.6064 | -0.0042 (-0.0070 to -0.0014) |
| Minutes 10–20 | 3,856 | 0.4983 | 0.4959 | -0.0024 (-0.0044 to -0.0004) |
| Minutes 20–30 | 3,850 | 0.3383 | 0.3374 | -0.0009 (-0.0020 to +0.0003) |
| Minutes 30+ | 2,136 | 0.2876 | 0.2876 | -0.0000 (-0.0012 to +0.0012) |
| Major league | 3,084 | 0.4789 | 0.4768 | -0.0021 (-0.0040 to -0.0001) |
| International | 297 | 0.4480 | 0.4481 | +0.0001 (-0.0070 to +0.0073) |
| Other | 476 | 0.4261 | 0.4183 | -0.0078 (-0.0124 to -0.0031) |

Known draft: 3,447 maps; combined − objectives -0.0029 (-0.0050 to -0.0010).

Missing draft: 410 maps; combined − objectives +0.0003 (-0.0006 to +0.0012).

## Secondary: momentum versus objectives

| Slice | Maps | Objectives LL | Momentum LL | Momentum − Objectives |
|---|---|---|---|---|
| All | 3,857 | 0.4700 | 0.4675 | -0.0025 (-0.0033 to -0.0017) |
| Minutes 0–10 | 3,857 | 0.6106 | 0.6100 | -0.0006 (-0.0010 to -0.0002) |
| Minutes 10–20 | 3,856 | 0.4983 | 0.4975 | -0.0008 (-0.0020 to +0.0002) |
| Minutes 20–30 | 3,850 | 0.3383 | 0.3343 | -0.0040 (-0.0057 to -0.0023) |
| Minutes 30+ | 2,136 | 0.2876 | 0.2756 | -0.0120 (-0.0158 to -0.0083) |
| Major league | 3,084 | 0.4789 | 0.4760 | -0.0029 (-0.0038 to -0.0019) |
| International | 297 | 0.4480 | 0.4465 | -0.0015 (-0.0039 to +0.0008) |
| Other | 476 | 0.4261 | 0.4257 | -0.0005 (-0.0023 to +0.0014) |

## Objective calibration diagnostics

| Model | LL | ECE |
|---|---:|---:|
| Global | 0.4700 | 0.0191 |
| Raw | 0.4683 | 0.0080 |
| Fixed time buckets | 0.4694 | 0.0148 |

## Raw versus global objective calibration (diagnostic)

| Slice | Maps | Global LL | Raw LL | Raw − Global |
|---|---|---|---|---|
| All | 3,857 | 0.4700 | 0.4683 | -0.0017 (-0.0031 to -0.0001) |
| Minutes 0–10 | 3,857 | 0.6106 | 0.6062 | -0.0044 (-0.0063 to -0.0025) |
| Minutes 10–20 | 3,856 | 0.4983 | 0.4962 | -0.0021 (-0.0038 to -0.0004) |
| Minutes 20–30 | 3,850 | 0.3383 | 0.3369 | -0.0014 (-0.0031 to +0.0003) |
| Minutes 30+ | 2,136 | 0.2876 | 0.2893 | +0.0016 (-0.0003 to +0.0037) |
| Major league | 3,084 | 0.4789 | 0.4770 | -0.0019 (-0.0037 to -0.0003) |
| International | 297 | 0.4480 | 0.4497 | +0.0017 (-0.0031 to +0.0063) |
| Other | 476 | 0.4261 | 0.4238 | -0.0023 (-0.0063 to +0.0017) |

## Fixed time buckets versus global objective calibration (diagnostic)

| Slice | Maps | Global LL | Fixed time buckets LL | Fixed time buckets − Global |
|---|---|---|---|---|
| All | 3,857 | 0.4700 | 0.4694 | -0.0006 (-0.0011 to -0.0001) |
| Minutes 0–10 | 3,857 | 0.6106 | 0.6066 | -0.0040 (-0.0055 to -0.0024) |
| Minutes 10–20 | 3,856 | 0.4983 | 0.4981 | -0.0002 (-0.0003 to -0.0001) |
| Minutes 20–30 | 3,850 | 0.3383 | 0.3392 | +0.0009 (+0.0005 to +0.0014) |
| Minutes 30+ | 2,136 | 0.2876 | 0.2888 | +0.0011 (-0.0013 to +0.0034) |
| Major league | 3,084 | 0.4789 | 0.4781 | -0.0008 (-0.0014 to -0.0002) |
| International | 297 | 0.4480 | 0.4474 | -0.0006 (-0.0025 to +0.0013) |
| Other | 476 | 0.4261 | 0.4270 | +0.0009 (-0.0003 to +0.0021) |

## Combined models versus v1

### Primary: original draft

| Slice | Maps | v1 LL | Primary: original draft LL | Primary: original draft − v1 |
|---|---|---|---|---|
| All | 3,857 | 0.4811 | 0.4682 | -0.0129 (-0.0168 to -0.0090) |
| Minutes 0–10 | 3,857 | 0.6094 | 0.6075 | -0.0019 (-0.0049 to +0.0010) |
| Minutes 10–20 | 3,856 | 0.5117 | 0.4967 | -0.0150 (-0.0201 to -0.0096) |
| Minutes 20–30 | 3,850 | 0.3551 | 0.3377 | -0.0174 (-0.0227 to -0.0120) |
| Minutes 30+ | 2,136 | 0.3160 | 0.2878 | -0.0282 (-0.0372 to -0.0191) |
| Major league | 3,084 | 0.4919 | 0.4775 | -0.0144 (-0.0185 to -0.0102) |
| International | 297 | 0.4581 | 0.4479 | -0.0102 (-0.0240 to +0.0038) |
| Other | 476 | 0.4257 | 0.4205 | -0.0053 (-0.0171 to +0.0063) |

### Objectives + momentum

| Slice | Maps | v1 LL | Objectives + momentum LL | Objectives + momentum − v1 |
|---|---|---|---|---|
| All | 3,857 | 0.4811 | 0.4675 | -0.0136 (-0.0170 to -0.0100) |
| Minutes 0–10 | 3,857 | 0.6094 | 0.6100 | +0.0006 (-0.0011 to +0.0023) |
| Minutes 10–20 | 3,856 | 0.5117 | 0.4975 | -0.0142 (-0.0192 to -0.0091) |
| Minutes 20–30 | 3,850 | 0.3551 | 0.3343 | -0.0208 (-0.0260 to -0.0156) |
| Minutes 30+ | 2,136 | 0.3160 | 0.2756 | -0.0404 (-0.0489 to -0.0317) |
| Major league | 3,084 | 0.4919 | 0.4760 | -0.0158 (-0.0198 to -0.0119) |
| International | 297 | 0.4581 | 0.4465 | -0.0116 (-0.0234 to +0.0007) |
| Other | 476 | 0.4257 | 0.4257 | -0.0001 (-0.0108 to +0.0100) |

## Calibration across all feed candidates

| Model | LL | ECE |
|---|---:|---:|
| Objectives | 0.4700 | 0.0191 |
| v1 | 0.4811 | 0.0147 |
| Primary: original draft | 0.4682 | 0.0185 |
| Secondary: draft with interactions | 0.4674 | 0.0185 |
| Objectives + momentum | 0.4675 | 0.0182 |
| Objectives raw | 0.4683 | 0.0080 |
| Objectives bucketed | 0.4694 | 0.0148 |

## Limits

The test is reused and intervals are unadjusted for multiple comparisons. Objective counts include cumulative inhibitors and an approximate soul flag. The original draft shift avoids the later interaction-feature selection, but still comes from earlier exploratory work. Missing picks concentrate in LPL. No participant-feed or production-frame validation; no trading-profit claim.
