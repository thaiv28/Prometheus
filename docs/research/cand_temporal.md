# Live model: momentum and calibration checks

Fixed v2 split; feed-only fits, equal map weights, C=1. Train 2,757 maps; calibration 1,733; test 3,857. Negative log-loss deltas are better; intervals resample whole series. The test has already been used for earlier research; these are retrospective checks.

## Primary: three-minute gold momentum versus v1

| Slice | Maps | v1 LL | Momentum LL | Momentum − v1 |
|---|---|---|---|---|
| All | 3,857 | 0.4811 | 0.4805 | -0.0006 (-0.0022 to +0.0010) |
| Minutes 0–10 | 3,857 | 0.6094 | 0.6096 | +0.0002 (-0.0009 to +0.0013) |
| Minutes 10–20 | 3,856 | 0.5117 | 0.5106 | -0.0011 (-0.0032 to +0.0009) |
| Minutes 20–30 | 3,850 | 0.3551 | 0.3546 | -0.0005 (-0.0026 to +0.0016) |
| Minutes 30+ | 2,136 | 0.3160 | 0.3027 | -0.0133 (-0.0183 to -0.0083) |
| Major league | 3,084 | 0.4919 | 0.4915 | -0.0004 (-0.0022 to +0.0015) |
| International | 297 | 0.4581 | 0.4566 | -0.0015 (-0.0073 to +0.0041) |
| Other | 476 | 0.4257 | 0.4241 | -0.0016 (-0.0052 to +0.0016) |

## Momentum versus same-row refit

| Slice | Maps | Refit LL | Momentum LL | Momentum − Refit |
|---|---|---|---|---|
| All | 3,857 | 0.4816 | 0.4805 | -0.0011 (-0.0018 to -0.0004) |
| Minutes 0–10 | 3,857 | 0.6098 | 0.6096 | -0.0002 (-0.0004 to +0.0001) |
| Minutes 10–20 | 3,856 | 0.5102 | 0.5106 | +0.0004 (-0.0004 to +0.0012) |
| Minutes 20–30 | 3,850 | 0.3563 | 0.3546 | -0.0017 (-0.0033 to -0.0002) |
| Minutes 30+ | 2,136 | 0.3113 | 0.3027 | -0.0087 (-0.0125 to -0.0050) |
| Major league | 3,084 | 0.4930 | 0.4915 | -0.0015 (-0.0024 to -0.0007) |
| International | 297 | 0.4565 | 0.4566 | +0.0001 (-0.0023 to +0.0022) |
| Other | 476 | 0.4233 | 0.4241 | +0.0008 (-0.0009 to +0.0023) |

## Calibration diagnostics

| Model | Log loss | ECE (10 bins) |
|---|---:|---:|
| v1 | 0.4811 | 0.0147 |
| Raw refit | 0.4804 | 0.0048 |
| Global calibration | 0.4816 | 0.0152 |
| Time-bucket calibration | 0.4814 | 0.0122 |

## Raw refit versus global calibration (diagnostic)

| Slice | Maps | Global LL | Raw refit LL | Raw refit − Global |
|---|---|---|---|---|
| All | 3,857 | 0.4816 | 0.4804 | -0.0011 (-0.0024 to +0.0002) |
| Minutes 0–10 | 3,857 | 0.6098 | 0.6071 | -0.0026 (-0.0041 to -0.0011) |
| Minutes 10–20 | 3,856 | 0.5102 | 0.5081 | -0.0021 (-0.0036 to -0.0006) |
| Minutes 20–30 | 3,850 | 0.3563 | 0.3552 | -0.0011 (-0.0026 to +0.0003) |
| Minutes 30+ | 2,136 | 0.3113 | 0.3134 | +0.0020 (+0.0003 to +0.0037) |
| Major league | 3,084 | 0.4930 | 0.4913 | -0.0017 (-0.0032 to -0.0003) |
| International | 297 | 0.4565 | 0.4582 | +0.0017 (-0.0026 to +0.0056) |
| Other | 476 | 0.4233 | 0.4239 | +0.0005 (-0.0024 to +0.0035) |

## Time-bucket calibration versus global calibration (diagnostic)

| Slice | Maps | Global LL | Time-bucket calibration LL | Time-bucket calibration − Global |
|---|---|---|---|---|
| All | 3,857 | 0.4816 | 0.4814 | -0.0002 (-0.0006 to +0.0003) |
| Minutes 0–10 | 3,857 | 0.6098 | 0.6078 | -0.0019 (-0.0030 to -0.0008) |
| Minutes 10–20 | 3,856 | 0.5102 | 0.5092 | -0.0009 (-0.0015 to -0.0003) |
| Minutes 20–30 | 3,850 | 0.3563 | 0.3574 | +0.0010 (+0.0005 to +0.0016) |
| Minutes 30+ | 2,136 | 0.3113 | 0.3117 | +0.0004 (-0.0020 to +0.0026) |
| Major league | 3,084 | 0.4930 | 0.4926 | -0.0004 (-0.0010 to +0.0001) |
| International | 297 | 0.4565 | 0.4564 | -0.0001 (-0.0018 to +0.0016) |
| Other | 476 | 0.4233 | 0.4247 | +0.0013 (+0.0004 to +0.0023) |

No model is shipped. Momentum uses only past samples, including across pauses on the existing estimated-clock axis. Its zero-history fallback is shared in all partitions. Bucket calibration is discontinuous at fixed boundaries and has not been validated on production ten-second frames. ECE is descriptive, not an adoption test.
