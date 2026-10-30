

## 2026-10-30 — Playbook: infra deploy and cron jobs need no human

The owner allowed the agent to merge the infra PR, run the execution `diff`, and deploy when the diff holds only the game's two read keys; anything else stops. Removed H5/H6; cron-job.org jobs use the saved API key. Docs only; checks: steering test.

## 2026-10-30 — Playbook: cron-job.org key location

Recorded where the cron-job.org API key lives (owner's `~/.config/cron-job.org/api_key`, value not in the repo) and how jobs are created from an existing job's headers; H6 no longer needs the owner. Docs only; checks: steering test.

## 2026-10-30 — Playbook: lessons from the Dota 2 run

`docs/playbooks/new_game.md` now names dota2-model as a reference and records what the run taught: commit only on green tests, never print secrets, verify workers live; concrete H2/H4/H5/H6 steps (shared fine-grained token, override option, diff-then-deploy, cron-job.org API); Kalshi live vs historical endpoints; Liquipedia, OpenDota and local-setup traps; stage-1-only runs and the stage-2 look budget; Dota ladder results; the Prometheus game registry; live wiring check; CI backups and single rebuild; a **Where things live** section with lookups, no values. The cron-job.org key location is pending. Docs only; checks: steering test.

## 2026-10-30 — Playbook: seeding S3 from a Mac

Phase 6 now lists what to seed before the first scheduled run and the macOS `tar` flags that keep `._*` files out (they broke dota2-model's first refresh). Docs only; checks: steering test.

## 2026-10-30 — Playbook: CI cost rules

Added **CI cost rules** to `docs/playbooks/new_game.md` Phase 6 (public repo, cadence from the consumer, stdlib gate before setup, incremental fetching, skip unchanged work, cheap setup) and changed Phase 1 to create model repos public: dota2-model was created private, which made its 10-minute feed billable (estimated 4,320–11,520 minutes a month). Phase 6 cadences now 15 min (gated) and 3 h; Phase 7 notes thin-book `no_two_sided_blend_quote`. Docs only; checks: pytest (steering).

## 2026-10-29 — New-esport playbook

Branch `new-game-playbook`, base `origin/main`. Added `docs/playbooks/new_game.md`: the CS2/Valorant path for a new game in eight phases (feasibility, scaffold, data, baseline, refinement ladder, holdout gate, trading wiring, candidate-only run), with seven human stops and the steps an agent may take alone (repo creation, opening the holdout, infra PRs, Prometheus PRs). Gate: holdout blended flat ROI interval excludes 0 on a trade set fixed before opening; the plateau is the end of the nine-idea ladder. A `new-esport` skill and an AGENTS.md link point to it. Checks: pytest, ruff; links checked by hand. Limit: Phase 6 file list reflects the hard-coded game sets of 2026-10-29.

## 2026-10-29 — Private trading dashboard

Branch `dashboard`, base `close-issues` (PR #136). Added ledger-derived market bankrolls, P&L/ROI, dated charts, positions and results; shared canonical Kalshi links include game slugs. Lambda paginates history, reads accounts and stores issue/hash in `DASHBOARD`. Initialization finds/creates and pins the issue; changed content PATCHes, matching hashes skip GitHub. Failures never affect trading. Checks: offline/no-sync full pytest (1,242 passed, 2 skipped; 10.44s), ruff format/check and diff check passed. Initial document-budget failures were trimmed. Focused dashboard/notify tests: 30 passed, 0.05s. No dependencies/CI jobs added. Copy review: PASS for supplied dashboard headings, tables, chart keys, empty state and footer; copy already minimal. No network or commits. GitHub desktop/phone rendering, pin permissions and deployment unverified. Plain uv startup panicked; checks use the synced environment with offline/no-sync settings.

## 2026-10-29 — Close settled fill issues

Branch `close-issues`, base `main`. Fill notifications save the GitHub issue number; settlement comments with won/lost/even and realized P&L, then closes the issue. Legacy rows match exact Ticker/Environment lines across at most three open-issue pages, excluding pull requests and ambiguous matches. CS2/Valorant links use their game series; League links stay unchanged. The execution handler shares its cached token with the close callback. Notification/closure failures remain best effort; settled rows leave pending reconciliation, so failed closes are not retried. No trading, permissions, dependencies or CI jobs changed. Checks: offline/no-sync pytest (1,221 passed, 2 skipped); ruff format/check; diff check. New mocked tests add no external calls; full suite 10.71 seconds. No network or commits; GitHub/Lambda deployment unverified.

## 2026-10-29 — Game pages hide an empty Live now table

Branch `live-pause`, base `origin/main`. The CS2 page showed Live now with "No matches fit these filters." when its only live matches were tier 3 and the default filter is Majors; Valorant, with nothing live, had no section. `predictions.js` now hides a `data-section-for` section when the filters leave its table empty, matching the LoL Live now (hidden when nothing is in progress); the empty-filter line for live is gone. Checks: pytest, ruff, rendered CS2 page with the live feed at desktop and phone. Copy review: PASS (Live now, Coming up, Results on the CS2 page; cut the live empty-filter line).

## 2026-10-29 — Paused maps stay on the live pages

Branch `live-pause`, base `origin/main`. During a pause Riot's feed repeats one frozen frame marked `paused`; the collector rejected it (not in game, then stale), the page went `unavailable` and `write_index` dropped the match, so the live pages said no match was on. The collector now records `paused` when the newest frame is a paused one rejected only for pause, duplicate, order or staleness; the page publishes status `paused` (age check skipped), which stays in the index, keeps the last call for the series odds and shows "Paused." (already in `live.js`). `nav.js` and `fixtureOnLive` count `paused` as on. Live-map signals still need `live`. Checks: live tests (164 passed), full pytest, ruff. Confirmed frozen paused frames in recorded feeds. Limit: a feed lost mid-pause shows "Paused." until getLive drops the match. Copy review: PASS (no copy added).

## 2026-10-29 — Isolated game bankrolls and guarded S3 refits

CS2/Valorant configuration now requires enabled objects with their own positive starting bankroll. `ACCOUNT#cs2` / `ACCOUNT#valorant` hold reservations and settlement profit; League retains `ACCOUNT`. Plans use game free capital and aggregate held balance/exposure guards. Atomic held/realized checks bound losses including fees to seed plus realized; a repeated losing-fill/settlement test exhausts a $50 CS2 account without touching League. Shared daily limits remain. Optional `GAME_BLEND_KEYS` fetches enabled games' S3 refits hourly per warm container. Installation requires packaged validation and unchanged identity/clip; months already loaded are kept and only later months are appended (bounded slopes, ≥300 series), since a recomputed refit can nudge past months; rejection keeps current coefficients and is counted. Missing objects are silent. Checks: offline/no-sync pytest (1,186 passed, 2 skipped; 24.60s), ruff format/check, diff check. No CI job/build changes. No network or commits; AWS permissions/latency unverified.

## 2026-10-29 — CS2 and domestic Valorant series execution prepared

Branch `game-trading`, base `main`. Lambda accepts private CS2/domestic Valorant series candidates keyed by Kalshi names, blends current mids with frozen per-game coefficients (`prometheus/game_blends/`, copied from the model repos' `blend_artifact.json`; clip 0.01), then uses shared fees, Kelly, caps and ledger fences. League output is regression-pinned; League team aliases apply only to League ("DRX" → "Kiwoom DRX" would block Valorant DRX). Games start off: execution off → Configure `games` → mode on. `GAME_CANDIDATE_KEYS` (infra PR #25) names `cs2-model/feed/candidates.json`, `valorant-model/feed/candidates.json`. Valorant international never trades; Cloud9 veto stays universal. Checks: pytest (1,150 passed), ruff; real candidates give 62 CS2 / 6 Valorant proposals; blend matches the model repos' formula; read-only `PublicKalshi.resolve` on 11 live events: 6 resolved, 5 had no two-sided quote, none failed identity checks.
