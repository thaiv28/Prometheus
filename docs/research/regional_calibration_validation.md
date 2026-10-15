# Regional calibration production validation

Production probabilities reproduce the original persistent two-layer experiment within 1e-12 on every eligible map and priced forecast. No numeric setting was selected again for production.

Map parity: 2,177 maps. Artifact: 36 frozen snapshots; latest trained through 2026-10-02.

| 2022+ slice | Maps | Elo LL | Calibrated LL | Delta (series-cluster 95%; event sensitivity) |
|---|---:|---:|---:|---|
| All | 1006 | 0.591756 | 0.574292 | -0.0175 [-0.0272, -0.0075]; event [-0.0276, -0.0065] |
| Major v major | 556 | 0.620941 | 0.611053 | -0.0099 [-0.0199, +0.0008]; event [-0.0189, -0.0008] |
| 2026 | 255 | 0.590881 | 0.583912 | -0.0070 [-0.0272, +0.0133]; event [-0.0248, +0.0064] |

## Fixed priced cohort

| Kind / cutoff | Calls | Maximum probability error |
|---|---:|---:|
| series / close | 95 | 2.2e-15 |
| series / 12h | 95 | 2.2e-15 |
| map1 / close | 43 | 1.1e-16 |
| map1 / 12h | 43 | 1.1e-16 |

Primary market endpoint and closing comparison:

- 12h timed common cohort (76): calibrated LL 0.554163, Elo 0.551022, Kalshi 0.534863.
- All closing series (95): calibrated LL 0.572980, Elo 0.571643, Kalshi 0.526916.

The original paired market comparisons span zero. This is evidence of historical forecast improvement, not evidence of beating Kalshi.

## Scope and limits

Only cross-home fixtures in recognized international events are calibrated. Domestic, same-home international, EMEA Masters, promotion and other cross-league competitions retain their existing methods. An unrestricted exploratory application worsened non-international cross-league LL by +0.01595; that scope was rejected. See the [native benchmark comparison](regional_calibration_benchmarks.md) for every adoption guard.

The broad 2022+ international gain is significant under both series and event resampling. Major-v-major and 2026-only gains remain within noise. Historical event boundaries, current Elo development and the viewed later seasons make this retrospective evidence. The fixed market cohort covers four events through September 30, no actual Worlds. A prospective untouched market holdout remains necessary.

Runtime loads committed coefficients, never fits. Historical snapshots admit only earlier completed events, freeze through known event boundaries, and use UTC forecast-day cutoffs. The deployment artifact deliberately retains the last evaluated pre-event fit (October 2), rather than learning from an incomplete tournament. Old saved calls remain frozen; future calls record artifact version, snapshot and training cutoff. REGIONAL_CALIBRATION=0 disables the overlay.
