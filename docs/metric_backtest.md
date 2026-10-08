## Metric backtest (2026-10-07)

### Domestic: 16,802 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0383 to +0.0466) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.7% | 0.2243 | 0.6395 | -0.0086 (-0.0114 to -0.0058) |
| Elo (live) | 64.4% | 0.2210 | 0.6321 | -0.0159 (-0.0191 to -0.0128) |
| Team Elo, no player ratings (live) | 64.2% | 0.2222 | 0.6347 | -0.0133 (-0.0165 to -0.0103) |
| Form (live) | 64.0% | 0.2217 | 0.6339 | -0.0142 (-0.0172 to -0.0111) |
| FORGE (live) | 64.8% | 0.2197 | 0.6294 | -0.0187 (-0.0218 to -0.0157) |

- FORGE (live) vs Elo (live): log loss -0.0027 (-0.0039 to -0.0016)
- Form (live) vs Elo (live): log loss +0.0018 (-0.0007 to +0.0042)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0026 (-0.0046 to -0.0005)

### International: 1,004 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6912 | +0.0032 (-0.0068 to +0.0131) |
| Win % so far | 54.5% | 0.2474 | 0.6880 | baseline |
| Elo (as of cutoff) | 64.3% | 0.2240 | 0.6381 | -0.0499 (-0.0656 to -0.0338) |
| Elo (live) | 65.6% | 0.2192 | 0.6280 | -0.0600 (-0.0776 to -0.0427) |
| Team Elo, no player ratings (live) | 65.0% | 0.2200 | 0.6296 | -0.0583 (-0.0773 to -0.0396) |
| Form (live) | 58.4% | 0.2393 | 0.6711 | -0.0169 (-0.0275 to -0.0062) |
| FORGE (live) | 65.6% | 0.2192 | 0.6280 | -0.0600 (-0.0776 to -0.0427) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0431 (+0.0290 to +0.0572)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0016 (-0.0070 to +0.0038)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,802 | 0.6347 | 0.6321 | -0.0026 (-0.0046 to -0.0005) |
| Either team in its first 10 games of the season | 347 | 0.6335 | 0.6106 | -0.0228 (-0.0446 to +0.0003) |
| Either team within 10 games of a starter change | 10,313 | 0.6311 | 0.6295 | -0.0017 (-0.0046 to +0.0013) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,057 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,057 | 65.7% | 0.2152 | 0.6194 |
| Major v major | 1,032 | 63.9% | 0.2223 | 0.6358 |
| Major v other | 1,896 | 66.7% | 0.2099 | 0.6047 |
| Other v other | 7,129 | 65.7% | 0.2156 | 0.6209 |
| At an international event | 2,180 | 65.3% | 0.2143 | 0.6159 |
| At any other event (EMEA Masters, cups, promotion) | 7,877 | 65.8% | 0.2155 | 0.6204 |

### Within other leagues: 69,603 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,603 | 0.6457 | 0.6288 | 0.6271 | -0.0169 (-0.0182 to -0.0156) | -0.0017 (-0.0021 to -0.0011) |
| 2022 on | 37,115 | 0.6401 | 0.6233 | 0.6212 | -0.0169 (-0.0188 to -0.0150) | -0.0021 (-0.0028 to -0.0013) |

#### FORGE within other leagues: 69,603 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,603 | 0.6288 | 0.6271 | 0.6222 | 64.2% | 64.8% | -0.0049 (-0.0058 to -0.0039) | -0.0065 (-0.0074 to -0.0057) |
| 2022 on | 37,115 | 0.6233 | 0.6212 | 0.6167 | 64.6% | 65.5% | -0.0045 (-0.0060 to -0.0032) | -0.0066 (-0.0078 to -0.0054) |

FORGE weights (log-odds per point): elo_weight = 0.00492, form_weight = 0.49364, cross_region_elo_weight = 0.00876, other_league_elo_weight = 0.01248, other_league_forge_elo_weight = 0.00786, other_league_form_weight = 0.51312. Form: half-life 20 games, carry 0.5, prior 5 games.
