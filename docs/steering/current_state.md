# Current state

Last reviewed: 2026-10-01 (season stats vs forecasts split). This is a code baseline. Read `db/prometheus.db` or the live site for current rankings.

## Working

- **Data:** Oracle's Elixir CSVs for 2014 to the present, rebuilt from scratch by `scripts/setup_db.sh` and refreshed daily in CI. International events (Worlds, MSI, EWC, First Stand, ...) are ingested as their own leagues (`INTERNATIONAL_LEAGUES`); they are the only games that connect regions.
- **Two families.** Season stats describe a team-season with hindsight and are judged by `scripts/evaluate_season_stats.py` (stability and fit to that season's results; `docs/season_stats_report.md`). Forecasts predict the next game from earlier games only and are judged by `scripts/evaluate_metrics.py` (`docs/metric_backtest.md`). No forecast uses a season stat as input.
- **Season stats** (LCK/LPL/LEC/LCS team-seasons):
  - GLORY: per-year regression weights on gold and objective rates, with every game's stats adjusted for the opponent's full-season Record; about 0–100, with Era Z and League Z. Full-season reliability 0.91; about 8 games to reach 0.5.
  - Record (sunset 2026-10-01; page kept, still GLORY's opponent-strength input): a schedule-adjusted results rating (Bradley-Terry on game-length-weighted results, every league including international events), shown as the chance to beat the average major-league team that year. Reliability 0.89.
  - Luck (sunset 2026-10-01; page kept): wins above what a team's play earned (GLORY's per-game model, calibrated per season). Reliability 0.34, so it is mostly luck; it correlates 0.23 with win %.
  - Sunset (`sunset.html`, linked from the header's Teams menu): Record, Luck, GLORB, GLORY unadjusted (`glory_unadjusted.html`), Form (folded into FORGE), and GLORY+ (folded into GLORY; `glory_plus.html` redirects).
- **Forecasts:**
  - Game-length Elo for every team in every region, built from player ratings: a team's rating is the average of its five starters plus its league offset; new players start at the average of their league's active players (last game within 365 days). League offsets move with cross-league international games. Domestic log loss 0.6319 against 0.6343 for team Elo without players (−0.0024, −0.0045 to −0.0003).
  - Form (Predictive GLORY; sunset as a page 2026-10-02, still FORGE's input and a column on its register): each team's recency-weighted, opponent-adjusted stats before every game, carried over between seasons and shrunk toward average, scored by weights fit to predict the next game, and shown relative to the team's own league in Elo points. Every team in every league. Alone it does not beat Elo (domestic log loss +0.0015, −0.0010 to +0.0040; international +0.0451).
  - FORGE (renamed from GlorELO+ on 2026-10-02; `glorelo_plus.html` redirects to `forge.html`): Elo + Form within a league; Elo alone between leagues. Domestic backtest log loss 0.6291 (64.7% picked) against Elo's 0.6319; international games equal Elo's 0.6295. Weights in `prometheus/forge_weights.json` and `form_weights.json`, written by `--write-weights`; CI refits and warns when a blend weight moves more than 10%.
- **Site:** the header has two menus, **Teams** (GLORY, FORGE, Elo, then Sunset stats) and **Players** (Elo), each listing its stats by name with the question it answers. Home leads with FORGE (head-to-head box and top 10 teams playing now), then the top 10 of Team Elo and Player Elo; the margin lists every stat. One rankings page per metric, a Sunset stats page (including Record and Luck), one page per team (GLORY figure, year rank and season-end FORGE by season; current FORGE and Elo; last roster with player Elo and starters by season and role; Elo history), one page per listed player (Elo after every game, career by team stint, other names), a header search over teams and players (`teams.json`, `players.json`), a name filter on every rankings page, and 404, published daily to https://prometheus.thaiv.dev. Forecast pages open on current ratings for teams active in the last six months; the season picker switches to ratings at the end of each chosen year. The FORGE head-to-head uses Elo alone, with a note, for teams from different leagues.
- **CLI:** `prometheus rankings glory|record|luck|forge|form|glorb` with league filters and years or year ranges (`--year 2021-2023`). Forecasts show now by default, or season-end ratings when years are given.

## Known limits

- Season stats cover only the four major leagues. Whether to extend them is an open product decision (`PRODUCT.md`). Form and Elo cover every league; FORGE shows major-league teams.
- Elo links regions only through international games. League offsets carry those results to every team in a region, but a league that rarely plays abroad still has a weakly measured offset. K=20, a between-season pull to the mean and an international K multiplier were tested and not adopted (see the work log).
- Form doesn't compare across regions (stats in a weaker league look better), so it is league-relative and FORGE falls back to Elo between leagues. FORGE therefore adds nothing over Elo for international games; the old GLORY+-based blend was 0.0007 better there (not significant).
- FORGE ratings mix regions in one table, but only same-league gaps translate directly into odds; cross-league odds come from Elo.
- Form's hyperparameters (half-life 20, carry 0.5, prior 5) were picked on the same backtest that reports them (a coarse 27-point grid; shrinkage barely mattered). Form's opponent adjustment and weights use only earlier or other seasons, but the blend curve's out-of-year fit is the only guard on the hyperparameters.
- Luck's earned win % comes from a linear per-game model; the season calibration removes its pull toward 50%, but Luck still repeats a little (0.34), so part of it is skill the stats miss.
- Record and Luck count games differently: Record counts every game that season (any league), Luck only major-league games.
- The 5-game minimum stays for every season stat, although the report says GLORY needs about 8 games and win % about 16 to reach 0.5 reliability.
- CI only warns when forecast weights drift; someone still has to run `--write-weights` and commit the files.
- A team page's current FORGE (fact line) uses today's Elo and Form, while its season row for this year uses the state after its last game; they can differ slightly.
- The CLI's `--sort-by` applies to GLORY and GLORB only.
- Player Elo moves all five starters together, so it records how a player's teams did and carries it through transfers; it does not split credit within a team. The player register and pages cover 4,854 players (ever in a major league or at an international event, or active in the last two years); past seasons in the register list only major-league player-seasons with 10+ games, to keep the page about 200KB gzipped.
- Each release is about 100MB (4,854 player pages, 2,087 team pages), and every page changes daily (footer date), so each deploy uploads the whole site and keeps a full copy under `releases/`.
- About 1,850 team-games have no opponent row, so they get no Elo; Form counts them as unadjusted and GLORY's adjustment drops them (one team-season, so GLORY lists 603 against unadjusted GLORY's 604).
- The `before` date filter in `get_matches_frame` is exercised only by the backtest, not by its own test.
- e2e tests need a built DB, so they only run locally and in the publish workflow after `setup_db.sh`.

## Future work

- **Series odds.** Best-of-3 and best-of-5 win chances in the FORGE head-to-head box (from the one-game chance, assuming independent games, then checked against past series).
- **Form follow-ups.** Roster continuity from player data (carry more weight into a new season when the roster stays), and a finer hyperparameter search with a held-out period. (Early-game gold, XP, CS and kill diffs at 10/15/20 were tested on 2026-10-01 and gave no significant gain; see the work log.)
- **GLORY weights.** Team-season-level weights (one half's averages → the other half's win %, ridge, out of year) were tested on 2026-10-01 and gave no significant gain (see the work log). Ideas left: per-era standardization, fewer, more stable features, or a target with less luck than win % (for example the other half's Record).
- **Season-stat report centring.** Centre correlations within league-season as well as season, so stats that carry region strength (GLORY, Record) aren't penalised against win %, which averages 50% in every league.
- **Minimum games.** Use the season-stat report to set each stat's minimum (or show a reliability flag) instead of the shared 5-game cut.
- **Player Elo follow-ups.** Version 1 shipped 2026-10-02 (no synergy), with a player register and player pages. Next, each only under the significance rule: (a) familiarity, one fitted bonus that grows with games the five have played together; (b) role weights, team rating as a weighted mean by position; (c) pairwise synergy ratings, heavily shrunk. Also test a rookie start below league average, and pulling inactive players toward their league average. Still to do: individual credit within a team (role weights or AURA), which player Elo cannot give.
- **Release size.** An S3 lifecycle rule for old `releases/` (each about 100MB now), and only rewriting pages whose content changed (the footer date changes every page daily).
- **Elo follow-ups.** Tune the game-length curve (`lower_bound`, `center`). Measure each in the backtest, then refresh the forecast weights.
- **FORGE follow-ups.** Weight recent seasons more when fitting the blend. Extend FORGE to every region (Form already covers them; between leagues it is Elo already); ship only if a backtest on non-major domestic games shows it beats Elo there by more than noise. If it does, Team Elo could become a column on the FORGE page.
- **Betting-odds benchmark.** Collect closing bookmaker odds for past games (one source, de-vigged to win probabilities), join them to `matches`, and score them in the backtest next to Elo and FORGE (accuracy, Brier, log loss, paired bootstrap). The market is the strongest public forecast, so it tells us how close our forecast models get to the best available. Note the source, its coverage by league and year, and its licence before ingesting it.
- **Backtest report.** Add month-cluster bootstrap intervals for accuracy and paired accuracy differences to `evaluate_metrics.py`, so the report shows every interval quoted on the site.
- **Tests.** A fixture-DB test for the `before` filter; run e2e tests against a small fixture DB so they don't need the full download.
- **Cleanup.** Remove the `if __name__ == "__main__":` scratch blocks and move `players.py` off table reflection to raw SQL.
- **AURA.** The player metric: calibrate the snapshot win-probability model, attribute win-probability changes to players by role, and publish player-seasons.
