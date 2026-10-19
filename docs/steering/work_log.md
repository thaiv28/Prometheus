# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Fresh calls, part 4: browser rating overlays

Added effective `player_rating`, build-matched `fresh.json` deltas (including idle players' league-offset moves), listed-player slug export and hourly upload with 30-second caching. Registers, head-to-head and home top tens apply current Elo/FORGE deltas; season rows and Form stay frozen. No new style; only added text is the results timestamp. Checks: pytest 950 passed, 2 skipped; 26 Node tests; ruff format/check; offline site build; built slug index, timestamps and script references; home DOM values/order/ranks/bars/captions; diff whitespace. Tech: 9,416 words. Reviewer: headless Chrome with a test overlay on Team/Player Elo, FORGE and home at 1440 and 390 px (re-rank, bars, head to head); moved the home captions' note before their trailing link. Copy review: PASS (registers, home captions; only "Results through …"). Limits: HTTP/S3 and Actions time unmeasured; team and player pages' fact lines and Elo history update only at builds.

## 2026-10-19 — Fresh calls, part 3: hourly pages and live ratings

Hourly/dispatched prices renders Predictions, monthly results and call performance after a successful log save, using published backtest/team/series artifacts; failed fetches publish nothing. Builds add `series-links.json`. Refresh exports shifted live inputs without overwriting the base; the worker checks every five minutes and adopts only newer inputs from the same publish. JSON prices cache for 30 seconds, rendered HTML for 60; alerts/props keep five minutes. Checks: pytest 941 passed, 2 skipped; ruff format/check; 23 JS tests; live shell syntax; doc word budgets and diff whitespace. Offline fixture render: 0.037 s; added HTTP/S3 and CI wall time unmeasured. Limits: not run in CI; Elo pages still update only at builds until the overlay lands. No templates, CSS, JS or page copy changed.

## 2026-10-19 — Fresh calls, part 2: finished maps from the live worker; refreshed calls on the page

Worker records each settled map in `maps.json` (winner, players from the collector's last frame, length only when `find_start` found the start and it is 15–75 minutes), uploads it, and dispatches `prices.yml` (5-minute debounce; token from SSM). The refresh adds worker maps (precedence: scoreboard, worker, schedule); worker league labels map to ours (`WLDs` → Worlds). `kalshi.json` carries each unstarted call, which `predictions.js` applies. Checks: pytest 926 passed, 2 skipped; JS tests 23 passed; ruff; `record_map` on the backed-up KC v MVK match (players exact; map 1 length dropped because the worker joined late); headless Chrome at 1440 and 390 px. Copy review: PASS (Predictions, home fixtures; only new text is the tooltip's "results through …"). Limits: dispatch needs the token, SSM grant and live-stack deploy; no live match run yet.

## 2026-10-19 — Fresh calls, part 1: resume Elo with Leaguepedia results hourly

`EloState` makes the replay resumable (rebuilt Elo tables identical row for row). Publish saves the state (3.1 MB, ~11 s); the hourly job's new step replays Leaguepedia games Oracle's Elixir lacks (each matched to an OE game of the same pair within 3 hours, or applied) and refreshes unstarted calls; Form stays frozen, `data_through` stays the OE date. Real run: 31 games applied, 37 known, 6 calls changed, 13 s. Justified by measured lag (+0.0039 series log loss a day); same-day games alone are within noise (−0.0010, −0.0024 to +0.0003) after fixing a leak in the first research run (own games dated before the start). Checks: pytest, ruff. Limits: not yet run in CI.

## 2026-10-19 — Weekly live benchmark data refresh in CI

New `live-bench.yml` (Mondays, main only, read-only contents; commits nothing): restores the feed timelines and Kalshi tapes from `s3://…/prometheus/live-bench/`, collects new feed maps in four shards, runs `--build-data --refresh-markets`, syncs grown state back and saves `live-bench-data-<hash>` to the Actions cache. `benchmarks.yml` restores that one entry for both sides (in the markets dump key); the release pin stays as fallback. `feed_timelines.py schedule` stops paging at saved matches. Cost: state 7.4 MB + 56 MB compressed (13 s to tar locally); ~17 s a map, ~100 maps a week; no time added to publish, PR checks or hourly jobs. Checks: full suite 894 passed, 2 skipped; ruff; YAML parses. Limits: not yet run in CI (needs merge, S3 seed, a dispatch); Riot may refuse GitHub runners; CI build time unmeasured.

## 2026-10-19 — Live results' map odds follow the series score; current_state trimmed

Branch `live-anchor`, base `b6e0b62`. Series pages showed the pre-series map chance on every row; "Map: ours" and the map chart's opening call now take `series.map_prior` (rho from `forge.json`, else the log's home leagues), as the live page and series column already did. The shift alone beats the unshifted pregame call on 732 priced maps 2+ (−0.0077, −0.0135 to −0.0025; `live_anchor.md`). `current_state.md` condensed 9,561 → ~2,900 words (Codex). Checks: archive tests (one new), full pytest, ruff; site built from a read-only S3 sync of compact live maps; four series tables checked, one page screenshotted at desktop and phone widths. Copy review: PASS (Table I, note and figure; no copy changed, the note already says "FORGE and the score"). Headless phone render clips the table's right edge, unverified on a device.

## 2026-10-19 — Live model: FORGE pregame, FORGE anchor, raw calibration tested

`scripts/research/live_anchor.py` ([report](../research/live_anchor.md)); rule fixed before scoring; viewed test split. Pregame: displayed FORGE + series shift beats the benchmark's v1 t=0 call by −0.0111 (−0.0209 to −0.0019) on 1,271 priced maps; shift −0.0044, FORGE over shifted v1 −0.0066 (n.s.). Anchoring in-game calls on FORGE: +0.0023 (−0.0014 to +0.0060), 30+ min significantly worse: rejected. Dropping calibration: feed −0.0015 (−0.0030 to −0.0002) but live-benchmark 30 min +0.0030 (+0.0002 to +0.0055): rejected. No runtime, model or CI change; 37 s, local only. Limit: FORGE p is the backtest's (month-start ratings, out-of-year curves), covering 38% of pre-maps.

## 2026-10-19 — Merge Live into Predictions; props page fix

Base `fd8120c`; Codex via delegate. Predictions now holds Live now, Coming up and 7 days of results, linked to live series pages when recorded. `live.html` and `live-results/<month>` redirect. Record and Kalshi tables moved to Call performance. Home and watch fixtures keep whole UTC days (`_whole_days`). The header marks Predictions with a red dot while a match is live (not if the index is 10+ minutes old). Dropped the fixtures "By" column (in the tooltip) and live towers/dragons/barons. Props: NaN `p_side` crashed the page silently; page failures now fail the build.

Checks: pytest 906 passed, 2 skipped; ruff; full build; no table overflow at 1280/1440 (Predictions, Call performance). Copy review: PASS (Predictions, Call performance, home; cut full name and "Gold lead" to "Gold"). Limit: tables still scroll at 1001–1279px.

## 2026-10-19 — Live-map trading switched on with a $15 budget

At the user's request (shadow skipped), merged #94 (executor released by publish `39300099249`) and infrastructure PR #20 (signal queue in `ThaivPrometheusExecution`, worker grants and `LIVE_MAP_SIGNAL_ARGS` in `ThaivPrometheusLive`). Deployed both stacks through their workflows after diffs (no existing resource replaced except the worker instance; no match was live). Updated `LIVE_WORKER_INSTANCE_ID`. Paused global execution about 1.5 minutes to save `live_maps` (queue ARN, quarter Kelly, 1%/2% caps, `budget_usd` 15), restored live, then set live-map mode live; activation validated the config and runtime. Unverified: the new worker's env and first signal delivery (local AWS session expired), real fills and latency. Infra cost estimate: about $0–0.30 a month (SQS polling inside the free tier).

## 2026-10-19 — RD information on the game's slope; Elo follow-up results

RD's information term now uses the game's update slope (.0065 in non-major domestic games), matching the update. Reproduces the research variant exactly; FORGE, Form and league-curve weights refit, `metric_backtest.md` regenerated (season stats unchanged). Paired vs main: other-league FORGE −0.0001 (−0.0002 to −0.0000); every other guarded row, including markets, within noise.

Also tested, not adopted (reports in `docs/research/`; scripts on their branches): Glicko-2 volatility (τ has no effect; reduces to the shipped RD, +46% replay), g(RD) in forecasts (≈1e-5), league-offset RD (cross-league −0.0002, other leagues +0.00002), no move-down bonus (cross-league +0.0052), no regional calibration (cross-league +0.0015).

Checks: DB rebuilt, pytest, ruff, `evaluate_metrics.py --write-weights`, `evaluate_markets.py --offline --dump`, `compare_benchmarks.py`.
