# Objective-based margins of victory for player-built Elo

Can end-of-game objective counts (towers, dragons, barons, first objectives) replace or add to the
published game-length margin? **No.** No candidate beats the published Elo on held-out seasons. Most
are slightly worse, and every one is significantly worse for FORGE domestic.

## Protocol

- Harness: `scripts/elo_variants.py` (shared). Script: `scripts/elo_variants_objectives.py`
  (`--run <candidate>` per candidate, `--report` for the tables).
- Each candidate maps a raw objective margin to the winner's score with `bounded` (logistic, 0.65 to 1,
  the published range). Where a stat is missing, it falls back to the published game-length score
  (`with_fallback`). Towers, dragons and barons cover 99 to 100% of games every year. First-objective
  flags cover 79 to 100% of games, with gaps mostly in the LPL.
- Tuning: grid search on seasons 2014 to 2021, minimising domestic Elo-live log loss (`held_out`). K is
  tuned jointly over {20, 28}. Reporting: seasons 2022 to 2026 against the published Elo (game length,
  K = 20) on the same games, with paired-bootstrap 95% intervals. Held-out baselines: Elo live domestic
  0.6232, FORGE domestic 0.6208, international 0.6158. Between leagues FORGE is Elo alone, so the two
  international columns are identical.
- Control: the published game-length margin with only K tuned over the same {20, 28}. This separates a
  gain from K from a gain from the margin.
- Candidates:
  1. tower difference (scale × center × K);
  2. tower share w/(w+l);
  3. dragon difference;
  4. baron difference;
  5. composite: weighted sum of tower, dragon and baron differences, with weight sets (1,1,1),
     (1,1,2), (1,0.5,1.5) and (1,2,3);
  6. composite blended with game length: α·composite + (1−α)·game length, with the composite's
     params fixed at its training-years choice;
  7. first tower + first dragon + first baron taken by the winner (0 to 3), squashed and blended
     with game length.
- Multiple comparisons: 8 candidates (7 margins and the K control), 116 parameter sets in all. A
  first composite grid with K fixed at 20 (24 more sets) was replaced by the grid with K tuned, for
  140 sets in total. Its pick, (1,1,1)/3/6 at K = 20, scored train 0.6400 and held-out Elo domestic
  +0.0004 (−0.0004 to +0.0012).

## Training seasons (2014 to 2021, domestic Elo live; published baseline 0.6395)

| Candidate | Grid | Chosen params | Train log loss |
|---|---:|---|---:|
| Control: game length, K tuned | 2 | K 28 | 0.6390 |
| Tower diff | 18 | scale 2, center 6, K 28 | 0.6388 |
| **Tower share** | 18 | scale 0.05, center 0.75, K 28 | **0.6385** |
| Dragon diff | 12 | scale 4, center 0, K 28 | 0.6405 |
| Baron diff | 12 | scale 2, center 0, K 28 | 0.6409 |
| Objective composite | 32 | weights (1,1,1), scale 3, center 6, K 28 | 0.6395 |
| Composite + game length | 6 | α 0.25, K 28 | 0.6389 |
| First tower/dragon/baron | 16 | scale 1, center 2, α 0.5, K 28 | 0.6397 |

## Held-out seasons (2022 to 2026): log loss (Δ vs published, 95% CI)

| Variant | Elo dom. | Elo intl. | FORGE dom. | FORGE intl. |
|---|---|---|---|---|
| Control: game length, K 28 | 0.6236 (+0.0004, −0.0005 to +0.0012) | 0.6184 (+0.0026, −0.0009 to +0.0060) | 0.6214 (+0.0006, +0.0001 to +0.0011) | 0.6184 (+0.0026, −0.0009 to +0.0060) |
| Tower diff | 0.6239 (+0.0007, −0.0005 to +0.0018) | 0.6170 (+0.0012, −0.0036 to +0.0059) | 0.6218 (+0.0010, +0.0003 to +0.0017) | 0.6170 (+0.0012, −0.0036 to +0.0059) |
| Tower share | 0.6242 (+0.0010, −0.0003 to +0.0024) | 0.6146 (−0.0012, −0.0068 to +0.0044) | 0.6220 (+0.0012, +0.0004 to +0.0020) | 0.6146 (−0.0012, −0.0068 to +0.0044) |
| Dragon diff | 0.6245 (+0.0013, +0.0002 to +0.0024) | 0.6209 (+0.0051, −0.0003 to +0.0102) | 0.6217 (+0.0010, +0.0003 to +0.0016) | 0.6209 (+0.0051, −0.0003 to +0.0102) |
| Baron diff | 0.6249 (+0.0017, +0.0006 to +0.0029) | 0.6233 (+0.0075, +0.0023 to +0.0123) | 0.6219 (+0.0011, +0.0004 to +0.0018) | 0.6233 (+0.0075, +0.0023 to +0.0123) |
| Objective composite | 0.6238 (+0.0006, −0.0004 to +0.0017) | 0.6179 (+0.0020, −0.0026 to +0.0064) | 0.6216 (+0.0009, +0.0002 to +0.0015) | 0.6179 (+0.0020, −0.0026 to +0.0064) |
| Composite + game length | 0.6235 (+0.0003, −0.0005 to +0.0012) | 0.6180 (+0.0022, −0.0014 to +0.0055) | 0.6214 (+0.0006, +0.0001 to +0.0011) | 0.6180 (+0.0022, −0.0014 to +0.0055) |
| First tower/dragon/baron | 0.6239 (+0.0007, −0.0002 to +0.0016) | 0.6185 (+0.0027, −0.0015 to +0.0065) | 0.6215 (+0.0007, +0.0002 to +0.0013) | 0.6185 (+0.0027, −0.0015 to +0.0065) |

## Verdict

- **Chosen on training seasons:** tower share, with scale 0.05, center 0.75 and K 28 (train 0.6385
  against the baseline's 0.6395).
- **Held out:** Elo domestic is +0.0010 (−0.0003 to +0.0024), so its interval doesn't lie below 0.
  International is −0.0012 (−0.0068 to +0.0044), which is noise. FORGE domestic is +0.0012
  (+0.0004 to +0.0020), significantly worse. **It fails the significance rule. Don't ship.**
- The small training gains come mostly from K. The K-only control gets 0.6390 on training seasons,
  and the best objective margin adds at most 0.0005 to that. Held out, larger K doesn't help either.
- Dragon and baron differences are worse than game length even on training seasons. Baron diff is
  significantly worse held out, both domestic and international. These counts track game length
  (long games pile up dragons and barons) more than they track dominance.
- No candidate's held-out domestic Elo Δ is below 0, so the training-season choice can't hide a
  better candidate. With 8 candidates and 140 parameter sets, a nominal win would also have needed a
  multiple-comparisons discount.

Runtime: about 30 s to load inputs per process, then about 4 s per parameter set. Each candidate took
45 to 135 s of wall time, running up to three in parallel, for about 15 min of compute in all.
