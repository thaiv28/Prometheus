## Metric backtest (2026-10-12)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0382 to +0.0465) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.6% | 0.2243 | 0.6394 | -0.0086 (-0.0114 to -0.0057) |
| Elo (live) | 64.4% | 0.2206 | 0.6312 | -0.0169 (-0.0203 to -0.0135) |
| Team Elo, no player ratings (live) | 64.1% | 0.2221 | 0.6346 | -0.0135 (-0.0166 to -0.0104) |
| Form (live) | 64.0% | 0.2220 | 0.6345 | -0.0135 (-0.0166 to -0.0105) |
| FORGE (live) | 64.9% | 0.2193 | 0.6285 | -0.0196 (-0.0227 to -0.0164) |

- FORGE (live) vs Elo (live): log loss -0.0027 (-0.0038 to -0.0015)
- Form (live) vs Elo (live): log loss +0.0034 (+0.0005 to +0.0062)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0034 (-0.0057 to -0.0012)

### International: 1,024 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.2% | 0.2491 | 0.6913 | +0.0034 (-0.0066 to +0.0136) |
| Win % so far | 54.2% | 0.2474 | 0.6879 | baseline |
| Elo (as of cutoff) | 65.1% | 0.2232 | 0.6369 | -0.0510 (-0.0691 to -0.0323) |
| Elo (live) | 65.0% | 0.2178 | 0.6244 | -0.0635 (-0.0825 to -0.0441) |
| Team Elo, no player ratings (live) | 66.3% | 0.2182 | 0.6255 | -0.0624 (-0.0818 to -0.0416) |
| Form (live) | 58.3% | 0.2385 | 0.6697 | -0.0182 (-0.0290 to -0.0064) |
| FORGE (live) | 65.0% | 0.2178 | 0.6244 | -0.0635 (-0.0825 to -0.0441) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0452 (+0.0294 to +0.0606)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0010 (-0.0069 to +0.0053)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6346 | 0.6312 | -0.0034 (-0.0057 to -0.0012) |
| Either team in its first 10 games of the season | 347 | 0.6338 | 0.6134 | -0.0204 (-0.0438 to +0.0031) |
| Either team within 10 games of a starter change | 10,313 | 0.6308 | 0.6280 | -0.0028 (-0.0059 to +0.0003) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,184 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,184 | 68.2% | 0.2035 | 0.5925 |
| Major v major | 1,052 | 64.0% | 0.2203 | 0.6304 |
| Major v other | 1,920 | 69.6% | 0.1998 | 0.5820 |
| Other v other | 7,212 | 68.5% | 0.2021 | 0.5898 |
| At an international event | 2,219 | 65.9% | 0.2107 | 0.6072 |
| At any other event (EMEA Masters, cups, promotion) | 7,965 | 68.9% | 0.2015 | 0.5885 |

### Within other leagues: 69,736 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6240 | 0.6107 | 0.6094 | -0.0132 (-0.0143 to -0.0120) | -0.0014 (-0.0018 to -0.0009) |
| 2022 on | 37,248 | 0.6180 | 0.6049 | 0.6036 | -0.0131 (-0.0147 to -0.0115) | -0.0014 (-0.0020 to -0.0007) |

#### FORGE within other leagues: 69,736 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6107 | 0.6094 | 0.6076 | 65.9% | 66.2% | -0.0018 (-0.0025 to -0.0011) | -0.0032 (-0.0037 to -0.0026) |
| 2022 on | 37,248 | 0.6049 | 0.6036 | 0.6012 | 66.3% | 66.7% | -0.0024 (-0.0035 to -0.0013) | -0.0037 (-0.0045 to -0.0029) |

FORGE weights (log-odds per point): elo_weight = 0.00526, form_weight = 0.45336, cross_region_elo_weight = 0.00859, other_league_elo_weight = 0.01012, other_league_forge_elo_weight = 0.00784, other_league_form_weight = 0.37737. Form: half-life 20 games, carry 0.5, prior 5 games.
