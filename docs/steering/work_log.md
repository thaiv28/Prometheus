# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-29 — Executor caches its Kalshi key for an hour

Branch `secret-cache`, base `main`. The 1-minute execution Lambda read its Kalshi key (and the fill-issue token) from Secrets Manager on every live invocation; each read is a KMS request, which reached 18,271 of KMS's 20,000 free monthly requests on 2026-10-29 (`aws freetier get-free-tier-usage`). `handler.cached_secret` keeps each secret for an hour in a warm container, keyed by secret ID because each invocation makes new boto3 clients (failures are never cached); the live-map handler uses it too. Expected: a few hundred KMS requests a month instead of ~43,000. A rotated key takes effect within an hour. Checks: pytest (execution tests and full suite), ruff. No schedule, IAM or config change; ships through the usual execution release.

## 2026-10-29 — Other games CI publishing

Branch `game-feed`, building on phase 1 HEAD. Added DB-free `games.yml` (model-job dispatch/hourly backup), nonfatal `game_feeds.sh` restore, `render_games.py`, shared navigation installation and `deploy_games.py`. Inputs: backup bucket `{cs2-model,valorant-model}/feed/{cs2,valorant}.json.gz`; outputs: site `current/other/`, hash manifest `deploy/other-manifest.json`, 60-second cache. Publish restores the same feeds. Real-feed render: cs2 + valorant, 22 HTML pages, 7.136 s (previously no standalone job); added CI cost keeps calls fresh without a full build. Checks: pytest (1,104 passed, 2 skipped), ruff format/check, bash syntax, diff check; seven new tests: 1.04 s including startup. Limits: not run on GitHub yet; depends on model repos' `feed.yml` and cron-job.org dispatch; S3 timing and deployment unverified offline. No UI/copy changes.

## 2026-10-29 — Generic game-feed predictions and results

Branch `game-feed`, base `main`. Added an Other games menu and pages `other/<game>.html` (with monthly results and a JSON download) rendered from `data/games/*.json` feeds (`PROMETHEUS_GAME_FEEDS` override), written by cs2-model and valorant-model `export`. `games/` already holds the game logs, so pages live under `other/`. The fixture register gains Tier/filter labels, unknown best-of and optional Blend; League pages render byte-identically. Invalid feeds warn and skip; no feeds means no menu. Feeds are local only. Cost: full build 78 s with both real feeds; game pages alone 5 ms per fixture feed. CS2 month pages run to 3.7 MB (all tiers). Checks: pytest (1,097 passed), ruff, `node --check`, JS tests, full build, desktop/phone screenshots. Copy review: PASS (game page, month page: lede, captions, notes, empty states; already minimal, nothing cut).

## 2026-10-28 — Raised trading limits from a 2027 sizing simulation

Branch `map-caps`, base `main`. A scratch Monte Carlo (46 weeks; pregame picks and live 30 s-stability bets bootstrapped by week) ranked 90 configs with fills 1¢ worse. Best downside/median: pregame full Kelly, 10% series cap, live maps full Kelly at 5% map/10% series, $250 order/$1k exposure/$2k day: median $13.3k from $50, 10th percentile $1.1k, 1% below seed; old config median $1.7k, 7% below seed. Applied in SSM (off → configure → live): $250 order/fixture, $1k exposure, $2k day. Live-map validator maxima raised to Kelly 1, 5% map, 10% series; values applied after deploy. Checks: pytest, ruff. Limits: edges selected on the same history; live edge priced from tapes; book depth for $250 orders unmodelled.

## 2026-10-28 — Kalshi markets listed a day off still match

Branch `kalshi-day`, base `main`. Kalshi listed T1 v MKOI (Worlds, 28 Oct 4 PM EDT) as 29 Oct, so the live worker's exact-date `contract()` and the static page's 18-hour `MATCH_WINDOW` both skipped it. `contract()` now falls back to a lone event a day either side when none is on the date; `attach_prices`/`backfill_prices` take a lone market within 18h + `DAY_SLIP` (1 day) when none is within 18h. Ambiguous fallbacks give nothing. Pregame and live trading use the same `contract()`. Checked: the fix matches the real open T1 v MKOI series and map 1–2 markets. Checks: pytest (1,089 passed, 2 skipped), ruff format/check. No forecast or benchmark input changed; no CI cost. Copy review: PASS (no copy changed).

## 2026-10-28 — Live table: start time for waiting matches

Branch `waiting-start`, base `main`. Predictions page Table I caption drops the match count and "updated N s ago"; it keeps "Matches in progress." plus the stalled/unreachable warnings. A row waiting for its first map shows the start time in Pacific time (`2:00 AM PDT`) under "Waiting". Checks: pytest (1,087 passed, 2 skipped), ruff check, `node --check`, JS tests. Not checked against a live feed. Copy review: PASS (Table I caption cut to its heading; warnings kept as material caveats).

## 2026-10-26 — Result rows link to series pages minutes after a map

Branch `result-links`, base `origin/main`. Worker uploads maps, results and final pages before dispatch; unsettled snapshots preserve settlement's debounce. Prices restores archives, overlays local links and stages live-results HTML with Predictions/Results; missing/broken archives retain fetched links. Figures embed SVG. Checks: pytest 1,065 passed, 2 skipped (10.14 s); ruff format/check and diff --check passed. Local filesystem-backed S3 shim: `live_archive.sh` 0.770 s new map, 0.093 s cached (one map, cached series record). Warm render medians, five runs: absent 0.0037 s, restored 0.0057 s (+0.0020 s). Added cost enables prompt links without full builds. AWS/API latency and Actions timing unmeasured. Copy review: PASS (no copy changed).

## 2026-10-26 — Shared capital, series cap, position-aware live maps, idle-only restarts

Removed the map budget; pregame and live maps share free capital. Optional global `series_fraction` caps combined held cost; live targets subtract same-team active filled contracts across strategies. Existing map-only caps and legacy budget releases remain. Refresh flags wait until no tracked game is live; worker exit 5 requests systemd restart. Root `deploy/live/install.sh` must run once for the unit change. Added [sizing evidence](../research/pregame_sizing.md) and its CSV-driven script. Checks: ruff format/check; full pytest (1,082 passed, 2 skipped); feed/steering checks (21 passed); research script --help; bash -n; diff --check. Regression checks add no CI job/build step; Actions timing unmeasured. Limit: the global series cap is not enforced atomically across concurrent pregame and map reservations. No SSM values changed; 10% awaits configuration.

## 2026-10-26 — Live model: fixed FORGE offset tested, rejected

Branch `live-offset`, base `1a74d73`. `scripts/research/live_offset.py` ([report](../research/live_offset.md)); viewed test split. D enters logit(FORGE) as an offset (calls start at the pre-map call), fits its fade, drops Elo and calibration: −0.0024 (−0.0062 to +0.0011), 0–20 min better, 30+ worse (+0.0072): FAIL. Diagnosis: production refit on D's maps loses the same at 30+; Elo, calibration and prior source don't matter, the 1,237 dropped maps without FORGE do. F (all maps, Elo prior where FORGE is missing): −0.0008 (−0.0035 to +0.0019), ECE 0.0194 → 0.0086, 30+ still worse (+0.0030, +0.0006 to +0.0054): FAIL; FORGE maps −0.0037 (significant). No runtime change. Checks: ruff, full pytest.

## 2026-10-26 — Live worker: feed back-off, game retries, start tolerance, CloudWatch logs

Audit (Oct 23–26): 13 tracked maps, 2,059 decisions; 1,153 pause-bug skips fixed earlier in #124. GEN v LYON began 20:59Z against Riot's 22:00Z start; ten matches went untracked; HLE v IG dropped on HTTP 404. Shared two-hour start tolerance preserves earlier-day ratings. HTTP 400 doubles per-game lag (30–600s); 30 successes halve it. Other window errors retry for 30 polls; failed IDs expire after 300s. Decisions carry match/game/map; worker events persist except cycles. Rerunnable install configures CloudWatch collection for both logs. Checks: ruff; pytest 1,060 passed, 2 skipped (10.01s; existing cases 11.80s); 13 recovery tests 0.30s; bash -n; diff --check. Actions timing unmeasured. Limit: Riot's longer delay on Oct 24 is inferred, not observed; agent and log groups need the infrastructure PR and an install.sh rerun.

## 2026-10-26 — Live maps: pregame positions, pause check, executor log

BLG v KC 18:20Z: KC (18¢ ask, 30.7% blended) skipped with `existing_fixture_exposure`; pregame KC held the same Bo1 tickers (PR #123 fixed only ledger fences). That exchange check is now pregame-only; positions still count toward exposure. The worker's `flat` compared the last two frames (0.17 s apart), rejecting 81% of BLG v KC polls as paused; it now needs ten seconds of unchanged gold after two minutes, as `feed_timelines.py` defines it for the benchmark. The live handler prints one JSON line per signal (outcome, reason) to CloudWatch. New end-to-end test (outbox → SQS pointer → handler → real Kalshi over faked HTTP → ledger with a pregame position) failed before the fix. Checks: ruff; pause and log tests; full pytest 1,044 passed, 2 skipped. Limit: one candidate per map; worker needs a restart.

## 2026-10-26 — Live maps no longer blocked by pregame fences

Both live candidates so far (DK v G2 10-23, DK at 25¢ vs 34% model; G2 v TES 10-25, TES at 42¢ vs 52%) were rejected: same-side pregame orders held their Bo1 event fences, and pregame held ($4.09, $2.48) exceeded the shared ~$0.93 2% series cap. It would also have blocked Bo3/Bo5 maps. Maps now use MAPEVENT#/MAPSERIES# (shadow sizing too); pregame unchanged apart from storing series_key; old intents release against SERIES#. Checks: ruff; tests for the Bo1 collision, map fence, MAPSERIES# cap and release, legacy release; full pytest (1,037 passed, 2 skipped). Limit: correlated exposure (the live prior reuses the pregame rating) is bounded only by map/series/budget caps; executor redeploys on merge.

## 2026-10-23 — Live feed polls on the window boundary; recorded-page guard

Feed windows start on 10 s boundaries 30 s back, so the newest frame's age is ~20.6 s plus the poll's offset into the cycle (BLG v MKOI: 20.6 s at +0 s rising to 29.8 s at +9 s; median 25.6 s). The worker now polls once per 10 s slot, 0.5 s after it opens (`feed_slot`), and wakes for it: ~5 s fresher on average, no extra requests (`--interval` must be 10, 20 or 30). After a restart the old code wrote BLG v MKOI's waiting page over its recorded map page (restored from `map1.json`); `without_recorded` now skips waiting pages for matches whose file holds frames. Checks: new timing and guard tests; cadence test on slot-aligned clock; full pytest; ruff. Limit: alignment unmeasured live.
