## Metric backtest (2026-10-06)

### Domestic: 16,765 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6905 | +0.0419 (+0.0376 to +0.0460) |
| Win % so far | 62.7% | 0.2285 | 0.6486 | baseline |
| Elo (as of cutoff) | 63.7% | 0.2240 | 0.6389 | -0.0097 (-0.0125 to -0.0069) |
| Elo (live) | 64.3% | 0.2208 | 0.6318 | -0.0168 (-0.0203 to -0.0135) |
| Team Elo, no player ratings (live) | 64.3% | 0.2221 | 0.6345 | -0.0141 (-0.0171 to -0.0111) |
| Form (live) | 64.1% | 0.2216 | 0.6336 | -0.0151 (-0.0181 to -0.0120) |
| FORGE (live) | 64.7% | 0.2195 | 0.6290 | -0.0196 (-0.0228 to -0.0166) |

- FORGE (live) vs Elo (live): log loss -0.0028 (-0.0039 to -0.0016)
- Form (live) vs Elo (live): log loss +0.0018 (-0.0008 to +0.0043)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0028 (-0.0048 to -0.0007)

### International: 979 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.3% | 0.2490 | 0.6911 | +0.0049 (-0.0054 to +0.0139) |
| Win % so far | 54.5% | 0.2466 | 0.6863 | baseline |
| Elo (as of cutoff) | 64.5% | 0.2253 | 0.6414 | -0.0449 (-0.0619 to -0.0275) |
| Elo (live) | 65.3% | 0.2205 | 0.6310 | -0.0552 (-0.0729 to -0.0378) |
| Team Elo, no player ratings (live) | 65.2% | 0.2215 | 0.6332 | -0.0531 (-0.0725 to -0.0337) |
| Form (live) | 57.4% | 0.2404 | 0.6733 | -0.0130 (-0.0238 to -0.0020) |
| FORGE (live) | 65.3% | 0.2205 | 0.6310 | -0.0552 (-0.0729 to -0.0378) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0423 (+0.0280 to +0.0574)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0022 (-0.0081 to +0.0038)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,765 | 0.6345 | 0.6318 | -0.0028 (-0.0048 to -0.0007) |
| Either team in its first 10 games of the season | 324 | 0.6302 | 0.6127 | -0.0176 (-0.0408 to +0.0058) |
| Either team within 10 games of a starter change | 10,300 | 0.6309 | 0.6292 | -0.0017 (-0.0046 to +0.0013) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 9,430 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 9,430 | 66.8% | 0.2097 | 0.6070 |
| Major v major | 1,039 | 63.4% | 0.2224 | 0.6360 |
| Major v other | 1,771 | 68.8% | 0.2040 | 0.5928 |
| Other v other | 6,620 | 66.8% | 0.2092 | 0.6062 |
| At an international event | 2,182 | 65.4% | 0.2135 | 0.6140 |
| At any other event (EMEA Masters, cups, promotion) | 7,248 | 67.2% | 0.2085 | 0.6049 |

### Within other leagues: 67,928 games, 2014–2027

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 67,928 | 0.6453 | 0.6285 | 0.6270 | -0.0168 (-0.0181 to -0.0154) | -0.0015 (-0.0020 to -0.0011) |
| 2022 on | 36,122 | 0.6398 | 0.6232 | 0.6213 | -0.0167 (-0.0186 to -0.0148) | -0.0018 (-0.0026 to -0.0011) |

#### FORGE within other leagues: 67,928 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 67,928 | 0.6285 | 0.6270 | 0.6217 | 64.2% | 64.8% | -0.0052 (-0.0062 to -0.0043) | -0.0068 (-0.0076 to -0.0059) |
| 2022 on | 36,122 | 0.6232 | 0.6213 | 0.6161 | 64.6% | 65.4% | -0.0053 (-0.0066 to -0.0039) | -0.0071 (-0.0084 to -0.0059) |

FORGE weights (log-odds per point): elo_weight = 0.00495, form_weight = 0.49345, cross_region_elo_weight = 0.00875, other_league_elo_weight = 0.01238, other_league_forge_elo_weight = 0.00782, other_league_form_weight = 0.51388. Form: half-life 20 games, carry 0.5, prior 5 games.
