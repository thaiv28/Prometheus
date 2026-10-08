## AURA report (2026-10-07)

### Calibration

Fit on every earlier year, scored on each year from 2022. Blue-side log loss is the baseline that only knows blue's win rate.

| Snapshot | Games | Log loss | Blue-side log loss | Brier | AUC | ECE |
|---|---:|---:|---:|---:|---:|---:|
| 10 min | 47,219 | 0.5690 | 0.6913 | 0.1943 | 0.770 | 0.0072 |
| 15 min | 47,219 | 0.5044 | 0.6913 | 0.1683 | 0.829 | 0.0082 |
| 20 min | 47,089 | 0.4270 | 0.6913 | 0.1388 | 0.883 | 0.0067 |
| 25 min | 44,186 | 0.3451 | 0.6917 | 0.1096 | 0.926 | 0.0074 |

At 15 minutes, by predicted chance:

| Predicted | Games | Mean predicted | Actual |
|---|---:|---:|---:|
| 0–10% | 3,949 | 0.051 | 0.055 |
| 10–20% | 4,109 | 0.150 | 0.162 |
| 20–30% | 4,327 | 0.250 | 0.259 |
| 30–40% | 4,373 | 0.351 | 0.342 |
| 40–50% | 4,614 | 0.451 | 0.444 |
| 50–60% | 4,680 | 0.550 | 0.542 |
| 60–70% | 4,776 | 0.650 | 0.648 |
| 70–80% | 5,123 | 0.750 | 0.734 |
| 80–90% | 5,323 | 0.851 | 0.843 |
| 90–100% | 5,945 | 0.952 | 0.945 |

### Player scores

| Score | Split-half r (95% CI) | Full-season reliability | r with teammates (same game) | Next season, same team | Next season, new team |
|---|---|---:|---:|---:|---:|
| AURA (15 min + ¼ team-centred change) | 0.60 (0.57 to 0.62) | 0.75 | 0.24 | 0.53 | 0.46 |
| AURA at 10 min only | 0.49 (0.46 to 0.52) | 0.66 | 0.08 | 0.51 | 0.35 |
| AURA at 15 min only | 0.57 (0.54 to 0.59) | 0.72 | 0.22 | 0.52 | 0.45 |
| AURA at 20 min only | 0.61 (0.59 to 0.64) | 0.76 | 0.35 | 0.53 | 0.43 |
| AURA at 25 min only | 0.65 (0.62 to 0.67) | 0.79 | 0.56 | 0.57 | 0.41 |
| Lane gold gap at 15 min | 0.55 (0.53 to 0.58) | 0.71 | 0.40 | 0.52 | 0.40 |
| Team win % | 0.65 (0.63 to 0.68) | 0.79 | — | 0.60 | 0.25 |

2,393 player-seasons with 10+ games in each half; 719 same-team and 710 new-team pairs of consecutive seasons with 20+ games ("team" is the team name the player played most for that year).

AURA (15 min + ¼ team-centred change) against the others (paired bootstrap, 95% interval):

| Against | Split-half r | Next season, new team |
|---|---|---|
| AURA at 10 min only | +0.106 (+0.077 to +0.134) | +0.115 (+0.061 to +0.169) |
| AURA at 15 min only | +0.031 (+0.022 to +0.040) | +0.016 (-0.000 to +0.034) |
| AURA at 20 min only | -0.017 (-0.034 to +0.000) | +0.037 (+0.008 to +0.068) |
| AURA at 25 min only | -0.051 (-0.073 to -0.028) | +0.054 (+0.010 to +0.098) |
| Lane gold gap at 15 min | +0.043 (+0.024 to +0.062) | +0.059 (+0.018 to +0.096) |
| Team win % | -0.057 (-0.091 to -0.021) | +0.209 (+0.124 to +0.294) |

### Held-out check (the AURA change rule)

Both scores with weights fit on every earlier year only, major-league seasons from 2017: 2,023 player-seasons (split-half), 606 same-team and 580 new-team pairs, 381 team-seasons (roster). The team-centred change adds up to zero over a team, so the 15-minute term alone is also AURA's team-only control.

| Score | Split-half r | r with teammates | Next season, same team | Next season, new team | Roster r |
|---|---:|---:|---:|---:|---:|
| AURA (15 min + ¼ team-centred change) | 0.617 | 0.282 | 0.558 | 0.451 | 0.640 |
| AURA at 15 min only | 0.592 | 0.269 | 0.556 | 0.424 | 0.640 |

AURA minus 15 min only: split-half +0.025 (+0.017 to +0.033); new team +0.027 (+0.012 to +0.044); roster +0.000 (-0.001 to +0.002); r with teammates +0.014.

### Do the players add up to the team?

Each predictor is taken from one half of a team-season and correlated with win % in the other half (both directions pooled, centred within year). 452 major-league team-seasons with 10+ games in each half. Roster AURA uses only players' own AURA, so it follows lineup changes; team AURA is the same lane sum without crediting players.

| From the other half | r with this half's win % | Against roster AURA (paired bootstrap) |
|---|---:|---|
| Roster AURA (players' AURA, this half's lineups) | 0.65 | — |
| Team AURA (the team's own lane sum) | 0.66 | -0.006 (-0.015 to +0.003) |
| GLORY | 0.70 | -0.049 (-0.077 to -0.020) |
| Win % | 0.71 | -0.056 (-0.085 to -0.029) |

### Substitutions

Games where exactly one starter differs from the team's previous game, every league. Each player's AURA so far is their last 50 games before this one, shrunk toward the average lane as if 5 average games were added; the difference is incoming minus outgoing. Surprise is the result minus Player Elo's expected result, which already rates the incoming player, so a positive r means AURA knows something about the swap that Player Elo doesn't. AURA's weights are fit on the whole year, a small look-ahead in the weights only.

For reference, the test can see a signal: over all 92,185 games, the gap between the two teams' summed AURA so far correlates 0.28 with the result (major leagues 0.25). Swaps where the AURA difference doesn't predict even the raw result (r -0.010) point to how teams choose substitutes (rotations, call-ups in games that matter less); mean surprise in swap games is -0.022.

| Games | Difference in | Swaps | r with surprise (95% CI) | Surprise, lowest third | Surprise, highest third |
|---|---|---:|---|---:|---:|
| All swaps | AURA so far | 13,219 | -0.005 (-0.023 to +0.012) | -0.016 | -0.028 |
| All swaps | Lane gold gap so far | 13,219 | -0.009 (-0.026 to +0.008) | -0.015 | -0.031 |
| Both players 10+ games | AURA so far | 7,740 | +0.006 (-0.016 to +0.028) | +0.008 | +0.003 |
| Both players 10+ games | Lane gold gap so far | 7,740 | +0.010 (-0.013 to +0.032) | +0.003 | +0.003 |
| Major leagues | AURA so far | 2,167 | +0.033 (-0.009 to +0.075) | -0.029 | +0.001 |
| Major leagues | Lane gold gap so far | 2,167 | +0.033 (-0.009 to +0.075) | -0.021 | -0.009 |

### 2026 weights at 15 minutes

Log-odds per unit of the lane gap (own minus lane opponent). The stats overlap (kills and deaths move gold), so a single weight is not the stat's whole value.

| Role | gold | xp | cs | kills | deaths | assists |
|---|---:|---:|---:|---:|---:|---:|
| top | 0.0003 | 0.0002 | 0.0024 | 0.1001 | 0.0893 | 0.0123 |
| jng | -0.0001 | 0.0001 | 0.0249 | 0.2853 | 0.0756 | 0.0835 |
| mid | 0.0003 | 0.0002 | 0.0121 | 0.1322 | 0.1580 | 0.0148 |
| bot | 0.0006 | 0.0002 | 0.0032 | 0.0393 | 0.1264 | -0.0235 |
| sup | 0.0003 | 0.0002 | -0.0055 | 0.0422 | 0.1285 | -0.0150 |
