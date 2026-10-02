## Metric backtest (2026-10-01)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| Elo (as of cutoff) | 63.1% | 0.2249 | 0.6409 | -0.0078 (-0.0106 to -0.0048) |
| Elo (live) | 64.1% | 0.2221 | 0.6345 | -0.0141 (-0.0171 to -0.0111) |
| Form (live) | 64.2% | 0.2214 | 0.6332 | -0.0155 (-0.0184 to -0.0125) |
| GlorELO+ (live) | 64.6% | 0.2209 | 0.6319 | -0.0167 (-0.0196 to -0.0138) |

- GlorELO+ (live) vs Elo (live): log loss -0.0026 (-0.0037 to -0.0015)
- Form (live) vs Elo (live): log loss -0.0013 (-0.0033 to +0.0004)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| Elo (as of cutoff) | 63.4% | 0.2250 | 0.6402 | -0.0461 (-0.0649 to -0.0267) |
| Elo (live) | 65.0% | 0.2201 | 0.6297 | -0.0566 (-0.0759 to -0.0374) |
| Form (live) | 57.3% | 0.2422 | 0.6772 | -0.0091 (-0.0195 to +0.0016) |
| GlorELO+ (live) | 65.0% | 0.2201 | 0.6297 | -0.0566 (-0.0759 to -0.0374) |

- GlorELO+ (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0474 (+0.0300 to +0.0653)

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
GlorELO+ weights (log-odds per point): elo_weight = 0.00317, form_weight = 0.65130, cross_region_elo_weight = 0.00842. Form: half-life 20 games, carry 0.5, prior 5 games.
