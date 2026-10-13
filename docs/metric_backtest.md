## Metric backtest (2026-10-12)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0382 to +0.0465) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.3% | 0.2244 | 0.6395 | -0.0086 (-0.0114 to -0.0058) |
| Elo (live) | 64.2% | 0.2208 | 0.6315 | -0.0165 (-0.0198 to -0.0133) |
| Team Elo, no player ratings (live) | 64.2% | 0.2222 | 0.6348 | -0.0133 (-0.0163 to -0.0103) |
| Form (live) | 64.0% | 0.2220 | 0.6345 | -0.0136 (-0.0167 to -0.0105) |
| FORGE (live) | 64.8% | 0.2194 | 0.6286 | -0.0194 (-0.0225 to -0.0164) |

- FORGE (live) vs Elo (live): log loss -0.0029 (-0.0041 to -0.0017)
- Form (live) vs Elo (live): log loss +0.0030 (+0.0002 to +0.0059)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0032 (-0.0056 to -0.0010)

### International: 1,024 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.2% | 0.2491 | 0.6913 | +0.0034 (-0.0066 to +0.0136) |
| Win % so far | 54.2% | 0.2474 | 0.6879 | baseline |
| Elo (as of cutoff) | 64.8% | 0.2240 | 0.6386 | -0.0493 (-0.0664 to -0.0314) |
| Elo (live) | 65.0% | 0.2197 | 0.6289 | -0.0590 (-0.0771 to -0.0406) |
| Team Elo, no player ratings (live) | 64.9% | 0.2198 | 0.6293 | -0.0586 (-0.0775 to -0.0382) |
| Form (live) | 58.0% | 0.2386 | 0.6700 | -0.0179 (-0.0287 to -0.0061) |
| FORGE (live) | 65.0% | 0.2197 | 0.6289 | -0.0590 (-0.0771 to -0.0406) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0411 (+0.0263 to +0.0555)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0004 (-0.0063 to +0.0061)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6348 | 0.6315 | -0.0032 (-0.0056 to -0.0010) |
| Either team in its first 10 games of the season | 347 | 0.6335 | 0.6130 | -0.0204 (-0.0440 to +0.0037) |
| Either team within 10 games of a starter change | 10,313 | 0.6311 | 0.6286 | -0.0025 (-0.0056 to +0.0005) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,184 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,184 | 68.2% | 0.2041 | 0.5940 |
| Major v major | 1,052 | 64.0% | 0.2225 | 0.6355 |
| Major v other | 1,920 | 69.6% | 0.2010 | 0.5850 |
| Other v other | 7,212 | 68.4% | 0.2022 | 0.5903 |
| At an international event | 2,219 | 66.3% | 0.2112 | 0.6090 |
| At any other event (EMEA Masters, cups, promotion) | 7,965 | 68.7% | 0.2021 | 0.5898 |

### Within other leagues: 69,736 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6263 | 0.6124 | 0.6111 | -0.0140 (-0.0151 to -0.0127) | -0.0013 (-0.0017 to -0.0009) |
| 2022 on | 37,248 | 0.6216 | 0.6071 | 0.6057 | -0.0145 (-0.0161 to -0.0128) | -0.0015 (-0.0020 to -0.0008) |

#### FORGE within other leagues: 69,736 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,736 | 0.6124 | 0.6111 | 0.6085 | 65.8% | 66.2% | -0.0026 (-0.0033 to -0.0018) | -0.0039 (-0.0045 to -0.0032) |
| 2022 on | 37,248 | 0.6071 | 0.6057 | 0.6025 | 66.2% | 66.7% | -0.0032 (-0.0043 to -0.0021) | -0.0046 (-0.0055 to -0.0037) |

FORGE weights (log-odds per point): elo_weight = 0.00512, form_weight = 0.46708, cross_region_elo_weight = 0.00853, other_league_elo_weight = 0.01037, other_league_forge_elo_weight = 0.00782, other_league_form_weight = 0.41096. Form: half-life 20 games, carry 0.5, prior 5 games.
