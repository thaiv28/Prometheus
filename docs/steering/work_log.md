# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Cut agents' token use: lean AGENTS.md, rotating log, doc budgets

Branch `token-diet`, base `b0acbac` (main). Docs and tooling only; no metric, build or CI change.
- `AGENTS.md` 4.1k → 2.3k words: read only the docs a change touches and the newest 5 log entries (`scripts/work_log.py recent 5`). Layout, metric change rules and benchmark commands moved to `tech.md`.
- `tech.md` 17.1k → 8.9k words (Codex, via the delegate skill): history and research cut to pointers.
- `.githooks/pre-commit` runs `work_log.py rotate`: past 15 entries, the newest 10 stay. Moved 68; no heading or line lost.
- Kept entries shortened to 150 words (originals at `b0acbac`).
- `test_steering.py`: word budgets for changed steering docs and new entries.

Checks: pytest 794 passed, 2 skipped; ruff; `git diff --check`. Hook not yet run on a real commit.

## 2026-10-18 — Repair Live discovery and series lifecycle

Branch `fix-live-lifecycle`, base `09679a5` (PR #90). KC–MVK: side probes on the default window returned 204 until 18:33 UTC though map 1 started at 18:10, so side discovery now uses polling's delayed timestamped window (feed-side identity check kept). A red kill-counter disagreement dropped 5,975 frames on map 2; now only that counter is invalidated and the v1 objective fallback used. Started and completed series persist in `live/lifecycle.json` (7 days) through empty indexes and shutdown; Finished links them to Watch until the archive row exists; the worker settles a final map before untracking. Migration reconciled KC–MVK to 3–0 (214 ms, once). No model, benchmark-input, DB or CI change; one extra browser JSON read per poll. Checks: 792 passed, 2 skipped; pinned live benchmark identical base/head; site build. Copy review: PASS (Live, Watch at 1440/390; final-state copy replaces "Between maps"/"Stalled"; phone rows wrap).

## 2026-10-18 — Fix refresh/publisher ordering during live rollout

Branch `live-refresh-ordering`, base `f522db3` (PR #85). Rollout exposed a deadlock (also seen 2026-10-17): refresh stuck in start-post while the publisher waited on `After=prometheus-live-refresh.service`, timing out after 30 minutes. The conditional try-restart is now queued with `--no-block`. Installed via SSM with daemon-reload and `systemd-analyze verify` (only an unrelated acpid warning); the stuck refresh process was killed. Unit files install once, so `refresh.sh`'s git pull doesn't apply changed units on existing hosts. Readback: revision f522db3, model `objectives-momentum-2026-10-17`, smoke PASS, publisher running, nothing blocked. No trading change. Checks: 789 passed, 2 skipped; ruff. PR #85 CI: check 41 s, site build 3m58 s, live replay 3.5 s; no job added. Open: behavior on the first new map after rollout.

## 2026-10-18 — Release objective and gold-momentum in-game calls

Branch `live-model-release`, base research `de6ec95`, runtime base `27c3013`; the user asked to deploy. `time_model_objectives_v1.json` freezes the objective + momentum model (2024 feed training, Jan–Jun 2025 calibration): raw objective counters, a dragons ≥ 4 soul proxy, and the gold-lead change over at least 180 estimated seconds. Invalid objectives fall back to v1; clock range 0–40 minutes. Pre-map calls keep the old model (the new inputs worsened them, +0.0025, +0.0012 to +0.0038). Test: 3,857 maps, log loss −0.0136 vs v1 (−0.0170 to −0.0100), ECE 0.018; export parity 5e-16. Pinned benchmark: all guards pass; checkpoints −0.0127 (−0.0177 to −0.0073). Replay +33 ms per map; no new dependency, request, DB read or CI step. Checks: 789 passed, 2 skipped; ruff; links; site build. No UI change.

## 2026-10-17 — Second live research wave: conditional gains and role leads

Branch `research/live-candidates` from `e0a9617`. Protocol in `cand_followups.py` fixed before scoring; the test set was already used, so gains are retrospective. Beyond objectives (3,857 feed maps): original draft −0.0018 (−0.0035 to −0.0002), interaction draft −0.0026, momentum −0.0025 (−0.0033 to −0.0017; −0.0136 vs v1). Raw objective calibration beats global: log loss −0.0017 (−0.0031 to −0.0001), ECE 0.008 vs 0.019; time buckets worsen 20–30 minutes. Role leads at OE 10–25 minutes (3,378 maps), beyond gold + Elo: gold+CS −0.0030, +XP −0.0068 (−0.0100 to −0.0035); no gain shown beyond objectives. Nothing adopted. Artifacts in `data/research/live_followups/`. Checks: 784 passed, 2 skipped; three new tests (empty cohort, orientation); ruff; 66 links. No runtime, CI or dependency change.

## 2026-10-17 — Consolidate live candidates; momentum and calibration checks

Branch `research/live-candidates`, base `9b670eb` (PR #83). Imported the objectives candidate (`5cb5e0f`, full script), the draft candidate and per-map Elo (`baf763a`); results in [the candidate review](../research/live_candidates.md). Objectives − v1 −0.0111 (−0.0146 to −0.0075); draft −0.0027 (−0.0052 to −0.0002, coverage caveats); neither deployed. Three-minute gold momentum − v1 −0.0006 (−0.0022 to +0.0010): not adopted. Raw and time-bucket calibration don't beat global significantly and have worse slices: no change. Checks: 781 passed, 2 skipped; ruff; `git diff --check`; 40 links; draft and objectives reports reproduced. No production, CI or build change.

## 2026-10-17 — Live map model candidate: objectives on top of gold

Branch `cand-objectives` from `9b670eb`. `scripts/research/cand_objectives.py` (report `docs/research/cand_objectives.md`): protocol committed first (`e33fa23`); v1's six features plus blue − red towers, dragons, barons, inhibitors, kills and soul, each with a time interaction, trained on 2,757 2024 feed maps. Test (3,857 maps): − v1 −0.0111 (−0.0146 to −0.0075), passing the adoption rule; gains from minute 10 on, none at 0–10; ECE 0.0147 → 0.0191. Not shipped: needs a live model contract and a prospective check. A repeated clock key in one map is now aligned by position. Checks: research and steering tests, ruff, `git diff --check`.

## 2026-10-17 — Back up the feed timelines; live model v3 (weights that change with game time)

Branch `time-model-v3` from `27c3013` (PR #66). Feed timelines (9,046 maps, 7.8 MB tarball) uploaded to `s3://$DATA_BACKUP_BUCKET/prometheus/feed-timelines/` with their SHA-256, downloaded again and matched (`deployment.md`). `train_time_model_v2.partitions` shares v2's split. `scripts/research/train_time_model_v3.py` (report `docs/research/time_model_v3.md`): spline-in-time weights on time, gold lead, gold share and Elo gap; test v3 − v1 +0.0000 (−0.0012 to +0.0013), not adopted (better at 10–20 and 30+ minutes, worse at 0–10). With gold, Elo and time the model looks saturated; the next tests are new inputs (Future work). Checks: live and research tests, ruff, `git diff --check`.

## 2026-10-17 — Align alert selection with execution fees

Branch `alert-execution-fees`, base `0cc01bd` (PR #80). The executor rejected the KC v MVK alert, so new alerts use the Lambda's fee bound (`trading.quote(execution_fees=True)` → `core.fee_bound`, rate 0.07, precision 0.0001): at 86¢ the reserve is 3¢, so 87.66% doesn't clear it. Edges are subtracted in Decimal, so a zero edge is rejected. New records freeze the fee policy; old alerts and paper results keep their terms. Update the two public fee constants with any private fee-profile change. No executor, metric or order change. Checks: 59 focused and 745 full passed, 2 skipped; ruff; quote +3.7 µs per call. Copy review: PASS (Market Blend page at 1440/390; "estimated fee" → "execution fee bound").

## 2026-10-17 — Faster Live prices and started fixture handoff

Branch `live-refresh`, base `ac5745c` (PR #76). Kalshi books and publication every 2 s (was 10), browser polls every 2 s (was 5), live JSON cache 1 s; the Riot feed, settlement and model stay at 10 s, and price-only cycles refresh the page without replaying the model. Coming up hides a match once its series shows live or between maps, keeping later repeat pairings and supporting older worker summaries. Cost while live: orderbook reads 720 → 3,600 an hour, S3 cycles 360 → 1,800, browser polls 2.5×. Checks: live and Node tests (cadence: 6 price cycles per Riot cycle); 717 passed, 2 skipped; ruff. Production timings unverified. Copy review: PASS (Live and Watch at 1440/390; no strings added).
