**Benchmarks: no guarded value is significantly worse.**

#### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6394 | 0.6394 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6312 | 0.6312 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6346 | 0.6346 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6285 | 0.6285 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | blue_side log loss (1,024 games) | 0.6913 | 0.6913 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,024 games) | 0.6879 | 0.6879 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,024 games) | 0.6369 | 0.6369 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | **elo_live log loss (1,024 games)** | 0.6244 | 0.6222 | -0.0023 (-0.0114 to +0.0075) | within noise | 0 / 0 |
| International | team_elo_live log loss (1,024 games) | 0.6255 | 0.6255 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | form log loss (1,024 games) | 0.6697 | 0.6697 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | **forge log loss (1,024 games)** | 0.6244 | 0.6222 | -0.0023 (-0.0114 to +0.0075) | within noise | 0 / 0 |
| Cross-league | **elo_live log loss (10,184 games)** | 0.5925 | 0.5906 | -0.0020 (-0.0035 to -0.0005) | better | 0 / 0 |
| Within other leagues | elo_standard log loss (69,736 games) | 0.6240 | 0.6240 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,736 games) | 0.6107 | 0.6107 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,736 games)** | 0.6094 | 0.6094 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | **forge log loss (69,736 games)** | 0.6076 | 0.6076 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |

#### Season stats

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Season stats | win_pct split-half r (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | win_pct r with other half's win % (547 team-seasons) | 0.696 | 0.696 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory split-half r (547 team-seasons)** | 0.827 | 0.827 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | **glory r with other half's win % (547 team-seasons)** | 0.695 | 0.695 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw split-half r (547 team-seasons) | 0.762 | 0.762 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_raw r with other half's win % (547 team-seasons) | 0.717 | 0.717 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_elo split-half r (547 team-seasons) | 0.826 | 0.826 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
| Season stats | glory_elo r with other half's win % (547 team-seasons) | 0.693 | 0.693 | +0.000 (+0.000 to +0.000) | within noise | 0 / 0 |
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
| Markets | **series log loss, all (2,398)** | 0.5671 | 0.5671 | +0.0000 (-0.0014 to +0.0014) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (788)** | 0.5868 | 0.5868 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,263) | 0.5548 | 0.5548 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Markets | series log loss, other (347) | 0.5668 | 0.5671 | +0.0003 (-0.0095 to +0.0098) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6147 | 0.6144 | -0.0003 (-0.0014 to +0.0009) | within noise | 0 / 0 |

#### Props

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Props | **Bo3 maps 1-2 assists log score (16,741)** | 3.1598 | 3.1598 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **Bo3 maps 1-2 kills log score (16,741)** | 2.4404 | 2.4404 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **Bo5 maps 1-3 assists log score (4,792)** | 3.4470 | 3.4470 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **Bo5 maps 1-3 kills log score (4,792)** | 2.6989 | 2.6989 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **map assists log score (64,050)** | 2.7399 | 2.7399 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **map cs log score (64,050)** | 5.1860 | 5.1860 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **map deaths log score (64,050)** | 1.9672 | 1.9672 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Props | **map kills log score (64,050)** | 1.9995 | 1.9995 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |

#### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,398) | Any | 2,093 / 2,093 | +0.1 / +0.5 | +0.4 (-0.0 to +0.9) | +0.3 / +0.3 | +0.0 (-0.0 to +0.1) | 45.9 / 45.9 |
| All (2,398) | > 0 | 1,943 / 1,942 | +5.9 / +5.5 | -0.3 (-1.5 to +0.7) | +0.5 / +0.6 | +0.0 (-0.0 to +0.1) | 49.8 / 50.1 |
| All (2,398) | > 3 | 1,398 / 1,393 | +8.0 / +7.7 | -0.3 (-1.6 to +0.9) | +0.8 / +0.8 | +0.0 (-0.0 to +0.1) | 53.6 / 53.8 |
| All (2,398) | > 5 | 1,078 / 1,080 | +11.4 / +11.1 | -0.3 (-1.9 to +1.0) | +1.2 / +1.2 | +0.0 (-0.1 to +0.1) | 57.2 / 57.3 |
| All (2,398) | > 10 | 572 / 567 | +18.8 / +17.1 | -1.7 (-7.0 to +2.0) | +1.8 / +1.9 | +0.0 (-0.1 to +0.1) | 60.5 / 60.5 |
| FORGE (788) | Any | 756 / 756 | -1.0 / -1.0 | +0.0 (+0.0 to +0.0) | -0.7 / -0.7 | +0.0 (+0.0 to +0.0) | 39.6 / 39.6 |
| FORGE (788) | > 0 | 706 / 706 | +12.2 / +12.2 | +0.0 (+0.0 to +0.0) | +0.1 / +0.1 | +0.0 (+0.0 to +0.0) | 47.9 / 47.9 |
| FORGE (788) | > 3 | 463 / 463 | +14.0 / +14.0 | +0.0 (+0.0 to +0.0) | +0.4 / +0.4 | +0.0 (+0.0 to +0.0) | 52.9 / 52.9 |
| FORGE (788) | > 5 | 332 / 332 | +18.2 / +18.2 | +0.0 (+0.0 to +0.0) | +0.5 / +0.5 | +0.0 (+0.0 to +0.0) | 56.3 / 56.3 |
| FORGE (788) | > 10 | 146 / 146 | +24.7 / +24.7 | +0.0 (+0.0 to +0.0) | +0.4 / +0.4 | +0.0 (+0.0 to +0.0) | 61.0 / 61.0 |
| Other (1,610) | Any | 1,337 / 1,337 | +0.7 / +1.4 | +0.7 (-0.1 to +1.5) | +0.8 / +0.8 | +0.0 (-0.0 to +0.1) | 49.5 / 49.4 |
| Other (1,610) | > 0 | 1,237 / 1,236 | +2.2 / +1.7 | -0.5 (-2.5 to +1.0) | +0.8 / +0.8 | +0.1 (-0.0 to +0.2) | 50.9 / 51.3 |
| Other (1,610) | > 3 | 935 / 930 | +5.1 / +4.6 | -0.5 (-2.6 to +1.2) | +0.9 / +1.0 | +0.1 (-0.0 to +0.1) | 53.9 / 54.3 |
| Other (1,610) | > 5 | 746 / 748 | +8.4 / +7.9 | -0.5 (-2.8 to +1.4) | +1.5 / +1.5 | -0.0 (-0.1 to +0.1) | 57.6 / 57.8 |
| Other (1,610) | > 10 | 426 / 421 | +16.8 / +14.4 | -2.3 (-9.8 to +2.6) | +2.3 / +2.4 | +0.0 (-0.1 to +0.2) | 60.3 / 60.3 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.
