# Draft player features: fixed walk-forward candidate

Fixed protocol before test scoring, 2026-10-17; one candidate, no tuning.

Add one whole seven-feature block to v2: log(1+career distinct-champion count), career
pick concentration (sum of squared champion shares), pick among the player's
three most-played champions (ties alphabetical), champion-specific prior lane
gold and XP differences at 15 above the player's own prior mean (shrink 100,
units 1000), role different from the player's career modal role, and different
from the team's previous-day role incumbent. Flags are zero without history.
Incumbents use the chronologically last map on each previous day. Pools/roles
use all available prior games; lane data use only player_stats available rows.
No current-day information updates any history until every row is scored.
Five roles summed blue-minus-red; keep v2's four original features. Fit each
2021..2026 test year on 2019..Y-1 using v2's logistic settings and same games.
Primary candidate-v2 paired series bootstrap, all/majors/LPL/international/other,
years and before2025. Report lane coverage by league. No exploratory variants;
2025-26 already viewed while choosing v2. Research only, no production change.

Feature construction/scoring 94.8 seconds (cached production calls; bootstrap reporting excluded). One candidate; no exploratory variants.

| Slice | Games | v2 LL | Candidate LL | Candidate − v2 (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.60706 | 0.60507 | -0.00199 (-0.00252 to -0.00144) |
| major leagues | 10,808 | 0.62004 | 0.62004 | -0.00000 (-0.00095 to +0.00097) |
| LPL | 4,470 | 0.62306 | 0.62238 | -0.00069 (-0.00215 to +0.00079) |
| international | 1,696 | 0.59376 | 0.59301 | -0.00075 (-0.00329 to +0.00190) |
| other leagues | 51,134 | 0.60476 | 0.60231 | -0.00245 (-0.00308 to -0.00180) |
| before 2025 | 44,450 | 0.60808 | 0.60589 | -0.00220 (-0.00283 to -0.00158) |
| 2021 | 11,802 | 0.61834 | 0.61610 | -0.00224 (-0.00348 to -0.00105) |
| 2022 | 12,050 | 0.60545 | 0.60264 | -0.00280 (-0.00404 to -0.00159) |
| 2023 | 10,750 | 0.60997 | 0.60797 | -0.00200 (-0.00333 to -0.00077) |
| 2024 | 9,848 | 0.59696 | 0.59533 | -0.00163 (-0.00307 to -0.00028) |
| 2025 | 9,761 | 0.60761 | 0.60603 | -0.00158 (-0.00292 to -0.00018) |
| 2026 | 9,427 | 0.60166 | 0.60023 | -0.00143 (-0.00283 to +0.00003) |

## Lane snapshot coverage

Shares of player rows with a current snapshot (diagnostic only) and prior champion snapshot history, on the scored games. Current snapshots never enter their own features.

| Slice | Current snapshot | Prior champion snapshot |
|---|---:|---:|
| all | 89.0% | 80.4% |
| major leagues | 66.9% | 84.7% |
| LPL | 19.9% | 71.0% |
| international | 90.4% | 94.6% |
| other leagues | 93.6% | 79.0% |

## Added-feature coefficients

| Year | breadth | depth | top_pool | lane_gold | lane_xp | role_swap | substitute |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2021 | +0.0759 | +0.0130 | +0.0062 | +0.2418 | +0.2294 | -0.0716 | -0.0036 |
| 2022 | +0.0825 | +0.0621 | +0.0055 | +0.1251 | +0.2293 | -0.1013 | -0.0030 |
| 2023 | +0.0869 | +0.0539 | +0.0119 | +0.1183 | +0.1634 | -0.0885 | -0.0106 |
| 2024 | +0.0870 | +0.0605 | +0.0149 | +0.1569 | +0.1295 | -0.0884 | -0.0147 |
| 2025 | +0.0834 | +0.0501 | +0.0140 | +0.1925 | +0.1063 | -0.0990 | -0.0176 |
| 2026 | +0.0811 | +0.0306 | +0.0152 | +0.1465 | +0.1284 | -0.0965 | -0.0150 |

Verdict: the whole predeclared block passes the v3 inclusion gate: all and pre-2025 intervals are below zero, and no named league slice is significantly worse. Gains are concentrated in other leagues; this does not identify an individual component or prove a pool effect beyond overall career experience. Research candidate only.

Limits: career pools mix changing metas; role/substitute flags are historical proxies, not confirmed lineup announcements. LPL missing snapshots shrink lane signals toward zero. FORGE upstream weights were fit using years included here; 2025–26 were already viewed in v2. No tradable edge or prospective performance established.
