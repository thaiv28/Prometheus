## Metric backtest (2026-10-01)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| GLORB | 62.3% | 0.2287 | 0.6490 | +0.0004 (-0.0017 to +0.0025) |
| GLORY | 62.8% | 0.2266 | 0.6446 | -0.0040 (-0.0055 to -0.0026) |
| GLORY+ | 63.1% | 0.2260 | 0.6433 | -0.0053 (-0.0070 to -0.0036) |
| Elo (as of cutoff) | 63.1% | 0.2252 | 0.6414 | -0.0072 (-0.0100 to -0.0044) |
| GlorELO+ | 63.5% | 0.2234 | 0.6376 | -0.0110 (-0.0131 to -0.0090) |
| GlorELO+ (season-weighted) | 63.4% | 0.2235 | 0.6377 | -0.0109 (-0.0130 to -0.0088) |
| Elo (live) | 64.1% | 0.2222 | 0.6349 | -0.0137 (-0.0167 to -0.0108) |
| GlorELO+ (live Elo) | 64.4% | 0.2214 | 0.6330 | -0.0156 (-0.0181 to -0.0132) |

- GlorELO+ vs Elo (as of cutoff): log loss -0.0038 (-0.0051 to -0.0025)
- GlorELO+ (season-weighted) vs Elo (as of cutoff): log loss -0.0037 (-0.0050 to -0.0024)
- GlorELO+ (live Elo) vs Elo (live): log loss -0.0019 (-0.0029 to -0.0011)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| GLORB | 56.3% | 0.2461 | 0.6857 | -0.0006 (-0.0085 to +0.0075) |
| GLORY | 55.4% | 0.2451 | 0.6832 | -0.0031 (-0.0076 to +0.0015) |
| GLORY+ | 58.3% | 0.2359 | 0.6639 | -0.0224 (-0.0295 to -0.0148) |
| Elo (as of cutoff) | 60.4% | 0.2314 | 0.6540 | -0.0323 (-0.0440 to -0.0201) |
| GlorELO+ | 59.8% | 0.2318 | 0.6548 | -0.0314 (-0.0415 to -0.0209) |
| GlorELO+ (season-weighted) | 59.9% | 0.2321 | 0.6554 | -0.0309 (-0.0413 to -0.0201) |
| Elo (live) | 60.6% | 0.2274 | 0.6456 | -0.0407 (-0.0534 to -0.0279) |
| GlorELO+ (live Elo) | 60.6% | 0.2283 | 0.6474 | -0.0389 (-0.0500 to -0.0273) |

- GlorELO+ vs Elo (as of cutoff): log loss +0.0009 (-0.0028 to +0.0047)
- GlorELO+ (season-weighted) vs Elo (as of cutoff): log loss +0.0014 (-0.0023 to +0.0054)
- GlorELO+ (live Elo) vs Elo (live): log loss +0.0018 (-0.0008 to +0.0044)

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
GlorELO+ weights (log-odds per point, all games): GLORY_PLUS_WEIGHT = 0.00976, ELO_WEIGHT = 0.00636
