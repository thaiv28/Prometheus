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
       └─ 001_create_tables.sql  → matches, match_stats, match_players, player_stats, game_length_elo(_player_elo, _league_offsets)
       └─ 002_add_matches.py     → filter/normalize CSVs (keeps international events), append rows
       └─ 003_create_glory.sql   → VIEW match_glory_stats (per-minute rates)
       └─ 004_bootstrap_elo.py   → fill game_length_elo, game_length_player_elo, offsets
  └─ scripts/build_site.py ─▶ output/ (index, glory, record, luck, forge, form, game_length_elo,
                               player_elo, sunset, glory_unadjusted, glorb, glory_plus (redirect), 404, teams/*.html,
                               players/*.html, teams.json, players.json)
  └─ scripts/evaluate_metrics.py ─▶ docs/metric_backtest.md (forecast backtest; refreshes forecast weights)
  └─ scripts/evaluate_season_stats.py ─▶ docs/season_stats_report.md (season-stat stability and fit)
```

### Tables

- `matches`: one row per (gameid, teamid). Holds year, date, split, league, teamname, side, gamelength (seconds), and result.
- `match_stats`: team totals per game (gold, kills, towers, objectives, firsts, vision).
- `match_players`: each team's five starters per game (gameid, teamid, position, playerid, playername); `playerid` falls back to `name:<playername>|<teamid>` (0.7% of rows). Covers every game, unlike `player_stats`.
- `player_stats`: per-player snapshots at 10/15/20/25 minutes, including the lane opponent.
- `match_glory_stats` (view): per-minute and per-10-minute rates used as GLORY features.
- `game_length_elo`: per-game pre/post Elo per team, keyed on (gameid, teamid), with the team's `home_league` and that league's `league_offset` after the game. Without the key every pre-game Elo join made SQLite build a temporary index.
- `game_length_player_elo`: every rostered starter's rating before and after each game (offset included), keyed on (gameid, playerid). Each team row in `game_length_elo` is the mean of its five rows here.
- `game_length_elo_league_offsets`: each league's offset after every international game that moved it (gameid, date, league, league_offset).

## Season stats and forecasts

The metrics come in two families, judged differently:

- **Season stats** (GLORY; sunset: Record, Luck, GLORB, unadjusted GLORY) describe a team-season with hindsight. They may use every game of the season, weight games equally, and show small samples as they are. They are judged by `evaluate_season_stats.py`: split-half reliability (random halves by game id, Spearman-Brown, games to reach 0.5) within-season correlation with win % and Record, and correlation of the stat on one half with win % on the other half (out of sample, so a stat can't score well just by restating results).
- **Forecasts** (FORGE, Elo; Form, sunset as a page, is FORGE's input) predict the next game from earlier games only, weight recent games more and shrink small samples. They are judged only by `evaluate_metrics.py`. No forecast takes a season stat's output as input.

**Change a metric only for a significant benchmark gain.** A change to how a published metric is computed (features, weights scheme, hyperparameters, method) ships only when its benchmark beats the current version on the same games or team-seasons by more than noise: for forecasts, the paired-bootstrap 95% interval of the domestic log-loss difference (`evaluate_metrics.py`) must exclude 0 and international log loss must not get significantly worse; for season stats, a paired bootstrap over team-seasons of split-half reliability or r with the other half's win % (`evaluate_season_stats.py`) must exclude 0, with neither getting significantly worse. A gain inside the noise is not a reason to change. Record each tested change and its numbers in the work log either way. Refitting the existing weights on new data (`--write-weights`) is not a metric change.

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

## Record and Luck (sunset)

Both leave the header and team pages but keep their pages. Record is still computed every build because GLORY's opponent adjustment uses it.

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

## FORGE

FORGE (Form + Elo) was called GlorELO+ until 2026-10-02; the module, weights file, CLI metric (`forge`) and column names were renamed with it.

`prometheus/forge.py`. Same home league: P(win) = sigmoid(`ELO_WEIGHT` × Elo gap + `FORM_WEIGHT` × Form gap), so the rating is Elo + `FORM_POINTS` × Form and P = sigmoid(`ELO_WEIGHT` × rating gap). Different home leagues: P = sigmoid(`CROSS_REGION_ELO_WEIGHT` × Elo gap), because Form only compares a team with its own league (blending it into cross-region games made them worse in the backtest). `team_forms` gives now and season-end Form per team; `forge_ratings` joins Form with Elo on team name (and year). Weights are fit by the backtest and stored in `forge_weights.json`; `forecast.js` gets `ELO_WEIGHT` and `CROSS_REGION_ELO_WEIGHT` through the page config. `evaluate_metrics.py --write-weights` refreshes both weight files; `--check-weights` prints every change and warns (GitHub annotation) when a blend weight moves more than `WEIGHT_TOLERANCE` (10%); Form's per-stat weights are printed but never warn, because some are near zero.

## Elo

`prometheus/elo.py`, replayed in date order by `004_bootstrap_elo.py`. Ratings belong to players. A team's rating is the average of its five starters' ratings (`match_players`) plus its home league's offset (home league = the last domestic league it played in). Each game changes every starter's rating by the team's K=20 × (actual − expected), where the winner's "actual" falls from 1.0 for very short games to 0.65 for very long ones. When teams from two leagues meet at an international event, each league's offset also moves by `LEAGUE_SHARE` (0.5) of the team's change. A new player starts at the average rating of the league's active players (last game in that league within `ACTIVE_DAYS`, 365), or 1500 plus the offset if there are none; a player who changes league keeps their rating. A team with no roster for a game uses its last roster, and one that never had one plays as a single "player" (plain team Elo; this is what unit tests without rosters exercise). `get_latest_elos` adds each league's offset changes since the team's last game. `compute_elo_records(..., player_records=True)` also returns each starter's ratings, which `bootstrap_elo` stores; `get_player_history` reads them with names, roles and teams, and `get_player_elos` gives each player's current and calendar-year-end rating (offset moves included, as for teams). `get_season_elos` gives every team's rating at the end of each calendar year it played (last game that year plus offset changes through year end), labelled with its most-played domestic league that year. Calendar years, not Oracle's Elixir `year`, because some autumn games are filed under the next season.

## Forecast pages

`build_site.py` gives the Elo, Form (sunset) and FORGE pages two kinds of rows, flagged `now`. Now rows are current ratings, `active` when the team played within `ACTIVE_WINDOW` (183 days) of the newest game (Elo and Form: every team; FORGE: active major-league teams only). Season rows are team-seasons at year end (Elo: `get_season_elos`; Form: the state after the team's last game that year against that league-season's average; FORGE: that Form plus season-end Elo). Team pages reuse the FORGE season rows for their FORGE column and the now rows for the fact line; GLORY comes from rankings with `minimum_matches=1`. Record and Luck (sunset) are no longer on team pages. `rankings.js` shows active now rows until seasons are picked, and searches all now rows. The head-to-head box uses now rows only. The home page reuses the FORGE now rows (head-to-head box and top 10) and the Team and Player Elo now rows (top 10 active), with bars on each page's scale (`_rating_bar`).

Players (`player_pages_and_rows`): listed players have played in a major league or at an international event, or anywhere within `PLAYER_PAGE_WINDOW` (730 days) of the newest game; `dup:` ids are never listed. `player_elo.html` (config `entity: "player"`) has a now row per listed player and season rows for major-league player-seasons with `PLAYER_SEASON_GAMES` (10) or more games. Each listed player gets `players/<slug>.html`: slug from the name, then name plus last team for shared names, then a number. Career rows are stints (consecutive games for one team id). `players.json` feeds the header search with `teams.json`. `team_rosters` gives each team page its last lineup (the five starters of its latest game, by role, with today's player Elo) and its starters by calendar year and role (main starter first, then up to `ROSTER_EXTRAS` = 3 others with games started), grouped by team name like the team pages. `names.js` holds the JS shared by `search.js` and `rankings.js` (`fold`, `slugify`, `rank`); `base.html.j2` loads it before `search.js`. Team and player pages embed their Elo series as `[date, elo]` pairs (`compact_series`).

## Backtest

`scripts/evaluate_metrics.py` (helpers in `prometheus/evaluation.py`) scores forecasts only: blue side, win % so far (baseline), Elo as of each month's start, live (pre-game) Elo, live Form and live FORGE. A month is scored when both teams have 5+ major-league games that season before it. Each metric's win curve is fit on the other seasons; Form's stat weights are too (`add_form`). FORGE uses a curve on Elo and Form gaps for same-league games (fit on same-league games) and the Elo curve for the rest (`forge_probabilities`). Scores: accuracy, Brier, log loss, paired bootstrap against win % so far, domestic and cross-region international games reported separately. "Elo (as of cutoff)" is `evaluation.elo_as_of`: each team's rating after its last game before the cutoff plus its home league's offset moves since then (from `game_length_elo_league_offsets`), matching `get_latest_elos`. "Elo (live)" is each game's pre-match rating. "Team Elo, no player ratings" replays the same Elo without rosters (`compute_elo_records` without `rosters`) as a reference, and a last table compares the two on domestic games early in a season and within 10 games of a starter change (`load_roster_context`).

## Testing

- `tests/test_*.py`: unit tests with `get_matches_frame` mocked.
- `tests/integration/`: in-memory SQLite fixtures (`conftest.py`).
- `tests/e2e/`: run against the real `db/prometheus.db` and assert known outcomes (for example, Gen.G and T1 at the top in 2022).
- `tests/test_steering.py`: fails when uncommitted code changes have no `docs/steering/work_log.md` change.
- `tests/test_season.py` (Record, Luck), `tests/test_form.py` (states, carry-over, home league, league-relative scores, opponent adjustment), `tests/test_forge.py` (ratings, same- and cross-league odds, weights), and the reliability helpers in `tests/test_evaluation.py`, all on synthetic data.
- `tests/test_utils.py` covers CLI year parsing (`parse_years`). There are no tests for the CLI command itself.
- `tests/test_build_site.py`: the site builder without a DB: slugs (including a shared fixture, `tests/js/slugs.json`), player listing, register rows and pages, team rosters, `compact_series`, rendering `player.html.j2` and the roster part of `team.html.j2`, and `players.json` order.
- `tests/js/*.test.mjs`: Node's built-in runner on `site_static/js/names.js` (name folding, `slugify` against the same fixture as Python, search ranking). `tests/test_js.py` runs them under pytest and skips when `node` is missing. DOM code (`search.js`, `rankings.js`, `team.js`) is still checked only in the browser.

## Constraints

- Static hosting only. Anything dynamic must be precomputed at build time or done in browser JS.
- Each CI build re-downloads every CSV from Google Drive. The upstream folder ID is hardcoded in `setup_db.sh`.
- A site build takes about 25 seconds: SQLite reads (each year's games, every game for Record and Form, Elo, about a million player-games), the Form pass over about 200,000 team-games in Python, and writing about 2,000 team pages and 4,900 player pages. The forecast backtest takes about 8 seconds and the season-stat report about 5.
