## Metric backtest (2026-10-02)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| Elo (as of cutoff) | 63.6% | 0.2242 | 0.6393 | -0.0093 (-0.0122 to -0.0065) |
| Elo (live) | 64.3% | 0.2209 | 0.6319 | -0.0167 (-0.0202 to -0.0134) |
| Team Elo, no player ratings (live) | 64.2% | 0.2220 | 0.6343 | -0.0143 (-0.0173 to -0.0113) |
| Form (live) | 64.1% | 0.2215 | 0.6335 | -0.0151 (-0.0182 to -0.0121) |
| FORGE (live) | 64.7% | 0.2196 | 0.6291 | -0.0195 (-0.0226 to -0.0165) |

- FORGE (live) vs Elo (live): log loss -0.0028 (-0.0040 to -0.0016)
- Form (live) vs Elo (live): log loss +0.0015 (-0.0010 to +0.0040)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0024 (-0.0045 to -0.0003)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| Elo (as of cutoff) | 64.2% | 0.2244 | 0.6392 | -0.0471 (-0.0642 to -0.0296) |
| Elo (live) | 65.5% | 0.2200 | 0.6295 | -0.0567 (-0.0746 to -0.0393) |
| Team Elo, no player ratings (live) | 65.4% | 0.2202 | 0.6299 | -0.0564 (-0.0760 to -0.0368) |
| Form (live) | 57.8% | 0.2410 | 0.6746 | -0.0117 (-0.0227 to -0.0006) |
| FORGE (live) | 65.5% | 0.2200 | 0.6295 | -0.0567 (-0.0746 to -0.0393) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0451 (+0.0301 to +0.0610)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0004 (-0.0064 to +0.0053)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,765 | 0.6343 | 0.6319 | -0.0024 (-0.0045 to -0.0003) |
| Either team in its first 10 games of the season | 324 | 0.6309 | 0.6126 | -0.0184 (-0.0430 to +0.0064) |
| Either team within 10 games of a starter change | 10,300 | 0.6307 | 0.6295 | -0.0012 (-0.0040 to +0.0017) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
FORGE weights (log-odds per point): elo_weight = 0.00486, form_weight = 0.50119, cross_region_elo_weight = 0.00873. Form: half-life 20 games, carry 0.5, prior 5 games.
