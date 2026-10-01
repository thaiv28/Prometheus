# Tech

## Stack

- **Python 3.12+**, managed with **uv** (`uv.lock` is committed; CI uses `uv sync --frozen`).
- **SQLite** at `db/prometheus.db`, built from scratch by `scripts/setup_db.sh`.
- **pandas + SQLAlchemy engine** for reads/writes (raw SQL strings, no ORM).
- **scikit-learn** for GLORY (StandardScaler + LinearRegression). **XGBoost** for the experimental win-probability model.
- **Typer + Rich** for the CLI.
- **Jinja2** static site generation. Vanilla JS + hand-written CSS. **Chart.js 4** from jsDelivr on team pages.
- **GitHub Actions to GitHub Pages** (`.github/workflows/static.yml`): runs on push to `main`, daily at 10:00 UTC, and on manual dispatch.

## Data pipeline

```
Oracle's Elixir Google Drive folder
  └─ gdown ─▶ data/raw/*.csv   (one CSV per year)
       └─ 001_create_tables.sql  → matches, match_stats, player_stats, game_length_elo
       └─ 002_add_matches.py     → filter/normalize CSVs, append rows
       └─ 003_create_glory.sql   → VIEW match_glory_stats (per-minute rates)
       └─ 004_bootstrap_elo.py   → fill game_length_elo
  └─ scripts/build_site.py ─▶ output/ (index, glory, glorb, game_length_elo, teams/*.html)
```

### Tables

- `matches`: one row per (gameid, teamid). Holds year, date, split, league, teamname, side, gamelength (seconds), and result.
- `match_stats`: team totals per game (gold, kills, towers, objectives, firsts, vision).
- `player_stats`: per-player snapshots at 10/15/20/25 minutes, including the lane opponent.
- `match_glory_stats` (view): per-minute and per-10-minute rates used as GLORY features.
- `game_length_elo`: per-game pre/post Elo per team.

## GLORY algorithm (as implemented)

For each year:
1. Fit `StandardScaler → LinearRegression(result)` on all major-league games that year.
2. Average each team-season's features, keeping only team-seasons with at least `minimum_matches` games.
3. Score = `pipeline.predict(averages) * 100`.
4. GLORB instead sums the scaled features, z-normalizes them, and maps them to mean 80 and SD 15.
5. Add `era_score` (z within the year) and `league_score` (z within league and year).

## Testing

- `tests/test_*.py`: unit tests with `get_matches_frame` mocked.
- `tests/integration/`: in-memory SQLite fixtures (`conftest.py`).
- `tests/e2e/`: run against the real `db/prometheus.db` and assert known outcomes (for example, Gen.G and T1 at the top in 2022).
- There are no tests for `build_site.py`, `elo.py`, templates, or JS.

## Constraints

- Static hosting only. Anything dynamic must be precomputed at build time or done in browser JS.
- Each CI build re-downloads every CSV from Google Drive. The upstream folder ID is hardcoded in `setup_db.sh`.
- Build time is dominated by repeated per-year model fits.
