**FAIL: players-alive confirmation; research only.**

# Players-alive confirmation

Fixed candidate: deployed 20 inputs plus blue-minus-red players alive and alive ×time. Cached live_state rows, original train/calibration split, C=1, map weights and Platt fit. Pinned 1,666-map input; verdict rules fixed before results.

Parity max |Δp|=0.0443195411. Research control differs from deployed because Elo inputs and the calibration set changed since the deployed fit. Objectives/momentum use deployed inputs. Blue probabilities convert to teams[0]. Nearest raw first-window-frame timestamp within 2 seconds; invalid health/levels or unsupported calls retain research control. Deployed uses unmodified replay probabilities.

Calls 52892; state-model 52892; matched 52892; fallback 0; Elo-skipped maps 1. Pregame/pre-map unchanged.

ΔLL=alive−comparison; 95% whole-series bootstrap. Live uses benchmark checkpoints, fit-date filter and bootstrap. Trading averages calls per map (2,000 draws, seed 42); bands [5,10), [10,20), [20,30]; leagues ≥100 maps. Monthly blends refit on earlier settled series. Each trading arm runs once.

## A: Feature effect: alive vs research control

| Live band | Maps | ΔLL [95% CI] |
|---|---:|---|
| pre-map, every priced map | 3344 | +0.000000 [+0.000000, +0.000000] |
| pregame | 1522 | +0.000000 [+0.000000, +0.000000] |
| early | 1612 | +0.000141 [-0.000089, +0.000389] |
| mid | 1628 | +0.000699 [-0.000300, +0.001843] |
| late | 1593 | -0.000418 [-0.002809, +0.002239] |
| all | 1658 | +0.000142 [-0.000585, +0.000950] |

| Trading measure | ΔLL [95% CI] |
|---|---|
| Model All | -0.000577 [-0.000988, -0.000169] |
| Blend All | -0.000427 [-0.000692, -0.000170] |
| Blend 5–10 | -0.000100 [-0.000246, +0.000038] |
| Blend 10–20 | -0.000180 [-0.000428, +0.000083] |
| Blend 20–30 | -0.000831 [-0.001398, -0.000288] |
| Blend CBLOL | -0.000273 [-0.000865, +0.000327] |
| Blend LCK | -0.000336 [-0.000906, +0.000245] |
| Blend LCP | -0.000747 [-0.001635, +0.000019] |
| Blend LCS | -0.000570 [-0.001303, +0.000115] |
| Blend LEC | -0.000231 [-0.000804, +0.000376] |
| Blend LPL | -0.000691 [-0.001362, -0.000048] |

FAIL: (a) FAIL; (b) PASS; (c) PASS. compare_benchmarks exit 0.

## B: Ship decision: alive vs deployed

| Live band | Maps | ΔLL [95% CI] |
|---|---:|---|
| pre-map, every priced map | 3344 | +0.000000 [+0.000000, +0.000000] |
| pregame | 1522 | +0.000000 [+0.000000, +0.000000] |
| early | 1612 | +0.000377 [-0.000593, +0.001315] |
| mid | 1628 | +0.002655 [+0.001217, +0.004238] |
| late | 1593 | +0.000160 [-0.002573, +0.003130] |
| all | 1658 | +0.000950 [-0.000088, +0.002062] |

| Trading measure | ΔLL [95% CI] |
|---|---|
| Model All | +0.000648 [-0.000344, +0.001708] |
| Blend All | -0.000042 [-0.000724, +0.000603] |
| Blend 5–10 | +0.000059 [-0.000706, +0.000802] |
| Blend 10–20 | +0.000414 [-0.000330, +0.001183] |
| Blend 20–30 | -0.000594 [-0.001325, +0.000175] |
| Blend CBLOL | +0.000653 [-0.000785, +0.002172] |
| Blend LCK | +0.000508 [-0.001051, +0.002043] |
| Blend LCP | +0.000182 [-0.002284, +0.002362] |
| Blend LCS | -0.000023 [-0.001778, +0.001648] |
| Blend LEC | +0.001828 [+0.000334, +0.003255] |
| Blend LPL | -0.001764 [-0.003313, -0.000148] |

FAIL: (a) FAIL; (b) FAIL; (c) FAIL. compare_benchmarks exit 1.

Primary paper ROI per $1 entry: control +7.57% (257 bets); alive +7.15% (264 bets); deployed +11.72% (260 bets).

Fixed gates: (a) live All upper <0 and point ≤−0.0005; (b) comparator exit 0; (c) trading blend All point <0 and no reported blend slice lower >0. Overall requires A and B. Logs/summary: `data/research/live_alive/`.

Limits: alive was the one passing candidate of six in live_state; the 2026 benchmark overlaps the study test period; trade prices are not executable asks; no forward holdout. Paper ROI and historical blend refits do not establish executable profitability. No production change.


Scope note (added after the fixed verdict, not part of it): the live benchmark guards minutes up to 30 and the trading study keeps minutes 5–30, while the feed study's alive gain is mostly after 30 minutes (−0.0071 at 30+, −0.0008 at 20–30). B also carries the refit drift: the research control alone trails the deployed model (ROI 7.57% vs 11.72%). A frozen-base variant (alive fitted as an offset on the deployed model) and a 30–40 minute benchmark band would isolate the feature; neither was run.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_role_levels_check.py --candidate alive
```
