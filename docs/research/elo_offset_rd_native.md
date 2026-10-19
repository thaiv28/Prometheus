# League-offset RD: native comparisons

Selected `league_rd=(120, 80, 1, 1)` (floor 80, new/floor 1.5, growth 1, information 1). Each arm: full `evaluate_metrics.py --dump` and `evaluate_markets.py --offline --dump` against the main baseline dumps, compared by `compare_benchmarks.py`. Calibration was disabled with `REGIONAL_CALIBRATION=0` (the loader's own switch), so `regional_calibration.json` was never edited (checked unchanged with `cmp`). Published Elo restored afterwards with `004_bootstrap_elo.py`.

Unrounded paired 95% intervals for the rows that decide the verdict (head − base log loss):

| Arm | Within other leagues, elo_per_league | Within other leagues, FORGE | Cross-league, elo_live |
|---|---|---|---|
| (a) RD, calibration on | +0.000022 (+0.000003 to +0.000041) | +0.000021 (+0.000004 to +0.000036) | -0.000223 (-0.000346 to -0.000097) |
| (b) RD, calibration off | +0.000022 (+0.000003 to +0.000041) | +0.000021 (+0.000004 to +0.000036) | +0.001489 (+0.000024 to +0.002970) |
| (c) published, calibration off | 0 | 0 | +0.001844 (+0.000380 to +0.003353) |

Verdicts: (a) gains on cross-league but two guarded within-other-league rows are significantly worse (about 2e-5, all years): offset RD fails the rule. (b) and (c) make cross-league significantly worse: the calibration stays. Markets series log loss is within noise in all arms.

## (a) RD, calibration on

**Benchmarks: 2 guarded check(s) failed** (Within other leagues: elo_per_league log loss (69,760 games); Within other leagues: forge log loss (69,760 games)).
Season-stat report: missing from one side, not compared.
AURA report: missing from one side, not compared.
Prop projections: missing from one side, not compared.
Live benchmark: missing from one side, not compared.

### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6388 | 0.6388 | -0.0000 (-0.0001 to +0.0000) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6303 | 0.6303 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6346 | 0.6346 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0000 (+0.0000 to +0.0001) | worse | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6284 | 0.6284 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| International | blue_side log loss (1,057 games) | 0.6920 | 0.6920 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,057 games) | 0.6889 | 0.6889 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,057 games) | 0.6396 | 0.6386 | -0.0010 (-0.0015 to -0.0005) | better | 0 / 0 |
| International | **elo_live log loss (1,057 games)** | 0.6252 | 0.6250 | -0.0001 (-0.0004 to +0.0001) | within noise | 0 / 0 |
| International | team_elo_live log loss (1,057 games) | 0.6289 | 0.6289 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | form log loss (1,057 games) | 0.6725 | 0.6727 | +0.0003 (+0.0001 to +0.0004) | worse | 0 / 0 |
| International | **forge log loss (1,057 games)** | 0.6252 | 0.6250 | -0.0001 (-0.0004 to +0.0001) | within noise | 0 / 0 |
| Cross-league | **elo_live log loss (10,241 games)** | 0.5894 | 0.5892 | -0.0002 (-0.0003 to -0.0001) | better | 0 / 0 |
| Within other leagues | elo_standard log loss (69,760 games) | 0.6213 | 0.6213 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,760 games) | 0.6081 | 0.6082 | +0.0000 (+0.0000 to +0.0000) | worse | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,760 games)** | 0.6070 | 0.6070 | +0.0000 (+0.0000 to +0.0000) | **worse** | 0 / 0 |
| Within other leagues | **forge log loss (69,760 games)** | 0.6066 | 0.6066 | +0.0000 (+0.0000 to +0.0000) | **worse** | 0 / 0 |

### Markets

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Markets | **series log loss, all (2,436)** | 0.5635 | 0.5635 | -0.0000 (-0.0002 to +0.0001) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (791)** | 0.5873 | 0.5872 | -0.0001 (-0.0002 to +0.0001) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,265) | 0.5490 | 0.5492 | +0.0002 (+0.0000 to +0.0003) | worse | 0 / 0 |
| Markets | series log loss, other (380) | 0.5621 | 0.5614 | -0.0007 (-0.0016 to +0.0002) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6150 | 0.6149 | -0.0001 (-0.0002 to +0.0001) | within noise | 0 / 0 |

### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,436) | Any | 2,122 / 2,122 | -0.1 / -0.3 | -0.2 (-0.7 to +0.3) | +0.3 / +0.3 | +0.0 (-0.0 to +0.0) | 46.3 / 46.3 |
| All (2,436) | > 0 | 1,972 / 1,969 | +4.7 / +4.7 | -0.1 (-0.5 to +0.3) | +0.7 / +0.7 | +0.0 (-0.0 to +0.0) | 50.6 / 50.7 |
| All (2,436) | > 3 | 1,376 / 1,377 | +9.0 / +10.0 | +0.9 (+0.3 to +1.8) | +1.0 / +1.0 | -0.0 (-0.0 to +0.0) | 55.4 / 55.6 |
| All (2,436) | > 5 | 1,060 / 1,056 | +10.7 / +10.3 | -0.3 (-1.7 to +0.5) | +1.2 / +1.2 | -0.0 (-0.0 to +0.0) | 57.1 / 57.0 |
| All (2,436) | > 10 | 539 / 539 | +19.0 / +18.6 | -0.4 (-2.9 to +1.4) | +1.9 / +2.0 | +0.1 (-0.1 to +0.3) | 60.7 / 60.7 |
| FORGE (791) | Any | 759 / 759 | -1.5 / -1.6 | -0.2 (-1.3 to +0.7) | -0.7 / -0.7 | -0.0 (-0.0 to +0.0) | 39.8 / 39.8 |
| FORGE (791) | > 0 | 715 / 713 | +11.8 / +11.9 | +0.0 (-0.4 to +0.5) | +0.2 / +0.2 | +0.0 (+0.0 to +0.0) | 47.6 / 47.7 |
| FORGE (791) | > 3 | 463 / 464 | +14.8 / +15.4 | +0.6 (+0.0 to +1.3) | +0.4 / +0.5 | +0.0 (-0.0 to +0.1) | 52.9 / 53.0 |
| FORGE (791) | > 5 | 338 / 336 | +16.6 / +17.3 | +0.7 (-0.3 to +2.0) | +0.5 / +0.5 | -0.0 (-0.0 to +0.0) | 56.2 / 56.2 |
| FORGE (791) | > 10 | 147 / 148 | +26.4 / +23.1 | -3.4 (-11.6 to +1.9) | +0.3 / +0.3 | +0.1 (-0.2 to +0.4) | 59.9 / 59.5 |
| Other (1,645) | Any | 1,363 / 1,363 | +0.6 / +0.5 | -0.2 (-0.8 to +0.4) | +0.9 / +0.9 | +0.0 (-0.0 to +0.0) | 49.9 / 50.0 |
| Other (1,645) | > 0 | 1,257 / 1,256 | +0.7 / +0.6 | -0.1 (-0.8 to +0.4) | +1.0 / +1.0 | +0.0 (-0.0 to +0.0) | 52.3 / 52.4 |
| Other (1,645) | > 3 | 913 / 913 | +6.1 / +7.2 | +1.1 (+0.2 to +2.5) | +1.3 / +1.3 | -0.0 (-0.1 to +0.0) | 56.6 / 56.8 |
| Other (1,645) | > 5 | 722 / 720 | +7.9 / +7.1 | -0.8 (-2.5 to +0.3) | +1.6 / +1.6 | -0.0 (-0.0 to +0.0) | 57.5 / 57.4 |
| Other (1,645) | > 10 | 392 / 391 | +16.2 / +16.9 | +0.7 (-0.5 to +2.2) | +2.6 / +2.7 | +0.1 (-0.1 to +0.4) | 61.0 / 61.1 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.

## (b) RD, calibration off

**Benchmarks: 3 guarded check(s) failed** (Cross-league: elo_live log loss (10,241 games); Within other leagues: elo_per_league log loss (69,760 games); Within other leagues: forge log loss (69,760 games)).
Season-stat report: missing from one side, not compared.
AURA report: missing from one side, not compared.
Prop projections: missing from one side, not compared.
Live benchmark: missing from one side, not compared.

### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6388 | 0.6388 | -0.0000 (-0.0001 to +0.0000) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6303 | 0.6303 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6346 | 0.6346 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0000 (+0.0000 to +0.0001) | worse | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6284 | 0.6284 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| International | blue_side log loss (1,057 games) | 0.6920 | 0.6920 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,057 games) | 0.6889 | 0.6889 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,057 games) | 0.6396 | 0.6386 | -0.0010 (-0.0015 to -0.0005) | better | 0 / 0 |
| International | **elo_live log loss (1,057 games)** | 0.6252 | 0.6277 | +0.0025 (-0.0073 to +0.0115) | within noise | 0 / 0 |
| International | team_elo_live log loss (1,057 games) | 0.6289 | 0.6289 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | form log loss (1,057 games) | 0.6725 | 0.6727 | +0.0003 (+0.0001 to +0.0004) | worse | 0 / 0 |
| International | **forge log loss (1,057 games)** | 0.6252 | 0.6277 | +0.0025 (-0.0073 to +0.0115) | within noise | 0 / 0 |
| Cross-league | **elo_live log loss (10,241 games)** | 0.5894 | 0.5909 | +0.0015 (+0.0000 to +0.0030) | **worse** | 0 / 0 |
| Within other leagues | elo_standard log loss (69,760 games) | 0.6213 | 0.6213 | -0.0000 (-0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,760 games) | 0.6081 | 0.6082 | +0.0000 (+0.0000 to +0.0000) | worse | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,760 games)** | 0.6070 | 0.6070 | +0.0000 (+0.0000 to +0.0000) | **worse** | 0 / 0 |
| Within other leagues | **forge log loss (69,760 games)** | 0.6066 | 0.6066 | +0.0000 (+0.0000 to +0.0000) | **worse** | 0 / 0 |

### Markets

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Markets | **series log loss, all (2,436)** | 0.5635 | 0.5637 | +0.0002 (-0.0014 to +0.0017) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (791)** | 0.5873 | 0.5872 | -0.0001 (-0.0002 to +0.0001) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,265) | 0.5490 | 0.5492 | +0.0002 (+0.0000 to +0.0003) | worse | 0 / 0 |
| Markets | series log loss, other (380) | 0.5621 | 0.5631 | +0.0010 (-0.0090 to +0.0102) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6150 | 0.6153 | +0.0003 (-0.0010 to +0.0013) | within noise | 0 / 0 |

### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,436) | Any | 2,122 / 2,122 | -0.1 / -0.7 | -0.6 (-1.3 to +0.1) | +0.3 / +0.3 | -0.0 (-0.1 to +0.0) | 46.3 / 46.4 |
| All (2,436) | > 0 | 1,972 / 1,969 | +4.7 / +4.7 | -0.1 (-1.1 to +1.2) | +0.7 / +0.6 | -0.1 (-0.1 to -0.0) | 50.6 / 50.1 |
| All (2,436) | > 3 | 1,376 / 1,377 | +9.0 / +9.8 | +0.8 (-0.7 to +2.5) | +1.0 / +1.0 | -0.0 (-0.1 to +0.1) | 55.4 / 55.2 |
| All (2,436) | > 5 | 1,060 / 1,059 | +10.7 / +10.3 | -0.3 (-2.4 to +1.7) | +1.2 / +1.2 | -0.0 (-0.1 to +0.1) | 57.1 / 56.7 |
| All (2,436) | > 10 | 539 / 549 | +19.0 / +20.2 | +1.3 (-3.6 to +7.5) | +1.9 / +1.9 | -0.0 (-0.2 to +0.2) | 60.7 / 60.1 |
| FORGE (791) | Any | 759 / 759 | -1.5 / -1.6 | -0.2 (-1.3 to +0.7) | -0.7 / -0.7 | -0.0 (-0.0 to +0.0) | 39.8 / 39.8 |
| FORGE (791) | > 0 | 715 / 713 | +11.8 / +11.9 | +0.0 (-0.4 to +0.5) | +0.2 / +0.2 | +0.0 (+0.0 to +0.0) | 47.6 / 47.7 |
| FORGE (791) | > 3 | 463 / 464 | +14.8 / +15.4 | +0.6 (+0.0 to +1.3) | +0.4 / +0.5 | +0.0 (-0.0 to +0.1) | 52.9 / 53.0 |
| FORGE (791) | > 5 | 338 / 336 | +16.6 / +17.3 | +0.7 (-0.3 to +2.0) | +0.5 / +0.5 | -0.0 (-0.0 to +0.0) | 56.2 / 56.2 |
| FORGE (791) | > 10 | 147 / 148 | +26.4 / +23.1 | -3.4 (-11.6 to +1.9) | +0.3 / +0.3 | +0.1 (-0.2 to +0.4) | 59.9 / 59.5 |
| Other (1,645) | Any | 1,363 / 1,363 | +0.6 / -0.2 | -0.8 (-1.8 to +0.0) | +0.9 / +0.9 | -0.0 (-0.1 to +0.0) | 49.9 / 50.0 |
| Other (1,645) | > 0 | 1,257 / 1,256 | +0.7 / +0.6 | -0.1 (-1.8 to +1.7) | +1.0 / +0.8 | -0.1 (-0.2 to -0.0) | 52.3 / 51.5 |
| Other (1,645) | > 3 | 913 / 913 | +6.1 / +7.0 | +0.9 (-1.4 to +3.4) | +1.3 / +1.3 | -0.1 (-0.2 to +0.1) | 56.6 / 56.3 |
| Other (1,645) | > 5 | 722 / 723 | +7.9 / +7.1 | -0.8 (-3.8 to +2.2) | +1.6 / +1.5 | -0.0 (-0.2 to +0.1) | 57.5 / 56.8 |
| Other (1,645) | > 10 | 392 / 401 | +16.2 / +19.2 | +3.0 (-3.2 to +11.3) | +2.6 / +2.5 | -0.1 (-0.3 to +0.2) | 61.0 / 60.3 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.

## (c) published Elo, calibration off

**Benchmarks: 1 guarded check(s) failed** (Cross-league: elo_live log loss (10,241 games)).
Season-stat report: missing from one side, not compared.
AURA report: missing from one side, not compared.
Prop projections: missing from one side, not compared.
Live benchmark: missing from one side, not compared.

### Forecasts

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Domestic | blue_side log loss (16,810 games) | 0.6906 | 0.6906 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | win_pct log loss (16,810 games) | 0.6480 | 0.6480 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | elo log loss (16,810 games) | 0.6388 | 0.6388 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | **elo_live log loss (16,810 games)** | 0.6303 | 0.6303 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | team_elo_live log loss (16,810 games) | 0.6346 | 0.6346 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | form log loss (16,810 games) | 0.6345 | 0.6345 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Domestic | **forge log loss (16,810 games)** | 0.6284 | 0.6284 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | blue_side log loss (1,057 games) | 0.6920 | 0.6920 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | win_pct log loss (1,057 games) | 0.6889 | 0.6889 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | elo log loss (1,057 games) | 0.6396 | 0.6396 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | **elo_live log loss (1,057 games)** | 0.6252 | 0.6283 | +0.0031 (-0.0068 to +0.0123) | within noise | 0 / 0 |
| International | team_elo_live log loss (1,057 games) | 0.6289 | 0.6289 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | form log loss (1,057 games) | 0.6725 | 0.6725 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| International | **forge log loss (1,057 games)** | 0.6252 | 0.6283 | +0.0031 (-0.0068 to +0.0123) | within noise | 0 / 0 |
| Cross-league | **elo_live log loss (10,241 games)** | 0.5894 | 0.5913 | +0.0018 (+0.0004 to +0.0034) | **worse** | 0 / 0 |
| Within other leagues | elo_standard log loss (69,760 games) | 0.6213 | 0.6213 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | elo_one_curve log loss (69,760 games) | 0.6081 | 0.6081 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | **elo_per_league log loss (69,760 games)** | 0.6070 | 0.6070 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Within other leagues | **forge log loss (69,760 games)** | 0.6066 | 0.6066 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |

### Markets

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Markets | **series log loss, all (2,436)** | 0.5635 | 0.5638 | +0.0003 (-0.0013 to +0.0018) | within noise | 0 / 0 |
| Markets | **series log loss, forge (major) (791)** | 0.5873 | 0.5873 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Markets | series log loss, forge (other league) (1,265) | 0.5490 | 0.5490 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Markets | series log loss, other (380) | 0.5621 | 0.5638 | +0.0018 (-0.0083 to +0.0109) | within noise | 0 / 0 |
| Markets | **map1 log loss, all (1,444)** | 0.6150 | 0.6154 | +0.0003 (-0.0009 to +0.0015) | within noise | 0 / 0 |

### Betting (report only)

$1 on our side 12 hours before the start, as the Predictions page's Table IV: our pick in every series (Any), or where our chance beat Kalshi's price by more than the edge. Return is per $1 after the 7% fee; CLV is the closing price minus the price paid, in points. Never fails the check.

| Calls | Edge | Bets (base / head) | Return % (base / head) | Head − base (95% CI) | CLV (base / head) | Head − base (95% CI) | Beat close % (base / head) |
|---|---:|---:|---:|---|---:|---|---:|
| All (2,436) | Any | 2,122 / 2,122 | -0.1 / -0.5 | -0.4 (-0.9 to +0.0) | +0.3 / +0.3 | -0.0 (-0.0 to +0.0) | 46.3 / 46.3 |
| All (2,436) | > 0 | 1,972 / 1,971 | +4.7 / +4.8 | +0.1 (-0.9 to +1.3) | +0.7 / +0.6 | -0.1 (-0.1 to -0.0) | 50.6 / 50.1 |
| All (2,436) | > 3 | 1,376 / 1,374 | +9.0 / +9.2 | +0.2 (-1.2 to +1.8) | +1.0 / +1.0 | -0.0 (-0.1 to +0.0) | 55.4 / 54.9 |
| All (2,436) | > 5 | 1,060 / 1,062 | +10.7 / +10.6 | -0.0 (-1.7 to +1.8) | +1.2 / +1.2 | -0.0 (-0.1 to +0.1) | 57.1 / 56.7 |
| All (2,436) | > 10 | 539 / 549 | +19.0 / +20.6 | +1.6 (-2.7 to +7.7) | +1.9 / +1.8 | -0.1 (-0.3 to -0.0) | 60.7 / 60.1 |
| FORGE (791) | Any | 759 / 759 | -1.5 / -1.5 | +0.0 (+0.0 to +0.0) | -0.7 / -0.7 | +0.0 (+0.0 to +0.0) | 39.8 / 39.8 |
| FORGE (791) | > 0 | 715 / 715 | +11.8 / +11.8 | +0.0 (+0.0 to +0.0) | +0.2 / +0.2 | +0.0 (+0.0 to +0.0) | 47.6 / 47.6 |
| FORGE (791) | > 3 | 463 / 463 | +14.8 / +14.8 | +0.0 (+0.0 to +0.0) | +0.4 / +0.4 | +0.0 (+0.0 to +0.0) | 52.9 / 52.9 |
| FORGE (791) | > 5 | 338 / 338 | +16.6 / +16.6 | +0.0 (+0.0 to +0.0) | +0.5 / +0.5 | +0.0 (+0.0 to +0.0) | 56.2 / 56.2 |
| FORGE (791) | > 10 | 147 / 147 | +26.4 / +26.4 | +0.0 (+0.0 to +0.0) | +0.3 / +0.3 | +0.0 (+0.0 to +0.0) | 59.9 / 59.9 |
| Other (1,645) | Any | 1,363 / 1,363 | +0.6 / -0.0 | -0.6 (-1.5 to +0.1) | +0.9 / +0.9 | -0.0 (-0.1 to +0.0) | 49.9 / 50.0 |
| Other (1,645) | > 0 | 1,257 / 1,256 | +0.7 / +0.8 | +0.1 (-1.4 to +2.0) | +1.0 / +0.8 | -0.1 (-0.2 to -0.0) | 52.3 / 51.5 |
| Other (1,645) | > 3 | 913 / 911 | +6.1 / +6.4 | +0.3 (-1.9 to +2.7) | +1.3 / +1.3 | -0.1 (-0.2 to +0.1) | 56.6 / 56.0 |
| Other (1,645) | > 5 | 722 / 724 | +7.9 / +7.8 | -0.1 (-2.4 to +2.5) | +1.6 / +1.5 | -0.0 (-0.2 to +0.1) | 57.5 / 56.9 |
| Other (1,645) | > 10 | 392 / 402 | +16.2 / +18.4 | +2.3 (-3.8 to +10.5) | +2.6 / +2.4 | -0.2 (-0.4 to -0.0) | 61.0 / 60.2 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.

