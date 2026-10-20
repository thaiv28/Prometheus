# Live model: refit on more data, buffs and boosted trees

Research only, 2026-10-20, base main `0a39146`. **Verdict: not shipped.** A raw
(uncalibrated) refit on all 2024–2025 feed maps is slightly better alone but
slightly worse once blended with Kalshi prices, which is what the executor trades.

## Exploratory screen (2026 feed maps)

Deployed recipe (objectives + momentum, 20 inputs, C=1, equal map weights). Test:
2,800 feed maps from 2026-01-01 (1,160 series), inside the July 2025+ test that
earlier studies viewed. Control: production recipe (train 2024, calibrate 2025 H1).
Negative is better; intervals resample whole series.

| Candidate | Δ log loss (95% CI) | ECE |
|---|---|---:|
| Production recipe | 0.4710 | 0.0212 |
| Refit train ≤2025-06, calibrate 2025 H2 | +0.0000 (−0.0016 to +0.0016) | 0.0254 |
| **Refit all pre-2026, no calibration** | **−0.0025 (−0.0040 to −0.0011)** | 0.0176 |
| + Baron (3 min) / inhibitor (5 min) recency gaps | +0.0000 vs same refit | — |
| Gradient-boosted trees, same inputs | +0.0048 (+0.0014 to +0.0082) | 0.0291 |

A first run calibrated on October–December 2025 (96 off-season maps) and was
discarded as miscalibrated (ECE 0.07). The screen's script was a scratch file
and is not kept; the raw refit is reproduced below.

## Raw refit: live benchmark

`refit_live_raw.py` trains on 5,633 feed maps before 2026 and sets the
calibration layer to identity; runtime parity on 2,836 later maps (max error
3e−16). Pinned 1,665-map priced data, all maps 2026 (after the fit), compared with
`compare_benchmarks.py`: no guarded band worse. Early −0.0017 (−0.0042 to +0.0008),
mid −0.0012 (−0.0033 to +0.0008), late −0.0006 (−0.0032 to +0.0018), all −0.0010
(−0.0027 to +0.0006). Not significant; upper bounds miss the +0.0005
non-inferiority margin a calibration removal needs.

## Trading check

`live_trading.py` with the raw refit swapped in (monthly blends refit by the study),
paired on the same 1,352 maps / 32,158 calls:

| Measure | New − current (95% CI) |
|---|---|
| Model alone | −0.0005 (−0.0025 to +0.0015) |
| Blend, all | +0.0008 (−0.0004 to +0.0019) |
| Blend, minutes 10–20 | **+0.0015 (+0.0001 to +0.0029)** |
| Blend, CBLOL (150 maps) | **+0.0037 (+0.0007 to +0.0069)** |
| Paper ROI per $1 entry | +11.7% (260) → +10.7% (248) |

Fails the trading gate (gain and no significantly worse slice). The calibration
layer stretches logits (slope 1.077), which apparently helps the blend more than
the model's own accuracy gain. Hence the blend stays pinned to the model hash:
a model change needs its blend refit and this trading check.

## Limits

Retrospective test, reused across many studies, no multiplicity adjustment.
Trade prices are not executable asks. Repeat the refit when more priced 2026
maps settle.

## Reproduce

```bash
uv run python scripts/research/refit_live_raw.py      # writes data/research/time_model_raw.json
uv run python scripts/evaluate_live.py --fetch-data
uv run python scripts/evaluate_live.py --dump base/live
uv run python scripts/evaluate_live.py --model data/research/time_model_raw.json --dump head/live
uv run python scripts/compare_benchmarks.py base head
```

For the trading check, copy the candidate over `prometheus/live/time_model_objectives_v1.json`
temporarily, run `scripts/research/live_trading.py --data data/live_bench/live_maps.json.gz
--db db/prometheus.db --out <dir>` for both models, pair `calls.csv.gz` on game and
minute, then restore the file and `docs/research/live_trading.md` (the study rewrites it).
