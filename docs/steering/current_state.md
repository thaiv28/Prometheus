# Current state

Last reviewed: 2026-10-01. This is a code baseline. Read `db/prometheus.db` or the live site for current rankings.

## Working

- **Data:** Oracle's Elixir CSVs for 2014 to the present, rebuilt from scratch by `scripts/setup_db.sh` and refreshed daily in CI. International events (Worlds, MSI, EWC, First Stand, ...) are ingested as their own leagues (`INTERNATIONAL_LEAGUES`); they are the only games that connect regions for Elo.
- **Season stats** (describe how well a team played, LCK/LPL/LEC/LCS only):
  - GLORY: per-year regression weights on gold and objective rates, scored on team-season averages, about 0–100, with Era Z and League Z.
  - GLORB: GLORY's stats with equal weights.
  - GLORY+: GLORY with every game's stats adjusted for the opponent's pre-game Elo.
- **Forecasts** (predict the next game):
  - Game-length Elo for every team in every region. Each rating includes a league offset that cross-league international games move (half of the team's own change), so a region rises or falls together; new teams start at their league's level.
  - GlorELO+: this season's GLORY+ blended with current Elo on the Elo scale, with a head-to-head win probability. Weights live in `prometheus/glorelo_weights.json`, written by the backtest (`--write-weights`); CI refits them on every build and warns when one moves more than 10%.
- **Backtest:** `scripts/evaluate_metrics.py` computes every metric as of the start of each month and scores how well it predicts that month's games (accuracy, Brier, log loss, paired bootstrap against win % so far), separately for domestic and cross-region international games. Latest results in `docs/metric_backtest.md`.
- **Site:** home, one rankings page per metric (grouped in the header and contents as Season stats and Forecasts), one page per team, and 404, published daily to https://prometheus.thaiv.dev.
- **CLI:** `prometheus rankings glory|glorb` with league and year filters.

## Known limits

- Season stats cover only the four major leagues. Whether to extend them is an open product decision (`PRODUCT.md`).
- Elo links regions only through international games. League offsets carry those results to every team in a region, but a league that rarely plays abroad still has a weakly measured offset. K=20, a between-season pull to the mean and an international K multiplier were tested and not adopted (see the work log).
- GLORY's weights are fit to explain each game's own result, so GLORY describes rather than predicts. In the backtest it only slightly beats plain win %, and GLORB does not beat it.
- GlorELO+ beats Elo on log loss for domestic games, but its accuracy edge over Elo is not significant, and it ties Elo on international games (−0.0030, interval crosses 0).
- CI only warns when the GlorELO+ weights drift; someone still has to run `--write-weights` and commit the file.
- Team pages do not show GLORY+ or GlorELO+.
- The CLI does not offer GLORY+ or GlorELO+.
- The backtest's "Elo (as of cutoff)" uses each team's rating after its last game, without league-offset changes since then, so it slightly understates the published rating.
- About 1,850 team-games have no opponent row, so they get no Elo and are left out of GLORY+ (for example Gamers2 in 2015).
- The `before` date filter in `get_matches_frame` is exercised only by the backtest, not by its own test.
- e2e tests need a built DB, so they only run locally and in the publish workflow after `setup_db.sh`.

## Future work

- **Sunset GLORB.** Add a "Sunset stats" link (a section in the header and home contents, or a page of its own) and move GLORB there. Explain why: GLORB was built as a comparison baseline for GLORY, and on its own it adds little. In the backtest it predicts no better than win % so far. Keep its page and data so old links keep working.
- **Predictive GLORY.** Fit GLORY-style weights on each team's stat averages *before* a game to predict that game (logistic regression, shrunk toward multi-year weights, previous-season weights early in a season). Ship it as a separate forecast stat, judge it with the backtest, and try 15-minute snapshot stats (gold, XP and CS at 15) as features.
- **Stability check.** For each season stat and win %, correlate odd-game and even-game halves of each team-season, apply Spearman-Brown, and find the games needed to reach r = 0.5. Use the result to replace the 5-game minimum and to tell readers when a score means something. Needs `get_glory_ranking` to score an arbitrary set of games.
- **Elo follow-ups.** Pull ratings back only for teams with big roster changes (needs player data), and tune the game-length curve (`lower_bound`, `center`). Measure each in the backtest, then refresh the GlorELO+ weights.
- **GlorELO+ follow-ups.** Weight recent seasons more when fitting the blend, show a team's GlorELO+ on its team page, and consider a series (best-of-3/5) probability in the head-to-head box.
- **Betting-odds benchmark.** Collect closing bookmaker odds for past games (one source, de-vigged to win probabilities), join them to `matches`, and score them in the backtest next to Elo and GlorELO+ (accuracy, Brier, log loss, paired bootstrap). The market is the strongest public forecast, so it tells us how close our forecast models get to the best available. Note the source, its coverage by league and year, and its licence before ingesting it.
- **Backtest report.** Add month-cluster bootstrap intervals for accuracy and paired accuracy differences to `evaluate_metrics.py`, so the report shows every interval quoted on the site.
- **CLI.** Add GLORY+ and GlorELO+, and year ranges (`2021-2023`, the TODO in `main.py`).
- **Tests.** A fixture-DB test for the `before` filter; run e2e tests against a small fixture DB so they don't need the full download.
- **Cleanup.** Remove the `if __name__ == "__main__":` scratch blocks and move `players.py` off table reflection to raw SQL.
- **AURA.** The player metric: calibrate the snapshot win-probability model, attribute win-probability changes to players by role, and publish player-seasons.
