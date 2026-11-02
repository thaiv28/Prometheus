

## 2026-11-02 — Executor: top-up reserve permission and health issue

Branch `executor-health` from `main`. The role lacks ConditionCheckItem, so every top-up reserve failed with AccessDeniedException (2026-10-30 21:40 to 2026-11-02 12:59 on an unfilled first leg, again from 20:38 after the guard fix), surfacing as "Execution incomplete" every minute. Reserve now uses a no-op conditional Update, previously validated against DynamoDB with a forced-cancel probe (nothing written). The test fake rejects operations outside the role. Errors record step:type; a private GitHub issue opens after 10 consecutive failing runs and closes on recovery. Checks: full pytest (1,323 passed, 2 skipped), focused execution/steering (265 passed), Ruff format/check, diff check. Used UV_NO_SYNC=1 to bypass a uv macOS startup panic; focused tests needed PYTHONPATH=. Limit: GitHub publication and Lambda execution not exercised against production.

## 2026-11-02 — Polymarket US checked against Kalshi

Branch `polymarket-check` from `main`. Closes the Future work item "investigate Polymarket books". Polymarket US (public API `gateway.polymarket.us`, LoL series 33, minute bid/ask history from April 2026) matched to the cached Kalshi frame: 1,199 series priced on both 12 h before the start. Mid gap median 0.005 (3% over 3 points), spreads 1 point on both; log loss Polymarket − Kalshi −0.0015 (−0.0039 to +0.0008). Buying at the cheaper venue after fees (Polymarket taker 0.0695, Kalshi 0.07) gained nothing over Kalshi alone at any edge (all intervals span 0). Limits: top of book only, no depth; scratch scripts, not committed. Checks: pytest (steering). No code change.

## 2026-11-02 — Pre-match top-ups pass the account guard

Branch `retrade-backtest`. Every top-up failed `kalshi.exposure()` (`existing_fixture_exposure`), so none was ever placed. `topup_position` now returns each ticker's signed filled count (bid +, ask −); the executor passes it to the client, which accepts fixture positions only when Kalshi's `position_fp` matches exactly. Extra, missing or other-ticker positions, and any position before the first leg, still block. Checks: new client cases and an end-to-end top-up through the real guard (fail before the fix); full pytest; ruff. Limit: a live-map Bo1 fill on the series ticker makes positions differ and blocks top-ups (fails closed). Not yet exercised live.

## 2026-11-02 — Pre-match re-trading backtest

Branch `retrade-backtest` from `main`. Live ledger: no top-up ever placed; `kalshi.exposure()` raises `existing_fixture_exposure` on any held fixture (63 skip rows). Added `scripts/research/pregame_retrading.py` and [the report](../research/pregame_retrading.md): 8,553 series over four games on hourly candles. Top-ups +6.4 bp P&L per series [+1.0, +11.9] but +0.8 bp log growth [−4.4, +5.8]; selling and side swaps no better; first-hour entry beats last-hour by ~30 bp. Model rows were exported from each game repo's adopted replay (Valorant weights from `game-candidates`). Checks: script runs (6 s), sensitivity windows/caps; ruff; pytest. No production change.

## 2026-11-02 — Live page: deciding map awaiting its result

Branch `deciding-map-wait` from `main`. After the deciding map ended, the live page showed "Between maps." at the old score until Kalshi or Riot reported the winner (TL vs LØS map 3 had no map contract; ~5+ minutes at 1–1). A finished map with no result that could end the series now sets `awaiting_result` and the note "Map N is over; waiting for the result."; `live.js` drops "Between maps." for it. Checks: new `GameStateTest` case; full pytest 1,288 passed, 2 skipped (34.3 s); JS tests 26 passed; ruff format/check. Limit: the score and series close still wait on Kalshi settlement or Riot's completed state.

## 2026-10-30 — Playbook: Liquipedia 429s and secret writes

Phase 6 now says CI feeds must survive Liquipedia `HTTP 429` on shared runner IPs by reusing the last raw snapshot (`liquipedia_stale=1`), as cs2-model and dota2-model now do, and that `tee` steps need `shell: bash` for pipefail. H2 notes that a blocked secret write goes to the user as a `!` command. Docs only; checks: steering test.

## 2026-10-30 — Playbook: infra deploy and cron jobs need no human

The owner allowed the agent to merge the infra PR, run the execution `diff`, and deploy when the diff holds only the game's two read keys; anything else stops. Removed H5/H6; cron-job.org jobs use the saved API key. Docs only; checks: steering test.

## 2026-10-30 — Playbook: cron-job.org key location

Recorded where the cron-job.org API key lives (owner's `~/.config/cron-job.org/api_key`, value not in the repo) and how jobs are created from an existing job's headers; H6 no longer needs the owner. Docs only; checks: steering test.

## 2026-10-30 — Playbook: lessons from the Dota 2 run

`docs/playbooks/new_game.md` now names dota2-model as a reference and records what the run taught: commit only on green tests, never print secrets, verify workers live; concrete H2/H4/H5/H6 steps (shared fine-grained token, override option, diff-then-deploy, cron-job.org API); Kalshi live vs historical endpoints; Liquipedia, OpenDota and local-setup traps; stage-1-only runs and the stage-2 look budget; Dota ladder results; the Prometheus game registry; live wiring check; CI backups and single rebuild; a **Where things live** section with lookups, no values. The cron-job.org key location is pending. Docs only; checks: steering test.

## 2026-10-30 — Playbook: seeding S3 from a Mac

Phase 6 now lists what to seed before the first scheduled run and the macOS `tar` flags that keep `._*` files out (they broke dota2-model's first refresh). Docs only; checks: steering test.
