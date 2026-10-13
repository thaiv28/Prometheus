# Fixed duration curve: latest-main adoption checks (2026-10-13)

Baseline: main 3b0e33f, including the combined FORGE/Elo changes and new player props. Both databases were rebuilt with the current schema on 205,701 team-game rows. Forecast/season/AURA/market results below were generated against b4e3681; PR #52 adds player-total columns and props without changing those algorithms. Its freshly rebuilt props scores are also paired below, and all five protected benchmark groups pass. Candidate Form/FORGE weights and league slopes are refitted; Record keeps its original power curve.

International, cross-league and other-league gains are significant in the full native forecast benchmark. [Completion gates](duration_curve_gates.md) on the combined model confirm international and other-league gains under earlier-only fitting and team-pair/day clustering; the 2022+ cross-league difference is within noise there. Map-1 markets and the new prop projections have no significant regression. These are retrospective findings, not a newly untouched holdout.

Markets use the same saved cohort of 2,398 priced series / 1,444 maps, rebuilding every prediction through roster-aware `form.load_states()` and each version’s database/weights. Cached predictions are unused. Local candle inputs are incomplete; no new prices are fetched. Published GLORY/Record/AURA guards are unchanged; sunset GLORY+ other-half fit worsens (unguarded).

Verification includes DB rebuilds, all five benchmark groups, 382 tests after PR #52, Ruff formatting/lint and local site builds. Scalar `math.tanh` avoids NumPy scalar propagation through player ratings: measured full replay 3.535s power versus 3.502s candidate on 102,844 games (before that optimization, tanh 3.915s). No new benchmark or workflow step is added. CI is required before the requested merge.

**Benchmarks: no guarded value is significantly worse.**

#### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6395 | 0.6394 | -0.0000 (-0.0006 to +0.0005) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6315 | 0.6312 | -0.0003 (-0.0010 to +0.0003) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6348 | 0.6346 | -0.0002 (-0.0008 to +0.0004) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0001 (-0.0001 to +0.0002) | within noise | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6286 | 0.6285 | -0.0001 (-0.0005 to +0.0003) | within noise | 0 / 0 |
| International | blue_side log loss (1,024 games) | 0.6913 | 0.6913 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,024 games) | 0.6879 | 0.6879 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,024 games) | 0.6386 | 0.6369 | -0.0016 (-0.0045 to +0.0013) | within noise | 0 / 0 |
| International | **elo_live log loss (1,024 games)** | 0.6289 | 0.6244 | -0.0044 (-0.0074 to -0.0014) | better | 0 / 0 |
| International | team_elo_live log loss (1,024 games) | 0.6293 | 0.6255 | -0.0038 (-0.0067 to -0.0006) | better | 0 / 0 |
| International | form log loss (1,024 games) | 0.6700 | 0.6697 | -0.0003 (-0.0010 to +0.0004) | within noise | 0 / 0 |
| International | **forge log loss (1,024 games)** | 0.6289 | 0.6244 | -0.0044 (-0.0074 to -0.0014) | better | 0 / 0 |
| Cross-league | **elo_live log loss (10,184 games)** | 0.5940 | 0.5925 | -0.0014 (-0.0024 to -0.0004) | better | 0 / 0 |
| Within other leagues | elo_standard log loss (69,736 games) | 0.6263 | 0.6240 | -0.0024 (-0.0026 to -0.0021) | better | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,736 games) | 0.6124 | 0.6107 | -0.0016 (-0.0020 to -0.0013) | better | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,736 games)** | 0.6111 | 0.6094 | -0.0017 (-0.0020 to -0.0014) | better | 0 / 0 |
| Within other leagues | **forge log loss (69,736 games)** | 0.6085 | 0.6076 | -0.0009 (-0.0012 to -0.0007) | better | 0 / 0 |

#### Season stats

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Season stats | win_pct split-half r (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | win_pct r with other half's win % (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory split-half r (547 team-seasons)** | 0.827 | 0.827 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory r with other half's win % (547 team-seasons)** | 0.695 | 0.695 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw split-half r (547 team-seasons) | 0.762 | 0.762 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw r with other half's win % (547 team-seasons) | 0.717 | 0.717 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_elo split-half r (547 team-seasons) | 0.824 | 0.826 | +0.002 (+0.001 to +0.004) | better | 0 / 0 |
| Season stats | glory_elo r with other half's win % (547 team-seasons) | 0.698 | 0.693 | -0.004 (-0.006 to -0.003) | worse | 0 / 0 |
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
| Markets | **series log loss, all (2,398)** | 0.5680 | 0.5671 | -0.0010 (-0.0026 to +0.0008) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (788)** | 0.5886 | 0.5868 | -0.0018 (-0.0039 to +0.0003) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,263) | 0.5554 | 0.5548 | -0.0006 (-0.0029 to +0.0019) | within noise | 0 / 0 |
| Markets | series log loss, other (347) | 0.5672 | 0.5668 | -0.0004 (-0.0071 to +0.0061) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6148 | 0.6147 | -0.0001 (-0.0017 to +0.0016) | within noise | 0 / 0 |

#### Props

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Props | **Bo3 maps 1-2 assists log score (16,741)** | 3.1604 | 3.1598 | -0.0006 (-0.0018 to +0.0005) | within noise | 0 / 0 |
| Props | **Bo3 maps 1-2 kills log score (16,741)** | 2.4407 | 2.4404 | -0.0003 (-0.0008 to +0.0002) | within noise | 0 / 0 |
| Props | **Bo5 maps 1-3 assists log score (4,792)** | 3.4471 | 3.4470 | -0.0001 (-0.0032 to +0.0028) | within noise | 0 / 0 |
| Props | **Bo5 maps 1-3 kills log score (4,792)** | 2.6989 | 2.6989 | -0.0000 (-0.0015 to +0.0014) | within noise | 0 / 0 |
| Props | **map assists log score (64,050)** | 2.7403 | 2.7399 | -0.0004 (-0.0009 to +0.0001) | within noise | 0 / 0 |
| Props | **map cs log score (64,050)** | 5.1860 | 5.1860 | +0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **map deaths log score (64,050)** | 1.9674 | 1.9672 | -0.0003 (-0.0006 to +0.0001) | within noise | 0 / 0 |
| Props | **map kills log score (64,050)** | 1.9996 | 1.9995 | -0.0002 (-0.0004 to +0.0000) | within noise | 0 / 0 |

#### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,398) | Any | 2,093 / 2,093 | -0.2 / +0.1 | +0.3 (-0.9 to +1.6) | +0.1 / +0.3 | +0.1 (-0.0 to +0.3) | 45.8 / 45.9 |
| All (2,398) | > 0 | 1,933 / 1,943 | +4.0 / +5.9 | +1.8 (-0.5 to +4.2) | +0.4 / +0.5 | +0.1 (-0.0 to +0.2) | 49.7 / 49.8 |
| All (2,398) | > 3 | 1,365 / 1,398 | +6.6 / +8.0 | +1.4 (-0.9 to +4.0) | +0.7 / +0.8 | +0.0 (-0.1 to +0.2) | 53.1 / 53.6 |
| All (2,398) | > 5 | 1,048 / 1,078 | +9.2 / +11.4 | +2.2 (-0.9 to +5.3) | +1.0 / +1.2 | +0.2 (-0.0 to +0.4) | 55.9 / 57.2 |
| All (2,398) | > 10 | 542 / 572 | +17.5 / +18.8 | +1.3 (-3.0 to +5.7) | +1.8 / +1.8 | +0.1 (-0.2 to +0.4) | 62.0 / 60.5 |
| FORGE (788) | Any | 756 / 756 | -1.5 / -1.0 | +0.5 (-1.6 to +2.6) | -0.7 / -0.7 | -0.0 (-0.1 to +0.0) | 40.1 / 39.6 |
| FORGE (788) | > 0 | 708 / 706 | +7.3 / +12.2 | +4.9 (+1.0 to +9.0) | +0.0 / +0.1 | +0.0 (-0.1 to +0.2) | 48.3 / 47.9 |
| FORGE (788) | > 3 | 451 / 463 | +15.3 / +14.0 | -1.3 (-5.6 to +3.1) | +0.3 / +0.4 | +0.1 (-0.1 to +0.3) | 52.5 / 52.9 |
| FORGE (788) | > 5 | 321 / 332 | +18.4 / +18.2 | -0.2 (-6.1 to +5.6) | +0.3 / +0.5 | +0.2 (-0.2 to +0.6) | 56.7 / 56.3 |
| FORGE (788) | > 10 | 137 / 146 | +26.5 / +24.7 | -1.9 (-9.6 to +5.5) | +0.2 / +0.4 | +0.2 (-0.2 to +0.9) | 63.5 / 61.0 |
| Other (1,610) | Any | 1,337 / 1,337 | +0.5 / +0.7 | +0.2 (-1.3 to +1.7) | +0.6 / +0.8 | +0.2 (+0.0 to +0.4) | 49.1 / 49.5 |
| Other (1,610) | > 0 | 1,225 / 1,237 | +2.2 / +2.2 | +0.1 (-2.8 to +3.0) | +0.6 / +0.8 | +0.1 (-0.0 to +0.3) | 50.5 / 50.9 |
| Other (1,610) | > 3 | 914 / 935 | +2.3 / +5.1 | +2.8 (-0.4 to +5.9) | +0.9 / +0.9 | +0.0 (-0.2 to +0.2) | 53.4 / 53.9 |
| Other (1,610) | > 5 | 727 / 746 | +5.2 / +8.4 | +3.3 (-0.3 to +7.0) | +1.4 / +1.5 | +0.2 (-0.1 to +0.5) | 55.6 / 57.6 |
| Other (1,610) | > 10 | 405 / 426 | +14.5 / +16.8 | +2.3 (-2.7 to +7.3) | +2.3 / +2.3 | +0.0 (-0.3 to +0.4) | 61.5 / 60.3 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.
