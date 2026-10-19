# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo.

## Read before work

Read only what your change touches. If your task came with a spec naming files and docs, read those and skip this list.

- **Always:** the newest work-log entries, `python3 scripts/work_log.py recent 5` (not the whole file). Search [the archive](docs/steering/work_log_archive.md) with `grep` when a topic may have been tried before.
- **Pipeline, tables, metric algorithms, tests, file layout:** [Tech](docs/steering/tech.md) (its Layout section maps every file; its Metric change rules section holds the full benchmark rules).
- **Feature status, known limits, future work:** [Current state](docs/steering/current_state.md).
- **Metrics, audience, vision:** [Product](docs/steering/product.md).
- **CI, publishing, data backup, AWS:** [Deployment](docs/steering/deployment.md).
- **Templates, CSS, JS:** [UI](docs/steering/ui.md), `DESIGN.md` and `PRODUCT.md`. Use the impeccable skill.
- **Research that changed no published metric** (in-game models, champions, gol.gg objectives, the broadcast pilot): [`docs/research/README.md`](docs/research/README.md).

Read large docs by section (`grep -n '^## '`, then the lines you need), not whole.

Code and the built DB are the source of truth. If a document disagrees with them, verify the behavior and correct the document in the same change. The user's latest instructions override these docs.

## Required document updates

- **Every substantive code or behavior change:** add a dated entry at the top of `docs/steering/work_log.md` with what changed, the checks actually run, and any remaining limit. Older entries move to the archive by themselves (see Work log below).
- **Feature status, known limit, or future work changes:** update `docs/steering/current_state.md` in the same change. Suggestions for future work go in its **Future work** section, not only in chat. Remove items once they ship.
- **Metric added, changed, or its status changed:** update the metrics table in `docs/steering/product.md`, the metric descriptions in `README.md`, and rerun `scripts/evaluate_metrics.py` (forecasts) and `scripts/evaluate_season_stats.py` (season stats).
- **Data pipeline, tables, algorithms, file layout, or test layout change:** update `docs/steering/tech.md`.
- **CI, publishing, schedules, secrets, or AWS resources change:** update `docs/steering/deployment.md`.
- **Visual design or UI components change:** update `DESIGN.md` (and `docs/steering/ui.md` if the direction changes).
- For documentation-only work, still add a short work-log entry and check the links and commands you touched. Do not add empty entries or claim a check you did not run.

`uv run pytest -q` includes `tests/test_steering.py`, which fails when code changed (uncommitted) without a `work_log.md` change. It can't judge whether the other docs are accurate, so do that review yourself.

### Work log

`work_log.md` keeps the newest entries. The pre-commit hook (`.githooks/pre-commit`) runs `scripts/work_log.py rotate` when a commit touches the log: past 15 entries, all but the newest 10 move to the top of `work_log_archive.md`. Entries are at most 150 words. Enable it once per clone (worktrees share it): `git config core.hooksPath .githooks`. Without the hook, run `python3 scripts/work_log.py rotate` yourself.

## What this is

Prometheus is a "sabermetrics for League of Legends esports" project. It ingests Oracle's Elixir match CSVs into SQLite, computes team and player metrics (GLORY, FORGE, game-length Elo, AURA, prop projections), and publishes them two ways:

1. **CLI** (`prometheus rankings glory ...`), built with Typer and Rich.
2. **Static website**: Jinja2 templates rendered by `scripts/build_site.py` into `output/`, published to https://prometheus.thaiv.dev (S3 + CloudFront) by `.github/workflows/publish.yml`. See `docs/steering/deployment.md`. A live in-game service (`prometheus/live/`, an EC2 worker) writes the live pages.

## Quick commands

```bash
uv sync                                # install (Python >= 3.12, managed by uv)
uv run bash scripts/setup_db.sh         # download raw CSVs (gdown), rebuild db/prometheus.db from scratch
uv run python scripts/build_site.py     # render static site to output/
PREDICTIONS_FETCH=0 uv run python scripts/build_site.py   # build without fetching the schedule (uses the saved log)
uv run pytest -q                        # run tests (unit + integration + e2e; e2e builds a small DB from a committed sample)
uv run ruff format && uv run ruff check # format and lint (CI checks both)
uv run prometheus rankings glory --league MAJOR --year 2024
uv run prometheus predict --days 2 --major   # odds for upcoming matches (Leaguepedia schedule)
python -m http.server -d output 8000    # preview the built site locally
```

Benchmark commands (forecasts, season stats, AURA, props, markets, live) are in `tech.md`, Metric change rules. `data/`, `db/`, and `output/` are gitignored build artifacts. Never commit them.

### Worktrees

Agents work in a separate worktree (see the global `AGENTS.md`). A new one has none of the gitignored state, so set it up from the main checkout (`MAIN`):

```bash
git worktree add ../Prometheus-<branch> -b <branch> <base> && cd ../Prometheus-<branch>
uv sync
mkdir -p data && ln -s "$MAIN/data/raw" data/raw    # raw CSVs: read-only, safe to share
cp "$MAIN/.env" .                                    # Leaguepedia bot login
cp "$MAIN/data/predictions.json" "$MAIN/data/market_prices.json" data/   # prediction log and Kalshi prices, for site builds
cp -R "$MAIN/data/markets" data/                     # Kalshi cache, only for evaluate_markets.py (rewrites frames.pkl)
mkdir -p data/live_bench "$MAIN/data/live_bench/pre_trades"   # Kalshi trade tapes: one file per market, never rewritten,
ln -s "$MAIN/data/live_bench/trades" "$MAIN/data/live_bench/pre_trades" data/live_bench/   # so share them (an hour to refetch)
uv run bash scripts/setup_db.sh                      # own db/ (~1 min); never symlink db/, setup_db.sh deletes it
```

Use a port other than 8000 for `http.server` if another worktree is serving. Before removing a worktree, move any fetched data you want to keep into `$MAIN/data/`: `git worktree remove --force` deletes gitignored files.

## Layout

The full file map is the Layout section of `tech.md`. The main entry points:

| Path | Purpose |
|---|---|
| `prometheus/` | Python package: metrics (`ranking.py` GLORY, `forge.py`, `form.py`, `elo.py`, `aura.py`, `props.py`), data access (`matches.py`, `player_tables.py`), predictions (`schedule.py`, `markets.py`, `alerts.py`), the CLI (`main.py`) |
| `prometheus/types.py` | Enums and feature lists: the single source of truth for column names |
| `prometheus/site/`, `scripts/build_site.py` | Static site generator; metric registries and paths in `site/config.py` |
| `prometheus/live/`, `deploy/live/` | The live pages' service and its EC2 worker |
| `scripts/NNN_*.sql\|py` | DB build steps, run **in numeric order** by `setup_db.sh` |
| `scripts/evaluate_*.py`, `scripts/compare_benchmarks.py` | Benchmarks and the PR benchmark check |
| `templates/`, `site_static/` | Jinja2 templates, hand-written CSS and vanilla JS |
| `tests/` | Unit (mocked), `integration/` (in-memory SQLite), `e2e/` (marked `e2e`), `js/` (Node) |

## Conventions

- **Data access is raw SQL through `pd.read_sql(stmt, utils.get_engine())`.** The project recently moved away from the SQLAlchemy ORM (`d3b361a`). Don't reintroduce ORM queries.
- **Schema changes go in a new numbered script** (`scripts/005_*.sql`), or in `001_create_tables.sql` if the change belongs to the base schema. The DB is always rebuilt from scratch, so there are no migrations.
- **Feature and column names live in `types.py`.** If you add a metric feature, add it there and to the SQL view that produces it (for example `003_create_glory.sql`).
- **Retiring a metric:** give its `METRICS` or `FORECASTS` entry a `sunset` note (shown on its page) and a short `sunset_why` (shown on `sunset.html`). It leaves the header menus and home contents; the "Sunset stats" link at the end of the Teams menu leads to the list. The page and data stay.
- **Static assets:** reference CSS and JS through `asset('css/…')` in templates, which adds a content-hash query so browsers pick up changes.
- **New metrics on the site** are registered in the `METRICS` (team season stats), `FORECASTS` / `ELO_METRICS` (team forecasts) or `PLAYER_METRICS` (player stats) dicts in `prometheus/site/config.py` (including the explainer copy) and given a column config (`METRIC_COLUMNS` / `FORGE_COLUMNS` / `ELO_COLUMNS` / `PLAYER_ELO_COLUMNS`) with `kind` set to `"season"` (0–100) or `"rating"` (Elo scale), and `entity` `"player"` for player registers (default team). Each needs a `question` (the one question it answers, shown under its name in the header menu and home contents). `SECTIONS` lists them under **Teams** or **Players**, the two header menus and the two parts of the home contents. A metric's `title` ("Team Elo", "Player Elo") is its page name when the short header `name` is shared. `rankings.html.j2` and `rankings.js` render any metric from that config.
- **Season stats vs forecasts.** Season stats (GLORY; sunset Record and Luck) may use the whole season; forecasts (FORGE, Elo; sunset Form) use only earlier games and must not take a season stat as input. Judge season stats with `evaluate_season_stats.py` and forecasts with `evaluate_metrics.py`.
- **Change a metric only for a significant benchmark gain** on the same games or team-seasons (paired-bootstrap 95% interval excluding 0), with nothing it targets getting significantly worse. Accuracy fixes (which data a forecast uses) follow a lighter rule, and AURA has its own four-part rule. Before any metric, weight or data-selection change, read the Metric change rules section of `tech.md`: it has the exact tests, the CI benchmark check (`benchmark-override` label) and the weight files. Record each tested change and its numbers in the work log either way. Refitting existing weights on new data (`--write-weights`) is not a metric change.
- **CI time is a budget; don't let it drift.** Think hard about every change that adds work to CI (a test, a benchmark, a build step, a job, or code that slows an existing step). Measure its cost locally and in the Actions timings, and take the cheapest design: reuse data already loaded (`games=`, `PlayerTables`), fit offline and commit the result (`*_weights.json`), read only the rows and columns needed, run beside existing work, cache by input hash, skip when the changed files can't move the output. Record the measured before and after in the work log; added wall time to the publish build, the PR checks or the hourly job needs a stated reason there.
- **Token use is a budget too.** Every agent rereads these docs, so keep them short. `tests/test_steering.py` fails when a changed steering doc passes its word budget (`WORD_BUDGETS`) or a new work-log entry passes 150 words: condense it (cut history, repetition, examples), don't raise the budget without the user. Keep command output short (`-q`, `| tail -n 40`), and make new scripts print a summary, not per-row logs. When a doc, script output or test log you read is far longer than its use, say so and propose a trim.
- `gamelength` is stored in **seconds**.
- League names are normalized at ingest (`002_add_matches.py`): NA LCS / LTA N → `LCS`, EU LCS → `LEC`.
- Formatting and linting: `ruff` (`ruff format`; `ruff check` with pyflakes, import sorting and syntax errors), configured in `pyproject.toml` and run by CI's `check` job before the data download. It is in the `dev` dependency group with `pytest` (`uv sync` installs it; the hourly prices job uses `--no-dev`).
- Frontend: no build step and no framework. Design tokens are in `site_static/css/tokens.css`, and league color comes only from `[data-league]`. Charts are hand-drawn SVG; there are no third-party scripts. JS that writes HTML must escape values with `esc()` in `rankings.js`.
- **Site copy is minimal:** every word must be necessary (see `docs/steering/ui.md`, *Copy*). Draft, cut by half, and drop anything a heading, column head, key or tooltip already says.
- **Succinct-copy review is required for every UI change**, including new pages, edits to existing pages, and copy generated by Python or JS. Review the whole affected page, not just the changed strings: headings, ledes, captions, margin notes, labels, tooltips, statuses and empty/error states. Remove repetition of table values or labels; keep methodology in the README/reports. Retain definitions, material caveats, accessibility names and information needed to act. Do not replace useful meaning with unexplained abbreviations or apply an arbitrary word limit. Check the rendered desktop/phone page, then record `Copy review: PASS` in the work log with the surfaces reviewed and what was cut (or why existing copy is already minimal). Include the result in the PR checklist. A UI change is not complete until this review passes; do not wait for the user to request it.
- Visual direction is "The Almanac": the site is set like a printed sabermetrics annual, with booktabs registers, margin notes and small printed figures on paper. See `DESIGN.md`, `.impeccable/surfaces/` and `docs/steering/ui.md` before changing the look.

## Gotchas

- `get_glory_ranking()` reads and fits one model **per year** on every call, so `build_site.py` loads the games once (`load_glory_games()`, passed as `games=`) and reads the player tables once (`PlayerTables`). Don't add a second read. Build timings are in `tech.md` (Layout, Build cost).
- International events (Worlds, MSI, ...) are ingested as their own leagues (`INTERNATIONAL_LEAGUES` in `types.py`). They are the only games linking regional Elo pools. A new cross-region event (an invitational, a new international cup) must be added there, or it becomes its teams' home league: their FORGE calls turn into Elo calls and leave the FORGE page and the Kalshi alerts (this happened with `DCGI` and `WSCI` until 2026-10-06). Oracle's Elixir leaves `split` empty for them, so don't reintroduce a blanket `dropna` over `split` in `002_add_matches.py`.
- `setup_db.sh` **deletes** `db/prometheus.db` before rebuilding.
- `scripts/004_bootstrap_elo.py` clears and refills `game_length_elo`, so it's safe to rerun.
- Leaguepedia rate-limits anonymous API calls after a few in a row and stays shut for minutes. Put a bot password in a gitignored `.env` (`LEAGUEPEDIA_USER=Name@bot`, `LEAGUEPEDIA_PASSWORD=...`) and local builds log in for a higher limit. Don't loop on it while developing: cache a fetched schedule (`fetch_schedule(...).to_pickle(...)`) and pass it as `schedule=` to `build_predictions`, or build with `PREDICTIONS_FETCH=0`.

## Before you finish a change

1. `uv run pytest -q` passes (including the steering guard).
2. If you touched the DB scripts or metrics, rebuild with `uv run bash scripts/setup_db.sh`, then `build_site.py`, and spot-check `output/`. Rerun `evaluate_metrics.py` to check the change helps, with `--write-weights` to refresh the forecast weights, and `evaluate_season_stats.py` for season stats.
3. For any UI change (including generated copy), build the affected pages and inspect desktop and phone widths. Complete the mandatory succinct-copy review above and record its result in the work log and PR checklist.
4. Inspect the diff and make the document updates above match the code. State anything you did not verify.
