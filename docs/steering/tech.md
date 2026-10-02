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
  └─ scripts/build_site.py ─▶ output/ (index, glory, record, luck, glorelo_plus, form, game_length_elo,
                               sunset, glory_unadjusted, glorb, glory_plus (redirect), 404, teams/*.html, teams.json)
  └─ scripts/evaluate_metrics.py ─▶ docs/metric_backtest.md (forecast backtest; refreshes forecast weights)
  └─ scripts/evaluate_season_stats.py ─▶ docs/season_stats_report.md (season-stat stability and fit)
```

### Tables

- `matches`: one row per (gameid, teamid). Holds year, date, split, league, teamname, side, gamelength (seconds), and result.
- `match_stats`: team totals per game (gold, kills, towers, objectives, firsts, vision).
- `player_stats`: per-player snapshots at 10/15/20/25 minutes, including the lane opponent.
- `match_glory_stats` (view): per-minute and per-10-minute rates used as GLORY features.
- `game_length_elo`: per-game pre/post Elo per team, keyed on (gameid, teamid), with the team's `home_league` and that league's `league_offset` after the game. Without the key every pre-game Elo join made SQLite build a temporary index.
- `game_length_elo_league_offsets`: each league's offset after every international game that moved it (gameid, date, league, league_offset).

## Season stats and forecasts

The metrics come in two families, judged differently:

- **Season stats** (GLORY, Record, Luck; sunset: GLORB, unadjusted GLORY) describe a team-season with hindsight. They may use every game of the season, weight games equally, and show small samples as they are. They are judged by `evaluate_season_stats.py`: split-half reliability (random halves by game id, Spearman-Brown, games to reach 0.5) and within-season correlation with win % and Record.
- **Forecasts** (GlorELO+, Form, Elo) predict the next game from earlier games only, weight recent games more and shrink small samples. They are judged only by `evaluate_metrics.py`. No forecast takes a season stat's output as input.

## GLORY algorithm (as implemented)

For each year:
1. Fit `StandardScaler → LinearRegression(result)` on all major-league games that year.
2. Average each team-season's features, keeping only team-seasons with at least `minimum_matches` games.
3. Score = `pipeline.predict(averages) * 100`.
4. GLORB instead sums the scaled features, z-normalizes them, and maps them to mean 80 and SD 15.
5. Add `era_score` (z within the year) and `league_score` (z within league and year).

`before=<date>` restricts both the fit and the averages to earlier games (used by the backtest).

Each year's major-league games are read once per call and used for both the fit and the averages (a separate read only happens when the league filter includes non-major leagues). `load_glory_games()` reads every year up front so several calls can share it through `games=`; `build_site.py` does this for its rankings.

### Opponent adjustment

The published GLORY is `opponent_adjusted="record"`: for each year and feature, fit `feature ~ own_rating + opp_rating` over that year's major-league games, where ratings are each team's full-season Record (log-odds), then restate each game against the average opponent (`f - b_opp * (opp_rating - mean)`) before averaging. The pipeline is still fit on the unadjusted games. Pass `record=` (a `season.get_record` frame) to share one Record fit. `opponent_adjusted="elo"` (or `True`) is the retired GLORY+, which used each opponent's pre-game Elo; the season-stat report still scores it for comparison. The unadjusted GLORY is published on the sunset page `glory_unadjusted.html`; `glory_plus.html` redirects to GLORY.

## Record and Luck

`prometheus/season.py`.

- **Record** (`get_record`): per year (`matches.year`), a Bradley-Terry model over every game in every league, including international events. Each game is two weighted rows: a win with weight s and a loss with weight 1 − s, where s is Elo's game-length winner score from the team's side (`elo.winner_score`). Ridge prior: ratings ~ N(0, `RECORD_PRIOR_SD`² = 1) in log-odds (`LogisticRegression(C=1)`, no intercept). Ratings are centred on the mean major-league team (home league = most-played domestic league that year) and published as `100 · sigmoid(rating)`. The site shows the same team-seasons as GLORY, with GLORY's league label.
- **Luck** (`get_luck`): per year, GLORY's per-game pipeline (unadjusted) predicts each major-league game's result, clipped to [0, 1]. A team-season's raw earned win % is the mean prediction; it is calibrated with a games-weighted linear fit of season win % on raw earned % across that year's team-seasons (the per-game linear model pulls every team toward 50%). Luck = win % − earned, as points and as wins (`luck_wins`).

## Form

`prometheus/form.py`. Per team-game GLORY stats for every league (`load_form_games`), then:

1. `opponent_adjust`: each stat is restated against an average opponent by pre-game Elo, `f − b_opp × (opp_elo − mean)`, with `b_opp` from `f ~ own_elo + opp_elo` fit on earlier seasons only (the first season uses its own games).
2. `form_states`: in date order, each team keeps an exponentially weighted sum of stats (`HALF_LIFE` = 20 games); at a new `matches.year` its sum and weight are multiplied by `CARRY` (0.5). The pre-game state mixes in the season's running average (`PRIOR_GAMES` = 5 games' worth). A missing stat counts as average. Home league is the domestic league the team has played most that season (a cup or international event doesn't change it). Returns pre- and post-game states per row.
3. `scores`: state · Form weights (logistic, per unit of stat gap, fit on domestic blue-minus-red pre-game gaps; `form_weights.json`).
4. `league_relative`: score minus the mean pre-game score of the same home league and season through that day.

Form on the site is league-relative Form in Elo points (`FORM_POINTS` = `form_weight / elo_weight` per log-odds unit).

## GlorELO+

`prometheus/glorelo.py`. Same home league: P(win) = sigmoid(`ELO_WEIGHT` × Elo gap + `FORM_WEIGHT` × Form gap), so the rating is Elo + `FORM_POINTS` × Form and P = sigmoid(`ELO_WEIGHT` × rating gap). Different home leagues: P = sigmoid(`CROSS_REGION_ELO_WEIGHT` × Elo gap), because Form only compares a team with its own league (blending it into cross-region games made them worse in the backtest). `team_forms` gives now and season-end Form per team; `glorelo_ratings` joins Form with Elo on team name (and year). Weights are fit by the backtest and stored in `glorelo_weights.json`; `forecast.js` gets `ELO_WEIGHT` and `CROSS_REGION_ELO_WEIGHT` through the page config. `evaluate_metrics.py --write-weights` refreshes both weight files; `--check-weights` prints every change and warns (GitHub annotation) when a blend weight moves more than `WEIGHT_TOLERANCE` (10%); Form's per-stat weights are printed but never warn, because some are near zero.

## Elo

`prometheus/elo.py`, replayed in date order by `004_bootstrap_elo.py`. A team's rating is its own rating plus its home league's offset (home league = the last domestic league it played in). Each game changes the teams' own ratings by K=20 × (actual − expected), where the winner's "actual" falls from 1.0 for very short games to 0.65 for very long ones. When teams from two leagues meet at an international event, each league's offset also moves by `LEAGUE_SHARE` (0.5) of the team's change. A new team starts at 1500 plus its league's offset; a team that changes league keeps its rating. `get_latest_elos` adds each league's offset changes since the team's last game. `get_season_elos` gives every team's rating at the end of each calendar year it played (last game that year plus offset changes through year end), labelled with its most-played domestic league that year. Calendar years, not Oracle's Elixir `year`, because some autumn games are filed under the next season.

## Forecast pages

`build_site.py` gives the Elo, Form and GlorELO+ pages two kinds of rows, flagged `now`. Now rows are current ratings, `active` when the team played within `ACTIVE_WINDOW` (183 days) of the newest game (Elo and Form: every team; GlorELO+: active major-league teams only). Season rows are team-seasons at year end (Elo: `get_season_elos`; Form: the state after the team's last game that year against that league-season's average; GlorELO+: that Form plus season-end Elo). Team pages reuse the GlorELO+ season rows for their GlorELO+ column and the now rows for the fact line; GLORY comes from rankings with `minimum_matches=1`, Record and Luck from the season pages (5+ games). `rankings.js` shows active now rows until seasons are picked, and searches all now rows. The head-to-head box uses now rows only.

## Backtest

`scripts/evaluate_metrics.py` (helpers in `prometheus/evaluation.py`) scores forecasts only: blue side, win % so far (baseline), Elo as of each month's start, live (pre-game) Elo, live Form and live GlorELO+. A month is scored when both teams have 5+ major-league games that season before it. Each metric's win curve is fit on the other seasons; Form's stat weights are too (`add_form`). GlorELO+ uses a curve on Elo and Form gaps for same-league games (fit on same-league games) and the Elo curve for the rest (`glorelo_probabilities`). Scores: accuracy, Brier, log loss, paired bootstrap against win % so far, domestic and cross-region international games reported separately. "Elo (as of cutoff)" is `evaluation.elo_as_of`: each team's rating after its last game before the cutoff plus its home league's offset moves since then (from `game_length_elo_league_offsets`), matching `get_latest_elos`. "Elo (live)" is each game's pre-match rating.

## Testing

- `tests/test_*.py`: unit tests with `get_matches_frame` mocked.
- `tests/integration/`: in-memory SQLite fixtures (`conftest.py`).
- `tests/e2e/`: run against the real `db/prometheus.db` and assert known outcomes (for example, Gen.G and T1 at the top in 2022).
- `tests/test_steering.py`: fails when uncommitted code changes have no `docs/steering/work_log.md` change.
- `tests/test_season.py` (Record, Luck), `tests/test_form.py` (states, carry-over, home league, league-relative scores, opponent adjustment), `tests/test_glorelo.py` (ratings, same- and cross-league odds, weights), and the reliability helpers in `tests/test_evaluation.py`, all on synthetic data.
- `tests/test_utils.py` covers CLI year parsing (`parse_years`). There are no tests for the CLI command itself, `build_site.py`, templates, or JS.

## Constraints

- Static hosting only. Anything dynamic must be precomputed at build time or done in browser JS.
- Each CI build re-downloads every CSV from Google Drive. The upstream folder ID is hardcoded in `setup_db.sh`.
- A site build takes about 10 seconds: SQLite reads (each year's games, every game for Record and Form, Elo), the Form pass over about 200,000 team-games in Python, and writing about 2,000 team pages. The forecast backtest takes about 8 seconds and the season-stat report about 5.
