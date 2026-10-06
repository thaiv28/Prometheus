# Elo variants: gold-based margins of victory

Can a gold-based "margin of victory" beat the published game-length margin in player-built Elo?
No. On the held-out seasons, none of the gold margins clears the significance rule in AGENTS.md.

Script: `scripts/elo_variants_gold.py` (uses the harness in `scripts/elo_variants.py`).
Runtime: 402 s for the whole run (single BLAS thread, load ~20 s).

## Protocol

- The baseline is the published margin: the winner's score is a logistic in game length (1.0 to 0.65), with K = 20.
- Every candidate is tuned with `held_out`: a grid search on seasons 2014–2021 only. The objective is domestic Elo-live log loss.
  The candidate is then scored on 2022 onward against the baseline on the same games. Win curves and Form weights come only from the scored seasons.
- Each Δ is the variant minus the baseline, with a paired-bootstrap 95% interval. Below 0 means the variant is better.
  FORGE is refit on each variant, because Form's opponent adjustment uses the variant's Elo.
- Gold margins go through `bounded(x, scale, center, lower)`, a logistic into (lower, 1).
  A game without recorded gold falls back to the game-length score (`with_fallback`). Gold coverage is at least 98.8% in every season.
- Candidates, with grid points in brackets:
  0. Control: the published game-length margin with only K tuned [6].
  1. Binary result, where the winner scores 1.0 and there is no margin; K tuned [6].
  2. Gold difference: center {5k, 10k} × scale {2.5k, 5k, 10k} × lower {0.55, 0.7} × K {20, 30} [24].
  3. Gold share, the winner's share of both teams' gold: center {0.53, 0.55} × scale {0.01, 0.02, 0.04} × lower × K [24].
  4. Gold difference per minute: center {250, 350} × scale {75, 150, 300} × lower × K [24].
  5. Blend: w × the gold-difference score (center 10k, lower 0.65) + (1 − w) × the game-length score. w {0.25, 0.5, 0.75} × scale {2.5k, 5k} × K {20, 30} [12].
  6–7. Extended grids for 3 and 4 [12 + 12]. Their first optima sat on the K = 30 and lower = 0.55 edges, so these grids add lower 0.51, K 40/50 and a higher center. They were still tuned on training seasons only.
- In total: 8 tuned candidates (6 margin families) and 120 grid points. The held-out intervals are not corrected for multiple comparisons.
  With this many candidates, one marginal "significant" result would be expected by chance anyway.

## Held-out seasons (2022 on): every candidate

Baseline: domestic Elo live 0.6232, FORGE 0.6208; international 0.6158.

| Variant | Elo dom. log loss (Δ, 95% CI) | Elo intl. log loss (Δ, 95% CI) | FORGE dom. log loss (Δ, 95% CI) | FORGE intl. log loss (Δ, 95% CI) |
|---|---|---|---|---|
| Control: game length, K tuned {'K': 28} | 0.6236 (+0.0004, -0.0005 to +0.0012) | 0.6184 (+0.0026, -0.0009 to +0.0060) | 0.6214 (+0.0006, +0.0001 to +0.0011) | 0.6184 (+0.0026, -0.0009 to +0.0060) |
| Binary result (no margin) {'K': 24} | 0.6242 (+0.0009, +0.0003 to +0.0016) | 0.6215 (+0.0056, +0.0026 to +0.0085) | 0.6212 (+0.0004, +0.0000 to +0.0008) | 0.6215 (+0.0056, +0.0026 to +0.0085) |
| Gold difference {'center': 5000, 'scale': 2500, 'lower': 0.55, 'K': 30} | 0.6234 (+0.0002, -0.0009 to +0.0013) | 0.6186 (+0.0028, -0.0025 to +0.0079) | 0.6214 (+0.0006, -0.0000 to +0.0013) | 0.6186 (+0.0028, -0.0025 to +0.0079) |
| Gold share {'center': 0.55, 'scale': 0.02, 'lower': 0.55, 'K': 30} | 0.6227 (-0.0005, -0.0019 to +0.0010) | 0.6143 (-0.0015, -0.0078 to +0.0052) | 0.6213 (+0.0005, -0.0003 to +0.0014) | 0.6143 (-0.0015, -0.0078 to +0.0052) |
| Gold diff per minute {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30} | 0.6225 (-0.0007, -0.0025 to +0.0011) | 0.6144 (-0.0014, -0.0089 to +0.0068) | 0.6211 (+0.0003, -0.0008 to +0.0014) | 0.6144 (-0.0014, -0.0089 to +0.0068) |
| Gold diff + game length blend {'weight': 0.5, 'scale': 2500, 'K': 30} | 0.6231 (-0.0001, -0.0011 to +0.0010) | 0.6184 (+0.0025, -0.0024 to +0.0071) | 0.6213 (+0.0005, -0.0001 to +0.0012) | 0.6184 (+0.0025, -0.0024 to +0.0071) |
| Gold share (extended grid) {'center': 0.55, 'scale': 0.02, 'lower': 0.51, 'K': 30} | 0.6228 (-0.0004, -0.0020 to +0.0012) | 0.6136 (-0.0022, -0.0094 to +0.0053) | 0.6214 (+0.0006, -0.0004 to +0.0016) | 0.6136 (-0.0022, -0.0094 to +0.0053) |
| Gold diff per minute (extended grid) {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30} | 0.6225 (-0.0007, -0.0025 to +0.0011) | 0.6144 (-0.0014, -0.0089 to +0.0068) | 0.6211 (+0.0003, -0.0008 to +0.0014) | 0.6144 (-0.0014, -0.0089 to +0.0068) |

## Training seasons (2014–2021)

These numbers are in sample for the tuned parameters, so they are optimistic.

Training objective (domestic Elo log loss, baseline 0.63949), best first:

```
  0.63686  Gold share (extended grid) {'center': 0.55, 'scale': 0.02, 'lower': 0.51, 'K': 30}
  0.63699  Gold share {'center': 0.55, 'scale': 0.02, 'lower': 0.55, 'K': 30}
  0.63710  Gold diff per minute {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30}
  0.63710  Gold diff per minute (extended grid) {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30}
  0.63820  Gold diff + game length blend {'weight': 0.5, 'scale': 2500, 'K': 30}
  0.63851  Gold difference {'center': 5000, 'scale': 2500, 'lower': 0.55, 'K': 30}
  0.63896  Control: game length, K tuned {'K': 28}
  0.64082  Binary result (no margin) {'K': 24}
```

| Variant | Elo dom. log loss (Δ, 95% CI) | Elo intl. log loss (Δ, 95% CI) | FORGE dom. log loss (Δ, 95% CI) | FORGE intl. log loss (Δ, 95% CI) |
|---|---|---|---|---|
| Control: game length, K tuned {'K': 28} | 0.6390 (-0.0005, -0.0013 to +0.0003) | 0.6506 (+0.0035, -0.0005 to +0.0077) | 0.6369 (-0.0000, -0.0005 to +0.0005) | 0.6506 (+0.0035, -0.0005 to +0.0077) |
| Binary result (no margin) {'K': 24} | 0.6408 (+0.0013, +0.0007 to +0.0020) | 0.6538 (+0.0067, +0.0031 to +0.0102) | 0.6375 (+0.0006, +0.0002 to +0.0010) | 0.6538 (+0.0067, +0.0031 to +0.0102) |
| Gold difference {'center': 5000, 'scale': 2500, 'lower': 0.55, 'K': 30} | 0.6385 (-0.0010, -0.0022 to +0.0003) | 0.6512 (+0.0042, -0.0028 to +0.0108) | 0.6367 (-0.0002, -0.0010 to +0.0006) | 0.6512 (+0.0042, -0.0028 to +0.0108) |
| Gold share {'center': 0.55, 'scale': 0.02, 'lower': 0.55, 'K': 30} | 0.6370 (-0.0025, -0.0040 to -0.0009) | 0.6458 (-0.0012, -0.0100 to +0.0074) | 0.6359 (-0.0010, -0.0020 to -0.0001) | 0.6458 (-0.0012, -0.0100 to +0.0074) |
| Gold diff per minute {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30} | 0.6371 (-0.0024, -0.0043 to -0.0005) | 0.6449 (-0.0021, -0.0127 to +0.0084) | 0.6359 (-0.0010, -0.0022 to +0.0002) | 0.6449 (-0.0021, -0.0127 to +0.0084) |
| Gold diff + game length blend {'weight': 0.5, 'scale': 2500, 'K': 30} | 0.6382 (-0.0013, -0.0024 to -0.0001) | 0.6503 (+0.0033, -0.0030 to +0.0096) | 0.6366 (-0.0003, -0.0011 to +0.0004) | 0.6503 (+0.0033, -0.0030 to +0.0096) |
| Gold share (extended grid) {'center': 0.55, 'scale': 0.02, 'lower': 0.51, 'K': 30} | 0.6369 (-0.0026, -0.0043 to -0.0009) | 0.6448 (-0.0023, -0.0120 to +0.0073) | 0.6358 (-0.0011, -0.0023 to -0.0000) | 0.6448 (-0.0023, -0.0120 to +0.0073) |
| Gold diff per minute (extended grid) {'center': 350, 'scale': 75, 'lower': 0.55, 'K': 30} | 0.6371 (-0.0024, -0.0043 to -0.0005) | 0.6449 (-0.0021, -0.0127 to +0.0084) | 0.6359 (-0.0010, -0.0022 to +0.0002) | 0.6449 (-0.0021, -0.0127 to +0.0084) |

## Verdict

- **Choice by training performance:** gold share with center 0.55, scale 0.02, lower 0.51 and K 30 (training 0.63686, against 0.63949 for the baseline).
  On training seasons it is significantly better for domestic Elo (−0.0026, −0.0043 to −0.0009). That gain is in sample.
- **Held out (2022 on):**
  - Domestic Elo live: −0.0004 (−0.0020 to +0.0012). The interval includes 0, so it **fails the rule**.
  - International: −0.0022 (−0.0094 to +0.0053). Not worse.
  - FORGE domestic: +0.0006 (−0.0004 to +0.0016). No gain.
- Gold difference per minute performs about the same: −0.0007 (−0.0025 to +0.0011) held out. It also fails the rule.
- **Does any margin matter?** Yes, a little. The binary result (no margin) is significantly worse than the game-length margin held out:
  - domestic Elo: +0.0009 (+0.0003 to +0.0016);
  - international: +0.0056 (+0.0026 to +0.0085).
  A margin helps. Gold-based margins just don't beat game length by more than noise.
- Tuning K alone, with game length kept, gives no gain (K 28: +0.0004 held out). K = 20 stays.
- **Recommendation:** keep the published game-length margin. About half of the training-season gain from gold share or gold per minute disappears on 2022 onward.
