# Tech

## Stack

- **Python 3.12+**, managed with **uv** (`uv.lock` is committed; CI uses `uv sync --frozen`).
- **SQLite** at `db/prometheus.db`, built from scratch by `scripts/setup_db.sh`.
- **pandas + SQLAlchemy engine** for reads/writes (raw SQL strings, no ORM).
- **scikit-learn** for GLORY (StandardScaler + LinearRegression). **XGBoost** for the experimental win-probability model.
- **Typer + Rich** for the CLI.
- **Jinja2** static site generation. Vanilla JS + hand-written CSS. Charts are hand-drawn SVG (no chart library). Source Serif 4 is self-hosted.
- **GitHub Actions to S3 + CloudFront** (`.github/workflows/publish.yml`): builds on every PR; deploys on push to `main`, daily at 10:00 UTC, and on manual dispatch. The AWS resources live in `project-platform-infrastructure`.

## Data pipeline

```
Oracle's Elixir Google Drive folder
  └─ gdown ─▶ data/raw/*.csv   (one CSV per year)
       └─ 001_create_tables.sql  → matches, match_stats, player_stats, game_length_elo
       └─ 002_add_matches.py     → filter/normalize CSVs (keeps international events), append rows
       └─ 003_create_glory.sql   → VIEW match_glory_stats (per-minute rates)
       └─ 004_bootstrap_elo.py   → fill game_length_elo
  └─ scripts/build_site.py ─▶ output/ (index, glory, glorb, glory_plus, glorelo_plus, game_length_elo, teams/*.html)
  └─ scripts/evaluate_metrics.py ─▶ docs/metric_backtest.md (backtest; run by hand)
```

### Tables

- `matches`: one row per (gameid, teamid). Holds year, date, split, league, teamname, side, gamelength (seconds), and result.
- `match_stats`: team totals per game (gold, kills, towers, objectives, firsts, vision).
- `player_stats`: per-player snapshots at 10/15/20/25 minutes, including the lane opponent.
- `match_glory_stats` (view): per-minute and per-10-minute rates used as GLORY features.
- `game_length_elo`: per-game pre/post Elo per team, keyed on (gameid, teamid), with the team's `home_league` and that league's `league_offset` after the game. Without the key every pre-game Elo join made SQLite build a temporary index.
- `game_length_elo_league_offsets`: each league's offset after every international game that moved it (gameid, date, league, league_offset).

## GLORY algorithm (as implemented)

For each year:
1. Fit `StandardScaler → LinearRegression(result)` on all major-league games that year.
2. Average each team-season's features, keeping only team-seasons with at least `minimum_matches` games.
3. Score = `pipeline.predict(averages) * 100`.
4. GLORB instead sums the scaled features, z-normalizes them, and maps them to mean 80 and SD 15.
5. Add `era_score` (z within the year) and `league_score` (z within league and year).

`before=<date>` restricts both the fit and the averages to earlier games (used by the backtest).

Each year's major-league games are read once per call and used for both the fit and the averages (a separate read only happens when the league filter includes non-major leagues). `load_glory_games()` reads every year up front so several calls can share it through `games=`; `build_site.py` does this for its five rankings.

## GLORY+

`opponent_adjusted=True`: for each year and feature, fit `feature ~ own_pre_elo + opp_pre_elo` over major-league games, then restate each game against the average opponent (`f - b_opp * (opp_elo - mean)`) before averaging. Scoring is otherwise GLORY's.

## Elo

`prometheus/elo.py`, replayed in date order by `004_bootstrap_elo.py`. A team's rating is its own rating plus its home league's offset (home league = the last domestic league it played in). Each game changes the teams' own ratings by K=20 × (actual − expected), where the winner's "actual" falls from 1.0 for very short games to 0.65 for very long ones. When teams from two leagues meet at an international event, each league's offset also moves by `LEAGUE_SHARE` (0.5) of the team's change. A new team starts at 1500 plus its league's offset; a team that changes league keeps its rating. `get_latest_elos` adds each league's offset changes since the team's last game.

## GlorELO+

`prometheus/glorelo.py`: rating = 1500 + (400 / ln 10) × (centred `GLORY_PLUS_WEIGHT × GLORY+ + ELO_WEIGHT × Elo`), so the win probability is the usual Elo formula. The weights are per-point log-odds fit by the backtest on GLORY+ and live Elo gaps, stored in `prometheus/glorelo_weights.json` (shipped as package data). `evaluate_metrics.py --write-weights` refreshes the file; `--check-weights` refits without the report and prints a GitHub warning when a weight moves more than `WEIGHT_TOLERANCE` (10%).

## Backtest

`scripts/evaluate_metrics.py` (helpers in `prometheus/evaluation.py`): at the first of each month, compute each metric from that season's earlier games, predict that month's games with a logistic win curve fit on the other seasons, and score accuracy, Brier and log loss. Compares each metric with win % so far using a paired bootstrap; domestic and cross-region international games are reported separately.

## Testing

- `tests/test_*.py`: unit tests with `get_matches_frame` mocked.
- `tests/integration/`: in-memory SQLite fixtures (`conftest.py`).
- `tests/e2e/`: run against the real `db/prometheus.db` and assert known outcomes (for example, Gen.G and T1 at the top in 2022).
- `tests/test_steering.py`: fails when uncommitted code changes have no `docs/steering/work_log.md` change.
- There are no tests for `build_site.py`, templates, or JS.

## Constraints

- Static hosting only. Anything dynamic must be precomputed at build time or done in browser JS.
- Each CI build re-downloads every CSV from Google Drive. The upstream folder ID is hardcoded in `setup_db.sh`.
- A site build takes about 5 seconds, mostly SQLite reads (each year's games, latest Elo, Elo history) and writing about 2,000 team pages.
