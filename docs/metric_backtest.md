## Metric backtest (2026-10-01)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| GLORB | 62.3% | 0.2287 | 0.6490 | +0.0004 (-0.0017 to +0.0025) |
| GLORY | 62.8% | 0.2266 | 0.6446 | -0.0040 (-0.0055 to -0.0026) |
| GLORY+ | 63.1% | 0.2259 | 0.6431 | -0.0055 (-0.0072 to -0.0038) |
| Elo (as of cutoff) | 63.2% | 0.2250 | 0.6410 | -0.0076 (-0.0104 to -0.0047) |
| GlorELO+ | 63.5% | 0.2233 | 0.6374 | -0.0112 (-0.0133 to -0.0092) |
| GlorELO+ (season-weighted) | 63.5% | 0.2234 | 0.6375 | -0.0111 (-0.0132 to -0.0090) |
| Elo (live) | 64.1% | 0.2221 | 0.6345 | -0.0141 (-0.0171 to -0.0111) |
| GlorELO+ (live Elo) | 64.3% | 0.2212 | 0.6327 | -0.0159 (-0.0184 to -0.0136) |

- GlorELO+ vs Elo (as of cutoff): log loss -0.0036 (-0.0050 to -0.0023)
- GlorELO+ (season-weighted) vs Elo (as of cutoff): log loss -0.0035 (-0.0049 to -0.0022)
- GlorELO+ (live Elo) vs Elo (live): log loss -0.0018 (-0.0027 to -0.0009)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| GLORB | 56.3% | 0.2461 | 0.6857 | -0.0006 (-0.0085 to +0.0075) |
| GLORY | 55.4% | 0.2451 | 0.6832 | -0.0031 (-0.0076 to +0.0015) |
| GLORY+ | 63.6% | 0.2258 | 0.6425 | -0.0438 (-0.0564 to -0.0315) |
| Elo (as of cutoff) | 62.7% | 0.2251 | 0.6405 | -0.0458 (-0.0645 to -0.0259) |
| GlorELO+ | 62.9% | 0.2238 | 0.6375 | -0.0487 (-0.0658 to -0.0310) |
| GlorELO+ (season-weighted) | 62.8% | 0.2241 | 0.6382 | -0.0481 (-0.0658 to -0.0297) |
| Elo (live) | 65.0% | 0.2201 | 0.6297 | -0.0566 (-0.0759 to -0.0374) |
| GlorELO+ (live Elo) | 64.6% | 0.2198 | 0.6290 | -0.0573 (-0.0748 to -0.0390) |

- GlorELO+ vs Elo (as of cutoff): log loss -0.0030 (-0.0072 to +0.0011)
- GlorELO+ (season-weighted) vs Elo (as of cutoff): log loss -0.0023 (-0.0067 to +0.0021)
- GlorELO+ (live Elo) vs Elo (live): log loss -0.0007 (-0.0036 to +0.0024)

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
GlorELO+ weights (log-odds per point, all games): GLORY_PLUS_WEIGHT = 0.00983, ELO_WEIGHT = 0.00634
