## Metric backtest (2026-10-19)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0381 to +0.0469) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.4% | 0.2240 | 0.6388 | -0.0092 (-0.0122 to -0.0063) |
| Elo (live) | 64.4% | 0.2202 | 0.6303 | -0.0177 (-0.0210 to -0.0143) |
| Team Elo, no player ratings (live) | 64.1% | 0.2221 | 0.6346 | -0.0135 (-0.0167 to -0.0102) |
| Form (live) | 64.0% | 0.2220 | 0.6345 | -0.0136 (-0.0167 to -0.0102) |
| FORGE (live) | 64.7% | 0.2193 | 0.6285 | -0.0196 (-0.0227 to -0.0163) |

- FORGE (live) vs Elo (live): log loss -0.0019 (-0.0028 to -0.0009)
- Form (live) vs Elo (live): log loss +0.0042 (+0.0016 to +0.0067)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0043 (-0.0063 to -0.0021)

### International: 1,057 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 52.7% | 0.2494 | 0.6920 | +0.0030 (-0.0069 to +0.0127) |
| Win % so far | 53.6% | 0.2479 | 0.6889 | baseline |
| Elo (as of cutoff) | 64.0% | 0.2243 | 0.6394 | -0.0496 (-0.0682 to -0.0296) |
| Elo (live) | 64.7% | 0.2179 | 0.6252 | -0.0637 (-0.0876 to -0.0390) |
| Team Elo, no player ratings (live) | 65.8% | 0.2198 | 0.6289 | -0.0601 (-0.0797 to -0.0403) |
| Form (live) | 57.7% | 0.2399 | 0.6726 | -0.0163 (-0.0282 to -0.0044) |
| FORGE (live) | 64.7% | 0.2179 | 0.6252 | -0.0637 (-0.0876 to -0.0390) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0474 (+0.0254 to +0.0695)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0037 (-0.0143 to +0.0073)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6346 | 0.6303 | -0.0043 (-0.0063 to -0.0021) |
| Either team in its first 10 games of the season | 347 | 0.6339 | 0.6098 | -0.0241 (-0.0488 to -0.0009) |
| Either team within 10 games of a starter change | 10,313 | 0.6308 | 0.6266 | -0.0041 (-0.0071 to -0.0013) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far. Intervals resample whole series (games between the same two teams within 12 hours).
### Cross-league, every league: 10,241 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,241 | 68.5% | 0.2021 | 0.5893 |
| Major v major | 1,085 | 64.7% | 0.2189 | 0.6270 |
| Major v other | 1,930 | 69.4% | 0.1987 | 0.5788 |
| Other v other | 7,226 | 68.9% | 0.2005 | 0.5865 |
| At an international event | 2,262 | 66.9% | 0.2075 | 0.5997 |
| At any other event (EMEA Masters, cups, promotion) | 7,979 | 69.0% | 0.2006 | 0.5864 |

### Within other leagues: 69,760 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6221 | 0.6082 | 0.6070 | -0.0139 (-0.0151 to -0.0128) | -0.0012 (-0.0016 to -0.0008) |
| 2022 on | 37,272 | 0.6160 | 0.6016 | 0.6005 | -0.0144 (-0.0160 to -0.0127) | -0.0011 (-0.0016 to -0.0005) |

#### FORGE within other leagues: 69,760 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6082 | 0.6070 | 0.6065 | 66.1% | 66.3% | -0.0005 (-0.0011 to +0.0001) | -0.0017 (-0.0021 to -0.0013) |
| 2022 on | 37,272 | 0.6016 | 0.6005 | 0.5997 | 66.6% | 66.7% | -0.0008 (-0.0017 to +0.0001) | -0.0019 (-0.0025 to -0.0013) |

FORGE weights (log-odds per point): elo_weight = 0.00548, form_weight = 0.40989, cross_region_elo_weight = 0.00849, other_league_elo_weight = 0.01023, other_league_forge_elo_weight = 0.00839, other_league_form_weight = 0.29251. Form: half-life 20 games, carry 0.5, prior 5 games.
