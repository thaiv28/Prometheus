# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Remove draft v2 from map trading; add a $15 live-map budget

User asked to drop draft v2 (no trading gain; FST significantly worse) and cap live-map trading at $15. The draft route is gone from `live_map.py`, `live/signals.py`, `pyproject.toml` and the README; `live_map_draft_blend.json` deleted; the executor zip, release hash and publish filter drop the draft model and blend but keep `live/draft.py` (imported by `live/timeline.py`). New required `live_maps.budget_usd` for shadow and live map modes: the ledger's `LIVE_MAPS` row tracks held cost and realized profit, and a map order is capped at budget + realized − held, reserved in the same transaction as ACCOUNT. Loss can't exceed the budget; profit extends it; pregame unaffected. Docs suggest `"budget_usd": "15"`; nothing configured in AWS. Checks: 862 passed, 2 skipped; two budget tests fail with their guards removed; ruff; `package.sh` builds without draft files. Limit: the shared 1%/2% caps (about $0.50 a map) still apply; not deployed.

## 2026-10-19 — Review draft v2 for the 30-second trading blend

User asked to merge and activate PR #92's draft model only if benchmarks improved. Integrated main `bc02c4e` into `live-map-trading`; signals used the frozen ready draft with separate earlier-only monthly fits, and absent or conflicting drafts kept the original inference. Fixed, untuned comparison (1,352 maps, 655 series): log loss −0.00133 (−0.00437 to +0.00174); FST significantly worse, +0.02692 (+0.01188 to +0.04563); flat ROI +18.74% vs original +21.05%. Gate FAIL: no merge, deploy or activation; evidence in `docs/research/live_map_draft_trading.md`. Checks: 873 passed, 2 skipped (signing tests pass with pinned cryptography); ruff; 110 links; runtime blend matches the replay within 1.12e-16; package SHA256 `ac8c5a02…`. No UI or CI change.

## 2026-10-19 — Cut agents' token use: lean AGENTS.md, rotating log, doc budgets

Branch `token-diet`, base `b0acbac` (main). Docs and tooling only; no metric, build or CI change.
- `AGENTS.md` 4.1k → 2.3k words: read only the docs a change touches and the newest 5 log entries (`scripts/work_log.py recent 5`). Layout, metric change rules and benchmark commands moved to `tech.md`.
- `tech.md` 17.1k → 8.9k words (Codex, via the delegate skill): history and research cut to pointers.
- `.githooks/pre-commit` runs `work_log.py rotate`: past 15 entries, the newest 10 stay. Moved 68; no heading or line lost.
- Kept entries shortened to 150 words (originals at `b0acbac`); main's six from PR #94 too.
- `test_steering.py`: word budgets for changed steering docs and new entries.

Checks: pytest 794 passed, 2 skipped; ruff; `git diff --check`. Hook not yet run on a real commit.

## 2026-10-18 — Prepare API draft v2 as a private live candidate

Branch `live-draft-v2` (PR #92), base `f999333`, updated with main `b0acbac`. `live.draft` resolves all ten Riot participants to OE players by role, side, champion and exact names (team-scoped first; no fuzzy matching); failures fall back to the current model. The first valid receipt freezes the draft shift, later conflicts stop its use, and the context persists across restarts. One read-only SQL pass exports the v2 histories (earlier UTC days) in the daily ratings artifact (about 12 s more on main's export, 18 MB); the worker reads no DB. `time_model_draft_v2.json` runs as a private shadow (`calls.jsonl`); public calls unchanged. `evaluate_live.py --model` and `prepare_draft_benchmark.py` replay it. Checks: 20-map API sample, 17 resolved; features reproduce within 4.4e-14; 822 passed, 2 skipped; ruff; CI passed on PR #92; replay +4 ms per map. Limit: availability timing is a proxy; upload and reload timing unmeasured.

## 2026-10-18 — Benchmark draft v3 against the current live model

Branch `research/live-draft-v3`, base `f522db3` (PR #85), with the v2 walk-forward and v3 player studies imported from `5811254` / `b5a2613`. Protocol fixed before scoring ([report](../research/live_draft_v3.md)). 3,893 test maps: v3 − production −0.00164 (−0.00393 to +0.00048), inconclusive; v3 − v2 +0.00138 (+0.00022 to +0.00250), significantly worse; v2 − production −0.00302 (−0.00582 to −0.00043). v3 not promoted. The test chronology was already viewed, so this is not prospective. `evaluate_live.py` gains `--model`; default and explicit dumps are identical on 13,935 rows, and CI is unchanged. Frozen inference matches runtime to 5e-16. Checks: 23 focused tests; 800 passed, 2 skipped; ruff; links. No runtime, weights, UI or CI change.

## 2026-10-18 — Wire the selected 30-second live-map blend for review

Branch `live-map-trading`, base research `e35e5d0` / main `f522db3`; the user chose 30-second trade stability. A frozen monthly earlier-only blend, last-trade market input, pinned objective/momentum inference, a net 5-cent edge and a private worker outbox feed the executor via SQS; off/shadow/live map controls are independent of pregame. Historical replay reproduces all 189 entries (ROI +21.05%, +1.83% to +41.61%; retrospective, on reused history). The executor adds map rules, trade and book rechecks, quarter-or-smaller Kelly, 1% map / 2% series caps and shared reservations; existing vetoes, fences and IOC stay. Details: `docs/live_map_execution.md`. Worker load: two trade GETs per eligible quote cycle, +55 ms per feed update. Checks: 827 passed, 2 skipped; ruff; cfn-lint; 71 links; Lambda zip matches its sources (SHA256 `8bbe0120…`). Nothing deployed or activated.

## 2026-10-18 — Historical live-map trading and Kelly research

Branch `research/live-trading`, base `f522db3`; protocol fixed first, research only. Earlier-only monthly blends on 1,352 maps / 655 series (March–October 2026). Primary rule (first entry in minutes 5–30, net edge ≥ 5¢ after the 7% fee, stable fresh tape): 273 entries, ROI +8.86% (−4.76% to +23.94%), CLV +1.25¢. Blend log loss − market −0.00643 (−0.01331 to +0.00020); − current model −0.00835 (−0.01238 to −0.00438). The 30-second stability variant, +21.05% (+1.83% to +41.61%), is exploratory. A +5¢ cost stress turns ROI to −2.58%. Kelly from $100: full $151 (95% drawdown); quarter capped at 1%/2%, $125 (10%); every log-growth interval includes zero. No historical books, depth or fills. Report `docs/research/live_trading.md`. Checks: four tests; 793 passed, 2 skipped; ruff; 84 links. No production change.

## 2026-10-18 — Repair Live discovery and series lifecycle

Branch `fix-live-lifecycle`, base `09679a5` (PR #90). KC–MVK: side probes on the default window returned 204 until 18:33 UTC though map 1 started at 18:10, so side discovery now uses polling's delayed timestamped window (feed-side identity check kept). A red kill-counter disagreement dropped 5,975 frames on map 2; now only that counter is invalidated and the v1 objective fallback used. Started and completed series persist in `live/lifecycle.json` (7 days) through empty indexes and shutdown; Finished links them to Watch until the archive row exists; the worker settles a final map before untracking. Migration reconciled KC–MVK to 3–0 (214 ms, once). No model, benchmark-input, DB or CI change; one extra browser JSON read per poll. Checks: 792 passed, 2 skipped; pinned live benchmark identical base/head; site build. Copy review: PASS (Live, Watch at 1440/390; final-state copy replaces "Between maps"/"Stalled"; phone rows wrap).

## 2026-10-18 — Fix refresh/publisher ordering during live rollout

Branch `live-refresh-ordering`, base `f522db3` (PR #85). Rollout exposed a deadlock (also seen 2026-10-17): refresh stuck in start-post while the publisher waited on `After=prometheus-live-refresh.service`, timing out after 30 minutes. The conditional try-restart is now queued with `--no-block`. Installed via SSM with daemon-reload and `systemd-analyze verify` (only an unrelated acpid warning); the stuck refresh process was killed. Unit files install once, so `refresh.sh`'s git pull doesn't apply changed units on existing hosts. Readback: revision f522db3, model `objectives-momentum-2026-10-17`, smoke PASS, publisher running, nothing blocked. No trading change. Checks: 789 passed, 2 skipped; ruff. PR #85 CI: check 41 s, site build 3m58 s, live replay 3.5 s; no job added. Open: behavior on the first new map after rollout.

## 2026-10-18 — Release objective and gold-momentum in-game calls

Branch `live-model-release`, base research `de6ec95`, runtime base `27c3013`; the user asked to deploy. `time_model_objectives_v1.json` freezes the objective + momentum model (2024 feed training, Jan–Jun 2025 calibration): raw objective counters, a dragons ≥ 4 soul proxy, and the gold-lead change over at least 180 estimated seconds. Invalid objectives fall back to v1; clock range 0–40 minutes. Pre-map calls keep the old model (the new inputs worsened them, +0.0025, +0.0012 to +0.0038). Test: 3,857 maps, log loss −0.0136 vs v1 (−0.0170 to −0.0100), ECE 0.018; export parity 5e-16. Pinned benchmark: all guards pass; checkpoints −0.0127 (−0.0177 to −0.0073). Replay +33 ms per map; no new dependency, request, DB read or CI step. Checks: 789 passed, 2 skipped; ruff; links; site build. No UI change.
