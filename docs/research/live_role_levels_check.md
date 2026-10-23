**FAIL: role level confirmation; research only.**

# Role level confirmation

Fixed level candidate: deployed 20 inputs plus five blue-minus-red role level gaps and their ×time terms. Same feed train/calibration split, C=1, map weights and Platt fit as the role study. Pinned 1,666-map live input; no candidates or verdict rules changed.

Parity max |Δp|=0.0443195411; control uses research fit probabilities in both research arms. Objectives and momentum come directly from deployed call inputs. Candidate blue probabilities convert to teams[0]; nearest raw first-frame source timestamp within 2 seconds. Unsupported/unmatched calls retain control.

In-game calls 52892; state-model 52892; matched 52892; fallback 0; Elo-skipped maps 1. Pregame and pre-map calls unchanged.

ΔLL=new−current; 95% whole-series bootstrap. Live uses the benchmark's checkpoint weighting, fit-date filter and bootstrap; trading averages calls per map, 2,000 draws, seed 42. Trading minute bands are [5,10), [10,20), [20,30]; leagues require ≥100 paired maps. Monthly blends refit separately using earlier settled series.

| Live band | Maps | ΔLL [95% CI] |
|---|---:|---|
| pre-map, every priced map | 3344 | +0.000000 [+0.000000, +0.000000] |
| pregame | 1522 | +0.000000 [+0.000000, +0.000000] |
| early | 1612 | -0.001246 [-0.002808, +0.000284] |
| mid | 1628 | +0.000777 [-0.000962, +0.002635] |
| late | 1593 | -0.002109 [-0.005280, +0.001482] |
| all | 1658 | -0.000685 [-0.001909, +0.000503] |

| Trading measure | ΔLL [95% CI] |
|---|---|
| Model All | -0.001098 [-0.002448, +0.000301] |
| Blend All | -0.000601 [-0.001439, +0.000274] |
| Blend 5–10 | -0.001018 [-0.001756, -0.000293] |
| Blend 10–20 | -0.000478 [-0.001367, +0.000373] |
| Blend 20–30 | -0.000453 [-0.001964, +0.001131] |
| Blend CBLOL | -0.000618 [-0.002919, +0.001554] |
| Blend LCK | -0.000651 [-0.002394, +0.001243] |
| Blend LCP | -0.001198 [-0.004095, +0.001746] |
| Blend LCS | -0.000801 [-0.003499, +0.001753] |
| Blend LEC | -0.000034 [-0.002391, +0.002244] |
| Blend LPL | +0.000052 [-0.001965, +0.002114] |

Primary paper ROI per $1 entry: current +7.57% (257 bets); level +5.35% (277 bets).

(a) FAIL: live All upper <0 and point ≤−0.0005. (b) PASS: compare_benchmarks exit 0, no significantly worse live band. (c) PASS: trading blend All point <0 and no reported blend slice lower >0. Full comparator output: `data/research/live_role_levels/compare.log` and `summary.json`.

Limits: level was a post hoc candidate among four secondaries; the 2026 benchmark maps overlap the study's test period; trade prices are not executable asks; no forward holdout used. Historical blend refitting and paper ROI do not establish executable profitability. No production change.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_role_levels_check.py
```
