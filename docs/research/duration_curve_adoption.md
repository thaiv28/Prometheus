# Fixed duration curve adoption checks (2026-10-12)

The integration branch `elo-duration-curve` builds on research commit 99f3d6a and compares against production baseline a2f7d37, using the same 205,701 team-game rows. Elo now uses `0.825 + 0.175 * tanh((1800 - seconds) / 300)`; K, rookie treatment and regional links retain their existing definitions. Record explicitly retains the original power curve, so published GLORY's opponent adjustment is unchanged. Form, FORGE and league slopes are refitted on the rebuilt candidate database.

The forecast gain meets the repository rule on international, cross-league and other-league games with no protected regression. [Completion gates](duration_curve_gates.md) additionally show that the gains survive earlier-only calibration and team-pair/day clustering; frozen-through-2024 map-1 calls are inconclusive rather than significantly worse. The curve originated from a retrospective attribution ablation, so this is historical evidence, not an untouched prospective result.

The ordinary offline market command cannot score this local candle cache (no priced rows). The market section below therefore uses the exact same saved cohort of 2,398 priced series and 1,444 map-1 markets on both sides. `scripts/research/rebuild_cached_markets.py` recalculates every published call from each database and its tracked weights; cached old predictions are unused, and prices/outcomes are preserved. The legacy GLORY+ season statistic loses some fit to the other half's win percentage; it is sunset and unguarded. Published GLORY, Record, Luck and AURA's guarded values are unchanged.

Verification: private DB rebuilt; required forecast/season reports regenerated; weights refreshed and `--check-weights` passed without warnings; all four benchmark dumps compared; 329 tests and repository Ruff checks passed; offline static site built with saved log/prices. No merge or live deployment has been performed.

**Benchmarks: no guarded value is significantly worse.**

#### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6396 | 0.6396 | +0.0000 (-0.0005 to +0.0006) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6316 | 0.6313 | -0.0003 (-0.0009 to +0.0004) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6348 | 0.6346 | -0.0002 (-0.0008 to +0.0004) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6341 | 0.6341 | +0.0001 (-0.0000 to +0.0002) | within noise | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6291 | 0.6289 | -0.0002 (-0.0005 to +0.0002) | within noise | 0 / 0 |
| International | blue_side log loss (1,024 games) | 0.6913 | 0.6913 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,024 games) | 0.6879 | 0.6879 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,024 games) | 0.6375 | 0.6357 | -0.0018 (-0.0047 to +0.0011) | within noise | 0 / 0 |
| International | **elo_live log loss (1,024 games)** | 0.6283 | 0.6238 | -0.0045 (-0.0074 to -0.0015) | better | 0 / 0 |
| International | team_elo_live log loss (1,024 games) | 0.6293 | 0.6255 | -0.0038 (-0.0067 to -0.0006) | better | 0 / 0 |
| International | form log loss (1,024 games) | 0.6720 | 0.6716 | -0.0004 (-0.0011 to +0.0003) | within noise | 0 / 0 |
| International | **forge log loss (1,024 games)** | 0.6283 | 0.6238 | -0.0045 (-0.0074 to -0.0015) | better | 0 / 0 |
| Cross-league | **elo_live log loss (10,184 games)** | 0.6015 | 0.5999 | -0.0016 (-0.0025 to -0.0006) | better | 0 / 0 |
| Within other leagues | elo_standard log loss (69,736 games) | 0.6276 | 0.6252 | -0.0024 (-0.0026 to -0.0022) | better | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,736 games) | 0.6139 | 0.6122 | -0.0017 (-0.0020 to -0.0014) | better | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,736 games)** | 0.6127 | 0.6110 | -0.0017 (-0.0021 to -0.0014) | better | 0 / 0 |
| Within other leagues | **forge log loss (69,736 games)** | 0.6101 | 0.6090 | -0.0010 (-0.0013 to -0.0008) | better | 0 / 0 |

#### Season stats

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Season stats | win_pct split-half r (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | win_pct r with other half's win % (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory split-half r (547 team-seasons)** | 0.827 | 0.827 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory r with other half's win % (547 team-seasons)** | 0.695 | 0.695 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw split-half r (547 team-seasons) | 0.762 | 0.762 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw r with other half's win % (547 team-seasons) | 0.717 | 0.717 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_elo split-half r (547 team-seasons) | 0.827 | 0.829 | +0.002 (+0.001 to +0.003) | better | 0 / 0 |
| Season stats | glory_elo r with other half's win % (547 team-seasons) | 0.694 | 0.690 | -0.004 (-0.005 to -0.002) | worse | 0 / 0 |
| Season stats | glorb split-half r (547 team-seasons) | 0.752 | 0.752 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glorb r with other half's win % (547 team-seasons) | 0.691 | 0.691 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | record split-half r (545 team-seasons) | 0.811 | 0.811 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | record r with other half's win % (545 team-seasons) | 0.704 | 0.704 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | luck split-half r (547 team-seasons) | 0.208 | 0.208 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | luck r with other half's win % (547 team-seasons) | 0.048 | 0.048 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |

#### AURA

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| AURA | **split-half r (2,023 player-seasons)** | 0.616 | 0.616 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| AURA | **new-team r (581 player-seasons)** | 0.450 | 0.450 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| AURA | **roster r (381 team-seasons)** | 0.638 | 0.638 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| AURA | **ECE at 10 min (limit 0.01)** | 0.007 | 0.007 | — | under the limit | 0 / 0 |
| AURA | **ECE at 15 min (limit 0.01)** | 0.008 | 0.008 | — | under the limit | 0 / 0 |
| AURA | **ECE at 20 min (limit 0.01)** | 0.007 | 0.007 | — | under the limit | 0 / 0 |
| AURA | **ECE at 25 min (limit 0.01)** | 0.007 | 0.007 | — | under the limit | 0 / 0 |

#### Markets

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Markets | **series log loss, all (2,398)** | 0.5711 | 0.5701 | -0.0010 (-0.0027 to +0.0007) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (788)** | 0.5903 | 0.5885 | -0.0018 (-0.0039 to +0.0001) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,263) | 0.5555 | 0.5548 | -0.0007 (-0.0030 to +0.0017) | within noise | 0 / 0 |
| Markets | series log loss, other (347) | 0.5843 | 0.5841 | -0.0002 (-0.0069 to +0.0062) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6142 | 0.6142 | +0.0001 (-0.0015 to +0.0017) | within noise | 0 / 0 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and higher r are better.
