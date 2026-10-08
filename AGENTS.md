# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo.

## Read before work

1. [Product](docs/steering/product.md) for the vision, audience, metric status and open questions.
2. [Current state](docs/steering/current_state.md) for what works, known limits, and **future work**.
3. [Tech](docs/steering/tech.md) before changing the data pipeline, tables, metric algorithms or tests.
4. [Deployment](docs/steering/deployment.md) before changing CI, publishing, data backup or AWS settings.
5. [UI](docs/steering/ui.md), `DESIGN.md` and `PRODUCT.md` before changing templates, CSS or JS. Use the impeccable skill for UI work.
6. [Work log](docs/steering/work_log.md): the newest entries, to avoid repeating work, and record what you change there (older entries in [the archive](docs/steering/work_log_archive.md); search it when a topic may have been tried before).

Research that changed no published metric (in-game models, champions, gol.gg objectives, the broadcast pilot) is in [`docs/research/README.md`](docs/research/README.md). Read it only for that work.

Code and the built DB are the source of truth. If a document disagrees with them, verify the behavior and correct the document in the same change. The user's latest instructions override these docs.

## Required document updates

- **Every substantive code or behavior change:** add a dated entry at the top of `docs/steering/work_log.md` with what changed, the checks actually run, and any remaining limit.
- **Feature status, known limit, or future work changes:** update `docs/steering/current_state.md` in the same change. Suggestions for future work go in its **Future work** section, not only in chat. Remove items once they ship.
- **Metric added, changed, or its status changed:** update the metrics table in `docs/steering/product.md`, the metric descriptions in `README.md`, and rerun `scripts/evaluate_metrics.py` (forecasts) and `scripts/evaluate_season_stats.py` (season stats).
- **Data pipeline, tables, algorithms, or test layout change:** update `docs/steering/tech.md`.
- **CI, publishing, schedules, secrets, or AWS resources change:** update `docs/steering/deployment.md`.
- **Visual design or UI components change:** update `DESIGN.md` (and `docs/steering/ui.md` if the direction changes).
- For documentation-only work, still add a short work-log entry and check the links and commands you touched. Do not add empty entries or claim a check you did not run.

`uv run pytest -q` includes `tests/test_steering.py`, which fails when code changed (uncommitted) without a `work_log.md` change. It can't judge whether the other docs are accurate, so do that review yourself.

## What this is

Prometheus is a "sabermetrics for League of Legends esports" project. It ingests Oracle's Elixir match CSVs into SQLite, computes team metrics (GLORY, GLORB, game-length Elo), and publishes them two ways:

1. **CLI** (`prometheus rankings glory ...`), built with Typer and Rich.
2. **Static website**: Jinja2 templates rendered by `scripts/build_site.py` into `output/`, published to https://prometheus.thaiv.dev (S3 + CloudFront) by `.github/workflows/publish.yml`. See `docs/steering/deployment.md`.

## Quick commands

```bash
uv sync                                # install (Python >= 3.12, managed by uv)
uv run bash scripts/setup_db.sh         # download raw CSVs (gdown), rebuild db/prometheus.db from scratch
uv run python scripts/build_site.py     # render static site to output/
uv run pytest -q                        # run tests (unit + integration + e2e; e2e builds a small DB from a committed sample)
uv run ruff format && uv run ruff check # format and lint (CI checks both)
uv run prometheus rankings glory --league MAJOR --year 2024
uv run prometheus predict --days 2 --major   # odds for upcoming matches (Leaguepedia schedule)
PREDICTIONS_FETCH=0 uv run python scripts/build_site.py   # build without fetching the schedule (uses the saved log)
uv run python scripts/evaluate_metrics.py --out docs/metric_backtest.md   # backtest forecasts (~8s)
uv run python scripts/evaluate_metrics.py --write-weights   # also refresh Form and FORGE weights
uv run python scripts/evaluate_season_stats.py --out docs/season_stats_report.md   # season-stat stability (~5s)
uv run python scripts/evaluate_aura.py --out docs/aura_report.md   # AURA calibration and player tests (~40s)
uv run python scripts/evaluate_markets.py --out docs/market_report.md   # our calls vs Kalshi's prices (~2.5 min; first run ~1 h fetching; --reuse rewrites the report in seconds)
python -m http.server -d output 8000    # preview the built site locally
```

`data/`, `db/`, and `output/` are gitignored build artifacts. Never commit them.

### Worktrees

Agents work in a separate worktree (see the global `AGENTS.md`). A new one has none of the gitignored state, so set it up from the main checkout (`MAIN`):

```bash
git worktree add ../Prometheus-<branch> -b <branch> <base> && cd ../Prometheus-<branch>
uv sync
mkdir -p data && ln -s "$MAIN/data/raw" data/raw    # raw CSVs: read-only, safe to share
cp "$MAIN/.env" .                                    # Leaguepedia bot login
cp "$MAIN/data/predictions.json" "$MAIN/data/market_prices.json" data/   # prediction log and Kalshi prices, for site builds
cp -R "$MAIN/data/markets" data/                     # Kalshi cache, only for evaluate_markets.py (rewrites frames.pkl)
uv run bash scripts/setup_db.sh                      # own db/ (~1 min); never symlink db/, setup_db.sh deletes it
```

Use a port other than 8000 for `http.server` if another worktree is serving.

## Layout

| Path | Purpose |
|---|---|
| `prometheus/` | Python package: metric computation and data access |
| `prometheus/types.py` | Enums (`Metric`, `League`, `ScoreCols`) and feature lists (`GLORY_FEATURES`, etc.). This is the single source of truth for column names. |
| `prometheus/matches.py` | Raw-SQL reads that join a stats table/view with `matches` |
| `prometheus/regression.py` | Fits the GLORY model (StandardScaler + LinearRegression, target = win) |
| `prometheus/ranking.py` | `get_glory_ranking()` fits a model per year, scores team-season averages, and adds z-scores. `opponent_adjusted="record"` is the published GLORY (stats adjusted by each opponent's season Record); `"elo"` is the retired GLORY+ |
| `prometheus/season.py` | Season stats built on results: Record (Bradley-Terry on game-length-weighted results, every league) and Luck (wins above earned) |
| `prometheus/form.py` | Form (Predictive GLORY): opponent-adjusted, recency-weighted per-team stat states before every game, league-relative scores; weights in `form_weights.json` |
| `prometheus/forge.py` | FORGE: Elo + Form within a league, Elo alone between leagues; ratings and head-to-head win probability; weights in `forge_weights.json` |
| `prometheus/elo.py` | Game-length-weighted Elo: bootstrap and query helpers (team and player Elo, used by FORGE, Form, rankings, predictions and the site) |
| `prometheus/schedule.py`, `team_aliases.json` | Predictions: the match schedule from Leaguepedia's Cargo API, team-name matching, game and series odds (FORGE / Elo), the prediction log (`data/predictions.json`, kept in S3 by CI) and its scorecard |
| `prometheus/aura.py`, `scripts/evaluate_aura.py` | AURA, the player season stat: each player's share of a 15-minute win-probability model by lane plus a quarter of their team-centred gain to 25 minutes; `season_aura` gives the site's player-seasons; report in `docs/aura_report.md` |
| `prometheus/gamelog.py`, `scripts/export_market_prices.py` | Game logs on team and player pages: series grouped from games, each game's pre-game call (FORGE or Elo), Kalshi's price per series (`data/market_prices.json`, exported from the market benchmark, plus the prediction log), compact JSON written by `site.gamelogs.add_game_logs` |
| `prometheus/main.py` | Typer CLI entry point (`prometheus` script) |
| `scripts/NNN_*.sql\|py` | DB build steps. `setup_db.sh` runs them **in numeric order**. |
| `scripts/download_data.py` | Oracle's Elixir CSVs from Google Drive, one file at a time: the current year's when `data/raw` has the rest, every year's with `--full` (`setup_db.sh`, `REFRESH_DATA=1`/`full`); a file is replaced only by one with newer games |
| `scripts/prediction_log.sh` | CI's restore and save of the prediction log in the backup bucket: restore fails on any S3 error but a missing file; save refuses a shrinking log, and with `--if-unchanged` (hourly prices job) skips when the backup changed since the restore |
| `scripts/build_site.py`, `prometheus/site/` | Static site generator: the script loads the data once and runs the parts in order (`main`); `site/config.py` holds the metric registries, column configs, paths and limits, `render.py` the Jinja environment and small pages, `registers.py` register rows and the home and rankings pages, then `teams.py`, `players.py`, `predictions.py` (the page, the log update, the Kalshi alert) and `gamelogs.py`. Tests patch paths on `prometheus.site.config` (`OUTPUT_DIR`, `PREDICTIONS_LOG`, ...), which the modules read at call time |
| `prometheus/player_tables.py` | `PlayerTables`: the player tables, each read once and joined in pandas, shared by `aura.load_aura_games`, `elo.get_player_history` and `gamelog.load_player_games` in the build |
| `scripts/deploy_site.py` | The publish workflow's upload: only files whose content hash changed go into the bucket's `current/` (manifest at `deploy/manifest.json`); see `docs/steering/deployment.md` |
| `scripts/evaluate_metrics.py`, `prometheus/evaluation.py` | Forecast backtest: how well each forecast, from earlier games only, predicts winners (domestic, cross-region, cross-league in every league, and within other leagues); fits the forecast weights. Results in `docs/metric_backtest.md` |
| `prometheus/markets.py`, `prometheus/alerts.py` | Kalshi's prediction market: parsing, quotes, name aliases and the prices stored on upcoming logged matches; the daily alert (FORGE beating Kalshi's ask by 5+ points, 6–36 hours out), recorded in the log and posted as a `kalshi-alert` GitHub issue by CI |
| `scripts/update_prices.py`, `scripts/post_kalshi_alert.sh` | The hourly job (`.github/workflows/prices.yml`): refresh Kalshi's prices in the prediction log without a rebuild, write `kalshi.json` / `predictions.json` for the live site, and post the day's alert issue (the shell script, shared with the publish workflow) |
| `scripts/research/`, `docs/research/` | Finished research that changed no published metric (in-game snapshots, champions and matchups, snapshot and visible-input Elo, gol.gg objectives, Elo margins, league moves), kept with its tests and reports |
| `scripts/oneoff/extend_log.py` | One-off: extend the prediction log back (`--since`) with calls rebuilt from the ratings the day before each match, as a new log's 30-day rebuild does |
| `scripts/oneoff/backfill_market_prices.py` | One-off: give logged matches that started before prices were read Kalshi's last pre-start price from its price history (`markets.backfill_prices`, marked `backfilled`) |
| `scripts/research/elo_variants.py`, `scripts/research/elo_variants_*.py` | Elo margin-of-victory experiments: replay player-built Elo with any margin function and score it like the forecast backtest (tune on ≤2021, report 2022 on). Results in `docs/research/elo_variants_*.md` (gold, kills, objectives, combined; none beat game length) |
| `scripts/evaluate_markets.py` | Market benchmark: our match calls against Kalshi's pre-match prices on the same series and map-1 games, and whether our call adds to the market. Results in `docs/market_report.md` |
| `scripts/compare_benchmarks.py`, `scripts/benchmark_comment.sh` | The PR benchmark check (`.github/workflows/benchmarks.yml`): compare base and head `--dump` output of the four benchmark scripts (forecasts, season stats, AURA, markets) with paired bootstraps, exit 1 when a guarded value is significantly worse; keep its one sticky PR comment |
| `scripts/evaluate_season_stats.py` | Season-stat report: split-half reliability, games to 0.5, and fit to same-season results. Results in `docs/season_stats_report.md` |
| `templates/*.html.j2` | Jinja2 templates: `base` (shell, with the Teams and Players menus), `index`, `rankings` (every metric page, driven by a column config), `predictions`, `team`, `player`, `sunset`, `redirect`, `404`, the `_marks` macros (league mark, signed number, ordinal, the fixture register), and the `_entry` macros (team and player pages' "On this page" list and game log) |
| `site_static/{css,js,fonts}` | Hand-written CSS (`tokens.css` holds all colors and the `@font-face` rules, including league inks), vanilla JS (`names.js` for name folding, slugs and search ranking shared by the others and unit-tested under Node, `rankings.js` for filtering, sorting and the distribution figure, `team.js` for the SVG Elo chart on team and player pages, `entry.js` for their game log and current-section marking (with `entry.css`), `forecast.js` for the FORGE head-to-head box, `search.js` for the header team and player search, `nav.js` for the header's Teams and Players menus, `predictions.js` for local times and filters on the fixture registers), and the self-hosted Source Serif 4 font (OFL), all copied verbatim into `output/` |
| `PRODUCT.md`, `.impeccable/surfaces/` | Product record and visual direction contract used by the impeccable design skill. Read them before UI work. |
| `tests/` | `test_*.py` unit tests (mocked; `test_build_site.py` for the site builder), `integration/` (in-memory SQLite), `e2e/` (marked `e2e`; a DB built at test time from `tests/fixtures/oe_sample/`, or the full DB with `PROMETHEUS_E2E_DB=real`), `js/` (Node tests for `names.js`, run by `test_js.py`) |

## Conventions

- **Data access is raw SQL through `pd.read_sql(stmt, utils.get_engine())`.** The project recently moved away from the SQLAlchemy ORM (`d3b361a`). Don't reintroduce ORM queries.
- **Schema changes go in a new numbered script** (`scripts/005_*.sql`), or in `001_create_tables.sql` if the change belongs to the base schema. The DB is always rebuilt from scratch, so there are no migrations.
- **Feature and column names live in `types.py`.** If you add a metric feature, add it there and to the SQL view that produces it (for example `003_create_glory.sql`).
- **Retiring a metric:** give its `METRICS` or `FORECASTS` entry a `sunset` note (shown on its page) and a short `sunset_why` (shown on `sunset.html`). It leaves the header menus and home contents; the "Sunset stats" link at the end of the Teams menu leads to the list. The page and data stay.
- **Static assets:** reference CSS and JS through `asset('css/…')` in templates, which adds a content-hash query so browsers pick up changes.
- **New metrics on the site** are registered in the `METRICS` (team season stats), `FORECASTS` / `ELO_METRICS` (team forecasts) or `PLAYER_METRICS` (player stats) dicts in `prometheus/site/config.py` (including the explainer copy) and given a column config (`METRIC_COLUMNS` / `FORGE_COLUMNS` / `ELO_COLUMNS` / `PLAYER_ELO_COLUMNS`) with `kind` set to `"season"` (0–100) or `"rating"` (Elo scale), and `entity` `"player"` for player registers (default team). Each needs a `question` (the one question it answers, shown under its name in the header menu and home contents). `SECTIONS` lists them under **Teams** or **Players**, the two header menus and the two parts of the home contents. A metric's `title` ("Team Elo", "Player Elo") is its page name when the short header `name` is shared. `rankings.html.j2` and `rankings.js` render any metric from that config.
- **Season stats vs forecasts.** Season stats (GLORY; sunset Record and Luck) may use the whole season; forecasts (FORGE, Elo; sunset Form) use only earlier games and must not take a season stat as input. Judge season stats with `evaluate_season_stats.py` and forecasts with `evaluate_metrics.py`.
- **Change a metric only for a significant benchmark gain.** A change to how a published metric is computed (features, weights scheme, hyperparameters, method) ships only when its benchmark beats the current version on the same games or team-seasons by more than noise: for forecasts, the paired-bootstrap 95% interval of the domestic log-loss difference (`evaluate_metrics.py`) must exclude 0 and international log loss must not get significantly worse; for season stats, a paired bootstrap over team-seasons of split-half reliability or r with the other half's win % (`evaluate_season_stats.py`) must exclude 0, with neither getting significantly worse. A gain inside the noise is not a reason to change. Record each tested change and its numbers in the work log either way. Refitting the existing weights on new data (`--write-weights`) is not a metric change.
- **Accuracy fixes follow a lighter rule.** A change that corrects which data a forecast uses, without changing how the metric is computed (a team's home league, which roster stands for a team, a mislabelled league or event), is an accuracy fix, not a metric change. It ships when it is significantly better on the games it affects, by a paired bootstrap on the benchmark that covers them (`evaluate_metrics.py`'s cross-league section, or our calls in `evaluate_markets.py`), and neither domestic nor international log loss gets significantly worse.
- **AURA follows the same rule on player benchmarks** (`evaluate_aura.py`). A change to how AURA is computed (snapshot, features, weights, credit scheme, matchup adjustment) is compared with the current AURA on the same player-seasons and team-seasons, with weights fit on earlier years only and any tuning constant fixed in advance. It ships only when all of these hold: (1) a gain: the paired-bootstrap 95% interval excludes 0 for next-season r of players who changed team, or for split-half reliability, but a split-half gain counts only if the correlation of a player's score with their teammates' in the same game rises by no more than 0.05 (a score that moves with the team becomes stable by restating it); (2) it beats its team-only control (the added part replaced, for every player, by their team's average of it in that game) on the gain it claims, by a paired bootstrap, so the gain is the player's and not the team's; (3) neither split-half nor new-team r gets significantly worse, and the roster test (r with the other half's win %, paired over team-seasons) doesn't either; (4) calibration stays close (ECE under 0.01) for a model that uses only in-game snapshots. A model with end-of-game stats as features is not judged on calibration, because those stats build up for the winner. The substitution test is reported but doesn't decide on its own: teams choose their substitutes, so it is confounded and noisy. Once AURA feeds a forecast (Player Elo, FORGE), that change falls under the forecast rule above, with the backtest's roster-change slice reported.
- **CI enforces the "not significantly worse" half of these rules:** on every PR, `.github/workflows/benchmarks.yml` runs the forecast, season-stat, AURA and market benchmarks with `--dump` on the base and the head and `scripts/compare_benchmarks.py` fails the check when a guarded value is significantly worse; the `benchmark-override` label is the escape hatch for an intended change (say why in the work log).
- **Forecast weights** live in `prometheus/form_weights.json`, `forge_weights.json` and `league_curves.json` (Elo's win-curve slope per non-major league) (package data), read by `form.py` and `forge.py`. After a metric or data change, rerun `evaluate_metrics.py --write-weights` and commit both. CI runs `--check-weights` and warns when a blend weight moves more than 10%.
- `gamelength` is stored in **seconds**.
- League names are normalized at ingest (`002_add_matches.py`): NA LCS / LTA N → `LCS`, EU LCS → `LEC`.
- Formatting and linting: `ruff` (`ruff format`; `ruff check` with pyflakes, import sorting and syntax errors), configured in `pyproject.toml` and run by CI's `check` job before the data download. It is in the `dev` dependency group with `pytest` (`uv sync` installs it; the hourly prices job uses `--no-dev`).
- Frontend: no build step and no framework. Design tokens are in `site_static/css/tokens.css`, and league color comes only from `[data-league]`. Charts are hand-drawn SVG; there are no third-party scripts. JS that writes HTML must escape values with `esc()` in `rankings.js`.
- Visual direction is "The Almanac": the site is set like a printed sabermetrics annual, with booktabs registers, margin notes and small printed figures on paper. See `DESIGN.md`, `.impeccable/surfaces/` and `docs/steering/ui.md` before changing the look.

## Gotchas

- `get_glory_ranking()` reads and fits one model **per year** on every call. Reading the games is the slow part, so `build_site.py` loads them once with `load_glory_games()` and passes `games=` to its calls (GLORY qualified/all, unadjusted GLORY, GLORB, Luck), and fits Record once and passes it as `record=`. The player tables are read once too (`PlayerTables`, passed to player Elo history, AURA and the game logs). A build takes about 50 seconds on an idle laptop: about 3 for the Form pass over every team-game, about 8 to read the player tables, a few for AURA's snapshot fits, about 15 for the game logs, and most of the rest writing about 7,000 pages and their game-log files. Rendering them in forked worker processes was tried and was slower (forking a process holding several GB of frames).
- International events (Worlds, MSI, ...) are ingested as their own leagues (`INTERNATIONAL_LEAGUES` in `types.py`). They are the only games linking regional Elo pools. A new cross-region event (an invitational, a new international cup) must be added there, or it becomes its teams' home league: their FORGE calls turn into Elo calls and leave the FORGE page and the Kalshi alerts (this happened with `DCGI` and `WSCI` until 2026-10-06). Oracle's Elixir leaves `split` empty for them, so don't reintroduce a blanket `dropna` over `split` in `002_add_matches.py`.
- `setup_db.sh` **deletes** `db/prometheus.db` before rebuilding.
- `scripts/004_bootstrap_elo.py` clears and refills `game_length_elo`, so it's safe to rerun.
- Leaguepedia rate-limits anonymous API calls after a few in a row and stays shut for minutes. Put a bot password in a gitignored `.env` (`LEAGUEPEDIA_USER=Name@bot`, `LEAGUEPEDIA_PASSWORD=...`) and local builds log in for a higher limit. Don't loop on it while developing: cache a fetched schedule (`fetch_schedule(...).to_pickle(...)`) and pass it as `schedule=` to `build_predictions`, or build with `PREDICTIONS_FETCH=0`.

## Before you finish a change

1. `uv run pytest -q` passes (including the steering guard).
2. If you touched the DB scripts or metrics, rebuild with `uv run bash scripts/setup_db.sh`, then `build_site.py`, and spot-check `output/`. Rerun `evaluate_metrics.py` to check the change helps, with `--write-weights` to refresh the forecast weights, and `evaluate_season_stats.py` for season stats.
3. If you touched templates, CSS, or JS, build the site and look at it in a browser at desktop and phone widths.
4. Inspect the diff and make the document updates above match the code. State anything you did not verify.
