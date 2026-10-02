# Current state

Last reviewed: 2026-10-01 (season stats vs forecasts split). This is a code baseline. Read `db/prometheus.db` or the live site for current rankings.

## Working

- **Data:** Oracle's Elixir CSVs for 2014 to the present, rebuilt from scratch by `scripts/setup_db.sh` and refreshed daily in CI. International events (Worlds, MSI, EWC, First Stand, ...) are ingested as their own leagues (`INTERNATIONAL_LEAGUES`); they are the only games that connect regions.
- **Two families.** Season stats describe a team-season with hindsight and are judged by `scripts/evaluate_season_stats.py` (stability and fit to that season's results; `docs/season_stats_report.md`). Forecasts predict the next game from earlier games only and are judged by `scripts/evaluate_metrics.py` (`docs/metric_backtest.md`). No forecast uses a season stat as input.
- **Season stats** (LCK/LPL/LEC/LCS team-seasons):
  - GLORY: per-year regression weights on gold and objective rates, with every game's stats adjusted for the opponent's full-season Record; about 0–100, with Era Z and League Z. Full-season reliability 0.91; about 8 games to reach 0.5.
  - Record: a schedule-adjusted results rating (Bradley-Terry on game-length-weighted results, every league including international events), shown as the chance to beat the average major-league team that year. Reliability 0.89.
  - Luck: wins above what a team's play earned (GLORY's per-game model, calibrated per season). Reliability 0.34, so it is mostly luck; it correlates 0.23 with win %.
  - Sunset (`sunset.html`, linked from the header): GLORB, GLORY unadjusted (`glory_unadjusted.html`), and GLORY+ (folded into GLORY; `glory_plus.html` redirects).
- **Forecasts:**
  - Game-length Elo for every team in every region, with league offsets moved by cross-league international games.
  - Form (Predictive GLORY): each team's recency-weighted, opponent-adjusted stats before every game, carried over between seasons and shrunk toward average, scored by weights fit to predict the next game, and shown relative to the team's own league in Elo points. Every team in every league.
  - GlorELO+: Elo + Form within a league; Elo alone between leagues. Domestic backtest log loss 0.6319 (64.6% picked) against Elo's 0.6345; international games equal Elo's 0.6297. Weights in `prometheus/glorelo_weights.json` and `form_weights.json`, written by `--write-weights`; CI refits and warns when a blend weight moves more than 10%.
- **Site:** home, one rankings page per metric (Season stats: GLORY, Record, Luck; Forecasts: GlorELO+, Form, Elo), a Sunset stats page, one page per team (GLORY with a GLORY/Record figure switch, year rank, Record, Luck and season-end GlorELO+ by season; current GlorELO+ and Elo; Elo history), a header team search (`teams.json`), a team-name filter on every rankings page, and 404, published daily to https://prometheus.thaiv.dev. Forecast pages open on current ratings for teams active in the last six months; the season picker switches to ratings at the end of each chosen year. The GlorELO+ head-to-head uses Elo alone, with a note, for teams from different leagues.
- **CLI:** `prometheus rankings glory|record|luck|glorelo+|form|glorb` with league filters and years or year ranges (`--year 2021-2023`). Forecasts show now by default, or season-end ratings when years are given.

## Known limits

- Season stats cover only the four major leagues. Whether to extend them is an open product decision (`PRODUCT.md`). Form and Elo cover every league; GlorELO+ shows major-league teams.
- Elo links regions only through international games. League offsets carry those results to every team in a region, but a league that rarely plays abroad still has a weakly measured offset. K=20, a between-season pull to the mean and an international K multiplier were tested and not adopted (see the work log).
- Form doesn't compare across regions (stats in a weaker league look better), so it is league-relative and GlorELO+ falls back to Elo between leagues. GlorELO+ therefore adds nothing over Elo for international games; the old GLORY+-based blend was 0.0007 better there (not significant).
- GlorELO+ ratings mix regions in one table, but only same-league gaps translate directly into odds; cross-league odds come from Elo.
- Form's hyperparameters (half-life 20, carry 0.5, prior 5) were picked on the same backtest that reports them (a coarse 27-point grid; shrinkage barely mattered). Form's opponent adjustment and weights use only earlier or other seasons, but the blend curve's out-of-year fit is the only guard on the hyperparameters.
- Luck's earned win % comes from a linear per-game model; the season calibration removes its pull toward 50%, but Luck still repeats a little (0.34), so part of it is skill the stats miss.
- Record and Luck count games differently: Record counts every game that season (any league), Luck only major-league games.
- The 5-game minimum stays for every season stat, although the report says GLORY needs about 8 games and win % about 16 to reach 0.5 reliability.
- CI only warns when forecast weights drift; someone still has to run `--write-weights` and commit the files.
- A team page's current GlorELO+ (fact line) uses today's Elo and Form, while its season row for this year uses the state after its last game; they can differ slightly.
- The CLI's `--sort-by` applies to GLORY and GLORB only.
- About 1,850 team-games have no opponent row, so they get no Elo; Form counts them as unadjusted and GLORY's adjustment drops them (one team-season, so GLORY lists 603 against unadjusted GLORY's 604).
- The `before` date filter in `get_matches_frame` is exercised only by the backtest, not by its own test.
- e2e tests need a built DB, so they only run locally and in the publish workflow after `setup_db.sh`.

## Future work

- **Series odds.** Best-of-3 and best-of-5 win chances in the GlorELO+ head-to-head box (from the one-game chance, assuming independent games, then checked against past series).
- **Form follow-ups.** Roster continuity from player data (carry more weight into a new season when the roster stays), 15-minute snapshot stats (gold, XP and CS at 15) as features, and a finer hyperparameter search with a held-out period.
- **Minimum games.** Use the season-stat report to set each stat's minimum (or show a reliability flag) instead of the shared 5-game cut.
- **Elo follow-ups.** Pull ratings back only for teams with big roster changes (needs player data), and tune the game-length curve (`lower_bound`, `center`). Measure each in the backtest, then refresh the forecast weights.
- **GlorELO+ follow-ups.** Weight recent seasons more when fitting the blend.
- **Betting-odds benchmark.** Collect closing bookmaker odds for past games (one source, de-vigged to win probabilities), join them to `matches`, and score them in the backtest next to Elo and GlorELO+ (accuracy, Brier, log loss, paired bootstrap). The market is the strongest public forecast, so it tells us how close our forecast models get to the best available. Note the source, its coverage by league and year, and its licence before ingesting it.
- **Backtest report.** Add month-cluster bootstrap intervals for accuracy and paired accuracy differences to `evaluate_metrics.py`, so the report shows every interval quoted on the site.
- **Tests.** A fixture-DB test for the `before` filter; run e2e tests against a small fixture DB so they don't need the full download.
- **Cleanup.** Remove the `if __name__ == "__main__":` scratch blocks and move `players.py` off table reflection to raw SQL.
- **AURA.** The player metric: calibrate the snapshot win-probability model, attribute win-probability changes to players by role, and publish player-seasons.
