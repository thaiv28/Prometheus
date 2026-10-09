## Metric backtest (2026-10-08)

### Domestic: 16,802 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0383 to +0.0466) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.3% | 0.2244 | 0.6396 | -0.0084 (-0.0113 to -0.0058) |
| Elo (live) | 64.2% | 0.2208 | 0.6315 | -0.0165 (-0.0198 to -0.0134) |
| Team Elo, no player ratings (live) | 64.2% | 0.2222 | 0.6347 | -0.0133 (-0.0165 to -0.0103) |
| Form (live) | 64.1% | 0.2218 | 0.6341 | -0.0140 (-0.0170 to -0.0109) |
| FORGE (live) | 64.7% | 0.2196 | 0.6290 | -0.0190 (-0.0221 to -0.0160) |

- FORGE (live) vs Elo (live): log loss -0.0025 (-0.0036 to -0.0014)
- Form (live) vs Elo (live): log loss +0.0025 (-0.0000 to +0.0049)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0032 (-0.0054 to -0.0010)

### International: 1,004 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6912 | +0.0032 (-0.0068 to +0.0131) |
| Win % so far | 54.5% | 0.2474 | 0.6880 | baseline |
| Elo (as of cutoff) | 64.7% | 0.2238 | 0.6381 | -0.0498 (-0.0662 to -0.0332) |
| Elo (live) | 65.3% | 0.2194 | 0.6283 | -0.0596 (-0.0777 to -0.0420) |
| Team Elo, no player ratings (live) | 65.0% | 0.2200 | 0.6296 | -0.0583 (-0.0773 to -0.0396) |
| Form (live) | 58.2% | 0.2392 | 0.6708 | -0.0171 (-0.0275 to -0.0068) |
| FORGE (live) | 65.3% | 0.2194 | 0.6283 | -0.0596 (-0.0777 to -0.0420) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0425 (+0.0282 to +0.0563)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0013 (-0.0073 to +0.0045)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,802 | 0.6347 | 0.6315 | -0.0032 (-0.0054 to -0.0010) |
| Either team in its first 10 games of the season | 347 | 0.6335 | 0.6069 | -0.0265 (-0.0499 to -0.0032) |
| Either team within 10 games of a starter change | 10,313 | 0.6311 | 0.6283 | -0.0028 (-0.0059 to +0.0002) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,057 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,057 | 67.5% | 0.2074 | 0.6019 |
| Major v major | 1,032 | 63.5% | 0.2227 | 0.6364 |
| Major v other | 1,896 | 68.6% | 0.2036 | 0.5907 |
| Other v other | 7,129 | 67.7% | 0.2062 | 0.5999 |
| At an international event | 2,180 | 65.0% | 0.2145 | 0.6164 |
| At any other event (EMEA Masters, cups, promotion) | 7,877 | 68.1% | 0.2054 | 0.5979 |

### Within other leagues: 69,603 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,603 | 0.6277 | 0.6140 | 0.6129 | -0.0137 (-0.0148 to -0.0125) | -0.0012 (-0.0015 to -0.0007) |
| 2022 on | 37,115 | 0.6237 | 0.6087 | 0.6075 | -0.0150 (-0.0165 to -0.0135) | -0.0013 (-0.0018 to -0.0007) |

#### FORGE within other leagues: 69,603 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,603 | 0.6140 | 0.6129 | 0.6102 | 65.6% | 65.9% | -0.0027 (-0.0034 to -0.0019) | -0.0038 (-0.0045 to -0.0032) |
| 2022 on | 37,115 | 0.6087 | 0.6075 | 0.6044 | 66.1% | 66.5% | -0.0030 (-0.0042 to -0.0020) | -0.0043 (-0.0053 to -0.0034) |

FORGE weights (log-odds per point): elo_weight = 0.00502, form_weight = 0.46644, cross_region_elo_weight = 0.00854, other_league_elo_weight = 0.01036, other_league_forge_elo_weight = 0.00803, other_league_form_weight = 0.36290. Form: half-life 20 games, carry 0.5, prior 5 games.
