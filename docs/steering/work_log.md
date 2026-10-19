# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Call staleness measured

`scripts/research/call_staleness.py` on the published prediction log: of 74 settled calls frozen at the start (since Oct 4), 40 used data one day old and 34 two to four days old (Oracle's Elixir lag). Rebuilding 4,201 settled logged series with older ratings than the backtest's day-before: one more day +0.0039 series log loss (+0.0007 to +0.0074), two +0.0053, seven +0.0134; international (155) within noise. So the backtest and market report flatter published calls, and fresher results (Leaguepedia before Oracle's Elixir) are worth about .004 a day of lag. Same-day results are not measured. Research only; no published change.

## 2026-10-19 — Series-clustered forecast intervals, forward holdout, addition/removal rules

Forecast report/dumps and PR comparisons now resample whole series; dumps carry series/ISO dates, with head metadata supporting older bases. Forward rows from 2026-10-20 are unguarded. Rules require ≥0.0005 log-loss gain for additions and upper CI <+0.0005 for removals. Clustering barely widens intervals (~2 games a series; domestic FORGE vs Elo −0.0028 to −0.0009 both ways), so game-level intervals were not the problem. Report runtime: 37.80 s before, 28.33 s after (local, no CI work added). Checks: report, unchanged `--check-weights`, dump/self-comparison (exit 0), pytest (902 passed, 2 skipped), ruff format/check, diff whitespace. Limit: research scripts in `scripts/research` retain game-level intervals.

## 2026-10-19 — Elo/forecast review added to Future work

Docs only, base `1057307`. Reviewed every Elo and forecast assumption against the code, the research reports and the literature (Glicko, TrueSkill 2, Elo++, dynamic Bradley-Terry, forecast combination). Added one ordered Future work item to `current_state.md`: evaluation rules (series-clustered bootstrap, non-inferiority for removals, minimum gain, forward holdout), call staleness, one rating scale with league offsets fixed at the source, fast/slow Elo in place of Form, and a dynamic Bradley-Terry ceiling. Checks: `pytest tests/test_steering.py`.

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

## 2026-10-19 — Simplify the Elo engine

Removed inactive and rejected options, legacy constants and their tests; kept the log rookie discount, stored move-down bonus, RD and non-major slope. RD now takes (new, floor, growth); bootstrap accepts research overrides. Eight historical research scripts frozen at 00237c0. Added the existing win-share report and its not-adopted index entry. Checks: DB rebuilt; the three Elo tables match main row for row (max |Δ| 0.0); pytest 886 passed, 2 skipped; ruff clean.
