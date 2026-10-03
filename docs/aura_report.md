## AURA report (2026-10-02)

### Calibration

Fit on every earlier year, scored on each year from 2022. Blue-side log loss is the baseline that only knows blue's win rate.

| Snapshot | Games | Log loss | Blue-side log loss | Brier | AUC | ECE |
|---|---:|---:|---:|---:|---:|---:|
| 10 min | 45,970 | 0.5708 | 0.6913 | 0.1950 | 0.768 | 0.0068 |
| 15 min | 45,970 | 0.5067 | 0.6913 | 0.1691 | 0.828 | 0.0082 |
| 20 min | 45,856 | 0.4291 | 0.6913 | 0.1395 | 0.882 | 0.0070 |
| 25 min | 43,145 | 0.3456 | 0.6917 | 0.1097 | 0.926 | 0.0071 |

At 15 minutes, by predicted chance:

| Predicted | Games | Mean predicted | Actual |
|---|---:|---:|---:|
| 0–10% | 3,762 | 0.051 | 0.057 |
| 10–20% | 4,007 | 0.150 | 0.164 |
| 20–30% | 4,230 | 0.250 | 0.257 |
| 30–40% | 4,268 | 0.351 | 0.343 |
| 40–50% | 4,533 | 0.451 | 0.441 |
| 50–60% | 4,565 | 0.550 | 0.545 |
| 60–70% | 4,672 | 0.650 | 0.649 |
| 70–80% | 5,018 | 0.750 | 0.734 |
| 80–90% | 5,216 | 0.851 | 0.844 |
| 90–100% | 5,699 | 0.951 | 0.943 |

### Player scores

| Score | Split-half r (95% CI) | Full-season reliability | r with teammates (same game) | Next season, same team | Next season, new team |
|---|---|---:|---:|---:|---:|
| AURA (15 min + ¼ team-centred change) | 0.59 (0.56 to 0.61) | 0.74 | 0.24 | 0.53 | 0.48 |
| AURA at 10 min only | 0.48 (0.45 to 0.51) | 0.65 | 0.08 | 0.50 | 0.36 |
| AURA at 15 min only | 0.55 (0.52 to 0.58) | 0.71 | 0.21 | 0.52 | 0.46 |
| AURA at 20 min only | 0.61 (0.58 to 0.63) | 0.76 | 0.35 | 0.53 | 0.44 |
| AURA at 25 min only | 0.65 (0.62 to 0.67) | 0.79 | 0.56 | 0.57 | 0.42 |
| Lane gold gap at 15 min | 0.54 (0.51 to 0.57) | 0.70 | 0.40 | 0.52 | 0.42 |
| Team win % | 0.65 (0.63 to 0.67) | 0.79 | — | 0.60 | 0.27 |

2,402 player-seasons with 10+ games in each half; 717 same-team and 711 new-team pairs of consecutive seasons with 20+ games ("team" is the team name the player played most for that year).

AURA (15 min + ¼ team-centred change) against the others (paired bootstrap, 95% interval):

| Against | Split-half r | Next season, new team |
|---|---|---|
| AURA at 10 min only | +0.104 (+0.075 to +0.133) | +0.116 (+0.062 to +0.171) |
| AURA at 15 min only | +0.037 (+0.027 to +0.046) | +0.018 (+0.001 to +0.035) |
| AURA at 20 min only | -0.020 (-0.038 to -0.003) | +0.038 (+0.008 to +0.070) |
| AURA at 25 min only | -0.060 (-0.082 to -0.037) | +0.058 (+0.015 to +0.103) |
| Lane gold gap at 15 min | +0.045 (+0.026 to +0.065) | +0.061 (+0.021 to +0.101) |
| Team win % | -0.064 (-0.101 to -0.027) | +0.208 (+0.120 to +0.294) |

### Held-out check (the AURA change rule)

Both scores with weights fit on every earlier year only, major-league seasons from 2017: 2,031 player-seasons (split-half), 607 same-team and 580 new-team pairs, 381 team-seasons (roster). The team-centred change adds up to zero over a team, so the 15-minute term alone is also AURA's team-only control.

| Score | Split-half r | r with teammates | Next season, same team | Next season, new team | Roster r |
|---|---:|---:|---:|---:|---:|
| AURA (15 min + ¼ team-centred change) | 0.616 | 0.281 | 0.561 | 0.469 | 0.643 |
| AURA at 15 min only | 0.590 | 0.266 | 0.559 | 0.441 | 0.642 |

AURA minus 15 min only: split-half +0.026 (+0.017 to +0.033); new team +0.028 (+0.012 to +0.043); roster +0.001 (-0.000 to +0.002); r with teammates +0.014.

### Do the players add up to the team?

Each predictor is taken from one half of a team-season and correlated with win % in the other half (both directions pooled, centred within year). 452 major-league team-seasons with 10+ games in each half. Roster AURA uses only players' own AURA, so it follows lineup changes; team AURA is the same lane sum without crediting players.

| From the other half | r with this half's win % | Against roster AURA (paired bootstrap) |
|---|---:|---|
| Roster AURA (players' AURA, this half's lineups) | 0.65 | — |
| Team AURA (the team's own lane sum) | 0.66 | -0.008 (-0.016 to +0.001) |
| GLORY | 0.71 | -0.058 (-0.086 to -0.030) |
| Win % | 0.71 | -0.065 (-0.094 to -0.036) |

### Substitutions

Games where exactly one starter differs from the team's previous game, every league. Each player's AURA so far is their last 50 games before this one, shrunk toward the average lane as if 5 average games were added; the difference is incoming minus outgoing. Surprise is the result minus Player Elo's expected result, which already rates the incoming player, so a positive r means AURA knows something about the swap that Player Elo doesn't. AURA's weights are fit on the whole year, a small look-ahead in the weights only.

For reference, the test can see a signal: over all 90,028 games, the gap between the two teams' summed AURA so far correlates 0.28 with the result (major leagues 0.25). Swaps where the AURA difference doesn't predict even the raw result (r -0.009) point to how teams choose substitutes (rotations, call-ups in games that matter less); mean surprise in swap games is -0.023.

| Games | Difference in | Swaps | r with surprise (95% CI) | Surprise, lowest third | Surprise, highest third |
|---|---|---:|---|---:|---:|
| All swaps | AURA so far | 12,969 | -0.004 (-0.021 to +0.014) | -0.017 | -0.028 |
| All swaps | Lane gold gap so far | 12,969 | -0.008 (-0.025 to +0.009) | -0.018 | -0.034 |
| Both players 10+ games | AURA so far | 7,580 | +0.009 (-0.013 to +0.032) | +0.008 | +0.009 |
| Both players 10+ games | Lane gold gap so far | 7,580 | +0.010 (-0.012 to +0.033) | -0.000 | +0.004 |
| Major leagues | AURA so far | 2,167 | +0.030 (-0.012 to +0.072) | -0.024 | -0.003 |
| Major leagues | Lane gold gap so far | 2,167 | +0.032 (-0.010 to +0.074) | -0.025 | -0.006 |

### 2026 weights at 15 minutes

Log-odds per unit of the lane gap (own minus lane opponent). The stats overlap (kills and deaths move gold), so a single weight is not the stat's whole value.

| Role | gold | xp | cs | kills | deaths | assists |
|---|---:|---:|---:|---:|---:|---:|
| top | 0.0003 | 0.0002 | 0.0018 | 0.0860 | 0.0907 | 0.0064 |
| jng | -0.0001 | 0.0001 | 0.0261 | 0.2858 | 0.0652 | 0.0901 |
| mid | 0.0003 | 0.0002 | 0.0104 | 0.1215 | 0.1809 | 0.0138 |
| bot | 0.0005 | 0.0002 | 0.0036 | 0.0500 | 0.1319 | -0.0342 |
| sup | 0.0003 | 0.0002 | -0.0048 | 0.0460 | 0.1269 | -0.0164 |
