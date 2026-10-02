# Work log

Append one dated entry for each substantive agent work session, newest first. Record what changed, the checks actually run, and any remaining limit. Update the other steering docs named in `AGENTS.md` in the same change.

## 2026-10-01 — Faster site builds (17s → 5s)

- Profiled the build: model fitting took about 0.03s; the time went to SQLite reads. `game_length_elo` had no key, so each of GLORY+'s 13 pre-game Elo joins built a temporary index (about 0.5s each), and the five ranking calls read every year's games twice per call.
- `game_length_elo` now has `PRIMARY KEY(gameid, teamid)` (`001_create_tables.sql`). `get_glory_ranking` reads each year's major-league games once and uses them for both the fit and the averages; new `load_glory_games()` and a `games=` argument let `build_site.py` share one read across its five calls. `regression.fit_glory_pipeline()` fits on a frame already in memory.
- Verification: rebuilt the DB with `setup_db.sh`; `build_site.py` went from 17.2s to 5.2s, and all 2,094 generated HTML files are byte-identical to the build before the change. `uv run pytest -q` passed, including a new test that shared and fresh reads give the same ranking.
- Limit: the backtest still reads per cutoff; it gets the one-read-per-year saving but no cross-call sharing.

## 2026-10-01 — Future work: betting-odds benchmark

- Added a "Betting-odds benchmark" item to the Future work section of `current_state.md`: score de-vigged closing odds in the backtest as the ceiling to compare the forecast models against.
- Verification: documentation only; no code changed.

## 2026-10-01 — Steering docs: work log, current state, future work

- Adopted the steering setup from the `jobflow` repo: `AGENTS.md` now lists the steering docs to read before work and the docs each kind of change must update. Added `current_state.md` (working features, known limits, future work) and this work log, backfilled with today's sessions. A guard test (`tests/test_steering.py`) fails when code changed without a work-log change.
- Recorded "Sunset GLORB" as future work rather than building it now, alongside the other suggested next steps.
- Updated `product.md` (metrics table, open questions) and `tech.md` (pipeline, algorithms, testing), which predated GLORY+, GlorELO+ and the backtest.
- Verification: `uv run pytest -q` passed (including the new guard); `git diff --check` clean; referenced paths checked.

## 2026-10-01 — GlorELO+ page and the season stats / forecasts split (PR #8)

- Renamed GlorELO to GlorELO+. New `prometheus/glorelo.py` turns this season's GLORY+ and each team's latest Elo into an Elo-scale rating (average major-league team = 1500) using weights from the backtest. New `glorelo_plus.html` with a head-to-head box (`site_static/js/forecast.js`).
- Header and home contents group Season stats (GLORY, GLORB, GLORY+) apart from Forecasts (GlorELO+, Elo). Rankings pages switch on a config `kind` instead of checking for Elo.
- Impeccable polish at 1440px and true 390px frames: fixed the phone nav divider, sized team selects to their content, moved the head-to-head type onto the DESIGN.md ramp, removed an animation DESIGN.md does not allow. DESIGN.md, PRODUCT.md and the surface brief updated.
- Verification: `pytest -q` passed 35; site built; detector advisories only. Limit: the margin note claims calibration, not a higher hit rate, because the accuracy edge over Elo is not significant.

## 2026-10-01 — GlorELO blend in the backtest (PR #7)

- Win curves accept several rating gaps, so a blend is a metric with two inputs. Scored GLORY+ + Elo, a games-played variant, and a live-Elo version, plus direct blend-vs-Elo comparisons.
- Results: beats Elo on domestic log loss (−0.0038, CI excludes 0); ties Elo internationally; the games-played variant adds nothing. GLORY+ and Elo gaps correlate at 0.83.
- Month-cluster bootstrap (run ad hoc, not yet in the report): GlorELO+'s domestic accuracy edge over Elo is +0.35 points (−0.08 to +0.80), not significant. GLORY+ beats GLORY internationally by +3.0 points (+0.6 to +5.5).
- Verification: `pytest -q` passed 32; full backtest run.

## 2026-10-01 — Metric backtest (PR #6)

- `scripts/evaluate_metrics.py` and `prometheus/evaluation.py`: rolling monthly backtest with a `before` cutoff added to `get_glory_ranking`; out-of-year logistic win curves; accuracy, Brier, log loss; paired bootstrap against win % so far. Domestic and cross-region international test sets.
- Results: GLORY barely beats win %, GLORB does not; GLORY+ is clearly better than GLORY internationally; Elo is best overall.
- Verification: `pytest -q` passed 30; full run takes about 90 seconds.

## 2026-10-01 — GLORY+ and international games (PRs #4, #5; deployed)

- PR #4: GLORY rankings use every year in the DB instead of a hardcoded 2014–2025 list, so 2026 reaches the site.
- PR #5: ingest kept no international games because `split` is empty for them and `dropna` removed them; Elo had no cross-region games. Fixed, plus the `WLDs` → `Worlds` mapping and home-league labels on the Elo page. Added GLORY+ (opponent-adjusted GLORY) and its rankings page.
- Verification: `pytest -q` passed; CI build passed; deployed and `glory_plus.html` returns 200 on prometheus.thaiv.dev with 2026 rows.
