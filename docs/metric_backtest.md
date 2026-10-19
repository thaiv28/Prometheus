## Metric backtest (2026-10-19)

### Domestic: 16,810 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 53.7% | 0.2487 | 0.6906 | +0.0425 (+0.0382 to +0.0465) |
| Win % so far | 62.8% | 0.2282 | 0.6480 | baseline |
| Elo (as of cutoff) | 63.5% | 0.2240 | 0.6388 | -0.0092 (-0.0119 to -0.0065) |
| Elo (live) | 64.4% | 0.2202 | 0.6303 | -0.0177 (-0.0211 to -0.0145) |
| Team Elo, no player ratings (live) | 64.1% | 0.2221 | 0.6346 | -0.0135 (-0.0166 to -0.0104) |
| Form (live) | 64.0% | 0.2220 | 0.6345 | -0.0136 (-0.0167 to -0.0106) |
| FORGE (live) | 64.8% | 0.2193 | 0.6284 | -0.0196 (-0.0227 to -0.0166) |

- FORGE (live) vs Elo (live): log loss -0.0019 (-0.0028 to -0.0009)
- Form (live) vs Elo (live): log loss +0.0042 (+0.0015 to +0.0068)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0043 (-0.0065 to -0.0022)

### International: 1,057 games, 2014–2026

| Metric | Accuracy | Brier | Log loss | Log loss vs win % (95% CI) |
|---|---:|---:|---:|---|
| Blue side wins | 52.7% | 0.2494 | 0.6920 | +0.0030 (-0.0065 to +0.0126) |
| Win % so far | 53.6% | 0.2479 | 0.6889 | baseline |
| Elo (as of cutoff) | 64.0% | 0.2244 | 0.6396 | -0.0493 (-0.0659 to -0.0316) |
| Elo (live) | 64.7% | 0.2179 | 0.6252 | -0.0637 (-0.0859 to -0.0394) |
| Team Elo, no player ratings (live) | 65.8% | 0.2198 | 0.6289 | -0.0601 (-0.0794 to -0.0395) |
| Form (live) | 57.9% | 0.2398 | 0.6725 | -0.0165 (-0.0269 to -0.0061) |
| FORGE (live) | 64.7% | 0.2179 | 0.6252 | -0.0637 (-0.0859 to -0.0394) |

- FORGE (live) vs Elo (live): log loss +0.0000 (+0.0000 to +0.0000)
- Form (live) vs Elo (live): log loss +0.0473 (+0.0251 to +0.0682)
- Elo (live) vs Team Elo, no player ratings (live): log loss -0.0037 (-0.0135 to +0.0058)

### Player-built Elo vs team Elo, where rosters matter

| Domestic games | Games | Team Elo log loss | Elo log loss | Difference (95% CI) |
|---|---:|---:|---:|---|
| All | 16,810 | 0.6346 | 0.6303 | -0.0043 (-0.0065 to -0.0022) |
| Either team in its first 10 games of the season | 347 | 0.6339 | 0.6096 | -0.0243 (-0.0460 to -0.0011) |
| Either team within 10 games of a starter change | 10,313 | 0.6308 | 0.6266 | -0.0042 (-0.0071 to -0.0010) |

Lower Brier and log loss are better. A negative log-loss delta means the metric beats win % so far; an interval that excludes 0 is a real difference.
### Cross-league, every league: 10,241 games, 2014–2026

Elo (live) on games between teams from two home leagues at any event; the home is the league a team played most that season.

| Teams | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| All | 10,241 | 68.5% | 0.2022 | 0.5894 |
| Major v major | 1,085 | 64.7% | 0.2188 | 0.6270 |
| Major v other | 1,930 | 69.5% | 0.1988 | 0.5789 |
| Other v other | 7,226 | 68.8% | 0.2006 | 0.5866 |
| At an international event | 2,262 | 67.0% | 0.2075 | 0.5999 |
| At any other event (EMEA Masters, cups, promotion) | 7,979 | 68.9% | 0.2007 | 0.5865 |

### Within other leagues: 69,760 games, 2014–2026

Elo on games inside one non-major league: the standard 400-point curve, one curve fit on the other seasons, and a curve per league fit the same way (each league's slope shrunk toward the pooled one by its sampling error).

| Games | n | Standard | One curve | Per league | One curve vs standard (95% CI) | Per league vs one curve (95% CI) |
|---|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6213 | 0.6081 | 0.6070 | -0.0131 (-0.0143 to -0.0120) | -0.0012 (-0.0016 to -0.0008) |
| 2022 on | 37,272 | 0.6151 | 0.6015 | 0.6004 | -0.0136 (-0.0152 to -0.0120) | -0.0011 (-0.0016 to -0.0005) |

#### FORGE within other leagues: 69,760 games (0 without Form left out)

Elo + Form on one curve fit on the other seasons, with Form's stat weights fit on major-league games of the other seasons (as in the domestic backtest).

| Games | n | Elo, one curve | Elo, per league | FORGE | Accuracy, per league | Accuracy, FORGE | FORGE vs per league (95% CI) | FORGE vs one curve (95% CI) |
|---|---:|---:|---:|---:|---:|---:|---|---|
| All | 69,760 | 0.6081 | 0.6070 | 0.6066 | 66.1% | 66.3% | -0.0003 (-0.0009 to +0.0002) | -0.0015 (-0.0019 to -0.0011) |
| 2022 on | 37,272 | 0.6015 | 0.6004 | 0.5997 | 66.6% | 66.8% | -0.0007 (-0.0015 to +0.0002) | -0.0017 (-0.0023 to -0.0012) |

FORGE weights (log-odds per point): elo_weight = 0.00546, form_weight = 0.41036, cross_region_elo_weight = 0.00847, other_league_elo_weight = 0.01001, other_league_forge_elo_weight = 0.00826, other_league_form_weight = 0.28125. Form: half-life 20 games, carry 0.5, prior 5 games.
