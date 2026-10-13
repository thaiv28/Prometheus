## Metric backtest (2026-10-12)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0382 to +0.0465) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.3% | 0.2244 | 0.6396 | -0.0084 (-0.0113 to -0.0055) |
| Elo (live) | 64.4% | 0.2207 | 0.6313 | -0.0168 (-0.0202 to -0.0134) |
| Team Elo, no player ratings (live) | 64.1% | 0.2221 | 0.6346 | -0.0135 (-0.0166 to -0.0104) |
| Form (live) | 64.0% | 0.2218 | 0.6341 | -0.0139 (-0.0168 to -0.0110) |
| FORGE (live) | 64.7% | 0.2195 | 0.6289 | -0.0191 (-0.0222 to -0.0161) |

- FORGE (live) vs Elo (live): log loss -0.0024 (-0.0035 to -0.0012)
- Form (live) vs Elo (live): log loss +0.0028 (+0.0001 to +0.0055)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0033 (-0.0056 to -0.0011)

### International: 1,024 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.2% | 0.2491 | 0.6913 | +0.0034 (-0.0066 to +0.0136) |
| Win % so far | 54.2% | 0.2474 | 0.6879 | baseline |
| Elo (as of cutoff) | 64.0% | 0.2227 | 0.6357 | -0.0522 (-0.0701 to -0.0331) |
| Elo (live) | 65.5% | 0.2175 | 0.6238 | -0.0641 (-0.0832 to -0.0448) |
| Team Elo, no player ratings (live) | 66.3% | 0.2182 | 0.6255 | -0.0624 (-0.0818 to -0.0416) |
| Form (live) | 57.4% | 0.2395 | 0.6716 | -0.0163 (-0.0264 to -0.0058) |
| FORGE (live) | 65.5% | 0.2175 | 0.6238 | -0.0641 (-0.0832 to -0.0448) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0478 (+0.0316 to +0.0633)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0017 (-0.0077 to +0.0040)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6346 | 0.6313 | -0.0033 (-0.0056 to -0.0011) |
| Either team in its first 10 games of the season | 347 | 0.6338 | 0.6073 | -0.0264 (-0.0493 to -0.0038) |
| Either team within 10 games of a starter change | 10,313 | 0.6308 | 0.6278 | -0.0030 (-0.0060 to +0.0000) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,184 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,184 | 67.5% | 0.2065 | 0.5999 |
| Major v major | 1,052 | 63.7% | 0.2204 | 0.6308 |
| Major v other | 1,920 | 68.1% | 0.2022 | 0.5876 |
| Other v other | 7,212 | 68.0% | 0.2057 | 0.5987 |
| At an international event | 2,219 | 64.5% | 0.2134 | 0.6135 |
| At any other event (EMEA Masters, cups, promotion) | 7,965 | 68.4% | 0.2046 | 0.5961 |

### Within other leagues: 69,736 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6252 | 0.6122 | 0.6110 | -0.0130 (-0.0142 to -0.0118) | -0.0012 (-0.0016 to -0.0008) |
| 2022 on | 37,248 | 0.6200 | 0.6061 | 0.6050 | -0.0138 (-0.0154 to -0.0122) | -0.0012 (-0.0017 to -0.0006) |

#### FORGE within other leagues: 69,736 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6122 | 0.6110 | 0.6090 | 65.6% | 66.0% | -0.0020 (-0.0026 to -0.0013) | -0.0032 (-0.0037 to -0.0026) |
| 2022 on | 37,248 | 0.6061 | 0.6050 | 0.6027 | 66.0% | 66.7% | -0.0023 (-0.0033 to -0.0012) | -0.0035 (-0.0043 to -0.0026) |

FORGE weights (log-odds per point): elo_weight = 0.00515, form_weight = 0.45487, cross_region_elo_weight = 0.00858, other_league_elo_weight = 0.01013, other_league_forge_elo_weight = 0.00802, other_league_form_weight = 0.33520. Form: half-life 20 games, carry 0.5, prior 5 games.
