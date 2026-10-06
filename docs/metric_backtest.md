## Metric backtest (2026-10-06)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| Elo (as of cutoff) | 63.6% | 0.2242 | 0.6392 | -0.0094 (-0.0123 to -0.0065) |
| Elo (live) | 64.3% | 0.2209 | 0.6320 | -0.0166 (-0.0200 to -0.0133) |
| Team Elo, no player ratings (live) | 64.2% | 0.2222 | 0.6347 | -0.0139 (-0.0168 to -0.0110) |
| Form (live) | 64.1% | 0.2215 | 0.6334 | -0.0152 (-0.0182 to -0.0121) |
| FORGE (live) | 64.8% | 0.2196 | 0.6292 | -0.0194 (-0.0226 to -0.0164) |

- FORGE (live) vs Elo (live): log loss -0.0028 (-0.0040 to -0.0016)
- Form (live) vs Elo (live): log loss +0.0014 (-0.0010 to +0.0038)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0027 (-0.0047 to -0.0006)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| Elo (as of cutoff) | 64.1% | 0.2244 | 0.6391 | -0.0472 (-0.0642 to -0.0301) |
| Elo (live) | 65.1% | 0.2201 | 0.6299 | -0.0564 (-0.0741 to -0.0389) |
| Team Elo, no player ratings (live) | 64.9% | 0.2208 | 0.6315 | -0.0548 (-0.0746 to -0.0355) |
| Form (live) | 58.1% | 0.2411 | 0.6749 | -0.0114 (-0.0224 to -0.0004) |
| FORGE (live) | 65.1% | 0.2201 | 0.6299 | -0.0564 (-0.0741 to -0.0389) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0450 (+0.0299 to +0.0610)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0016 (-0.0071 to +0.0040)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,765 | 0.6347 | 0.6320 | -0.0027 (-0.0047 to -0.0006) |
| Either team in its first 10 games of the season | 324 | 0.6303 | 0.6113 | -0.0190 (-0.0434 to +0.0054) |
| Either team within 10 games of a starter change | 10,300 | 0.6312 | 0.6295 | -0.0017 (-0.0046 to +0.0012) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 9,430 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 9,430 | 65.5% | 0.2153 | 0.6193 |
| Major v major | 1,039 | 63.4% | 0.2227 | 0.6370 |
| Major v other | 1,771 | 67.9% | 0.2051 | 0.5947 |
| Other v other | 6,620 | 65.2% | 0.2168 | 0.6231 |
| At an international event | 2,182 | 65.4% | 0.2142 | 0.6156 |
| At any other event (EMEA Masters, cups, promotion) | 7,248 | 65.5% | 0.2156 | 0.6204 |

### Within other leagues: 67,926 games, 2014–2027

Elo on games inside one non-major league, with the standard 400-point curve and with a curve fit on the other seasons.

| Games | n | Standard curve log loss | Fitted curve log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 67,926 | 0.6453 | 0.6285 | -0.0168 (-0.0181 to -0.0155) |
| 2022 on | 36,120 | 0.6398 | 0.6230 | -0.0168 (-0.0187 to -0.0148) |

FORGE weights (log-odds per point): elo_weight = 0.00483, form_weight = 0.50500, cross_region_elo_weight = 0.00874, other_league_elo_weight = 0.01241. Form: half-life 20 games, carry 0.5, prior 5 games.
