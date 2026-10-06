# Elo margin variants: combined / learned margins and update settings

Script: `scripts/elo_variants_combined.py` (harness `scripts/elo_variants.py`). Runtime 7.2 min.

## Protocol

- Tuning seasons 2014–2021; held-out seasons 2022–2026. Everything learned (z-score means and sds, learned and PCA weights, composite sd, every grid choice) uses training seasons only. Objective: domestic Elo-live log loss on training seasons (curves fit only on them).
- Features (winner minus loser): gold, kills, towers; shortness = minus game length. Coverage of all three stats is ~100% every season; missing stats fall back to the game-length score.
- Composites are rescaled to unit sd on training games, then squashed with `bounded(c, scale, center, lower, upper=1.0)` over {'scale': [0.5, 1.0, 2.0], 'center': [-0.5, 0.0, 0.5], 'lower': [0.55, 0.65, 0.75]} (27 points).
- 1a learned weights: logistic model of each team's next game (both in training seasons, 95,316 team-games), offset by plain Elo's pre-match gap (every win scores 1.0, K=20), margins signed + for the winner, − for the loser. Weights (per z): gold +0.084, kills -0.019, towers +0.005, short +0.065.
- 1b first principal component of the four z-scores (63% of variance): gold +0.559, kills +0.491, towers +0.509, short +0.433.
- Training correlations of the z-scores: gold/kills 0.64, gold/towers 0.72, gold/short 0.40, kills/towers 0.39, kills/short 0.45, towers/short 0.43.
- 3 re-tunes the published logistic in game length: {'lower_bound': [0.55, 0.65, 0.75], 'center': [1500, 1800, 2100], 'steepness': [2, 3, 5]} (upper bound 1.0).
- 4a tunes K over [12, 16, 20, 24, 28, 32, 40] with the published margin; 4b the same K grid with the composite that did best on training (1a. Dominance, learned (next game), squash {'scale': 0.5, 'center': 0.5, 'lower': 0.55} fixed).
- 5 keeps the game-length score and adds `bonus` (capped at 1.0) only when that composite exceeds `threshold` sds: {'threshold': [1.0, 1.5, 2.0], 'bonus': [0.05, 0.1, 0.2]}.
- 7 candidates, 131 parameter points evaluated on training seasons. Δ = variant minus baseline (published Elo, game length, K=20) on the same held-out games, paired bootstrap 95% interval; Δ < 0 is better.

## Held-out results (2022 onward), every candidate

Training objective = domestic Elo-live log loss on 2014–2021 (baseline 0.63949).

| Candidate | Chosen params | Train obj. |
|---|---|---:|
| 1a. Dominance, learned (next game) | {'scale': 0.5, 'center': 0.5, 'lower': 0.55} | 0.63766 |
| 1b. Dominance, first PC | {'scale': 0.5, 'center': 0.0, 'lower': 0.55} | 0.63812 |
| 2. Equal-weight z composite | {'scale': 0.5, 'center': 0.0, 'lower': 0.55} | 0.63806 |
| 3. Game length, re-tuned shape | {'lower_bound': 0.55, 'center': 1500, 'steepness': 3} | 0.63891 |
| 4a. K, published margin | {'K': 28} | 0.63896 |
| 4b. K, with Dominance, learned (next game) | {'K': 28} | 0.63683 |
| 5. Asymmetric (bonus for extreme composite) | {'threshold': 1.0, 'bonus': 0.2} | 0.63866 |

| Variant | Elo dom. log loss (Δ, 95% CI) | Elo intl. log loss (Δ, 95% CI) | FORGE dom. log loss (Δ, 95% CI) | FORGE intl. log loss (Δ, 95% CI) |
|---|---|---|---|---|
| 1a. Dominance, learned (next game) | 0.6223 (-0.0010, -0.0025 to +0.0006) | 0.6087 (-0.0071, -0.0144 to -0.0001) | 0.6205 (-0.0003, -0.0013 to +0.0006) | 0.6087 (-0.0071, -0.0144 to -0.0001) |
| 1b. Dominance, first PC | 0.6231 (-0.0002, -0.0016 to +0.0012) | 0.6126 (-0.0032, -0.0095 to +0.0031) | 0.6210 (+0.0002, -0.0007 to +0.0010) | 0.6126 (-0.0032, -0.0095 to +0.0031) |
| 2. Equal-weight z composite | 0.6230 (-0.0002, -0.0016 to +0.0011) | 0.6124 (-0.0034, -0.0097 to +0.0027) | 0.6209 (+0.0002, -0.0007 to +0.0009) | 0.6124 (-0.0034, -0.0097 to +0.0027) |
| 3. Game length, re-tuned shape | 0.6229 (-0.0003, -0.0007 to +0.0001) | 0.6134 (-0.0025, -0.0044 to -0.0005) | 0.6207 (-0.0001, -0.0004 to +0.0001) | 0.6134 (-0.0025, -0.0044 to -0.0005) |
| 4a. K, published margin | 0.6236 (+0.0004, -0.0005 to +0.0012) | 0.6184 (+0.0026, -0.0009 to +0.0060) | 0.6214 (+0.0006, +0.0001 to +0.0011) | 0.6184 (+0.0026, -0.0009 to +0.0060) |
| 4b. K, with Dominance, learned (next game) | 0.6223 (-0.0009, -0.0026 to +0.0009) | 0.6106 (-0.0052, -0.0126 to +0.0026) | 0.6210 (+0.0002, -0.0009 to +0.0012) | 0.6106 (-0.0052, -0.0126 to +0.0026) |
| 5. Asymmetric (bonus for extreme composite) | 0.6229 (-0.0003, -0.0008 to +0.0002) | 0.6131 (-0.0028, -0.0051 to -0.0005) | 0.6207 (-0.0001, -0.0004 to +0.0002) | 0.6131 (-0.0028, -0.0051 to -0.0005) |

## Verdict

Best by training objective: **4b. K, with Dominance, learned (next game)** with {'K': 28} (train 0.63683 vs baseline 0.63949).

Held out: Elo live domestic Δ -0.0009 (-0.0026 to +0.0009), international Δ -0.0052 (-0.0126 to +0.0026); FORGE domestic Δ +0.0002 (-0.0009 to +0.0012), international Δ -0.0052 (-0.0126 to +0.0026).

Does **not** meet the significance rule (domestic Elo-live interval must lie entirely below 0 with international not significantly worse).
 With 7 candidates (and 131 tuned points) the intervals are not corrected for multiple comparisons, so a single marginal pass would be weak evidence.

## Notes

- FORGE's international column equals Elo's: FORGE uses Elo alone between leagues.
- Several chosen points sit on a grid edge (scale 0.5 and lower 0.55 for the composites; center 25 min and lower 0.55 for the re-tuned game length): training prefers a steeper, wider-range margin than the published one. A finer or wider grid could move training numbers a little, but every held-out domestic Elo interval already includes 0, so the verdict is unlikely to change.
- The learned (next-game) weights put almost everything on gold (+0.084 per z) and shortness (+0.065); kills (−0.019) and towers (+0.005) add nothing beyond them. The equal-weight and first-PC composites, which give kills and towers a full share, did worse on training than the learned one and are no better than the published margin held out.
- Several international intervals exclude 0 in our favour (1a, 3, 5), and none is significantly worse; the rule decides on domestic Elo live, which no candidate clears.
- K alone (4a, K=28) is slightly worse held out, and significantly worse for FORGE domestic (+0.0006, +0.0001 to +0.0011).
