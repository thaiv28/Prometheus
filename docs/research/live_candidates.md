# Live model candidate review — 2026-10-17

Research only, branch `research/live-candidates`, base `9b670eb` (unmerged PR #83).
No production model or worker change, push, merge, or deployment.

All candidates retain the fixed split: training through 2024, calibration in
January–June 2025, test from July 2025. The shared feed test has 3,857 maps;
draft has 3,447 with complete picks. Each map receives equal weight, and 95%
intervals resample whole series. Negative candidate-minus-v1 log loss is better.
The retrospective statistical threshold is an all-map interval below zero.
Repeated use of this test and several candidate comparisons limit independent
confirmation; these intervals are not adjusted for multiple comparisons.

| Candidate | Maps | Log-loss difference vs v1 (95% interval) | Assessment |
|---|---:|---|---|
| [More training data (v2)](time_model_v2.md) | 3,857 | +0.0002 (−0.0011 to +0.0016) | Inconclusive |
| [Spline time weights (v3)](time_model_v3.md) | 3,857 | +0.0000 (−0.0012 to +0.0013) | Inconclusive |
| [Elo updated per map](cand_map_elo.md) | 3,857 | −0.0005 (−0.0021 to +0.0012) | Inconclusive |
| [Objective counts, primary](cand_objectives.md) | 3,857 | −0.0111 (−0.0146 to −0.0075) | Passes retrospective threshold |
| [Draft + matchups + synergy](cand_draft.md) | 3,447 | −0.0027 (−0.0052 to −0.0002) | Threshold met; overlapping feature selection |
| [Original draft features](cand_draft.md) | 3,447 | −0.0019 (−0.0042 to +0.0004) | Inconclusive; secondary |
| [Three-minute gold momentum](cand_temporal.md) | 3,857 | −0.0006 (−0.0022 to +0.0010) | Inconclusive |

## What the evidence supports

Objectives are the strongest candidate. The primary adds tower, dragon, Baron,
inhibitor and kill gaps plus an approximate soul flag, each interacting with
time. Against the same-row refit it gains −0.0116 (−0.0151 to −0.0082).
The improvement grows after 10 minutes; the 30+ minute difference versus v1 is
−0.0284. The declared smaller towers/dragons/Barons variant also gains, but
choosing it from this test would be exploratory. ECE worsens from 0.0147 to
0.0191; objective values use cumulative feed counts, not active buffs or
currently destroyed inhibitors. The soul flag counts dragons and can confuse
Elder with elemental dragons. Validate objective semantics, calibrate without
using test outcomes, and check production frames before proposing adoption.

Draft's fit weights exclude test years. However, matchup/synergy feature
selection used overlapping pre-match evidence, and missing picks disproportionately
remove LPL maps. The original feature set does not pass the all-map threshold.
Treat the combined draft result as promising exploratory evidence. Its effect
on top of objectives has not been tested; separate gains cannot be added.

Momentum beats its same-row refit by −0.0011 (−0.0018 to −0.0004), but does not
beat v1 significantly overall, so it does not pass the recorded adoption rule.
Its late-game gain warrants a fresh-data check rather than another test-set search.

## Calibration check

On the same feed-only refit, raw probabilities score 0.4804 log loss and 0.0048
ECE, versus global calibration's 0.4816 and 0.0152. Raw minus globally calibrated
log loss is −0.0011 (−0.0024 to +0.0002): inconclusive overall and significantly
worse after 30 minutes. Four fixed time buckets score 0.4814 and 0.0122 ECE;
the overall loss difference is −0.0002 (−0.0006 to +0.0003), with harm at
20–30 minutes and in other leagues. No calibration change is justified here.
These diagnostics concern the six-feature refit, not the objectives model.

## Remaining work

- Validate objectives on the worker's ten-second frames and on a prospective
  cohort; compare a frozen objectives model with v1 on the same maps.
- Test objectives plus draft on a fresh cohort, with an objectives-only control.
- Per-role leads phase A remains unrun in this continuation. Existing
  [snapshot research](snapshot_report.md) supports testing role gaps, but the
  collected timelines lack participant fields needed for live validation.
- Kalshi blend remains pending explicit go-ahead, as requested in the handoff.
- Recollecting participant data also remains pending explicit go-ahead: about
  a day of requests and an awake, plugged-in laptop. No collection was started.

## Reproduce

Use the existing main-checkout environment with the worktree first on the import
path. Link `data/feed_timelines`, `data/gol_training`, `data/raw`, and the existing
DB read-only; never run DB setup against a shared DB. These scripts only read it.

```bash
PYTHONPATH=$PWD /Users/tvillalu/repos/Prometheus/.venv/bin/python scripts/research/cand_objectives.py --report docs/research/cand_objectives.md
PYTHONPATH=$PWD /Users/tvillalu/repos/Prometheus/.venv/bin/python scripts/research/cand_draft.py --report docs/research/cand_draft.md
PYTHONPATH=$PWD /Users/tvillalu/repos/Prometheus/.venv/bin/python scripts/research/cand_temporal.py --report docs/research/cand_temporal.md
```

Candidate scripts and tests are consolidated locally. No runtime/CI step or
new dependency is added. Reports document retrospective results, not live trading
profitability. Per-map Elo and v2/v3 numbers above are imported prior results;
this continuation reruns draft, objectives, momentum and calibration only.
