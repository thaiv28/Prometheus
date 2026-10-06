## Metric backtest (2026-10-05)

### Domestic: 16,773 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0377 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| Elo (as of cutoff) | 63.6% | 0.2242 | 0.6393 | -0.0094 (-0.0123 to -0.0065) |
| Elo (live) | 64.3% | 0.2209 | 0.6319 | -0.0167 (-0.0200 to -0.0134) |
| Team Elo, no player ratings (live) | 64.2% | 0.2220 | 0.6343 | -0.0143 (-0.0174 to -0.0112) |
| Form (live) | 64.1% | 0.2215 | 0.6335 | -0.0151 (-0.0182 to -0.0121) |
| FORGE (live) | 64.8% | 0.2196 | 0.6291 | -0.0195 (-0.0227 to -0.0165) |

- FORGE (live) vs Elo (live): log loss -0.0028 (-0.0040 to -0.0017)
- Form (live) vs Elo (live): log loss +0.0015 (-0.0011 to +0.0040)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0024 (-0.0045 to -0.0002)

### International: 993 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6912 | +0.0052 (-0.0043 to +0.0142) |
| Win % so far | 54.4% | 0.2465 | 0.6860 | baseline |
| Elo (as of cutoff) | 64.2% | 0.2241 | 0.6385 | -0.0475 (-0.0643 to -0.0303) |
| Elo (live) | 65.6% | 0.2197 | 0.6291 | -0.0570 (-0.0740 to -0.0399) |
| Team Elo, no player ratings (live) | 65.3% | 0.2199 | 0.6292 | -0.0569 (-0.0760 to -0.0371) |
| Form (live) | 57.8% | 0.2413 | 0.6754 | -0.0106 (-0.0216 to +0.0004) |
| FORGE (live) | 65.6% | 0.2197 | 0.6291 | -0.0570 (-0.0740 to -0.0399) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0463 (+0.0312 to +0.0614)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0001 (-0.0058 to +0.0055)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,773 | 0.6343 | 0.6319 | -0.0024 (-0.0045 to -0.0002) |
| Either team in its first 10 games of the season | 324 | 0.6309 | 0.6126 | -0.0184 (-0.0430 to +0.0064) |
| Either team within 10 games of a starter change | 10,300 | 0.6307 | 0.6295 | -0.0012 (-0.0040 to +0.0017) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
FORGE weights (log-odds per point): elo_weight = 0.00486, form_weight = 0.50111, cross_region_elo_weight = 0.00873. Form: half-life 20 games, carry 0.5, prior 5 games.
