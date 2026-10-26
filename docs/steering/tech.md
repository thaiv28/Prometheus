# Tech

## Stack

- **Python 3.12+**, managed with **uv** (`uv.lock` is committed; CI uses `uv sync --frozen`).
- **SQLite** at `db/prometheus.db`, built from scratch by `scripts/setup_db.sh`.
- **pandas + SQLAlchemy engine** for reads/writes (raw SQL strings, no ORM).
- **scikit-learn** for GLORY (StandardScaler + LinearRegression). **XGBoost** for the experimental win-probability model.
- **Typer + Rich** for the CLI.
- **Jinja2** static site generation. Vanilla JS + hand-written CSS. Charts are hand-drawn SVG (no chart library). Source Serif 4 is self-hosted.
- **GitHub Actions to S3 + CloudFront** (`.github/workflows/publish.yml`): builds on every PR; deploys on push to `main`, daily at 10:00 UTC, and on manual dispatch. The AWS resources live in `project-platform-infrastructure`.

## Layout

| Path | Purpose |
|---|---|
| `prometheus/` | Python metrics and data access. |
| `prometheus/types.py` | Column enums and feature lists. |
| `prometheus/matches.py` | Raw-SQL stats joins. |
| `prometheus/regression.py` | GLORY: `StandardScaler` + `LinearRegression`, target win. |
| `prometheus/ranking.py` | `get_glory_ranking()`: yearly models, team-season scores and z-scores; published `opponent_adjusted="record"`, retired `"elo"` GLORY+. |
| `prometheus/season.py` | Record and Luck season stats. |
| `prometheus/form.py` | Opponent-adjusted recency-weighted pre-game states; league-relative Form; `form_weights.json`. |
| `prometheus/forge.py` | Within-league Elo/Form blend; cross-league Elo; ratings, head-to-head odds and `forge_weights.json`. |
| `prometheus/elo.py` | Team/player game-length Elo bootstrap and queries for forecasts, rankings and site. |
| `prometheus/schedule.py`, `team_aliases.json` | Leaguepedia schedule, name matching, odds, S3-backed `data/predictions.json` and scorecard. |
| `prometheus/live/archive.py`, `scripts/live_archive.sh`, `prometheus/site/live_results.py` | Compact `*.min.json` backups restored for linked results and per-series figures. |
| `prometheus/live/`, `deploy/live/`, `scripts/live_data.py` | Feed, forecasts, Kalshi, pages, EC2; `deploy/live/cloudwatch-agent.json` ships logs. |
| `scripts/live_markouts.py` | Offline candidate quote markouts. |
| `scripts/research/live_latency.py` | Offline lag/veto study; `docs/research/live_latency.md`. |
| `prometheus/aura.py`, `scripts/evaluate_aura.py` | AURA player season stat; `season_aura`; report `docs/aura_report.md`. |
| `prometheus/gamelog.py`, `scripts/export_market_prices.py` | Series game logs, pre-game calls, `data/market_prices.json` and prediction-log prices; `site.gamelogs.add_game_logs` JSON. |
| `prometheus/main.py` | Typer `prometheus` CLI. |
| `scripts/NNN_*.sql\|py` | Ordered DB build steps. |
| `scripts/download_data.py` | Oracle’s Elixir CSVs; current year/`--full`; newer files only. |
| `scripts/prediction_log.sh` | S3 log restore/save: fail except missing object, reject shrinking logs; `--if-unchanged` prevents concurrent overwrites. |
| `scripts/build_site.py`, `prometheus/site/` | Load once, ordered site parts; `site/config.py` registries, columns, paths/limits; modules read patched config paths at call time. |
| `prometheus/player_tables.py` | Lazy shared `PlayerTables` reads and pandas joins for AURA, Elo history and player logs. |
| `scripts/deploy_site.py` | Hash-changed uploads to bucket `current/`; `deploy/manifest.json`; see `docs/steering/deployment.md`. |
| `scripts/evaluate_metrics.py`, `prometheus/evaluation.py` | Forecast backtests and weight fits; report `docs/metric_backtest.md`. |
| `prometheus/markets.py`, `prometheus/alerts.py` | Kalshi parsing, quotes, aliases, logged prices and saved alert history and execution candidates. |
| `scripts/update_prices.py` | Hourly `prices.yml`: prices, `kalshi.json`, `predictions.json`, saved candidates/alerts. |
| `scripts/research/`, `docs/research/` | Research scripts, reports and tests outside published metrics. |
| `scripts/oneoff/extend_log.py` | `--since` extends logged history using day-before ratings, like the new-log 30-day reconstruction. |
| `scripts/oneoff/backfill_market_prices.py` | `markets.backfill_prices`: last pre-start price for unpriced started matches; marks `backfilled`. |
| `scripts/research/elo_variants.py`, `scripts/research/elo_variants_*.py` | Opt-in margin replay; tune through 2021, evaluate from 2022; `docs/research/elo_variants_*.md`. |
| `scripts/evaluate_live.py`, `scripts/live_bench_data.json` | Weekly CI-rebuilt feed/trade replay (release pin fallback); report `docs/live_report.md`; `--dump` minute-band PR guards. |
| `scripts/evaluate_markets.py` | Calls versus Kalshi pre-match series/map-1 prices and incremental information; report `docs/market_report.md`. |
| `scripts/compare_benchmarks.py`, `scripts/benchmark_comment.sh` | `benchmarks.yml`: paired base/head dumps, regression exit status and sticky PR comment. |
| `prometheus/props.py`, `props_weights.json`, `scripts/evaluate_props.py` | Published player prop distributions; fitted `props_weights.json`; `--write-weights`, `--dump`; report `docs/props_report.md`. |
| `prometheus/prop_lines.py`, `scripts/collect_props.py`, `scripts/prop_data.sh` | Hourly changed Underdog/Pick6/PrizePicks lines in `data/prop_lines.jsonl`; guarded backups with `data/prop_calls.json`. |
| `prometheus/props_live.py`, `prometheus/site/props.py`, `scripts/update_props.py` | Props page/results, build `props-dist.json`, hourly DB-free pricing, frozen calls and `props-lines.json`. |
| `scripts/evaluate_season_stats.py` | Split-half reliability, games to 0.5 and same-season fit; `docs/season_stats_report.md`. |
| `templates/*.html.j2` | Page templates and `_marks`/`_entry` macros; shared rankings driven by column config. |
| `site_static/{css,js,fonts}` | Verbatim copied CSS, vanilla JS and self-hosted OFL Source Serif 4; `tokens.css` colors, league inks and `@font-face`. |
| `PRODUCT.md`, `.impeccable/surfaces/` | Product and visual direction contract; read before UI work. |
| `tests/` | Mocked unit, in-memory integration, sample/full-DB `e2e`, and Node `js/` tests. |

**Build cost.** `get_glory_ranking()` reads/fits per year per call. `build_site.py` shares `load_glory_games()` through `games=` across GLORY qualified/all, unadjusted GLORY, GLORB and Luck, one Record fit through `record=`, and `PlayerTables` across player Elo history, AURA and logs. Reads, Form states, AURA snapshot fits, game logs and roughly 7,000 pages/log files dominate builds.

Site orchestration: `main` loads once, then `render.py` Jinja/small pages, `registers.py` home/rankings, `teams.py`, `players.py`, `predictions.py` page/log/alert and `gamelogs.py`. Tests patch `prometheus.site.config.OUTPUT_DIR`/`PREDICTIONS_LOG` at call time. Templates include `base`, `index`, `rankings`, `predictions`, `team`, `player`, `sunset`, `redirect`, `404`; `_marks` supplies league/signed/ordinal/fixture macros, `_entry` navigation/logs. Assets: `nav.js` menus, `forecast.js` head-to-head, `team.js` Elo SVG, `search.js` header search, `entry.js` logs/section marking with `entry.css`.

## Metric change rules

The full rules `AGENTS.md` summarizes. Benchmark commands:

```bash
uv run python scripts/evaluate_metrics.py --out docs/metric_backtest.md   # backtest forecasts (~8s)
uv run python scripts/evaluate_metrics.py --write-weights   # also refresh Form and FORGE weights
uv run python scripts/evaluate_season_stats.py --out docs/season_stats_report.md   # season-stat stability (~5s)
uv run python scripts/evaluate_aura.py --out docs/aura_report.md   # AURA calibration and player tests (~40s)
uv run python scripts/evaluate_props.py --out docs/props_report.md --write-weights   # prop projections: report and props_weights.json (~18 min; --dump alone ~25 s)
uv run python scripts/evaluate_markets.py --out docs/market_report.md   # our calls vs Kalshi's prices (~2.5 min; first run ~1 h fetching; --reuse rewrites the report in seconds)
uv run python scripts/evaluate_live.py --fetch-data --out docs/live_report.md   # in-game calls vs Kalshi's trades (~8 s; --build-data / --publish-data refresh the pinned data)
```

- **Change a metric only for a significant benchmark gain.** Changes to published metrics must beat the current version on the same games or team-seasons: for forecasts, the paired-bootstrap 95% interval of the log-loss difference on the games the change targets (`evaluate_metrics.py`: domestic, international, cross-league or within other leagues) must exclude 0, resampling whole series (`evaluation.series_ids`: same two teams, games within 12 hours), and none of those sections may get significantly worse; for season stats, a paired bootstrap over team-seasons of split-half reliability or r with the other half's win % (`evaluate_season_stats.py`) must exclude 0, with neither getting significantly worse. Record each tested change and its numbers in the work log either way. Refitting the existing weights on new data (`--write-weights`) is not a metric change.
- **Additions, removals and the forward holdout.** Adding a parameter, feature or step to a forecast also needs a log-loss gain of at least 0.0005 on its target section. Removing one ships without a gain when every guarded section's 95% interval stays below +0.0005 (non-inferiority). Games from `evaluation.FORWARD_START` (2026-10-20) on are an untouched holdout: research tunes and selects only on earlier games; `compare_benchmarks.py` reports them as unguarded forward rows; changes shipped after that date are rechecked once they hold about three months of games.
- **Accuracy fixes follow a lighter rule.** A change that corrects which data a forecast uses, without changing how the metric is computed (a team's home league, which roster stands for a team, a mislabelled league or event), is an accuracy fix, not a metric change. It ships when it is significantly better on the games it affects, by a paired bootstrap on the benchmark that covers them (`evaluate_metrics.py`'s cross-league section, or our calls in `evaluate_markets.py`), and neither domestic nor international log loss gets significantly worse.
- **AURA follows the same rule on player benchmarks** (`evaluate_aura.py`). A change to how AURA is computed (snapshot, features, weights, credit scheme, matchup adjustment) is compared with the current AURA on the same player-seasons and team-seasons, with weights fit on earlier years only and any tuning constant fixed in advance. It ships only when all of these hold: (1) a gain: the paired-bootstrap 95% interval excludes 0 for next-season r of players who changed team, or for split-half reliability, but a split-half gain counts only if the correlation of a player's score with their teammates' in the same game rises by no more than 0.05 (a score that moves with the team becomes stable by restating it); (2) it beats its team-only control (the added part replaced, for every player, by their team's average of it in that game) on the gain it claims, by a paired bootstrap, so the gain is the player's and not the team's; (3) neither split-half nor new-team r gets significantly worse, and the roster test (r with the other half's win %, paired over team-seasons) doesn't either; (4) calibration stays close (ECE under 0.01) for a model that uses only in-game snapshots. A model with end-of-game stats as features is not judged on calibration, because those stats build up for the winner. The substitution test is reported but doesn't decide on its own: teams choose their substitutes, so it is confounded and noisy. Once AURA feeds a forecast (Player Elo, FORGE), that change falls under the forecast rule above, with the backtest's roster-change slice reported.
- **CI enforces the "not significantly worse" half of these rules:** on every PR, `.github/workflows/benchmarks.yml` runs the forecast, season-stat, AURA, market, prop-projection and live (in-game) benchmarks with `--dump` on the base and the head and `scripts/compare_benchmarks.py` fails the check when a guarded value is significantly worse; the `benchmark-override` label is the escape hatch for an intended change (say why in the work log).
- **Forecast weights** live in `prometheus/form_weights.json`, `forge_weights.json`, `league_curves.json` and `props_weights.json` (the prop projections' fitted model; refit with `evaluate_props.py --write-weights`) (Elo's win-curve slope per non-major league) (package data), read by `form.py` and `forge.py`. After a metric or data change, rerun `evaluate_metrics.py --write-weights` and commit both. CI runs `--check-weights` and warns when a blend weight moves more than 10%.

## Data pipeline

```
Oracle's Elixir Google Drive folder
  └─ scripts/download_data.py (gdown, one file at a time) ─▶ data/raw/*.csv   (one CSV per year)
       └─ 001_create_tables.sql  → matches, match_stats, match_players, player_stats, game_length_elo(_player_elo, _league_offsets)
       └─ 002_add_matches.py     → filter/normalize CSVs (keeps international events), append rows (`utils.insert_rows`)
       └─ 003_create_glory.sql   → VIEW match_glory_stats (per-minute rates)
       └─ 004_bootstrap_elo.py   → fill game_length_elo, game_length_player_elo, offsets
  └─ scripts/build_site.py ─▶ output/ (index, glory, record, luck, forge, form, game_length_elo,
                               player_elo, sunset, glory_unadjusted, glorb, glory_plus (redirect), 404, teams/*.html,
                               players/*.html, teams.json, players.json, predictions.html, predictions.json)
       └─ prometheus/schedule.py ◀─ Leaguepedia Cargo API (MatchSchedule ⨝ Tournaments) ─▶ data/predictions.json (the prediction log)
       └─ prometheus/markets.py ◀─ Kalshi public API (open KXLOLGAME markets) ─▶ each upcoming match's `market` price in the log
  └─ scripts/evaluate_metrics.py ─▶ docs/metric_backtest.md (forecast backtest; refreshes forecast weights)
  └─ scripts/evaluate_season_stats.py ─▶ docs/season_stats_report.md (season-stat stability and fit)
  └─ scripts/evaluate_aura.py ─▶ docs/aura_report.md (AURA calibration and player-score tests)
  └─ each with --dump DIR ─▶ scripts/compare_benchmarks.py BASE HEAD (PR check: base vs head, paired)
  └─ scripts/evaluate_markets.py ◀─ Kalshi public API (KXLOLGAME, KXLOLMAP; cached in data/markets/) ─▶ docs/market_report.md (our calls against the prediction market)
  └─ scripts/evaluate_live.py ◀─ data/live_bench/live_maps.json.gz (feed timelines + Kalshi trade tapes; weekly CI rebuild, Actions cache; release pin fallback) ─▶ docs/live_report.md (in-game calls against Kalshi)
```

### Tables

- `matches`: one row per (gameid, teamid): year (calendar year of `date`), date, split, league, teamname, side, gamelength (seconds), result. `002_add_matches.fill_team_ids` fills missing `teamid` from the same name elsewhere in that year's file, else `name:<teamname>`.
- `match_stats`: team totals per game (gold, kills, towers, objectives, firsts, vision).
- `match_players`: each team's five starters per game (gameid, teamid, position, playerid, playername), with the champion and full-game totals (`kills`, `deaths`, `assists`, `cs` = Oracle's Elixir `total cs`); `playerid` falls back to `name:<playername>|<teamid>` (0.7% of rows). Covers every game, unlike `player_stats` (which has no LPL 2025 rows, for want of snapshots).
- `player_stats`: per-player snapshots at 10/15/20/25 minutes, including the lane opponent (`opp_*` columns are always the same-role player on the other team), and the champion. Games without snapshots (Oracle's Elixir "partial" data) are dropped; the 20- and 25-minute columns are NULL when the game ended first. `playerid` uses the same fallback as `match_players`, but AURA joins `match_players` on (gameid, teamid, position) for its ids.
- `match_glory_stats` (view): per-minute and per-10-minute rates used as GLORY features.
- `game_length_elo`: per-game pre/post Elo per team, keyed on (gameid, teamid), with the team's `home_league`, that league's `league_offset` after the game, and `main_elo` (the main roster's rating, used by forecasts).
- `game_length_player_elo`: every rostered starter's rating before and after each game (offset included), keyed on (gameid, playerid). Each team row in `game_length_elo` is the mean of its five rows here.
- `game_length_elo_league_offsets`: each league's combined offset after any game that moved it (gameid, date, league, league_offset).

## Season stats and forecasts

Season stats (GLORY; sunset Record, Luck, GLORB, unadjusted GLORY) describe team-seasons with hindsight, equal game weights and unshrunk samples. `evaluate_season_stats.py` measures random-game-id split-half reliability (Spearman-Brown, games to 0.5), within-season correlation with win %/Record, and other-half win-% correlation.

Forecasts (FORGE, Elo; sunset Form page supplies FORGE) use earlier games, recency and shrinkage, never season-stat outputs; `evaluate_metrics.py` judges them.

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

- **Record** (`get_record`): per year (`matches.year`), a Bradley-Terry model over every game in every league, including international events. Each game is two weighted rows: a win with weight s and a loss with weight 1 − s, where s is the original power game-length score from the team’s side (`elo.power_winner_score`). Record retains this curve independently of the steeper forecast curve. Ridge prior: ratings ~ N(0, `RECORD_PRIOR_SD`² = 1) in log-odds (`LogisticRegression(C=1)`, no intercept). Ratings are centred on the mean major-league team (home league = most-played domestic league that year) and published as `100 · sigmoid(rating)`. The site shows the same team-seasons as GLORY, with GLORY's league label.
- **Luck** (`get_luck`): per year, GLORY's per-game pipeline (unadjusted) predicts each major-league game's result, clipped to [0, 1]. A team-season's raw earned win % is the mean prediction; it is calibrated with a games-weighted linear fit of season win % on raw earned % across that year's team-seasons (the per-game linear model pulls every team toward 50%). Luck = win % − earned, as points and as wins (`luck_wins`).

## Form

`prometheus/form.py`. Per team-game GLORY stats for every league (`load_form_games`), then:

1. `opponent_adjust`: each stat is restated against an average opponent by pre-game Elo, `f − b_opp × (opp_elo − mean)`, with `b_opp` from `f ~ own_elo + opp_elo` fit on earlier seasons only (the first season uses its own games).
2. `form_states`: in date order, each team keeps an exponentially weighted sum of stats (`HALF_LIFE` = 20 games); at a new `matches.year` its sum and weight are multiplied by `CARRY` (0.5). The pre-game state mixes in the season's running average (`PRIOR_GAMES` = 5 games' worth). A missing stat counts as average. Home league is the domestic league the team has played most that season (a cup or international event doesn't change it). Returns pre- and post-game states per row. With `rosters=` (`elo.load_rosters`), the carried state is also scaled by the share of this game's starters who started the team's previous game ** `ROSTER_POWER` (0.5), at every lineup change and at a new season on top of `CARRY` (`ROSTER_AT` "change"; "season" scales only there; `scripts/research/form_roster.py`). `form.load_states()` is what the build, the backtest, the market benchmark and the CLI use: opponent-adjusted games with rosters. Without rosters (unit tests) lineups are ignored.
3. `scores`: state · Form weights (logistic, per unit of stat gap, fit on domestic blue-minus-red pre-game gaps; `form_weights.json`).
4. `league_relative`: score minus the mean pre-game score of the same home league and season through that day.

Form on the site is league-relative Form in Elo points (`FORM_POINTS` = `form_weight / elo_weight` per log-odds unit).

## FORGE

`prometheus/forge.py`. Same home league: P(win) = sigmoid(`ELO_WEIGHT` × Elo gap + `FORM_WEIGHT` × Form gap), so the rating is Elo + `FORM_POINTS` × Form and P = sigmoid(`ELO_WEIGHT` × rating gap). Each league rates on its own scale: `blend_weights(league)` gives the pair (a, b) (the majors' `ELO_WEIGHT`, `FORM_WEIGHT`; every other league the pooled `OTHER_LEAGUE_FORGE_ELO_WEIGHT`, `OTHER_LEAGUE_FORM_WEIGHT`, so per-league pairs can drop in there), the rating is Elo + (b / a) × Form and `forge_ratings` returns a as each row's `slope`. Different home leagues: P = sigmoid(`CROSS_REGION_ELO_WEIGHT` × Elo gap), because Form only compares a team with its own league. `team_forms` gives now and season-end Form per team; `forge_ratings` joins Form with Elo on team name (and year). Weights are fit by the backtest and stored in `forge_weights.json`; `forecast.js` gets `CROSS_REGION_ELO_WEIGHT` and each league's slope (`weights.leagues`, from `site.registers.forge_register`) through the page config. `evaluate_metrics.py --write-weights` refreshes both weight files; `--check-weights` prints every change and warns (GitHub annotation) when a blend weight moves more than `WEIGHT_TOLERANCE` (10%); Form's per-stat weights are printed but never warn, because some are near zero.

## Elo

`EloState.play` resumes the identical replay arithmetic; `to_dict`/`from_dict` round-trip its parameters, tuple keys/rosters and timestamps through JSON (input rosters excluded). `replay_state` retains the final state for export.

`prometheus/elo.py`, replayed in date order by `004_bootstrap_elo.py`. Ratings belong to players. A team's rating is the average of its five starters' ratings (`match_players`) plus its home league's offset. The home league is the non-international league the team has played most this calendar year, with last year's home counting as one game (a tie keeps the current home), so a cup, promotion series or EMEA Masters doesn't relabel it. Each game moves starters by RD²/floor² times the team's K=20 × (actual − expected), where the winner’s "actual" is `0.825 + 0.175 * tanh((1800 - gamelength) / 300)`: near 1.0 for very short games and 0.65 for very long ones, with a midpoint at 30 minutes and a five-minute transition. Explicit `steepness` arguments retain the historical power curve for research; Record calls `power_winner_score` directly. International cross-home games move shared offsets by `LEAGUE_SHARE` (.5). Non-international cross-home games move team-only link offsets (`LINK_SHARE=.5`, `LINK_MODE="team"`), excluded from player conversion. Movers supply compensated offset evidence (`TRANSFER_SHARE=.02`) for `TRANSFER_GAMES=20` destination appearances, including internationals; their own evidence leaves their effective rating unchanged. Selected through 2021 by `scripts/research/elo_offsets.py`. New players start at the league active-player mean (last game in that league within `ACTIVE_DAYS`, 365), or 1500 plus the offset if there are none; a player who changes league keeps their rating. A rookie discount (`ROOKIE_PENALTY` 250, `ROOKIE_GAMES` 200) makes a player count 250 × (1 − log(1 + g) / log(201)) points lower after g games, nothing from 200 games on; it is applied when the team's rating is formed (and in stored player and `main_elo` ratings) but never added to the player's own rating, so a league's average doesn't drift with turnover. A team's `elo_change` includes the fading of its rookies' discount. A player moving from a major (`MAJOR_LEAGUES`) down to another league gains `MOVE_DOWN_BONUS` (25) in their stored rating on top of the offset conversion. `evaluate_metrics.py`'s team-Elo reference (no rosters) runs with RD and the non-major update slope disabled, without rookie or league-move adjustments. Missing rosters reuse the last lineup; without one, the team plays as one player. Each team row also stores `main_elo`: the team's rating with its main roster (the starters of its last game in its home league or at an international event) after the game, so an academy lineup fielded under the team's name at a cup doesn't stand in for the team. `get_latest_elos` and `get_season_elos` use `main_elo` (falling back to `post_match_elo`) and the stored `home_league`, and add each league's offset changes since the team's last game. `compute_elo_records(..., player_records=True)` also returns each starter's ratings, which `bootstrap_elo` stores; `get_player_history` reads them with names, roles and teams, and `get_player_elos` gives each player's current and calendar-year-end rating (offset moves included, as for teams). `get_season_elos` gives every team's rating at the end of each calendar year it played (last game that year plus offset changes through year end), labelled with its most-played domestic league that year. Calendar years override OE `year` (autumn games may use next season).

Glicko-1-style RD (since 2026-10-19): `PLAYER_RD=(280,140,10)` (new, floor, growth per √day), `PLAYER_RD_INFORMATION=.125`. RD² grows by growth² × days away (capped at new²) and shrinks with each game's expected-score information (on that game's update slope) to the floor; a player's move scales by RD²/floor², so settled players keep K 20. No volatility or g(RD). `OTHER_LEAGUE_SLOPE=.0065` is the update's expected-score slope in non-major domestic games only. Tuned through 2021 by `scripts/research/elo_glicko_scale.py`. Frozen research scripts run against `prometheus/elo.py` at 00237c0.


## International forecast calibration

`regional_calibration.py` reads the packaged `regional_calibration.json`: 36 ordered historical snapshots, event boundaries, metadata-only exclusions and coefficient provenance. It never fits, reads the DB or changes Elo's state. Cross-home recognized international fixtures use `sigmoid(slope * Elo gap + regional effect A - regional effect B)`; same-home, domestic and other cross-league calls retain their old method. Effects are ridge-shrunk, zero-sum; ridge 4 and persistent history were chosen through 2021. The scale is fitted with a prior toward the original curve. Only completed older events enter each event-frozen fit; coefficients become available the UTC day after the last training game. Unknown regions have neutral residuals. The artifact retains the last evaluated pre-event fit (through 2026-10-02), not an incomplete current-event refit.

`schedule.game_probability` accepts event/title, forecast time and fixture day; `predict` records version/snapshot/training cutoff on eligible calls. Live, reconstructed, market-backtest and game-log paths share this calibration; native forecast scoring uses `apply_frame` on existing loaded data. Head-to-head embeds today's small coefficient dictionary and explicitly labels a hypothetical international matchup. Old logged calls remain frozen. `REGIONAL_CALIBRATION=0` disables the forecast overlay (rebuild to refresh embedded head-to-head coefficients).

Offline refresh, after the fixed-cohort diagnostic/correction scripts and a private DB: `VECLIB_MAXIMUM_THREADS=1 uv run python scripts/fit_regional_calibration.py`, then `uv run python scripts/research/validate_regional_calibration.py`; run all native benchmark guards before publishing a new artifact. The parity script checks every research map and both market cutoffs; reports are [validation](../research/regional_calibration_validation.md) and [native guards](../research/regional_calibration_benchmarks.md). No new CI job, dependency or runtime model fitting. Tests cover causality, event freeze, UTC boundaries, scope, symmetry, finite probabilities, provenance, kill switch and Python/JavaScript routing.

## Forecast pages

`build_site.py` gives Elo, sunset Form and FORGE registers current (`now`) and season-end rows. Current teams are `active` within `ACTIVE_WINDOW` (183 days); Elo/Form include every team, FORGE active domestic teams. Season sources: `get_season_elos`, last-game Form state, or their combination. Team pages reuse FORGE rows and GLORY with `minimum_matches=1`; Record/Luck stay sunset. `rankings.js` defaults to active now rows; search includes retired teams. FORGE's `leagueScales` groups majors, otherwise one league; search ranks within scales. Home shows major FORGE and all-region Team/Player Elo top tens, bars scaled by `_rating_bar`.

Hourly `fresh.json` carries team/player deltas; `fresh.js` updates current registers, head-to-head and home tables only when its base equals page-config `dataThrough` (newest Elo game datetime). Builds write listed-player `player-slugs.json`; player deltas include league-offset moves, while Form and season rows stay frozen.

Players (`player_pages_and_rows`): listed players have played in a major league or at an international event, or anywhere within `PLAYER_PAGE_WINDOW` (730 days) of the newest game; `dup:` ids are never listed. `player_elo.html` (config `entity: "player"`) has a now row per listed player and season rows for major-league player-seasons with `PLAYER_SEASON_GAMES` (10) or more games. Each listed player gets `players/<slug>.html`: slug from the name, then name plus last team for shared names, then a number. Career rows are stints (consecutive games for one team id). `players.json` feeds the header search with `teams.json`. `team_rosters` gives each team page its last lineup (the five starters of its latest game, by role, with today's player Elo) and its starters by calendar year and role (main starter first, then up to `ROSTER_EXTRAS` = 3 others with games started), grouped by team name like the team pages. `names.js` holds the JS shared by `search.js` and `rankings.js` (`fold`, `slugify`, `rank`); `base.html.j2` loads it before `search.js`. Team and player pages embed their Elo series as `[date, elo]` pairs (`compact_series`).

## Game logs

`prometheus/gamelog.py`, called by `site.gamelogs.add_game_logs` after the team and player pages are built. `load_team_games` reads every team-game with its opponent and Elo; `add_calls` adds the pre-game chance and method (pre-game Elo from `game_length_elo`, pre-game Form from the build's `form_states` made league-relative with `form.league_relative`, then `schedule.game_probability`'s rule: cross-region Elo between home leagues, FORGE within a league (`forge.other_league_forge_probability` outside the majors), Elo on the league's curve (`forge.other_league_weight`) when either team has no Form state); `add_series` groups a team's consecutive games against one opponent within `SERIES_GAP` (12 hours). `series_heads` gives each series its date, league, opponent, score, series chance (game 1's chance through `schedule.series_probability` with the best-of read off the score and `series_rho` of the two home leagues) and Kalshi's price (`PriceBook`: same two teams, start within `MARKET_WINDOW` = 36 hours, nearest; prices from `data/market_prices.json` via `load_prices`, plus prices saved in the prediction log). `load_player_games` merges starters, champions and player Elo from the build's `PlayerTables` (see *Player tables*). `team_logs` and `player_logs` build compact JSON (short keys, empty fields and the default method left out; documented in their docstrings); `year_records` gives each year's series and game record. `site.gamelogs.game_log_context` embeds the newest `GAME_LOG_SERIES` (20) series in the page (`#games-data`) and writes the whole log to `output/games/{teams,players}/<slug>.json` when there are more; `site_static/js/entry.js` renders both, loads the file on "Show every series" or a season jump, and marks the current section in the "On this page" list (`templates/_entry.html.j2`, styles in `site_static/css/entry.css`). `scripts/export_market_prices.py` writes `data/market_prices.json` from `evaluate_markets.py`'s saved `frames.pkl`.

## Player tables

`PlayerTables(method, stats, minutes)` in `prometheus/player_tables.py` lazily reads `roster`, `stats` (champion and SQL-computed `<stat>_<minute>` lane gaps), `elo` and `matches` columns once. SQLite lacks indexes for the `player_stats`/`match_players`/`matches`/`<method>_player_elo` joins; `aura.load_aura_games`, `elo.get_player_history` and `gamelog.load_player_games` merge in pandas. `build_site.py` shares one instance; standalone callers create theirs. `get_player_history` merges from the roster side to retain within-game tie order.

## AURA

`aura.load_aura_games` keeps complete five-starter sides' own−same-role-opponent gold/XP/CS/kills/deaths/assists snapshot gaps. `game_frame` makes blue-game rows (30 role×stat columns); `fit_aura_weights` fits standardized logistic C=1. Intercept+five lane terms gives blue log odds; `player_scores`/`snapshot_scores` assign opposite lane terms to opponents. `get_aura` adds `LATE_WEIGHT`=0.25 times `team_centred` 15→25-minute term change (20 if ended earlier, zero before20): own−four-teammate mean, summing zero/team. Outputs `aura`/`aura_late`. Yearly fits with `earlier_only=True` use prior years, NaN below `MIN_TRAIN_GAMES`.

`season_aura(scored,leagues)` returns major (player,year,role), last name, most-played team/league, games, `POINTS`=25×mean log-odds; ≥`SEASON_GAMES`=20 adds Role Z/rank/count. `site.players.aura_rows_and_seasons` filters listed players: qualified `aura.html` rows (`kind:season`, `entity:player`, symmetric domain, `filters.roles`); all seasons in `aura_seasons` player pages.

`evaluate_aura.py` reports earlier-year-fit calibration from2022 per snapshot; major-player split-half, teammate correlation and next-year stayed/moved correlation versus 15-minute gold/team win%, year/role-centred, `evaluation.paired_correlation_bootstrap`. `held_out` compares earlier-only AURA/15-minute term from2017. `roster_table` sums half-season starter AURA (5-average-game shrinkage, absent zero) over opposite-half lineups, correlating opposite-half win% versus `evaluate_season_stats.glory_stats`, own AURA/win%, paired team-seasons. `substitutions` correlates incoming−outgoing `so_far` (shrunk last50 earlier games, all leagues) with result−Player-Elo expectation for exactly one changed starter; `pregame_gap_r` references those sums across all games.

## Backtest

`scripts/evaluate_metrics.py`/`prometheus/evaluation.py` score blue, win-%-so-far baseline, month-start Elo (`evaluation.elo_as_of`: last pre-cutoff rating plus later home offsets), pre-game Elo/Form/FORGE. Both teams need ≥5 earlier major games that season. Other seasons fit win curves/Form weights (`add_form`); `forge_probabilities` fits same-home Elo/Form, otherwise Elo. Reports: accuracy/Brier/log loss, baseline paired bootstrap, domestic/international separately. No-roster `compute_elo_records` reference compares early-season/≤10-games-since-starter-change slices (`load_roster_context`).

`load_cross_league`/`evaluation.cross_league_games` select differing whole-season most-played domestic homes (selection only, never forecast inputs), all events/leagues: major/major, major/other, other/other; international versus cups/EMEA Masters/promotion. `evaluation.other_league_games` requires both season homes equal the non-major event league. It compares standard 400-point, other-season pooled and per-league curves (`evaluation.out_of_year_league_probabilities`). `evaluation.shrunk_league_slopes` fits through-origin logistic slopes, empirical-Bayes shrunk toward pool using DerSimonian-Laird between-league versus sampling variance. `summarize_other_league_forge` compares both Elo curves with other-season Elo/Form, `out_of_year_form` major-trained stat weights. `published_weights` fits `other_league_elo_weight`, `other_league_forge_elo_weight`, `other_league_form_weight` and `league_curves.json`; `--check-weights` prints all, warns on blends only.

Shared `resamples(units,n_resamples,seed)` yields row/cluster bootstrap positions from one seeded generator; `interval(values)` gives 95% percentiles; `ece(p,won,bins)` calibration error. `paired_bootstrap` takes `clusters=` (series). Users: `paired_correlation_bootstrap`, `compare_benchmarks._rows_bootstrap`, `evaluate_aura.roster_bootstrap`, market ROI/blend intervals.

## Benchmark comparison (PR check)

`--dump DIR` exports report inputs plus `metrics.json`: forecasts `forecasts.csv.gz` (section/forecast/gameid/teamid/year/series/date/won/log loss/Brier/accuracy); season `halves.csv.gz` (stat/team-season/full/h0/h1/n0/n1); AURA held-out `halves`, `moved`, `roster`, per-snapshot `calibration`. Market `calls.csv.gz` includes kind/event/team1/method/major/p/won1, series `cost1`/`cost2` at −12h and `market_close`. `evaluate_markets.py --offline` leaves uncached markets unpriced; `--update-cache` refreshes settled series/map-1 lists/candles without DB in publish.yml's `kalshi-cache` job.

`evaluate_props.py` exports `props/scores.csv.gz`: published settings, fits through 2023, 2024+ major/international per-stat map scores and kills/assists series totals (Bo3 first 2, Bo5 first 3), measure/unit keys (`gameid|playerid` or series-first-map/player), match clusters. `evaluate_live.py` exports `live/calls.csv.gz`: game/checkpoint, series/date/result/shared Kalshi, pregame and last calls ≤1.5min before minutes 5–30; checkpoint −1 is every priced pre-map at −1min. Model cutoff comes from `fit_through`, else last `trained_years`/`calibration_year`; comparison excludes maps through the later cutoff.

`scripts/compare_benchmarks.py BASE HEAD` reads `metrics/`, `season/`, `aura/`, `markets/`, `props/`, `live/`, pairs common keys (duplicates numbered), reports unmatched counts and head−base 95% paired intervals. Forecasts pair games and cluster by series (game-level without series in either dump); forward-holdout rows are unguarded; correlations pair year-centred team-seasons, AURA roster includes both halves; markets pair contracts, props cluster matches, live clusters series. Live bands: pre-map, pregame, early 5–10, mid 15–20, late 25–30, all feed. Market slices: series all/FORGE major/FORGE other/other, map-1 all, using head method.

Exit 2 means comparison error; 1 means significantly worse guarded forecast log loss (FORGE/Elo live domestic/international/cross-league/within-other, per-league Elo and other FORGE), GLORY reliability/other-half r, AURA split-half/new-team/roster r or ECE>0.01, market all-series/FORGE-major/map-1 loss, any prop measure or live band. Constants: `GUARDED_FORECASTS`, `GUARDED_STATS`, `ECE_LIMIT`, `GUARDED_MARKETS`. Missing benchmark is noted/skipped; `TOLERANCE`=1e-6 excludes machine noise. This enforces no regression, not proof of gain.

Report-only `compare_betting` shares legacy `schedule.paper_bets`/`schedule.edge_record`: $1 at −12h on our pick or `BET_EDGES`, 7% fees, CLV=close−cost. Shared series are split all/major FORGE/other by head method/edge; bets, return/$1, CLV, beating-close share and paired return/CLV differences are unguarded. Base borrows missing prices from head; absent both skips.

## Predictions

`site.predictions.update_predictions` calls `prometheus/schedule.py` after Form.

### Schedule and calls

`fetch_schedule` pages `MatchSchedule` ⨝ `Tournaments` by 500: match id, UTC start, teams, best-of, winner/scores, event/league. `_get` backs off 20/40/60/90/120s under anonymous rate limiting, then stops. `schedule.credentials` reads bot `LEAGUEPEDIA_USER`/`LEAGUEPEDIA_PASSWORD` from environment (wins) or local gitignored `.env`. Builds fetch −3/+7 days, −30 for new logs; failure preserves the log. `PREDICTIONS_FETCH=0` skips fetching.

`TeamMatcher` tries `prometheus/team_aliases.json`, exact name, accent/punctuation-folded name, then folding without Leaguepedia's “(… Team)” suffix; latest-active wins ties. Special letters expand as in `names.js`. `event_league` prefers a shared league at its own event, then `EVENT_LEAGUES`, shared home, “Intl” for differing homes, or the known home. `is_major` includes international events or major events with a team from that league.

`team_ratings` joins `get_latest_elos` and Form. `game_probability` uses major FORGE, cross-home `CROSS_REGION_ELO_WEIGHT` × Elo gap, or `forge.other_league_forge_probability` (`OTHER_LEAGUE_FORGE_ELO_WEIGHT` × Elo gap + `OTHER_LEAGUE_FORM_WEIGHT` × Form gap / `FORM_POINTS`). Missing `has_form` uses `forge.other_league_weight(league)`: `league_curves.json`, else `OTHER_LEAGUE_ELO_WEIGHT`. Both blends use method `forge`; legacy `schedule._group` distinguishes major `home1` FORGE from “Other”. International calibration overlays eligible calls as described above.

`series_probability(p, best_of, rho)` mixes independent games over Beta-distributed game chance with mean p/correlation rho (0 means independent). `series_rho(home1, home2)` selects `SERIES_RHO`: 0.054 for two major homes, 0.127 otherwise. `gamelog.series_heads` uses `home`/`opp_home` from `add_calls`; `evaluate_markets.py` uses equivalent `major`.

`fresh.py`/`scripts/refresh_calls.py` resume published Elo with Leaguepedia scoreboards, worker `maps.json`, then schedule maps (last roster, 1,800 seconds). Same-pair/map-number candidates within three hours dedupe in that priority order; worker maps still refresh when Leaguepedia results fail. Export saves three days of OE games; replay greedily pairs each Leaguepedia map with one unused same-team-id OE game within three hours. Unpaired maps over six hours before `data_through` count as known and `stale_skipped`; other unpaired maps replay in time order. Elo deltas shift Elo/FORGE, including international offsets; Form stays frozen. Only future calls refresh, carrying `provisional_games`/`results_through`; `data_through` stays the OE YYYY-MM-DD. Missing inputs, `REFRESH_CALLS=0` or schedule failure preserve the log; result-fetch failure does too without worker maps.

### Saved log, replay and identity

`data/predictions.json` (`PREDICTIONS_LOG`) keys Leaguepedia match ids. `update_log` refreshes pre-start calls (`predicted`, `data_through`), freezes started calls, copies available winner/scores, and reconstructs late-seen/unmatched calls with `RatingsBefore(states)(day)` (earlier Form, Elo through day−1), marked `reconstructed`. `RatingsBefore` caches `ratings_before(states, day)` by day and reads history once through `elo.LatestElos`, equivalent to dated `get_latest_elos(method, date)`. CI backs up the log in S3.

`prediction_backtest.rebuild(log, states)` deep-copies reconstructed calls only, reusing loaded states/one day cache to rebuild close-day/12h odds with current code/weights and causal ratings; unrateable copies become unmatched. `build_site.predictions_pages` writes this page-only replay to `backtest.json` and renders its statistics/results; `predictions.json` exports the original saved log, never replay to backup. Saved forward forecasts remain frozen across model releases.

Alerts pin canonical backed `team`. `schedule.carry_records` preserves terms across side reversal, orients prices, and retains a unique exact team-pair/start/league fixture key across provider-ID changes; ambiguous pairs stay separate. `aligned_result` aligns frozen names. Rescheduling/blank results cannot unfreeze/erase history. `alerts.alert_side` resolves identity for settlement/rendering, falling back to original side for legacy records without `team`.

### Pages and prices

Builds export root `series-links.json` (match ID → series page ID). After hourly save, `scripts/render_predictions.py` fetches it, `backtest.json` and `teams.json` once; renders Predictions, monthly results and call performance without DB. Reconstructed calls use build backtests; others use the refreshed log. Optional refresh-summary coverage; fetch failures preserve pages.

`predictions_view` splits matched upcoming/past entries; `fixture_row` supplies complementary whole-number chances, favourite, names/slugs and result/call by UTC day. Home keeps whole major/international UTC days: first starts within `HOME_FIXTURE_DAYS`=4; `HOME_FIXTURES`=10 caps subsequent days. `schedule.scorecard` reports picks/log loss for saved/reconstructed/all. `schedule.market_scorecard` compares settled pre-start/12h prices with paired intervals from `MARKET_MIN_SERIES`=30. `schedule.edge_record` uses `BET_GROUPS` (FORGE/Elo × saved/rebuilt), `site.predictions.method_groups`, `backtest_span`, and `market_12h` (last quote at least `markets.BET_LEAD` before start). `alert_record` uses `alerts.settled_alerts` for fee-adjusted ROI/CLV. Results cover `RECENT_RESULT_DAYS`=7; `result_months`/`render_results` write `results/YYYY-MM.html`. `predictions.js` localizes/filter fixtures.

After `update_log`, `schedule.attach_market_prices` reads public `KXLOLGAME` markets (one paged request, no key). `TeamMatcher`/`MARKET_ALIASES` match names; `attach_prices` chooses unstarted same-team markets within 18h. `market` stores `p` (mean of team-1 midpoint and complemented team-2 midpoint, spreads ≤0.10), `spread`, `at`, `ticker`. Started prices freeze; rebuilds/errors/`KALSHI_PRICES=0` preserve them. Browser cross-origin requests get 403. `fixture_row` supplies prices/time/URL; `markets.event_url` builds the Kalshi link.

Hourly `scripts/update_prices.py` (`prices.yml`) uses only the log and one open-market fetch; `TeamMatcher` covers logged teams. It attaches prices, runs `alerts.update`, saves, and emits `kalshi.json` (`markets.prices_file`: read time, rated matches from two days back, both chances, quote time/URL, and `ours`, the current call of each unstarted match) and `predictions.json` (`markets.published_log`). Builds also emit `kalshi.json`. `predictions.js` fetches no-store and updates `data-match` rows' caret, prices/link, tooltips and local-time caption, and unstarted calls from `ours`. Issue team links use live `teams.json`.

`site.alert_history.history_view` reads saved calls, resolves `alerts.alert_side`, and uses `settled_alerts` for first-ask fees/profit/CLV, `alert_record(..., key=)` for summaries/intervals. Domestic/international/minor picks include pending/unresolvable records without invented settlement. `predictions_pages` and hourly `update_prices.run` render `alerts.html`; hourly upload requires `saved=true` and retains its five-minute cache.

### Alerts, blend and execution

`alerts.select` requires matched/rated FORGE/Elo, known homes, valid probability, same-run executable ask, positive after-fee blended edge and ≥6h lead across `forecast_groups`; settled/missing-results guards apply. `alerts.record` freezes terms/team/forecast/group/`alert_contract.identity` before notification. `alerts.notified` exposes domestic/legacy international records read-only; archived unposted `paper_alert` may qualify anew at current terms. No historical backfill/legacy rewrites. Public issue posting stopped. `international_paper_alert` retains first terms/model snapshot and identity settlement via `schedule.ALERT_KEYS`; see [research](../research/international_alerts.md).

`forecast_groups.classify` uses known homes/actual international event scope independently of method. `schedule.edge_record` accepts grouping callbacks with legacy benchmark/test defaults. `site.call_performance` keeps raw thresholds; Table III uses blended net edge. Detail history shares `paper_bets` inputs/settlement without extra forecasts/DB/refit/fetch.

Stdlib `market_blend.py` loads packaged `market_blend.json`: `logit(p)=market_slope*logit(mid)+gap_slope*(logit(raw)-logit(mid))`. Monthly snapshots require ≥300 earlier results, availability start+24h; missing snapshot/midpoint prevents blending. Offline `scripts/fit_market_blend.py --input <rebuilt.csv> --available-through YYYY-MM-01` pins input SHA256; columns: unique event_ticker, decision, result_available, p, market, won. `site.render.render_market_blend` emits fixed `market-blend.html` from artifact metadata; Blend, Predictions notes and Call performance link there. No runtime fitting or DB read.

`trading.quote` shares five-group scope/probability/side/$1 fees with `site.trading`. Early quotes must be observed by start−12h, never closing inputs. Table III divides profit by stake+fees, publishing from 30 observations; saved/reconstructed sources stay separate, raw scorecards/alert ledgers retain their definitions. Signal returns precede personal vetoes.

`trading.quote(..., execution_fees=True)` calls executor stdlib `core.fee_bound` with `ALERT_FEE_RATE=0.07`, `ALERT_BALANCE_PRECISION=0.0001`; `alerts.select`/`alerts._current` opt in, default paper fees remain. Decimal subtraction precedes float conversion. `alerts.record` deep-copies optional new `fee_policy` (version, rate bound, balance precision, unit fee). Fee-setting changes need coordinated public-profile updates. Publishers make no account calls; fee import excludes API/signing adapter.

Stdlib `alert_contract.saved_candidates` adapts private `execution_candidate` forecasts (≤3h, unstarted, no future timestamp) into both sides with the current available blend snapshot. Fresh-price writers mark eligible fixtures independently of `KALSHI_ALERTS`, edge and lead; IDs share legacy alert fixture fences. `saved_alerts` remains compatible. `validate_alert` applies identity/group/veto/start/probability guards; candidates bypass alert activation/age and original-ask limits. One bulk market fetch screens canonical two-outcome, narrow two-sided quotes for positive after-fee edge and maximum price before full resolution; filtered/duplicate candidates never write skips. Full books refresh raw/snapshot against the backed midpoint and retain execution probability/net edge. Cloud9 and anti-NA international vetoes remain. Reconciliation posts private fill issues through optional Secrets Manager credentials and revision-safe `notified` marking; public issue workflows stopped. Private account/fill/skip data never enters public predictions. See [execution setup](../kalshi_execution.md).

### Sizing and release control

Decimal `execution.sizing.kelly_order` maximizes per-order expected log growth with price/conservative fee bound, zero and two 0.01-grid neighbours of the continuous optimum. `QUANTITY_STEP`=0.01; `core.plan_order` retains Decimal depth/cap divisions until flooring, compares route growth within cash/strategy/order/fixture/day/exposure/depth limits, shrinking to feasible caps. Strategy seed/fraction are explicit, never account-balance defaults. Counts/API counts are fixed two-decimal strings; optional `quantity_step` records grid; `max_contracts` stays a positive whole ceiling. `kelly-v1` supports old whole intents/funding checks; whole-unit fee bound scales because q/0.01 bounds minimum fills for either account precision.

Consistent ACCOUNT/UTC DAY reads precede sizing. Free capital=seed+realized−held; fraction scales it. Reserve checks observed held/realized and total funding atomically. Settlement derives payout from verified own fill count/outcome (scalar rounded down), subtracts actual cost/fees, and transactionally adds ACCOUNT.realized profit delta with intent revision/held release; retries cannot double-credit. Gross daily spend stays separate. This is sequential cash allocation, not joint correlated-portfolio Kelly; no new table/index/service/dependency. See [Kelly details](../kalshi_execution.md#kelly-bankroll-and-activation).

`deploy/execution/release.py` hashes isolated sources, artifact, handler, package script/requirements and canonical literal aliases without site imports; deterministic zip entries omit local timestamps. `deploy.py` preserves deployed template/non-release parameters, rejects current package drift before writes, no-ops matching sources, uploads checksum-keyed version-pinned private object, waits/verifies runtime. `control.configure` allowlists risk fields, validates complete active config but persists off; activation requires healthy matching Lambda source/package tags. OFF is independent; no runtime loop/model/DB/site change.

### CLI, backfill and benchmarks

`prometheus predict [--days N] [--league X] [--major]` prints upcoming odds without log writes. `scripts/oneoff/extend_log.py --since` fetches/caches monthly schedules and uses `update_log` to extend rebuilt history. `scripts/oneoff/backfill_market_prices.py` calls `markets.backfill_prices` for started unpriced entries, matching like `attach_prices`; last two-sided hourly pre-start quote (spread ≤0.10, both averaged) records `backfilled: True`, candle-end `at`, reusing `data/markets/` lists/candles and fetching missing data serially. Elo margin experiments: [research index](../research/README.md), `docs/research/elo_variants_*.md`.

`scripts/evaluate_markets.py` reads public settled `KXLOLGAME`/`KXLOLMAP` live/historical endpoints; parses event/teams/Eastern start from rules (day-only→midnight). `TeamMatcher`/`MARKET_ALIASES` resolve names. `RatingsBefore`/`game_probability` rebuild calls; games within one day supply best-of/result checks. Hourly candlestick midpoint uses more-traded contract (both if cached), last pre-start/12h candle, spread ≤0.10. It reports series/map-1 paired loss (`evaluation.paired_bootstrap`), logit `combined_weights`, calibration, exact-start common-cohort 0/6/12/18/24h ladder, and `alert_leads_section` at 12/24/36/48/72h using earlier-day `call_at` and >5-point ask edge. `$1` bets at 12h back our pick or 0/3/5/10-point value edges; `bets`/`bet_clv` report fee-adjusted ROI intervals and closing chance−cost. `markets.fetch_fee_rates` uses `/series` quadratic taker 7%×`fee_multiplier`, maker only when charged; fallback 7%/no maker. `saved_calls`/`saved_section` reread `--log` (default `data/predictions.json`), exclude reconstructed/unsettled/unpriced calls, compare `p_series`/`market.p` close and `market_12h.ours`/`.p` by FORGE major/other/Other, intervals from 10. `--reuse` uses `data/markets/frames.pkl`; candles cache in `data/markets/candles/`, serial fetch avoids bursts. macOS uses `VECLIB_MAXIMUM_THREADS=1` to avoid BLAS stalls.

`scripts/evaluate_live.py` replays `timeline.timeline_calls`/`timeline.MODEL_PATH` over minute feed samples against `KXLOLMAP` trades; `EloBefore` indexes each team's pre-UTC-day DB Elo once. Weekly CI/local `--build-data` fuzzy-matches teams (ignoring generic words)/map/time, selects feed `blue_id` else nearest OE game, rejects feed tower-winner/settlement disagreement. Trades use `/historical/trades` before cutoff, `/markets/trades` after; `data/live_bench/trades/` caches. Samples store prices at time/+21s lag, last-trade age, side costs within 120s, +2min price, preceding-minute trades/implied spread, and `score_before`. `premaps` uses `match_oe_game` (nth pair game in event window, matching result), −12/−1min prices, side costs within 10min and start price. `data/live_bench/pre_trades/` holds half-hour tapes separately; full-map cache may substitute. `--publish-data` uploads hash-named gzipped `live-bench-data` release asset and pins `scripts/live_bench_data.json`; `--fetch-data` verifies hash. `docs/live_report.md` reports minute/lag losses, blend weight, quiet-market flat/quarter-Kelly bets after taker fees, gap/trading/spread and pre-map loss/bets/CLV; intervals resample series.

## Player props (research)

Published `prometheus/props.py` is scored by `scripts/evaluate_props.py` (`docs/props_report.md`); research background: [index](../research/README.md).

`load_prop_games` uses raw sqlite3 through the engine for starter/game rows from `match_players`, opponent/pre-game Elo. `games_from_tables` uses build-shared `PlayerTables.totals/roster/matches` without Elo. `add_series` groups consecutive same-opponent games at 12h and numbers maps. `add_stat_states(g, settings)` computes pre-game EW rates on integer keys: league-role pace (`PACE_HALFLIFE`=400 rows), pace-shrunk player, and league-shrunk team/opponent `t_<stat>`/`o_<stat>` (kills made/conceded or minutes, 5 prior games), reusing each required half-life. (Half-life, prior) settings: kills (8,10), assists (16,10), deaths (32,3), CS (4,3). Live uses all historical games for rare-league paces. `series_start_states` copies first-map states across series.

Per-stat Poisson regression uses scaled logs of player/team/opponent/pace rates, role dummies, result/result×role to predict win/loss means; moment negative-binomial dispersion varies by stat/role/result. `p_map` mixes results, else logistic Elo (`PropModel.win_chance`). Pick6 fantasy (3 kills+2 assists−deaths+0.02 CS) uses normal result distributions with role/result residual SD. `series_pmf`/`series_normal` sum first `maps` over best-of result sequences, conditionally independent maps, unplayed zero. Plain-number `prometheus/props_weights.json` (`PropModel.to_dict`, `load_model`, `evaluate_props.py --write-weights` all-game refit) prevents build fitting. `game_log_score` directly scores map negative-binomial mixture for CI.

`prop_lines.py` normalizes Underdog `v1/over_under_lines` multipliers/implied probabilities; Pick6 `decode_turbo_stream` React Router cards (first home group, others `/events/LOL/<group>/<competition>`, arbitrary competition id, kills only); PrizePicks partner API league 121 (no combinations; demons/goblins over only). Unoffered sides have no multiplier. Hourly `scripts/collect_props.py` appends new/`CHANGE_FIELDS`-changed lines/time to `data/prop_lines.jsonl`. `scripts/prop_data.sh` guards shrinking backups by nonblank JSONL count/object keys, using original path format even for temporary files; `tests/test_prop_data.py` exercises real shell/local S3 stand-in with shorter/equal/growing files.

`props_live.fixtures_from_log` accepts rated upcoming list or match-id map. `project_fixtures` appends synthetic latest-lineup starter rows after all games for current `add_stat_states`, applies `props.load_model` win/loss means and FORGE/Elo `p_map`. `match_lines` folds player names among 180-day actives, prefers latest team matching app abbreviation/initials/name, then team fixture±12h. Shared `price_line`/`price_lines` gives over/under/push across line maps (Bo capped), offered-side pick/edge against `BREAK_EVEN`=1/√3 (3× two-pick entry), adjusted by multiplier, plus Underdog implied edge. `update_calls` freezes `source|line_id` at start; `settle_lines` uses date-window `series_totals` once/match side, void if player absent. `scorecard` reports hit/log loss and Underdog log loss.

Build `spread_table`/`compact_cdf` writes starter name/team/match and CDFs (0.05% tails, four decimals) to `props-dist.json` for maps 1–2/1–3, one for Bo1. DB-free hourly `scripts/update_props.py` uses `table_fixtures`/`table_index`, `price_from_table`/`cdf_chances` (build-equivalent rounded cells), is sole calls writer, and emits `props-lines.json` via `site.props.lines_payload`; `props.js` overlays built `_props.html.j2` `line_cell` markup.

`site/props.py` considers all rated matches, retaining `FIXTURE_LEAGUES` major/international or matched lines. Per stat/starters it shows median/10–90 range over line maps (default Bo5 first3/Bo3 first2), last10 mean×maps and app cells (PrizePicks standard first). It reads `PROP_CALLS=data/prop_calls.json`/`PROP_LINES=data/prop_lines.jsonl` without writing. `result_rows` groups match/player/stat app lines/picks/right/missed/push/void; `RECENT_RESULT_DAYS` stays on page, `render_prop_results` writes `props-results/YYYY-MM.html`. `build_site.props_page` fails the build on error; absent pick probabilities render no pick.

## Testing

`tests/test_*.py` mock data access; `tests/integration/conftest.py` supplies in-memory SQLite. `pyproject.toml` sets `testpaths=["tests"]`, `e2e` and `research` markers (`tests/research/conftest.py`); both run by default, selectable with `-m`. CI runs all before downloads, then full-DB `-m e2e`.

`tests/e2e/conftest.py` runs numeric `scripts/[0-9]*` on `tests/fixtures/oe_sample/` (every 24th 2017/2022 major/Worlds game plus Cloud9 Challenger, 702KB; `tests/fixtures/make_oe_sample.py` regenerates). `PROMETHEUS_E2E_DB=real` or a path selects an existing DB. `test_ranking_e2e.py` checks league/minimum filters; `test_before_filter_e2e.py` checks exclusive `before=` in `get_matches_frame`, `load_form_games`, `load_season_games`, `get_glory_ranking`; `test_elo_history_e2e.py` checks inclusive `get_elo_history(date=)` days.

`test_steering.py` requires work-log changes with uncommitted code. Offline synthetic/mocked tests cover metrics (`test_season.py`, `test_form.py`, `test_forge.py`, `test_aura.py`, `test_evaluate_aura.py`, `test_evaluation.py`), props (`test_props.py`, `test_prop_lines.py`, `test_props_live.py`, `test_props_site.py`), schedule/history (`test_schedule.py`, `test_prediction_history.py`), builders/logs (`test_build_site.py`, `test_gamelog.py`), live replay (`test_evaluate_live.py`), paired guards (`test_compare_benchmarks.py`), CLI years/weights (`test_utils.py`, `test_main.py`), and manifest/upload ordering/cache headers (`test_deploy_site.py`: CSS/JS year+immutable, fonts 30 days, including full upload).

`tests/js/*.test.mjs` uses Node's built-in runner for shared `names.js` folding/slugs/search/`esc`/`leagueMark`; `tests/js/slugs.json` is shared with Python. `test_js.py` skips without Node. DOM `search.js`/`rankings.js`/`team.js` still require browser checks. `test_trading.py` covers chronology, symmetry, no raw fallback, scope, immutable inputs, notification veto independence and all-in returns. `test_execution_sizing.py` covers exhaustive 0.01-grid optimality, fees/caps/depth, races, depletion, fragment rounding and exactly-once own-profit; `test_execution.py` covers failures/concurrency/partial fills/pause and whole-intent reconciliation. Release/control tests cover parameter preservation, versions/checksum/drift, active-edit rejection and old-code activation.

## Research scripts (not part of the build)

Opt-in experiments and their reports/tests are indexed in [`docs/research/README.md`](../research/README.md); scripts live in `scripts/research/`, tests in `tests/research/` (marker `research`). The persistent regional-correction experiment supplies the separately validated international calibration artifact described above; published live-model training/freezing is described under Live service.

## Constraints

- Static hosting only. Anything dynamic must be precomputed at build time or done in browser JS.
- `scripts/download_data.py` downloads only the current year's CSV from Google Drive when `data/raw` has the rest (every year's with `--full`), and keeps the old file unless the new one parses and has newer games. The upstream folder ID is hardcoded there.
- `002_add_matches.py` reads only `COLUMNS`; it and `bootstrap_elo` use `utils.insert_rows` (DB-API `executemany`, NaN → NULL). Input files are sorted.
- `tests/test_alerts.py`, `test_alert_history.py`, `test_forecast_groups.py`, `test_call_performance.py`: five-group blended notification policy and boundaries, first terms/identity and legacy notification compatibility, archived unposted records, issue/history/report rendering and current-model replay separation. `test_alert_contract.py` checks pinned execution identity; `test_execution.py`, `test_execution_api.py`, `test_execution_runner.py` cover mocked exchange/atomic-ledger failures and private runner/control boundaries.
- `tests/test_download_data.py`: which Drive files `download_data.py` fetches (current year, last year in January, all with `--full` or when one is missing) and when a download replaces the old file (only with newer games; never a refused or broken one). `tests/test_schedule.py` covers `missing_results`, and `tests/test_alerts.py` skipping a call whose ratings lack a team's settled result.
- `tests/test_update_prices.py`: one hourly run on a temporary log with a fake Kalshi book (prices, the alert, `kalshi.json` and `predictions.json`), and a run with no markets.
- `tests/test_markets.py`: backfilling started matches, matching open Kalshi markets to the log (team order swapped, thin quotes, a start too far off, map markets, started matches, an unmatched team) and parsing open markets.
- `tests/test_evaluate_markets.py`: Kalshi rules parsing (Eastern time, maps, day-only starts, a colon inside the event name), grouping contracts into matches, quotes from candlesticks (live and historical field names), the market chance from both contracts with the spread cut, series results from our games, value bets with their profit and CLV, and `combined_weights` on synthetic data; no network.


## Live pages

`render_live` (`prometheus/site/predictions.py`) redirects `live.html` to Predictions and builds `watch.html?match=<id>`; `LIVE_STREAMS`/`LIVE` (`site/config.py`) supply streams/notes, Watch selects its own capped major/international fixtures through the four-day horizon. Service publishes `live/index.json`, `live/<id>.json`, finished `live/<match>/map<n>.json`; builds never write them. `scripts/live_demo.py` provides four preview matches.

Pages fetch no-store every 2s with matches, 60s idle/missing (403/404 means none), 15s on errors; hidden tabs pause. Watch reads selected match without stream delay; `match.maps` picker/`?map=N` loads finished maps once. Overview/strip show latest index values. Match selection (strip/fullscreen Match select) switches official league stream unless co-streaming; selecting an official stream selects its live league match.

`live/index.json` has `{schema, published_at, note, matches:[...]}`; entries: `id`, pattern-restricted `url=live/<id>.json`, `league`, `event`, `best_of`, `teams:[{name,code}]`, `score`, `status`, optional `start`, and latest `game` (`number`, `blue`, `clock`, `at`, `pregame:{p,by}`, `clock_estimate`, `call`, `market`, `teams`, `winner`, `ended_at`). Completed matches leave; empty means idle.

Format, schema 1 (all times ISO 8601 UTC; every chance is for `match.teams[0]`, in 0–1; any number may be `null`):

| Field | Meaning |
|---|---|
| `schema`, `published_at` | Format version; when the collector wrote the file (the page calls it stalled after 45 s) |
| `status` | `waiting`, `live`, `paused`, `between_games`, `idle` (no game: the page shows the next fixtures) or `unavailable` |
| `note` | Optional line shown in the status ("Research preview."; "Karmine Corp won map 4."; the demo labels itself here) |
| `final` | `true` on a finished map's own file |
| `match` | `id`, `league` (picks the default stream), `event`, `best_of`, `teams` (`[{name}]`, Oracle's Elixir names, linked through `teams.json`), `score` (getLive's, plus maps Kalshi has settled that it hasn't counted), `series` (`ours`, `by`, `kalshi` `{at, bid, ask}`, `kalshi_url`), `maps` (`[{number, url, winner}]`, finished maps' files, then `{number, current: true}`) |
| `game.number`, `game.id`, `game.blue` | Map number, source game ID, index of the team on blue side |
| `game.pregame` | `{p, by, market}`: the call before the map (FORGE) and Kalshi's last map price before it started (`{at, bid, ask}`) |
| `game.calls` | `[{minute, p, by, at}]`: the in-game model's calls, the newest per estimated minute (`minute` is estimated game minutes) |
| `game.frames` | `[{at, clock, teams: [{gold, kills, towers, dragons, barons, inhibitors}] × 2}]`: the feed's totals, oldest first; `clock` is game seconds when verified, else `null`; `clock_estimate` is the estimated game time (below), which the figure then uses so a pause takes no width |
| `game.market`, `game.market_url` | `[{at, bid, ask}]`: Kalshi's map market (`KXLOLMAP`) for the first team, from the map's start (a deciding map has no map market: the series market stands in); quotes wider than 10 points are skipped. `market_url` is the market's page on Kalshi: both Kalshi rows in the odds link to it, and so does the bid and offer |
| `game.winner`, `game.ended_at` | Shown only once `ended_at` is released |


### Live results

`live-results/YYYY-MM.html` redirects to monthly results; Predictions Table III covers seven days. Main publish's `scripts/live_archive.sh` lists `$DATA_BACKUP_BUCKET/prometheus/live/`, downloads uncompacted `pages/map<n>.json`, and uploads `prometheus/live/archive.py` `compact` output beside it (again on `archive.SCHEMA` changes). Compact traces retain changed calls, Kalshi mids at spread≤0.10 and 30s gold leads on the `live_state.js` `axis`; `archive.backfill` flags missing-Kalshi minute-candle fills. `archive.series_record` writes `series.min.json` with feed map starts, settled winners and minute-before map/series prices. Compact files, `results.json`, `forge.json` sync to `data/live/`; failure warns only.

`site/live_results.py` joins saved log by pair/first-map start±12h, aligns chances/results to log team order via `fixture_row`, and shows unlogged matches without pre-series call. Every map gets build-time `figure` SVG or “Not recorded”; winners prefer `results.json`, then map, then series winner for last map. `live-results/<match id>.html` (`live_series.html.j2`) contains figures and pre-map Table I score/map chance/series chance/Kalshi prices. Map chance uses logged `p_game`, else `forge.json`; `live.series.series_chance` uses its `rho`. Month rows' `data-href`/`href` open via `predictions.js`. `live_results.js` redraws `data-trace` at page width with pointer/arrow inspection. `live_data.map_files` skips `.min.json`.

### Live service (`prometheus/live/`)

Single-threaded `python -m prometheus.live.service --fetch [--s3 s3://<bucket>/current/live]`:

- `service.py` discovers every 60s through `esports-api.lolesports.com` `getLive`/public `requests.SITE_API_KEY` (the schedule omits in-progress). Mapping tries Riot-ID aliases `prometheus/live/team_aliases.json`, exact `output/teams.json` name, unique slug, unique folded name, then without trailing Esports/Gaming; else skip. Tracking waits for feed `gameMetadata`/`feed_sides` blue/red; getLive may show previous sides. Resumes retain selected sides; `pin_order`/`data/live/<match>/teams.json` retain first-seen match order for results/FORGE/quotes/score.
- `feed.py`/`collector.py`/`requests.py` poll Riot's `window/<game>` 0.5 s after each 10 s boundary (`feed_slot`), from now−30s floored (400 if <20s ago; 204 draft). Single-writer SQLite `data/live/<match>/<game>/collector/`; resumes handle duplicate/stale/pause/terminal. No retries; 401/403/429 exits 3.
- `start.py`/`timeline.py` binary-search first 2,500/2,500-gold frame after first gold (~10 requests). Estimated clock subtracts flat combined-gold stretches after two minutes from source elapsed time; unverified.
- `timeline.py`/`page.py` retain newest call/estimated minute with dated DB `game_length_elo` at selection. `service.Forge` reloads `schedule.current_ratings`/`game_probability`/`series_probability` every 6h for pregame/series; `series.py` conditions beta-binomial on score/current map call. From map 2, `series.map_shift`/`series.map_prior` apply Beta posterior-mean log-odds update from pre-series p/`series_rho`; `service.Game.score_before` subtracts current map if counted, with no shift while winner unknown. `quality.timeline_model.series_shift` records shift.
- `kalshi.py` discovers open `KXLOLMAP`/`KXLOLGAME` each minute until matched by exact/`markets.MARKET_ALIASES` teams, map and Eastern date in `rules_primary`. Books poll every 2s: team-0 YES bid=best YES, ask=1−best NO. Settled map contracts populate `results.json`; deciding map uses series contract, ahead of getLive score. Series winner is recorded at required wins; `idle` leaves index 30min after final frame. Kalshi 401/403/429 disables Kalshi alone.
- `service.record_map` saves settled winners, timing and players from normalized collector journal frames to match `maps.json`, including restart catch-up and archived collectors. `notify.py` uploads it immediately and dispatches prices (five-minute debounce; cached SSM token).
- `service.Ratings` reads `data/live_inputs.json` from `scripts/export_live_inputs.py`: `current_ratings` fields passed unchanged to `game_probability`, latest `game_length_elo.post_match_elo`; absent export computes locally from DB.
- Cycles write match files/index of files <60s old, untouched idle; `--s3` syncs `--delete`, `Cache-Control: max-age=1` when tracking/index changes. `--idle-exit N` exits 4 after N idle minutes. Finished map-picker files remain; evidence requests/collector/quotes pack as `archive.tar.gz` (~1/18 size). Match `calls.jsonl` journals published calls.

`prometheus/live/data.py` `load_maps(root)` reads finished `<match>/pages/map<n>.json` after `scripts/live_data.py pull`, or `output/live/<match>/map<n>.json`, into `LiveMap`: `frames` (receipt/source times, `clock_estimate`, match-order `<stat>_0`/`<stat>_1`, `gold_lead`), `calls`, `market` with `mid`, `pregame`, `series`, `teams`, `blue`, `winner`. Pull unpacks archives once. `scripts/live_wake.py` `due(matches, now)` picks feed-league log fixtures starting within 75min or started ≤4h without result.

### Waiting fixtures, lifecycle and cadence

`service.waiting_pages` keeps the earliest undecided fixture/league in −4h/+75min, excluding leagues with an undecided tracked match. Pages carry start and FORGE/Kalshi series odds via `forge.json`/`series_quotes.jsonl`; books poll once/interval, misses retry every five minutes; excluded files disappear.

Optional scheduled `start` flows through pages/summaries. Live Coming up hides canonical pair matches (either order; start±12h when present) only for `live`/`between_games`; older workers omit start. Hiding persists per page session after completion, including empty days/section. Watch retains whole-section idle behavior. Seven-day `output/live/lifecycle.json` uses existing schedule/discovery/scores; completion survives empty indexes/shutdown. Completed recordings link Watch until daily archive replaces rows.

With tracked Kalshi games, quotes/publication target 2s; `Game.add_quotes` updates last page between ten-second feed/settlement/journal/model cycles without collector/model replay. Idle/Kalshi-disabled cycles retain feed interval; slow requests/uploads extend polling cycles.

### Local live-candidate research

See [candidate review](../research/live_candidates.md) and [research index](../research/README.md) for `cand_objectives.py`, `cand_draft.py`, `cand_map_elo.py`, `cand_temporal.py`, `cand_followups.py`; outputs stay local in `data/research/live_followups/`, without participant collection/production inference. Live-map trading and Kelly research (`scripts/research/live_trading.py`, [protocol](../research/live_trading_protocol.md), [report](../research/live_trading.md)), FORGE anchor/calibration (`scripts/research/live_anchor.py`, [report](../research/live_anchor.md)), draft v3 (`scripts/research/live_draft_v3.py`, [report](../research/live_draft_v3.md)) and the failed draft-v2 trading comparison (`scripts/research/live_map_draft.py`, [evidence](../research/live_map_draft_trading.md)) write only under gitignored `data/research/`.

### Objective/momentum inference

`timeline.MODEL_PATH` selects `time_model_objectives_v1.json`/`time_objectives_momentum_v1`: v1 gold gap/share, Elo gap, time/two interactions, plus blue−red towers/dragons/Barons/inhibitors/kills/dragons>=4 proxy gaps and time interactions, and three-minute gold momentum/time interaction (20 inputs). `freeze_live_objectives.py` reproduces offline training/calibration, checks every test prediction against dependency-free runtime; `fit_through=2025-06-30` excludes fitted maps from PR scores. Original v1 training is `scripts/research/train_time_model.py` on gol.gg gold graphs.

`timeline_calls` uses latest valid gold at/before estimated t−180s, else zero momentum. Missing/non-integer/negative objective counts fall back to frozen `time_model_v1.json`; pre-map always v1. Service/benchmark share model; calls record schema, page quality schema/version. No runtime fit/DB/network/cadence change. Dragon threshold is not verified soul; inhibitors are raw counters, not buffs.

### Refresh ordering and incomplete counters

Publisher `After=prometheus-live-refresh.service` requires post-step `systemctl --no-block try-restart` to avoid circular wait, retaining changed-code/data condition. Delayed timestamped side-discovery windows avoid default-endpoint late 204s. Aggregate/player kill mismatch retains candidate with null `totalKills`/field reason; missing counters trigger v1 fallback. Other field/freshness/identity failures reject.

Offline `tests/live/` covers feed/collector/pages/start/clock/Kalshi/series/mapping/settlement/index/data/wake; `tests/live/test_live_archive.py` covers archive. `tests/js/live_state.test.mjs` covers release/clock/axis/quotes/formats/order/paths/summaries; `test_build_site.py` covers pages/streams/demo.

### Live-map execution

`live_map.py` is a stdlib-only pinned model, blend and entry contract; `live_map_blend.json` holds the earlier-only monthly fits (refit offline with `scripts/fit_live_map_blend.py`, optional `--as-of`; parity replay `scripts/research/replay_live_map_policy.py`). `live.signals` reconstructs unshifted inputs through opt-in `timeline_calls(include_inputs=True)`, which pins the exact source frame; the default page and benchmark path is unchanged. Both contracts supply a 30-second normalized trade tape. Private immutable S3 candidate bytes precede an SQS pointer to the existing Lambda (`deploy.execution.live_handler`), which revalidates the originals and current rules, trades and books. Rating dates are normalized to explicit UTC; physical map identity is canonical teams + UTC scheduled start + map number, separate from the exchange-event fence.

`execution.ledger` adds a SERIES held update to each new reserve, with transactional partial-fill and settlement releases; shared ACCOUNT/DAY records and account-snapshot conditions prevent double funding. Legacy intents reconcile without new metadata; an old series fence without series tracking blocks map entry. Nested controls default off; shadow proposes without reservations or credentials. Live maps have their own budget, `live_maps.budget_usd`: `core.map_budget` reads the ledger's `LIVE_MAPS` row (held, realized), `plan_order` caps a map order at budget + realized − held, and `DynamoLedger.reserve` adds to that row in the same conditioned transaction; `replace` moves held and realized there on fills, releases and settlements. Loss can't exceed the budget; profit extends it. The runtime has no draft route. See [contract and rollout](../live_map_execution.md).

### Draft shadow

`live.draft_export.History` makes one chronological SQL pass over rosters, results and pre-match Elo, exporting player–champion experience, 60-day champion-role residuals, same-role matchup and champion-role pair residuals, and alias/catalog lookups (schema `draft_history_v2`; a snapshot excludes the whole UTC day named in `as_of`), inside the normal live-input export. `page.build_state` keeps metadata changes as `game.draft_observations`. `live.draft.prepare` resolves all ten identities, computes the frozen draft shift on the FORGE map prior and freezes a context at the first complete receipt (bounded by when model and history loaded); later contradictions set an invalid-from time, and `draft_context.json` persists it, keyed by artifact fingerprint and game ID. Unknown identities or a day mismatch keep the base model. `time_model_draft_v2.json` (`time_objectives_draft_v2`, base artifact embedded) is used by `timeline_calls(..., draft=context)` only while ready and valid; the worker replays it separately as `draft_shadow` in the private call journal, leaves public calls unchanged, and disables it when the parent differs. `prepare_draft_benchmark.py` enriches a separate data file with API metadata; `evaluate_live.py --model` selects a supported runtime artifact (default `timeline.MODEL_PATH`).
