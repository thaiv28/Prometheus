# AGENTS.md

Guidance for AI coding agents (and humans) working in this repo. Read this first, then the steering docs in `docs/steering/` for deeper context.

## What this is

Prometheus is a "sabermetrics for League of Legends esports" project. It ingests Oracle's Elixir match CSVs into SQLite, computes team metrics (GLORY, GLORB, game-length Elo), and publishes them two ways:

1. **CLI** (`prometheus rankings glory ...`), built with Typer and Rich.
2. **Static website**: Jinja2 templates rendered by `scripts/build_site.py` into `output/`, published to https://prometheus.thaiv.dev (S3 + CloudFront) by `.github/workflows/publish.yml`. See `docs/steering/deployment.md`.

## Quick commands

```bash
uv sync && uv pip install -e .          # install (Python >= 3.12, managed by uv)
bash scripts/setup_db.sh                # download raw CSVs (gdown), rebuild db/prometheus.db from scratch
uv run python scripts/build_site.py     # render static site to output/
uv run pytest -q                        # run tests (unit + integration + e2e; e2e needs a built DB)
uv run prometheus rankings glory --league MAJOR --year 2024
python -m http.server -d output 8000    # preview the built site locally
```

`data/`, `db/`, and `output/` are gitignored build artifacts. Never commit them.

## Layout

| Path | Purpose |
|---|---|
| `prometheus/` | Python package: metric computation and data access |
| `prometheus/types.py` | Enums (`Metric`, `League`, `ScoreCols`) and feature lists (`GLORY_FEATURES`, etc.). This is the single source of truth for column names. |
| `prometheus/matches.py` | Raw-SQL reads that join a stats table/view with `matches` |
| `prometheus/regression.py` | Fits the GLORY model (StandardScaler + LinearRegression, target = win) |
| `prometheus/ranking.py` | `get_glory_ranking()` fits a model per year, scores team-season averages, and adds z-scores |
| `prometheus/elo.py` | Game-length-weighted Elo: bootstrap and query helpers (WIP) |
| `prometheus/win_prediction.py`, `players.py`, `aura.py` | Player metric (AURA) groundwork, still experimental |
| `prometheus/main.py` | Typer CLI entry point (`prometheus` script) |
| `scripts/NNN_*.sql\|py` | DB build steps. `setup_db.sh` runs them **in numeric order**. |
| `scripts/build_site.py` | Static site generator |
| `templates/*.html.j2` | Jinja2 templates: `base` (shell), `index`, `rankings` (every metric page, driven by a column config), `team`, `404`, and the `_marks` macros (league mark, signed number, ordinal) |
| `site_static/{css,js,fonts}` | Hand-written CSS (`tokens.css` holds all colors and the `@font-face` rules, including league inks), vanilla JS (`rankings.js` for filtering, sorting and the distribution figure, `team.js` for the season switch and the SVG Elo chart), and the self-hosted Source Serif 4 font (OFL), all copied verbatim into `output/` |
| `PRODUCT.md`, `.impeccable/surfaces/` | Product record and visual direction contract used by the impeccable design skill. Read them before UI work. |
| `notebooks/` | Exploratory modeling. Not imported by the package. |
| `tests/` | `test_*.py` unit tests (mocked), `integration/` (in-memory SQLite), `e2e/` (real DB) |

## Conventions

- **Data access is raw SQL through `pd.read_sql(stmt, utils.get_engine())`.** The project recently moved away from the SQLAlchemy ORM (`d3b361a`). Don't reintroduce ORM queries. `players.py` is a leftover that still uses table reflection.
- **Schema changes go in a new numbered script** (`scripts/005_*.sql`), or in `001_create_tables.sql` if the change belongs to the base schema. The DB is always rebuilt from scratch, so there are no migrations.
- **Feature and column names live in `types.py`.** If you add a metric feature, add it there and to the SQL view that produces it (for example `003_create_glory.sql`).
- **New metrics on the site** are registered in the `METRICS` / `ELO_METRICS` dicts in `build_site.py` (including the explainer copy) and given a column config (`METRIC_COLUMNS` / `ELO_COLUMNS`). `rankings.html.j2` and `rankings.js` render any metric from that config.
- `gamelength` is stored in **seconds**.
- League names are normalized at ingest (`002_add_matches.py`): NA LCS / LTA N → `LCS`, EU LCS → `LEC`.
- Formatting: `black`. Linting: `pylint`. Both are listed as (non-dev) dependencies.
- Frontend: no build step and no framework. Design tokens are in `site_static/css/tokens.css`, and league color comes only from `[data-league]`. Charts are hand-drawn SVG; there are no third-party scripts. JS that writes HTML must escape values with `esc()` in `rankings.js`.
- Visual direction is "The Almanac": the site is set like a printed sabermetrics annual, with booktabs registers, margin notes and small printed figures on paper. See `DESIGN.md`, `.impeccable/surfaces/` and `docs/steering/ui.md` before changing the look.

## Gotchas

- `get_glory_ranking()` refits one regression **per year** on every call. `build_site.py` calls it 4 times (GLORY/GLORB × qualified/all), and a build takes about 6 seconds.
- The default year list in `ranking.py` is hardcoded to 2014–2025, but the DB contains 2026 data.
- `setup_db.sh` **deletes** `db/prometheus.db` before rebuilding.
- Several modules end in `if __name__ == "__main__":` scratch blocks. They aren't real entry points.
- `scripts/004_bootstrap_elo.py` clears and refills `game_length_elo`, so it's safe to rerun.

## Before you finish a change

1. `uv run pytest -q` passes.
2. If you touched the DB scripts or metrics, rebuild with `setup_db.sh`, then `build_site.py`, and spot-check `output/`.
3. If you touched templates, CSS, or JS, build the site and look at it in a browser at desktop and phone widths.
4. Keep `README.md` metric descriptions in sync with any metric change.
