# Draft v3 beyond the current live model

Protocol fixed before scoring this comparison, 2026-10-18. Base main f522db3.
Primary: objectives + causal three-minute momentum + draft v3 shift and shift × time,
compared with the frozen production objectives/momentum model. Secondary controls:
same-row objectives/momentum refit, and the same live fit with draft v2 instead.
No feature selection, tuning or calibration variants after scoring.

Use the existing feed-only chronological split: train 2024, calibrate Jan–Jun
2025, test July 2025 onward, supported seconds 0–2400. Equal map weight and
2,000 paired whole-series bootstrap draws, seed 42. Report all, minute bands,
major leagues, LPL, international, other leagues, years and missing-draft coverage.
Keep missing drafts with shift zero; never drop them to improve the candidate.

Draft v3 is v2's four features plus the entire seven-feature player block,
from the frozen player_feats_games cache (source research/draft-player-feats
b5a2613). Histories exclude the current UTC day. Fit draft weights on 2019–2023
for live training maps in 2024, and 2019–2024 for calibration/test maps. No draft
weight sees its target or future outcomes. Both v2/v3 shifts subtract the
identically trained FORGE-only recalibration. Histories can advance on prior days.

The adoption gate is an all-map 95% interval below zero versus the actual
frozen production model and no significantly worse named league/minute slice.
This is retrospective on previously viewed years; report that limitation even
if the gate passes. No production activation, inference export or trading change.

Reuse compare_benchmarks.py's CI Live guard through compatible research dumps
at 5/10/15/20/25/30 minutes. These feed-only dumps have no market prices and are
not the pinned market benchmark: do not invent pregame calls, prices or profit.
Native pinned benchmark remains unchanged; live draft identity/availability
must be implemented before it can evaluate a production draft model end to end.

## Decision

Do not promote draft v3 into the live worker. On 3,893 test maps its gain over
frozen production is inconclusive: −0.00164 (95% −0.00393 to +0.00048).
It is significantly worse than the v2 live-prior control: +0.00138
(+0.00022 to +0.00250). V2 versus frozen production is −0.00302
(−0.00582 to −0.00043). This does not select a new v3 feature subset.
V2 merits a separate production-input and prospective study; no candidate ships.

The existing CI comparator accepts the research dumps. V3 versus production
passes the no-regression guard, but pooled checkpoint improvement is inconclusive
(−0.0012, −0.0035 to +0.0012). V3 versus v2 **fails all four scored guards**:
early +0.0015 (+0.0001 to +0.0031), mid +0.0017 (+0.0005 to +0.0030),
late +0.0012 (+0.0001 to +0.0023), pooled +0.0015 (+0.0003 to +0.0027).
Passing the no-regression guard alone does not establish improvement.
These checkpoint losses weight checkpoints; the main comparison weights maps,
so their pooled estimates differ. Neither includes synthetic pregame calls.

The rebuilt corpus has 1,819 calibration / 3,893 test maps, versus the release's
1,733 / 3,857. Training still has 2,757 maps. Therefore the same-row refit is a
separate control, not an exact reconstruction of the frozen weights; maximum
prediction difference is 0.05289. All candidates and both controls score the
same rebuilt test rows. Frozen numerical inference agrees with the actual runtime
to 5e−16 over every test row. Input hashes below pin this run's corpus.
Histories are observational; previous FORGE weight selection and draft feature
selection used some of these years. No untouched confirmation or live identity
validation is claimed. Missing-draft inputs use zero in the research fit; a
production implementation still needs a tested fallback to the current model.

## Reproduction and CI

Sources imported unchanged from draft-v2 `5811254` (`draft_walkforward.py`)
and research/draft-player-feats `b5a2613` (`draft_player_feats.py`), with their
causality tests. The frozen cache contains the full eleven-feature game table.
It is gitignored, as are the feed corpus, DB, fitted research artifacts and dumps.
Preserve this worktree's caches until the work is merged or archived.

```bash
uv run python scripts/research/live_draft_v3.py
uv run python scripts/compare_benchmarks.py \
  data/research/live_draft_v3/production data/research/live_draft_v3/v3
uv run python scripts/compare_benchmarks.py \
  data/research/live_draft_v3/v2 data/research/live_draft_v3/v3
# Last command deliberately exits 1: v3 regresses versus v2.
```

The first run builds `data/research/live_draft_v3/rows.pkl` from existing feed
and gol.gg inputs and the worktree's DB. Delete or change `--rows` explicitly to
rebuild after an input change. `--games` selects the frozen player-feature table;
its default is `data/research/draft_v2/player_feats_games.pkl`. SHA256 values are
recorded below. The report replaces its generated Results section on reruns.

The automatic PR job remains `evaluate_live.py --fetch-data --dump …` against
its hash-pinned release asset, through production `timeline_calls`. New optional
`--model <supported-runtime-artifact.json>` routes the same candidate through
both live and pre-map replays and records its own fit cutoff in dump metadata.
The research v2/v3 artifacts deliberately have no runtime schema: live identity,
feature state and availability must be implemented before they can use that path.
No new CI job, expensive training run, data pin or default model change is added.

## Results

Train/calibration/test maps: 2,757 / 1,819 / 3,893. Missing test drafts: 39.

| Candidate | Control | Slice | Maps | LL | Control LL | Delta (95%) | ECE |
|---|---|---|---:|---:|---:|---|---:|
| v3 | production | All | 3,893 | 0.46458 | 0.46621 | -0.00164 (-0.00393 to +0.00048) | 0.0195 |
| v3 | production | Minutes 0–10 | 3,893 | 0.60316 | 0.60666 | -0.00350 (-0.00632 to -0.00084) | 0.0361 |
| v3 | production | Minutes 10–20 | 3,892 | 0.49543 | 0.49664 | -0.00122 (-0.00373 to +0.00123) | 0.0265 |
| v3 | production | Minutes 20–30 | 3,886 | 0.33599 | 0.33587 | +0.00012 (-0.00181 to +0.00210) | 0.0185 |
| v3 | production | Minutes 30+ | 2,158 | 0.27644 | 0.27650 | -0.00006 (-0.00240 to +0.00221) | 0.0086 |
| v3 | production | Major league | 3,100 | 0.47404 | 0.47601 | -0.00197 (-0.00436 to +0.00031) | 0.0191 |
| v3 | production | International | 305 | 0.45084 | 0.45036 | +0.00047 (-0.00623 to +0.00762) | 0.0266 |
| v3 | production | Other | 488 | 0.41303 | 0.41385 | -0.00082 (-0.00756 to +0.00643) | 0.0337 |
| v3 | production | LPL | 944 | 0.49559 | 0.50002 | -0.00443 (-0.00864 to +0.00011) | 0.0379 |
| v3 | production | Known draft | 3,854 | 0.46643 | 0.46810 | -0.00167 (-0.00389 to +0.00059) | 0.0200 |
| v3 | production | Missing draft | 39 | 0.28114 | 0.27989 | +0.00124 (-0.00116 to +0.00444) | 0.0354 |
| v3 | production | 2025 | 1,057 | 0.45434 | 0.45730 | -0.00296 (-0.00632 to +0.00050) | 0.0155 |
| v3 | production | 2026 | 2,836 | 0.46839 | 0.46953 | -0.00114 (-0.00369 to +0.00163) | 0.0256 |
| v3 | refit | All | 3,893 | 0.46458 | 0.46614 | -0.00156 (-0.00384 to +0.00056) | 0.0195 |
| v3 | refit | Minutes 0–10 | 3,893 | 0.60316 | 0.60577 | -0.00261 (-0.00539 to +0.00006) | 0.0361 |
| v3 | refit | Minutes 10–20 | 3,892 | 0.49543 | 0.49695 | -0.00152 (-0.00395 to +0.00086) | 0.0265 |
| v3 | refit | Minutes 20–30 | 3,886 | 0.33599 | 0.33634 | -0.00036 (-0.00220 to +0.00154) | 0.0185 |
| v3 | refit | Minutes 30+ | 2,158 | 0.27644 | 0.27588 | +0.00055 (-0.00170 to +0.00273) | 0.0086 |
| v3 | refit | Major league | 3,100 | 0.47404 | 0.47596 | -0.00192 (-0.00421 to +0.00032) | 0.0191 |
| v3 | refit | International | 305 | 0.45084 | 0.45054 | +0.00030 (-0.00605 to +0.00724) | 0.0266 |
| v3 | refit | Other | 488 | 0.41303 | 0.41352 | -0.00049 (-0.00739 to +0.00720) | 0.0337 |
| v3 | refit | LPL | 944 | 0.49559 | 0.49893 | -0.00334 (-0.00755 to +0.00134) | 0.0379 |
| v3 | refit | Known draft | 3,854 | 0.46643 | 0.46799 | -0.00156 (-0.00372 to +0.00063) | 0.0200 |
| v3 | refit | Missing draft | 39 | 0.28114 | 0.28346 | -0.00233 (-0.00424 to -0.00036) | 0.0354 |
| v3 | refit | 2025 | 1,057 | 0.45434 | 0.45739 | -0.00305 (-0.00637 to +0.00033) | 0.0155 |
| v3 | refit | 2026 | 2,836 | 0.46839 | 0.46940 | -0.00101 (-0.00357 to +0.00168) | 0.0256 |
| v3 | v2 | All | 3,893 | 0.46458 | 0.46319 | +0.00138 (+0.00022 to +0.00250) | 0.0195 |
| v3 | v2 | Minutes 0–10 | 3,893 | 0.60316 | 0.60166 | +0.00150 (+0.00006 to +0.00295) | 0.0361 |
| v3 | v2 | Minutes 10–20 | 3,892 | 0.49543 | 0.49389 | +0.00154 (+0.00027 to +0.00282) | 0.0265 |
| v3 | v2 | Minutes 20–30 | 3,886 | 0.33599 | 0.33471 | +0.00127 (+0.00033 to +0.00223) | 0.0185 |
| v3 | v2 | Minutes 30+ | 2,158 | 0.27644 | 0.27634 | +0.00010 (-0.00105 to +0.00132) | 0.0086 |
| v3 | v2 | Major league | 3,100 | 0.47404 | 0.47272 | +0.00132 (+0.00023 to +0.00247) | 0.0191 |
| v3 | v2 | International | 305 | 0.45084 | 0.45336 | -0.00252 (-0.00673 to +0.00120) | 0.0266 |
| v3 | v2 | Other | 488 | 0.41303 | 0.40881 | +0.00422 (-0.00014 to +0.00903) | 0.0337 |
| v3 | v2 | LPL | 944 | 0.49559 | 0.49322 | +0.00237 (+0.00023 to +0.00450) | 0.0379 |
| v3 | v2 | Known draft | 3,854 | 0.46643 | 0.46502 | +0.00141 (+0.00030 to +0.00256) | 0.0200 |
| v3 | v2 | Missing draft | 39 | 0.28114 | 0.28217 | -0.00104 (-0.00194 to -0.00012) | 0.0354 |
| v3 | v2 | 2025 | 1,057 | 0.45434 | 0.45393 | +0.00041 (-0.00150 to +0.00237) | 0.0155 |
| v3 | v2 | 2026 | 2,836 | 0.46839 | 0.46664 | +0.00175 (+0.00041 to +0.00311) | 0.0256 |
| v2 | production | All | 3,893 | 0.46319 | 0.46621 | -0.00302 (-0.00582 to -0.00043) | 0.0189 |
| v2 | production | Minutes 0–10 | 3,893 | 0.60166 | 0.60666 | -0.00500 (-0.00851 to -0.00168) | 0.0351 |
| v2 | production | Minutes 10–20 | 3,892 | 0.49389 | 0.49664 | -0.00276 (-0.00591 to +0.00019) | 0.0268 |
| v2 | production | Minutes 20–30 | 3,886 | 0.33471 | 0.33587 | -0.00115 (-0.00349 to +0.00120) | 0.0179 |
| v2 | production | Minutes 30+ | 2,158 | 0.27634 | 0.27650 | -0.00016 (-0.00294 to +0.00244) | 0.0092 |
| v2 | production | Major league | 3,100 | 0.47272 | 0.47601 | -0.00329 (-0.00628 to -0.00048) | 0.0199 |
| v2 | production | International | 305 | 0.45336 | 0.45036 | +0.00300 (-0.00579 to +0.01209) | 0.0290 |
| v2 | production | Other | 488 | 0.40881 | 0.41385 | -0.00504 (-0.01113 to +0.00107) | 0.0322 |
| v2 | production | LPL | 944 | 0.49322 | 0.50002 | -0.00680 (-0.01212 to -0.00131) | 0.0362 |
| v2 | production | Known draft | 3,854 | 0.46502 | 0.46810 | -0.00307 (-0.00577 to -0.00041) | 0.0193 |
| v2 | production | Missing draft | 39 | 0.28217 | 0.27989 | +0.00228 (-0.00077 to +0.00605) | 0.0386 |
| v2 | production | 2025 | 1,057 | 0.45393 | 0.45730 | -0.00337 (-0.00797 to +0.00113) | 0.0162 |
| v2 | production | 2026 | 2,836 | 0.46664 | 0.46953 | -0.00289 (-0.00594 to +0.00021) | 0.0256 |

Gate: FAIL. Retrospective evidence only; no deployment.

```json
{
  "base": "f522db3",
  "row_sha256": "7ff308db0751c4183f24ceb10d9d32aa08ebfe9a62ce3d6497170f98623170ef",
  "games_sha256": "b0a7775d5a0709bdd86c89bb607e2f4f9539caee54561994b5bd5cca6e3f1cd6",
  "model_sha256": "1e6832a9d1a6a40287fe66199adc903d23b1f2f0aadb83deac478dfec875a1bc",
  "runtime_parity_error": 4.996003610813204e-16,
  "frozen_vs_refit_error": 0.052891177294673186,
  "seconds": 40.48693691694643,
  "gate_pass": false
}
```
