# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Merge Live into Predictions; props page fix

Base `fd8120c`; Codex via delegate. Predictions now holds Live now, Coming up and 7 days of results, linked to live series pages when recorded. `live.html` and `live-results/<month>` redirect. Record and Kalshi tables moved to Call performance. Home and watch fixtures keep whole UTC days (`_whole_days`). The header marks Predictions with a red dot while a match is live (not if the index is 10+ minutes old). Dropped the fixtures "By" column (in the tooltip) and live towers/dragons/barons. Props: NaN `p_side` crashed the page silently; page failures now fail the build.

Checks: pytest 906 passed, 2 skipped; ruff; full build; no table overflow at 1280/1440 (Predictions, Call performance). Copy review: PASS (Predictions, Call performance, home; cut full name and "Gold lead" to "Gold"). Limit: tables still scroll at 1001–1279px.

## 2026-10-19 — Live-map trading switched on with a $15 budget

At the user's request (shadow skipped), merged #94 (executor released by publish `39300099249`) and infrastructure PR #20 (signal queue in `ThaivPrometheusExecution`, worker grants and `LIVE_MAP_SIGNAL_ARGS` in `ThaivPrometheusLive`). Deployed both stacks through their workflows after diffs (no existing resource replaced except the worker instance; no match was live). Updated `LIVE_WORKER_INSTANCE_ID`. Paused global execution about 1.5 minutes to save `live_maps` (queue ARN, quarter Kelly, 1%/2% caps, `budget_usd` 15), restored live, then set live-map mode live; activation validated the config and runtime. Unverified: the new worker's env and first signal delivery (local AWS session expired), real fills and latency. Infra cost estimate: about $0–0.30 a month (SQS polling inside the free tier).

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

## 2026-10-19 — Ship Glicko-1-style player RD and non-major update slope in Elo

Branch `elo-glicko-scale` (PR #96). Each player's move scales by RD²/floor² (`PLAYER_RD=(280,140,140,10)`, information .125), replacing the provisional and time-away factors; non-major domestic games update on slope .0065 (majors, international unchanged; K 20). `LEGACY_ELO` keeps the old Elo for research. Refit FORGE, Form and league-curve weights; reports regenerated.

Paired `evaluate_metrics.py` (CI and local agree): domestic Elo −0.0009, cross-league −0.0015, other-league Elo −0.0024 and FORGE −0.0009, all significant; domestic and international FORGE within noise. Markets: series log loss vs Kalshi −0.0030 (−0.0053 to −0.0007). Elo replay 5.5 → 6.5 s (DB build, cache misses only).

Checks: pytest, ruff, DB rebuild, site build, CI benchmarks pass. Not refit: regional calibration, market blend, props weights, live models (CI benchmarks within noise).

## 2026-10-19 — Elo research: rating uncertainty, update slope, joint tune

Reports: `elo_glicko.md`, `elo_fitted_scale.md`, `elo_glicko_scale.md`. Player RD v1 tied settled players to K ≈ 9 (flawed grid, kept as `elo_glicko_v1.md`); v2 (reference = floor) gained in other leagues. A uniform update slope hurt domestic FORGE; non-major-only passed. Jointly tuned through 2021, held out 2022+: combined vs published other-league Elo −0.0033, FORGE −0.0014, cross-league −0.0028. The joint script's verdict flagged a nine-game international roster-change slice; overruled as too few games (main sections pass). Player win share: not adopted (archive entry).

## 2026-10-19 — Future work: player win share and Elo rating model

Branch `future-win-share`, based on `b0acbac` (main). Documentation only: added two Future work items to `docs/steering/current_state.md`: splitting Elo changes among starters by their share of an in-game lead (gold difference at 15/20 minutes or similar), and the Elo rating model (expected score on the fitted slope with K retuned; Glicko-2-style uncertainty; later TrueSkill Through Time or dynamic Bradley-Terry). No code changed; no checks beyond reading the rendered Markdown.

## 2026-10-18 — Prepare API draft v2 as a private live candidate

Branch `live-draft-v2` (PR #92), base `f999333`, updated with main `b0acbac`. `live.draft` resolves all ten Riot participants to OE players by role, side, champion and exact names (team-scoped first; no fuzzy matching); failures fall back to the current model. The first valid receipt freezes the draft shift, later conflicts stop its use, and the context persists across restarts. One read-only SQL pass exports the v2 histories (earlier UTC days) in the daily ratings artifact (about 12 s more on main's export, 18 MB); the worker reads no DB. `time_model_draft_v2.json` runs as a private shadow (`calls.jsonl`); public calls unchanged. `evaluate_live.py --model` and `prepare_draft_benchmark.py` replay it. Checks: 20-map API sample, 17 resolved; features reproduce within 4.4e-14; 822 passed, 2 skipped; ruff; CI passed on PR #92; replay +4 ms per map. Limit: availability timing is a proxy; upload and reload timing unmeasured.
