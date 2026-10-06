# Kill-based margins of victory for player-built Elo

Can end-of-game kills replace or sharpen the game-length "actual score" in player-built Elo?
**No.** On the training seasons, every kill candidate does worse than the published
game-length margin at the same K, and none beats it on the held-out seasons. Most are
significantly worse.

Script: `scripts/elo_variants_kills.py` (harness: `scripts/elo_variants.py`).
Run: `VECLIB_MAXIMUM_THREADS=1 uv run python -u scripts/elo_variants_kills.py` takes about 2 minutes
per candidate. Use `--only i` to run one candidate (they can run in parallel) and `--report` to print the tables.

## Protocol

- **Baseline:** the published Elo. The winner scores 0.65 to 1.0 by game length (`elo.winner_score`), with K = 20.
- **Candidates:** each margin gives the winner's score in (0.5, 1]. Games without kills
  (none in the DB: kill coverage is 100% every season) and 0–0 games (kill share) fall back
  to the game-length score (`with_fallback`).
  1. **Kill difference:** `bounded(w_kills − l_kills, scale, lower)`.
  2. **Kill share:** `bounded(w_kills / total, scale, center 0.5, lower)`, with 0–0 games falling back.
  3. **Kill difference per minute:** `bounded((w_kills − l_kills) / minutes, scale, lower)`.
  4. **Blend:** `weight × bounded(kill diff, scale) + (1 − weight) × game-length score`.
  5. **Kills and gold:** the mean of `bounded(kill diff, kill_scale)` and `bounded(gold diff, gold_scale)`.
  6. **Control (not a kill candidate):** the game-length margin with only K tuned on the same K grid. It separates a gain from kills from a gain from a larger K.
- **Tuning:** each candidate is tuned on 2014–2021 only, with K ∈ {20, 28} tuned jointly. The objective is domestic Elo-live log loss (`elo_variants.held_out`). The kill candidates use 64 grid points (16 + 12 + 16 + 12 + 8), and the control uses 2 more.
- **Report:** each candidate's tuned version is scored on 2022–2026: 7,720 domestic games and 536 international games. It is compared with the baseline on the same games using the paired bootstrap 95% interval (`compare`). Δ < 0 means the candidate is better.
- **Choosing a candidate:** the lowest training-years objective picks the candidate. The held-out results play no part in the choice.

## Training seasons (2014–2021, domestic Elo live)

| Variant | Grid points | Best params | Train log loss | Δ vs baseline (0.63949) |
|---|---:|---|---:|---:|
| Kill difference, logistic | 16 | scale 10, lower 0.55, K 28 | 0.64018 | +0.00069 |
| Kill share, logistic around 0.5 | 12 | scale 0.2, lower 0.55, K 28 | 0.63962 | +0.00013 |
| Kill difference per minute, logistic | 16 | scale 0.2, lower 0.55, K 28 | 0.63975 | +0.00026 |
| Kill difference + game length blend | 12 | weight 0.25, scale 10, K 28 | 0.63923 | −0.00026 |
| Kills and gold, mean of two logistics | 8 | kill scale 10, gold scale 6000, K 28 | 0.63985 | +0.00036 |
| Control: game length, K tuned | 2 | K 28 | 0.63896 | −0.00053 |

Every candidate chose K = 28, the top of the grid. The only kill candidate that beats the baseline on training is the blend, and only because of K. At K = 28 the blend
gets worse as the kill weight rises (0.25 → 0.63923, 0.5 → 0.63954, 0.75 → 0.63988). The pure game-length score at K = 28 is 0.63896. Kills add noise to the margin, not signal.

## Held-out seasons (2022–2026)

| Variant | Elo dom. log loss (Δ, 95% CI) | Elo intl. log loss (Δ, 95% CI) | FORGE dom. log loss (Δ, 95% CI) | FORGE intl. log loss (Δ, 95% CI) |
|---|---|---|---|---|
| Baseline (published) | 0.6232 | 0.6158 | 0.6208 | 0.6158 |
| Kill difference, logistic {scale 10, lower 0.55, K 28} | 0.6246 (+0.0014, +0.0003 to +0.0025) | 0.6228 (+0.0069, +0.0013 to +0.0121) | 0.6218 (+0.0010, +0.0004 to +0.0016) | 0.6228 (+0.0069, +0.0013 to +0.0121) |
| Kill share, logistic around 0.5 {scale 0.2, lower 0.55, K 28} | 0.6242 (+0.0009, −0.0001 to +0.0020) | 0.6214 (+0.0055, −0.0001 to +0.0108) | 0.6216 (+0.0008, +0.0002 to +0.0014) | 0.6214 (+0.0055, −0.0001 to +0.0108) |
| Kill difference per minute, logistic {scale 0.2, lower 0.55, K 28} | 0.6241 (+0.0009, −0.0000 to +0.0019) | 0.6215 (+0.0056, +0.0006 to +0.0102) | 0.6215 (+0.0008, +0.0002 to +0.0013) | 0.6215 (+0.0056, +0.0006 to +0.0102) |
| Kill difference + game length blend {weight 0.25, scale 10, K 28} | 0.6238 (+0.0006, −0.0002 to +0.0014) | 0.6195 (+0.0037, −0.0001 to +0.0074) | 0.6214 (+0.0007, +0.0002 to +0.0012) | 0.6195 (+0.0037, −0.0001 to +0.0074) |
| Kills and gold, mean of two logistics {kill scale 10, gold scale 6000, K 28} | 0.6241 (+0.0009, +0.0000 to +0.0017) | 0.6217 (+0.0059, +0.0013 to +0.0100) | 0.6215 (+0.0007, +0.0002 to +0.0012) | 0.6217 (+0.0059, +0.0013 to +0.0100) |
| Control: game length, K tuned {K 28} | 0.6236 (+0.0004, −0.0005 to +0.0012) | 0.6184 (+0.0026, −0.0009 to +0.0060) | 0.6214 (+0.0006, +0.0001 to +0.0011) | 0.6184 (+0.0026, −0.0009 to +0.0060) |

FORGE uses Elo alone between leagues, so its international column matches Elo's.

## Verdict

- **Best kill candidate, chosen on the training seasons: the blend** (weight 0.25 on a kill-difference logistic with scale 10, plus 0.75 on game length, K = 28). Held out, domestic Elo live is +0.0006 (−0.0002 to +0.0014). That is not below 0, so the candidate **fails the significance rule**. International is +0.0037 (−0.0001 to +0.0074), which is not significant but points the wrong way. FORGE domestic is **significantly worse**: +0.0007 (+0.0002 to +0.0012).
- **No kill candidate has a held-out Δ below 0** on any test set. Kill difference and kills + gold are significantly worse on domestic Elo, international Elo and FORGE. Kill difference per minute is significantly worse on international Elo and FORGE. Kill share is significantly worse on FORGE. All five candidates are significantly worse on FORGE domestic.
- **The K-only control** was not one of the requested candidates. It was best on training, but on the held-out seasons it also does not beat K = 20, and FORGE domestic is significantly worse (+0.0006, +0.0001 to +0.0011). Raising K is not a gain either.
- **Multiple comparisons:** the five kill candidates use 64 grid points, plus the 2-point control. With this many tries, one spurious "significant" gain would have been plausible. None appeared, so no correction changes the answer.

**Recommendation: keep the game-length margin, with K = 20.** Kills only add noise as a margin of victory. That fits a known weakness of kills: a won game often ends with a large kill gap whichever way it went, and kill counts also track playstyle. Game length already captures how decisive a win was.
