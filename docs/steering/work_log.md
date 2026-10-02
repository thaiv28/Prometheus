# Work log

Append one dated entry for each substantive agent work session, newest first. Record what changed, the checks actually run, and any remaining limit. Update the other steering docs named in `AGENTS.md` in the same change.

## 2026-10-01 — Season stats vs forecasts: GLORY absorbs GLORY+, Record, Luck, Form, new GlorELO+

- **Rule.** Season stats describe a team-season with hindsight and are judged by a new report; forecasts use only earlier games and are judged by the backtest; no forecast takes a season stat as input. Recorded in `current_state.md`, `tech.md`, `product.md`, `README.md`, `AGENTS.md`.
- **Season-stat report** (`scripts/evaluate_season_stats.py`, `docs/season_stats_report.md`; helpers `spearman_brown`, `games_for_reliability`, `correlation_interval` in `evaluation.py`). Random halves by game id. Full-season reliability / games to 0.5: win % 0.82 / 16, GLORY (Record-adjusted) 0.91 / 8, unadjusted GLORY 0.87 / 11, old GLORY+ 0.91 / 7, GLORB 0.86 / 12, Record 0.89 / 10, Luck 0.34 / 140.
- **Record and Luck** (`prometheus/season.py`). Record: per-season Bradley-Terry on game-length soft results over every league (ridge prior SD 1 log-odds), centred on the average major-league team, shown as % chance to beat it. Luck: win % minus earned win % from GLORY's per-game model. The first version (raw mean prediction) made strong teams look lucky (reliability 0.44, r with win % 0.59); a per-season, games-weighted calibration of earned on actual fixed most of it (0.34, 0.23). `elo.winner_score` was extracted from the Elo change so both use the same game-length curve.
- **GLORY absorbs GLORY+.** `get_glory_ranking(opponent_adjusted="record", record=...)` adjusts stats by each opponent's full-season Record (`adjust_for_opponent_record`) instead of pre-game Elo. Correlation with old GLORY+ 0.947, with Record 0.97. Unadjusted GLORY is a sunset page (`glory_unadjusted.html`); `glory_plus.html` redirects to GLORY (`redirect.html.j2`); the sunset page lists folded metrics with a link to their replacement.
- **Form** (`prometheus/form.py`): opponent-adjusted stats (pre-game Elo, coefficients from earlier seasons), exponentially weighted per team (half-life 20 games, carry 0.5 into a new season, prior 5 games of the season's running average), logistic weights on pre-game state gaps (`form_weights.json`), league-relative (minus the home league's season mean of pre-game scores). Home league = most-played domestic league this season (the last domestic league put most LPL teams in the Demacia Cup at year end and broke season joins).
- **Tuning (scratch harness, not committed).** On the backtest's games: raw stats Form alone was 0.6356 domestic / 0.6678 international; opponent adjustment brought it to 0.6324 / 0.6373. Grid (half-life 10/20/40 × carry 0.25/0.5/0.75 × prior 2/5/10): prior barely matters; 20/0.5/5 kept as a middle choice. Blends tried: 12 stat gaps + Elo (international 0.6331), one Form score + Elo (0.6323), cross-region interactions (0.6324), short + long memory Form (no gain), separate international fits (worse, too few games). Every Form-in-international variant lost to Elo alone (0.6297), so GlorELO+ uses Elo + league-relative Form within a league and Elo alone between leagues.
- **GlorELO+** (`glorelo.py`): rating = Elo + Form in Elo points (`form_weight / elo_weight`); same-league odds from the rating gap, cross-league from Elo on its own curve. `forecast.js` reads both weights from the page config and notes when it fell back to Elo. Backtest (`evaluate_metrics.py`, now forecasts only; Form weights fit out of year): domestic GlorELO+ 64.6%, log loss 0.6319 vs Elo live 0.6345 (−0.0026, −0.0037 to −0.0015); old GlorELO+ (GLORY+ + live Elo) was 0.6327 in the harness. International = Elo (0.6297; old blend 0.6290, difference not significant). Weights written with `--write-weights`; `--check-weights` now warns only on the three blend weights (Form stat weights near zero made relative changes noisy). The backtest dropped from about 22 to 8 seconds without per-cutoff GLORY fits.
- **Site.** Header and contents: Season stats (GLORY, Record, Luck), Forecasts (GlorELO+, Form, Elo), Sunset stats. New pages `record.html`, `luck.html` (fixed signed scale via config `domain`), `form.html` (every league, now and season-end rows), plus the sunset pages above. Record lists the same team-seasons as GLORY with GLORY's league (Record's own home league left out 29 promoted or academy team-seasons). Team pages: GLORY/Record figure switch; register GLORY, year rank, Record, Luck, season-end GlorELO+. Captions name each metric (`value_word`/`value_plural`). Build takes about 10 seconds (Form pass about 3).
- **CLI.** `prometheus rankings glory|record|luck|glorelo+|form|glorb`; `glory+` removed (it was added earlier today and is now part of GLORY).
- Verification: `uv run pytest -q` passed 61 (new `test_season.py`, `test_form.py`, rewritten `test_glorelo.py`, record-adjustment and reliability tests), including e2e on the real DB. Ran `evaluate_metrics.py --write-weights --out docs/metric_backtest.md`, `--check-weights` (no warning), and `evaluate_season_stats.py --out docs/season_stats_report.md`. CLI smoke runs for every metric (with year ranges, league filters). Clean `output/teams` rebuild; headless Chromium at 1440px and 390px, no page errors: every rankings page, sunset, home, T1's team page (register fits at 390px), head to head Gen.G v T1 (68 in 100, same league) and Gen.G v Bilibili (61 in 100, Elo note shown), Form 2019 LPL (18 teams, FPX first), `glory_plus.html` redirect. Impeccable detector: advisories only.
- Limit: Form's hyperparameters were chosen on the backtest that reports them; series odds are not built yet; the header no longer fits on one line, so the search sits on its own row on desktop; see Known limits in `current_state.md`.

## 2026-10-01 — Plan: split season stats from forecasts

- Recorded the plan in `current_state.md` Future work ("Season stats vs forecasts"): the rule separating the two families, a season-stat report, Predictive GLORY (Form) feeding the headline forecast, GLORY absorbing GLORY+, new Record and Luck stats, and the site changes. It replaces the separate Predictive GLORY and Stability items.
- Verification: documentation only.

## 2026-10-01 — Sunset GLORB, forecasts on team pages, team search, CLI, backtest cutoff Elo

- **Sunset GLORB.** `METRICS` entries with a `sunset` note leave the header and home contents. The header ends with one "Sunset stats" link to a new `sunset.html`, which lists retired metrics with their pages and a short `sunset_why`; the link is marked current there and on `glorb.html`. GLORB's page keeps its numbers and prints a "Sunset." note under its lede. The 404 page iterated `nav` as a flat list after `nav` became groups (broken links); it now lists every metric plus Sunset stats.
- **Team pages.** GLORY+ replaces GLORB in the season figure switch. The season register adds GLORY+ and season-end GlorELO+ columns (the GlorELO+ page's season rows); the fact line adds the current GlorELO+. Under 480px the league and GLORY+ columns drop so the register fits. Negative scores print with a true minus. New `glorelo.glorelo_season_ratings`, shared by the site and CLI; the build ranks GLORY+ with `minimum_matches=1` for team pages instead of GLORB.
- **Stale CSS (reported as "numbers above the bars are messed up").** I could not reproduce it with the current files in Chromium or WebKit (scanned all 172 team charts at 1440/1100/390px in both metrics). Rendering new team HTML with the previous `register.css` reproduces it: both the GLORY and GLORY+ labels print over each bar, because the old CSS only hides `.season-val--glorb`. Fix: templates link CSS and JS through `asset()`, which adds a content-hash `?v=`, so a changed file always has a new URL (browser caches as well as CloudFront).
- **Search.** Rankings pages have a team-name search box in the filter line (`#filter-search`, still `?search=` in the URL, so team-page links into filtered registers keep working). The header search is now "Team · Go to a team": `search.js` fetches `teams.json` (all 2,087 teams; name, slug, league, last game; major-league teams first, then newest; 148KB, about 30KB gzipped) on first focus and suggests up to eight matches (exact, prefix, word start, anywhere). Arrow keys and Enter or a click open the team page. With no match, or without JS, the form submits to the Elo register search as before. The label is "Team" so the head stays on one line down to 1280px.
- **CLI.** `prometheus rankings glory+` and `glorelo+` (this season by default; past seasons at year-end Elo with `--year`), and year ranges (`--year 2021-2023`) through `utils.parse_years`.
- **Backtest.** "Elo (as of cutoff)" now adds league-offset moves since each team's last game (`evaluation.elo_as_of`), matching the published rating. Domestic log loss 0.6410 → 0.6409, international 0.6405 → 0.6402; GlorELO+ vs Elo deltas moved by ≤0.0002. Weights are fit on live Elo, so `--write-weights` left `glorelo_weights.json` unchanged.
- **Distribution figure.** The traced name and value were drawn at the base of the plot, under neighbouring columns. They now sit in the band above the tallest column with a paper knockout stroke; the median label hides while it would overlap.
- Verification: `uv run pytest -q` passed 50 (new tests for `elo_as_of` and `parse_years`). `evaluate_metrics.py --write-weights --out docs/metric_backtest.md` ran. CLI smoke-run for `glory+ --year 2024`, `glorelo+`, `glorelo+ --year 2019-2020 --league LCK`, `glory --year 2023-2024` and a bad year. Clean rebuild of `output/teams` then `build_site.py`. Headless Chromium at 1440px and 390px, no page errors: traced labels (GLORY+, Elo), GLORB page and its note, `sunset.html`, home, T1's team page in both switch states, phone team register without horizontal scroll, header one line at 1280–1600px; filter search (9 rows for "gen.g", URL updated, `?search=T1` prefilled), header suggestions for "gen" from a nested team page, ArrowDown+Enter opened Gen.G Scholars, "zzzz" showed the empty line and Enter went to `game_length_elo.html?search=zzzz`; `404.html` links. WebKit render of T1's chart. Impeccable detector: advisories only (one new: the suggestion list's 1rem, matching the header input).
- Limit: the CLI command, `search.js` and `build_site.py` have no automated tests; a team's current GlorELO+ and its this-season row can differ by a point when league offsets moved after its last game; `teams.json` is fetched on first focus, so the first suggestions wait for it on a slow connection.

## 2026-10-01 — Forecast pages open on now; seasons show year-end ratings

- Elo and GlorELO+ pages open on current ratings: Elo for teams that played in the last 183 days (`ACTIVE_WINDOW`), GlorELO+ for this season. Before, the Elo page listed every team ever at its last rating, so SK Telecom T1 (last active 2019) topped it.
- The year picker is now "season": picking seasons switches to one row per team-season, rated at the end of that calendar year (new `elo.get_season_elos`, one query plus pandas, about 1.3s). GlorELO+ gets past seasons too (that season's GLORY+ with year-end Elo). Head to head stays on today's ratings. Search on the Elo page still reaches every team's current rating, including retired teams, since the header search lands there.
- UI: picker empty value *Now*, a "Current ratings" text button in its panel, a Season column and caption wording for season views; Elo and GlorELO+ margin notes rewritten (including the league-offset Elo note). DESIGN.md filter-line spec, tech.md and current_state.md updated.
- Verification: `uv run pytest -q` passed, including a new integration test for season-end ratings with offset changes. Built the site and checked Elo (now, 2019, picker open) and GlorELO+ (now, 2019+2024) at 1440px and 390px in headless Chromium: no page errors, captions and counts correct, 2019 led by FunPlus Phoenix; searches for retired teams return them.
- Limit: GlorELO+ season ratings are centred per season, so cross-season comparisons are relative to each season's average.

## 2026-10-01 — Elo league offsets (international games move the whole region)

- `compute_elo_records`: rating = own rating + home league offset. A cross-league international game also moves each league's offset by `LEAGUE_SHARE` (0.5) of the team's change. New teams start at 1500 + their league's offset. `get_latest_elos` adds offset changes since a team's last game. Schema: `home_league` and `league_offset` columns on `game_length_elo`, plus a new `game_length_elo_league_offsets` table.
- Tuned with a scratch harness that replays Elo on the backtest's games (not committed). Kept: league share 0.5 (league_k 10 at K=20). Rejected: changing K (25–30 helps domestic by about 0.0005 but hurts international), a between-season pull to the league mean (hurts international by 0.002–0.01), an international K multiplier, and a "most common of the last 20 games" home-league rule (no measurable difference).
- Backtest: international Elo log loss 0.6540 → 0.6405 as of cutoff, 0.6456 → 0.6297 live (accuracy 60.6% → 65.0%); domestic 0.6414 → 0.6410 and 0.6349 → 0.6345. GlorELO+ weights refreshed with `--write-weights` (0.00983 / 0.00634).
- Verification: rebuilt the DB; `evaluate_metrics.py --write-weights --out docs/metric_backtest.md`; `build_site.py` ran. New unit and integration tests for offsets, new-team starts and latest-rating refresh pass. `pytest -q` passed 43 after the rebuild. Docs (current_state, tech, product, README) updated in a follow-up commit; the site was checked in the forecast-page entry above.
- Limit: the backtest's "as of cutoff" Elo uses each team's post-game rating without later offset changes; team-page Elo history is also per game.

## 2026-10-01 — GlorELO+ weights in a tracked file, checked in CI

- The weights moved from constants in `prometheus/glorelo.py` to `prometheus/glorelo_weights.json` (package data in `pyproject.toml`). `glorelo.py` loads them and adds `load_weights`, `save_weights` and `weight_changes`.
- `evaluate_metrics.py --write-weights` saves the refit weights; `--check-weights` refits without scoring the report and prints a `::warning::` annotation when a weight moves more than 10% (`WEIGHT_TOLERANCE`). Both refuse `--years`, since the weights are fit on every season. `publish.yml` runs the check after the tests.
- The backtest now takes about 22 seconds instead of about 90, a side effect of the Elo table key from the previous entry.
- Verification: `uv run pytest -q` passed (new round-trip and loading tests); `--check-weights` on the real DB reported +0.0% and +0.1%; a forced 23% move printed the warning; `--write-weights --out docs/metric_backtest.md` left both the weights file and the report unchanged.
- Limit: CI warns but does not commit refreshed weights; the warning has not yet been seen in a real Actions run.

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
