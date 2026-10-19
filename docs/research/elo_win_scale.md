# Why Elo needs a fitted forecast curve (2026-10-19)

Follow-up to [One Elo scale](elo_one_scale.md), designed after viewing its results (exploratory). Scripts: `scripts/research/elo_score_compression.py` (diagnostic) and `scripts/research/elo_win_scale.py` (win-scale variant). Training ≤2021, held out 2022–2026; regional calibration off; intervals cluster by series.

## Finding

Elo's own expected score is compressed against real win rates by c ≈ 1.4–1.9 in every tier (c = fitted slope / update slope; published held-out c_M 1.43, c_O 1.56, c_X 1.86). Raising K lowers c but makes log loss steadily worse ([One Elo scale](elo_one_scale.md), stage 1).

The cause is the game-length score. Elo's "actual score" is .65–1 for the winner (mean .79), so it learns the expected *score*, which sits closer to .5 than the win chance by about 2w − 1 ≈ .58 (predicted c ≈ 1.7). Replayed with plain 1/0 results, Elo is calibrated:

| Results | K | Train objective | c_M | c_O | c_X |
|---|---:|---:|---:|---:|---:|
| Game length (published) | 20 | 0.620024 | 1.500 | 1.652 | 1.654 |
| 1/0 | 12 | 0.625601 | 0.991 | 1.296 | 1.253 |
| 1/0 | 16 | 0.625094 | 0.904 | 1.141 | 1.117 |
| 1/0 | 20 | 0.625166 | 0.842 | 1.029 | 1.017 |

With 1/0 results, cross-region c matches within-league c, so league offsets add no extra compression: the regional calibration's large effects (LCK +.98 log-odds) are a level bias, not a scale one.

## Win-scale variant

Ratings on the win-probability scale: the update expects the score a win chance implies, E = .5 + m(σ(s0·gap) − .5), m = 2 × training mean winner score − 1 = .5536. Grid fixed before scoring: K_M {24, 32, 40} × K_O {24, 32, 40, 48}, share .5, selected on the training objective (refit curves). Chosen K_M 40 / K_O 40 (grid corner; train 0.622348 vs published 0.619996). Near K 24, c is about 1 (.87–1.07) but training loss is +.0033.

Held out (C = chosen, P = published, both refit unless "no curve"):

| Section | Metric | Games | C refit − P refit | C no curve − P refit | C no curve − C refit |
|---|---|---:|---|---|---|
| Domestic | Elo | 7,728 | +0.00072 (−0.00011 to +0.00153) | +0.02111 (+0.01630 to +0.02633) | +0.02039 (+0.01564 to +0.02554) |
| Domestic | FORGE | 7,728 | +0.00005 (−0.00049 to +0.00060) | — | — |
| International | Elo | 589 | +0.00207 (−0.00094 to +0.00485) | +0.01494 (−0.00127 to +0.03161) | +0.01286 (−0.00366 to +0.03023) |
| International | FORGE | 589 | +0.05153 (+0.02729 to +0.07774) | — | — |
| Cross-league | Elo | 5,442 | +0.01611 (+0.01321 to +0.01907) | +0.02063 (+0.01687 to +0.02460) | +0.00451 (+0.00155 to +0.00743) |
| Other leagues | Elo | 37,272 | +0.00408 (+0.00331 to +0.00482) | +0.01073 (+0.00920 to +0.01225) | +0.00666 (+0.00537 to +0.00802) |
| Other leagues | FORGE | 37,272 | +0.00376 (+0.00311 to +0.00438) | — | — |

International FORGE's +.05 likely reflects the harness carrying FORGE's domestic Elo weight onto the rescaled ratings; the verdict doesn't depend on it.

## Verdict (conclusive)

The fitted forecast curves cannot be removed. Calibrating Elo's own expected score, by K (one scale) or by rescaling the update (win scale), costs .003–.02 log loss: the game-length score carries information beyond a linear rescaling (favourites also win faster), and the fitted curve is the cheap, correct link from expected score to win chance. Keep the curves; the remaining cross-region question is the offsets' level bias, not their scale.
