# Live objective/momentum release validation

Release branch `live-model-release`, runtime base main `27c3013`, research base
`de6ec95`. User requested deployment after the [candidate review](live_candidates.md).
Target: the tested objective+gold-momentum model, with its existing calibration;
no draft input, role input, raw-calibration replacement or parameter retuning.

## Frozen fit and parity

Training is 2024 feed only (2,757 maps), calibration January–June 2025
(1,733 maps), test July 2025 onward (3,857 maps). Each map is weighted equally.
The all-map delta resamples whole series. The test has been used repeatedly in
research and intervals are not adjusted for multiple comparisons. ECE is
0.0182, and prospective accuracy is still unverified.

```json
{
  "maps": 3857,
  "metrics": {
    "games": 3857,
    "rows": 122815,
    "log_loss": 0.4675437319642068,
    "brier": 0.15489659581444368,
    "ece10": 0.018152869438970168
  },
  "delta_vs_v1": {
    "delta": -0.013565157371299916,
    "interval": [
      -0.016961151107740245,
      -0.009981782823920872
    ],
    "series": 1542
  },
  "max_export_error": 4.996003610813204e-16
}
```

`freeze_live_objectives.py` verifies all 122,815 test predictions against the
runtime implementation with exact raw feed counter pairs and causal momentum.
Gold/clock input validation and v1 compatibility are preserved. No library fit
or extra provider request enters the worker. Counts match collection semantics:
soul is the dragons>=4 proxy (can include Elder), inhibitors are raw counters.

## Production frames and cost

KC–MVK map 2, recorded 2026-10-16, read from the existing backup. No evidence is
overwritten. Five warm replays per version; an incomplete final minute is
excluded from the causal-prefix equality comparison.

```json
{
  "v1": {
    "median_ms": 22.449249983765185,
    "calls": 32,
    "fallback_calls": 0,
    "pregame": 0.8861479048633999
  },
  "objectives_momentum": {
    "median_ms": 55.15479203313589,
    "calls": 32,
    "fallback_calls": 0,
    "pregame": 0.8978833725467904
  },
  "production_frames": 7768,
  "causal_prefix": "PASS"
}
```

This confirms shape/semantics/cadence compatibility for one real recording;
it is not a prospective accuracy/calibration test. The additional ~33 ms for
replaying the entire recorded map is small beside the 10 s model cadence.
No new dependency, job, network call, production DB read or quote-cadence work.

## Pinned production benchmark

Pinned asset `live_maps-0705f02b1edf.json.gz` (1,666 maps), SHA256
`0705f02b1edf6df391809ba59a34ea4857fe2224757d7c509225e3875692422c`.
The older local 405-map asset lacked the current report's held-price columns;
it was replaced only in the temporary benchmark input, not in shared local data.
The first attempt to apply the new model before the map worsened the guarded
pre-map slice by +0.0025 (+0.0012 to +0.0038), so pre-map calls retain frozen v1.
This is an in-game release; objectives/history are unavailable before the map.
Final paired benchmark passes every guard. Pre-map and pregame calls are exactly unchanged.

**Benchmarks: no guarded value is significantly worse.**
Forecast backtest: missing from one side, not compared.
Season-stat report: missing from one side, not compared.
AURA report: missing from one side, not compared.
Market benchmark: missing from one side (no Kalshi cache in CI yet, or the base can't dump it), not compared.
Prop projections: missing from one side, not compared.
Live benchmark: maps after 2025-06-30 (the models' fit).

#### Live

| Section | Measure | Base | Head | Head − base (95% CI) | Result | Unpaired (base / head) |
|---|---|---:|---:|---|---|---:|
| Live | **log loss, pre-map, every priced map (3,327)** | 0.6393 | 0.6393 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Live | **log loss, pregame (1,522)** | 0.6315 | 0.6315 | +0.0000 (+0.0000 to +0.0000) | within noise | 0 / 0 |
| Live | **log loss, early (3,125)** | 0.6028 | 0.6003 | -0.0026 (-0.0064 to +0.0012) | within noise | 0 / 0 |
| Live | **log loss, mid (3,179)** | 0.5062 | 0.4915 | -0.0147 (-0.0237 to -0.0055) | better | 0 / 0 |
| Live | **log loss, late (2,765)** | 0.3492 | 0.3205 | -0.0287 (-0.0383 to -0.0188) | better | 0 / 0 |
| Live | **log loss, all (10,591)** | 0.5117 | 0.4991 | -0.0127 (-0.0177 to -0.0073) | better | 0 / 0 |

Bold measures are guarded: the check fails when one is significantly worse (its interval entirely on the bad side) or AURA's ECE is above 0.01. Lower log loss and log score and higher r are better.


## Deployment status

Local validation complete: 789 tests passed, 2 skipped; repository-wide lint
and formatting pass; 49 relative document links resolve. The site build generated
2,087 team and 4,854 player pages. Its Props page was skipped because the old
local DB lacks prop-total columns; no shared DB was rebuilt. Forecast and
season-stat evaluations completed. No UI/template/copy changes.

PR CI, merge and worker verification pending.
