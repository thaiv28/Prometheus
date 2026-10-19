**Benchmarks: no guarded value is significantly worse.**
Season-stat report: missing from one side, not compared.
AURA report: missing from one side, not compared.
Prop projections: missing from one side, not compared.
Live benchmark: missing from one side, not compared.

#### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6388 | 0.6388 | -0.0000 (-0.0001 to +0.0000) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6303 | 0.6303 | +0.0000 (-0.0000 to +0.0001) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6346 | 0.6346 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6284 | 0.6285 | +0.0000 (-0.0000 to +0.0001) | within noise | 0 / 0 |
| International | blue_side log loss (1,057 games) | 0.6920 | 0.6920 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,057 games) | 0.6889 | 0.6889 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,057 games) | 0.6396 | 0.6394 | -0.0002 (-0.0005 to +0.0000) | within noise | 0 / 0 |
| International | **elo_live log loss (1,057 games)** | 0.6252 | 0.6252 | +0.0000 (-0.0001 to +0.0002) | within noise | 0 / 0 |
| International | team_elo_live log loss (1,057 games) | 0.6289 | 0.6289 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | form log loss (1,057 games) | 0.6725 | 0.6726 | +0.0002 (+0.0000 to +0.0003) | worse | 0 / 0 |
| International | **forge log loss (1,057 games)** | 0.6252 | 0.6252 | +0.0000 (-0.0001 to +0.0002) | within noise | 0 / 0 |
| Cross-league | **elo_live log loss (10,241 games)** | 0.5894 | 0.5893 | -0.0001 (-0.0003 to +0.0001) | within noise | 0 / 0 |
| Within other leagues | elo_standard log loss (69,760 games) | 0.6213 | 0.6221 | +0.0009 (+0.0008 to +0.0009) | worse | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,760 games) | 0.6081 | 0.6082 | +0.0000 (-0.0001 to +0.0001) | within noise | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,760 games)** | 0.6070 | 0.6070 | +0.0000 (-0.0001 to +0.0001) | within noise | 0 / 0 |
| Within other leagues | **forge log loss (69,760 games)** | 0.6066 | 0.6065 | -0.0001 (-0.0002 to -0.0000) | better | 0 / 0 |

#### Markets

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Markets | **series log loss, all (2,436)** | 0.5635 | 0.5637 | +0.0002 (-0.0002 to +0.0007) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (791)** | 0.5873 | 0.5872 | -0.0001 (-0.0004 to +0.0002) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,265) | 0.5490 | 0.5495 | +0.0005 (-0.0003 to +0.0012) | within noise | 0 / 0 |
| Markets | series log loss, other (380) | 0.5621 | 0.5623 | +0.0003 (-0.0009 to +0.0014) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6150 | 0.6147 | -0.0003 (-0.0007 to +0.0001) | within noise | 0 / 0 |

#### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,436) | Any | 2,122 / 2,122 | -0.1 / +0.0 | +0.2 (-0.5 to +0.8) | +0.3 / +0.3 | +0.0 (-0.0 to +0.0) | 46.3 / 46.4 |
| All (2,436) | > 0 | 1,972 / 1,971 | +4.7 / +4.9 | +0.2 (-0.8 to +1.2) | +0.7 / +0.6 | -0.0 (-0.1 to +0.0) | 50.6 / 50.5 |
| All (2,436) | > 3 | 1,376 / 1,370 | +9.0 / +8.9 | -0.1 (-1.8 to +1.7) | +1.0 / +1.0 | -0.0 (-0.1 to +0.0) | 55.4 / 55.5 |
| All (2,436) | > 5 | 1,060 / 1,051 | +10.7 / +11.5 | +0.9 (-0.5 to +2.2) | +1.2 / +1.3 | +0.0 (-0.1 to +0.1) | 57.1 / 57.0 |
| All (2,436) | > 10 | 539 / 543 | +19.0 / +17.6 | -1.3 (-4.3 to +1.0) | +1.9 / +2.0 | +0.1 (-0.1 to +0.3) | 60.7 / 61.3 |
| FORGE (791) | Any | 759 / 759 | -1.5 / -1.6 | -0.1 (-1.3 to +0.9) | -0.7 / -0.7 | -0.0 (-0.0 to +0.0) | 39.8 / 39.7 |
| FORGE (791) | > 0 | 715 / 709 | +11.8 / +12.0 | +0.2 (-0.7 to +1.0) | +0.2 / +0.1 | -0.1 (-0.2 to +0.0) | 47.6 / 47.8 |
| FORGE (791) | > 3 | 463 / 464 | +14.8 / +15.0 | +0.2 (-1.2 to +1.6) | +0.4 / +0.4 | +0.0 (-0.1 to +0.1) | 52.9 / 53.0 |
| FORGE (791) | > 5 | 338 / 338 | +16.6 / +18.6 | +1.9 (+0.3 to +4.0) | +0.5 / +0.6 | +0.0 (-0.0 to +0.1) | 56.2 / 56.5 |
| FORGE (791) | > 10 | 147 / 148 | +26.4 / +25.7 | -0.8 (-9.3 to +6.2) | +0.3 / +0.4 | +0.1 (-0.2 to +0.5) | 59.9 / 60.1 |
| Other (1,645) | Any | 1,363 / 1,363 | +0.6 / +0.9 | +0.3 (-0.5 to +1.2) | +0.9 / +0.9 | +0.0 (-0.0 to +0.1) | 49.9 / 50.2 |
| Other (1,645) | > 0 | 1,257 / 1,262 | +0.7 / +1.0 | +0.3 (-1.2 to +1.9) | +1.0 / +0.9 | -0.0 (-0.1 to +0.0) | 52.3 / 52.0 |
| Other (1,645) | > 3 | 913 / 906 | +6.1 / +5.8 | -0.2 (-2.6 to +2.4) | +1.3 / +1.3 | -0.0 (-0.1 to +0.1) | 56.6 / 56.7 |
| Other (1,645) | > 5 | 722 / 713 | +7.9 / +8.2 | +0.3 (-1.4 to +2.2) | +1.6 / +1.6 | +0.0 (-0.1 to +0.2) | 57.5 / 57.2 |
| Other (1,645) | > 10 | 392 / 395 | +16.2 / +14.6 | -1.5 (-3.5 to +0.4) | +2.6 / +2.7 | +0.1 (-0.1 to +0.4) | 61.0 / 61.8 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.
