## Metric backtest (2026-10-19)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0381 to +0.0469) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.4% | 0.2240 | 0.6388 | -0.0093 (-0.0122 to -0.0063) |
| Elo (live) | 64.5% | 0.2202 | 0.6304 | -0.0177 (-0.0210 to -0.0143) |
| Team Elo, no player ratings (live) | 64.2% | 0.2220 | 0.6344 | -0.0137 (-0.0170 to -0.0104) |
| Form (live) | 64.0% | 0.2221 | 0.6348 | -0.0133 (-0.0165 to -0.0099) |
| FORGE (live) | 65.0% | 0.2194 | 0.6286 | -0.0195 (-0.0227 to -0.0162) |

- FORGE (live) vs Elo (live): log loss -0.0018 (-0.0027 to -0.0008)
- Form (live) vs Elo (live): log loss +0.0044 (+0.0018 to +0.0070)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0040 (-0.0061 to -0.0019)

### International: 1,057 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 52.7% | 0.2494 | 0.6920 | +0.0030 (-0.0069 to +0.0127) |
| Win % so far | 53.6% | 0.2479 | 0.6889 | baseline |
| Elo (as of cutoff) | 64.5% | 0.2247 | 0.6408 | -0.0481 (-0.0669 to -0.0278) |
| Elo (live) | 64.4% | 0.2177 | 0.6250 | -0.0640 (-0.0885 to -0.0395) |
| Team Elo, no player ratings (live) | 65.5% | 0.2211 | 0.6322 | -0.0567 (-0.0761 to -0.0379) |
| Form (live) | 58.0% | 0.2399 | 0.6727 | -0.0162 (-0.0283 to -0.0041) |
| FORGE (live) | 64.4% | 0.2177 | 0.6250 | -0.0640 (-0.0885 to -0.0395) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0478 (+0.0262 to +0.0697)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0072 (-0.0196 to +0.0053)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6344 | 0.6304 | -0.0040 (-0.0061 to -0.0019) |
| Either team in its first 10 games of the season | 347 | 0.6327 | 0.6073 | -0.0254 (-0.0489 to -0.0029) |
| Either team within 10 games of a starter change | 10,313 | 0.6304 | 0.6266 | -0.0038 (-0.0067 to -0.0010) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far. Intervals resample whole series (games between the same two teams within 12 hours).
### Cross-league, every league: 10,241 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,241 | 69.1% | 0.1984 | 0.5807 |
| Major v major | 1,085 | 64.2% | 0.2186 | 0.6268 |
| Major v other | 1,930 | 69.9% | 0.1970 | 0.5753 |
| Other v other | 7,226 | 69.7% | 0.1957 | 0.5752 |
| At an international event | 2,262 | 66.8% | 0.2067 | 0.5982 |
| At any other event (EMEA Masters, cups, promotion) | 7,979 | 69.8% | 0.1960 | 0.5758 |

### Within other leagues: 69,760 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6216 | 0.6080 | 0.6069 | -0.0136 (-0.0147 to -0.0124) | -0.0011 (-0.0015 to -0.0007) |
| 2022 on | 37,272 | 0.6154 | 0.6016 | 0.6006 | -0.0138 (-0.0154 to -0.0120) | -0.0010 (-0.0015 to -0.0004) |

#### FORGE within other leagues: 69,760 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6080 | 0.6069 | 0.6062 | 66.1% | 66.3% | -0.0006 (-0.0012 to -0.0000) | -0.0017 (-0.0022 to -0.0013) |
| 2022 on | 37,272 | 0.6016 | 0.6006 | 0.5995 | 66.6% | 66.8% | -0.0011 (-0.0020 to -0.0002) | -0.0021 (-0.0027 to -0.0014) |

FORGE weights (log-odds per point): elo_weight = 0.00556, form_weight = 0.40326, cross_region_elo_weight = 0.00852, other_league_elo_weight = 0.01013, other_league_forge_elo_weight = 0.00833, other_league_form_weight = 0.29236. Form: half-life 20 games, carry 0.5, prior 5 games.
