

## 2026-11-09 — Paused pre-match slices with no shown edge

Branch `pause-unproven-slices` from `main`. Added `PAUSED_SLICES` to `alert_contract.py`, enforced by `trade_veto`: LoL minor domestic and all international groups, CS2 `INTL` and `T1`, Valorant `GC` and `OFF`. Alerts stay visible; live-map trading is unchanged. CS2 and Valorant candidates must carry `provenance.section` (added in prometheus-models) or they are vetoed. Evidence and on/off table: [`docs/betting_scope.md`](../betting_scope.md). Checks: new veto and doc-sync tests; full pytest; ruff. Limit: not observed on the deployed Lambda or in the private S3 candidates (AWS login expired).

## 2026-11-02 — Game models moved to prometheus-models

Docs only. `cs2-model`, `dota2-model` and `valorant-model` were merged with history into `thaiv28/prometheus-models` (`games/<game>/`) and archived; their scheduled workflows and the cron-job.org dispatches now target that repo. S3 prefixes are unchanged, so `other_games.py`, `game_feeds.sh` and the execution Lambda need no change. Updated the Other games paragraph in `deployment.md`. Checks: every new-repo workflow ran green once; Prometheus `games.yml` publishes after their feeds; pytest (steering).

## 2026-11-02 — Polymarket US checked against Kalshi

Branch `polymarket-check` from `main`. Closes the Future work item "investigate Polymarket books". Polymarket US (public API `gateway.polymarket.us`, LoL series 33, minute bid/ask history from April 2026) matched to the cached Kalshi frame: 1,199 series priced on both 12 h before the start. Mid gap median 0.005 (3% over 3 points), spreads 1 point on both; log loss Polymarket − Kalshi −0.0015 (−0.0039 to +0.0008). Buying at the cheaper venue after fees (Polymarket taker 0.0695, Kalshi 0.07) gained nothing over Kalshi alone at any edge (all intervals span 0). Limits: top of book only, no depth; scratch scripts, not committed. Checks: pytest (steering). No code change.

## 2026-11-02 — Pre-match top-ups pass the account guard

Branch `retrade-backtest`. Every top-up failed `kalshi.exposure()` (`existing_fixture_exposure`), so none was ever placed. `topup_position` now returns each ticker's signed filled count (bid +, ask −); the executor passes it to the client, which accepts fixture positions only when Kalshi's `position_fp` matches exactly. Extra, missing or other-ticker positions, and any position before the first leg, still block. Checks: new client cases and an end-to-end top-up through the real guard (fail before the fix); full pytest; ruff. Limit: a live-map Bo1 fill on the series ticker makes positions differ and blocks top-ups (fails closed). Not yet exercised live.

## 2026-11-02 — Pre-match re-trading backtest

Branch `retrade-backtest` from `main`. Live ledger: no top-up ever placed; `kalshi.exposure()` raises `existing_fixture_exposure` on any held fixture (63 skip rows). Added `scripts/research/pregame_retrading.py` and [the report](../research/pregame_retrading.md): 8,553 series over four games on hourly candles. Top-ups +6.4 bp P&L per series [+1.0, +11.9] but +0.8 bp log growth [−4.4, +5.8]; selling and side swaps no better; first-hour entry beats last-hour by ~30 bp. Model rows were exported from each game repo's adopted replay (Valorant weights from `game-candidates`). Checks: script runs (6 s), sensitivity windows/caps; ruff; pytest. No production change.

## 2026-11-02 — Live page: deciding map awaiting its result

Branch `deciding-map-wait` from `main`. After the deciding map ended, the live page showed "Between maps." at the old score until Kalshi or Riot reported the winner (TL vs LØS map 3 had no map contract; ~5+ minutes at 1–1). A finished map with no result that could end the series now sets `awaiting_result` and the note "Map N is over; waiting for the result."; `live.js` drops "Between maps." for it. Checks: new `GameStateTest` case; full pytest 1,288 passed, 2 skipped (34.3 s); JS tests 26 passed; ruff format/check. Limit: the score and series close still wait on Kalshi settlement or Riot's completed state.

## 2026-11-02 — Playbook: one models repo, CI lessons, worktree cleanup

`docs/playbooks/new_game.md` now builds a game as `games/<game>/` in `thaiv28/prometheus-models` (no new repo, secrets or token change; root CI, hook and setup action cover it), copies root `dota2-*` workflows and joins the Kalshi matrix, and records the 2026-11-02 CI audit (drifted copies, content-hash dispatch, ratings in the gate, 500-title listings, cached link helpers, moved pages). Ground rules: remove worktrees once merged. The `new-esport` skill points at the game folder. Docs only; checks: steering test.

## 2026-11-02 — Executor: top-up reserve permission and health issue

Branch `executor-health` from `main`. The role lacks ConditionCheckItem, so every top-up reserve failed with AccessDeniedException (2026-10-30 21:40 to 2026-11-02 12:59 on an unfilled first leg, again from 20:38 after the guard fix), surfacing as "Execution incomplete" every minute. Reserve now uses a no-op conditional Update, previously validated against DynamoDB with a forced-cancel probe (nothing written). The test fake rejects operations outside the role. Errors record step:type; a private GitHub issue opens after 10 consecutive failing runs and closes on recovery. Checks: full pytest (1,323 passed, 2 skipped), focused execution/steering (265 passed), Ruff format/check, diff check. Used UV_NO_SYNC=1 to bypass a uv macOS startup panic; focused tests needed PYTHONPATH=. Limit: GitHub publication and Lambda execution not exercised against production.

## 2026-10-30 — Pre-match top-ups to the Kelly target

Branch `prematch-topups` from `main`. Ledger scan: 44 live intents; 5 depth-capped (≈$2.91 of $156.51 ideal), 9 limited by the 10% series cap (≈$47), which top-ups cannot lift; one unfilled. Added sequenced intent/active/evidence legs and exact held-position Kelly, same-side resolved-order guards, MAX_LEGS 4 and $0.50 minimum; first-leg identities and spending caps remain. Checks: existing `.venv` focused pytest 219 passed (0.26s; prior cases alone 187 passed, 0.21s); full pytest 1,287 passed, 2 skipped (10.53s); 144 legacy sizing payloads identical; ruff format/check and diff checks passed. `uv run --offline` panicked at startup. No dependencies, CI jobs or build steps added. ACK status `submitted` also blocks top-ups until reconciliation. Limits: live-map path still sizes on capital net of its own held cost (unchanged); each top-up fill opens its own trade issue; not exercised against the real exchange.

## 2026-10-30 — Dota 2 trading live

With the Lambda on main (source hash checked), execution was set off, `games` gained `dota2` ($50; CS2 and Valorant unchanged), and mode set back to live at 19:54 UTC through the configure and mode workflows. Live maps stayed live. Docs only; checks: steering test.

## 2026-10-30 — Dota 2 blend packaged; live candidates resolve

Added `prometheus/game_blends/dota2.json`, copied from dota2-model's `promdota/blend_artifact.json` (8 monthly snapshots; latest a 1.18, b 0.84, 992 series). A real dota2-model export (10 candidates) gives 20 proposals through `saved_candidates`; read-only `PublicKalshi.resolve` on the 10 events: 6 resolved, 4 had no two-sided quote, none failed identity checks. Dota stays disabled. Checks: pytest, ruff.
