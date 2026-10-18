# Draft v2 as a live prior

Protocol fixed before scoring in `scripts/research/live_draft_prior.py`.
One candidate, draft shift and shift × time. Negative log-loss difference favours the candidate.

Saved rows from `train_time_model_v2.partitions()`; that helper is absent at the branch base.
Input SHA256: `5a033eba154774108beda4bd47041ebdf38c22054d40108a93c869b83a49ec8b`.
Read-only design reference `../Prometheus-cand-draft/scripts/research/cand_draft.py`, SHA256 `74fd491f26153cecd2b0dfcbeea5a24036ff16e8336cfe6f7bd97e838fdf9d52`; adapted to v2, with primary same-row refit control.
Partition reference `../Prometheus-cand-mapelo/scripts/research/train_time_model_v2.py`, SHA256 `8236029492c6cb48b0f572ec69f23be2ac0b1edfa17095a915de66c93bc8325e`. Cache origin: main checkout `data/research/time_model_v2/rows.csv` (saved helper rows). Neither sibling module is imported.

| Partition | Original maps | Retained maps |
|---|---:|---:|
| train | 3,533 | 3,525 |
| calibration | 1,733 | 1,720 |
| test | 3,857 | 3,825 |

Train live rows start 2022; their draft weights freeze through 2021. Calibration/test draft weights freeze through 2024.
All comparisons share retained maps; absent shifts drop from all calls. Prior-year feature histories still update from earlier days.

| Slice | Maps | Candidate LL | Refit LL | v1 LL | Candidate − refit (95%) | Candidate − v1 (95%) |
|---|---:|---:|---:|---:|---|---|
| all | 3,825 | 0.4794 | 0.4823 | 0.4821 | -0.0029 (-0.0055 to -0.0003) | -0.0028 (-0.0057 to +0.0002) |
| majors | 2,315 | 0.4987 | 0.5030 | 0.5022 | -0.0044 (-0.0078 to -0.0007) | -0.0036 (-0.0074 to +0.0007) |
| LPL | 944 | 0.5095 | 0.5139 | 0.5112 | -0.0043 (-0.0097 to +0.0012) | -0.0016 (-0.0079 to +0.0050) |
| international | 297 | 0.4592 | 0.4567 | 0.4581 | +0.0025 (-0.0062 to +0.0113) | +0.0011 (-0.0095 to +0.0110) |
| other | 1,213 | 0.4475 | 0.4489 | 0.4497 | -0.0015 (-0.0057 to +0.0026) | -0.0022 (-0.0072 to +0.0023) |
| minutes 0–10 | 3,825 | 0.6067 | 0.6109 | 0.6106 | -0.0042 (-0.0074 to -0.0009) | -0.0039 (-0.0072 to -0.0005) |
| minutes 10–20 | 3,824 | 0.5092 | 0.5124 | 0.5135 | -0.0032 (-0.0061 to -0.0003) | -0.0042 (-0.0075 to -0.0010) |
| minutes 20–30 | 3,819 | 0.3555 | 0.3567 | 0.3559 | -0.0012 (-0.0036 to +0.0009) | -0.0004 (-0.0035 to +0.0024) |
| minutes 30–+ | 2,126 | 0.3103 | 0.3097 | 0.3150 | +0.0007 (-0.0020 to +0.0034) | -0.0046 (-0.0094 to +0.0005) |
| 2025 | 1,037 | 0.4710 | 0.4740 | 0.4755 | -0.0030 (-0.0075 to +0.0016) | -0.0045 (-0.0097 to +0.0006) |
| 2026 | 2,788 | 0.4825 | 0.4854 | 0.4846 | -0.0029 (-0.0061 to +0.0002) | -0.0021 (-0.0058 to +0.0014) |

## Limits

Pre-2025 test: unavailable (test begins July 2025). v2 features were selected after viewing 2025–26; this is a follow-up, not an untouched holdout.
Cached feed clock, OE joins and historical pre-series Elo inherit the v2 study's limitations. The live training draft fit freezes earlier than the test fit; a larger clean rolling-origin live study is future work.
The full shift includes intercept/FORGE recalibration terms; this is the requested prior, not a pure champion-effect causal estimate.
No live draft computation, fill test or trading claim. Published models/weights unchanged.
