# Product

## Vision

Prometheus is a public, browsable stat site for League of Legends esports, similar to FanGraphs or Basketball-Reference. It focuses on **advanced, cross-region, cross-era metrics** rather than raw box scores. It answers questions like "Was 2024 Gen.G better than 2021 FPX?" and "How dominant was this team relative to its league?"

## Audience

- Esports fans and analysts who already know the game and want deeper numbers than a stat dump.
- The author's portfolio. The site is a showcase hosted at **prometheus.thaiv.dev**.

## Metrics (current and planned)

| Metric | Status | What it measures |
|---|---|---|
| **GLORY** (Global League Offensive Rankings Yield) | Shipped (season stat) | How well a team played: per-season regression weights on gold/objective rates, applied to team-season averages of stats adjusted for each opponent's full-season Record, scaled to roughly 0–100 |
| **Era Z / League Z** | Shipped | Z-scores of a team's GLORY within its year (all major leagues) and within its league |
| **Record** | Sunset (still used inside GLORY) | What a team achieved: schedule-adjusted, game-length-weighted results over the season, as the chance to beat an average major-league team |
| **Luck** | Sunset | Wins above what a team's play earned (GLORY's per-game model, calibrated per season) |
| **Game-length Elo** | Shipped (forecast) | Elo for every team in every region, built from player ratings (team = average of its five starters), where fast wins move ratings more on a fixed steep curve around 30 minutes (winner evidence 0.65–1). International games move a shared league offset, so a region's teams rise or fall together. Release 2026-10-15: separate international forecast calibration learns remaining regional errors from completed earlier events; ratings stay unchanged. New players count lower (2026-10-08: within other leagues −0.0139 log loss, cross-league −0.0208), since 2026-10-12 on a log curve over 200 games; players back from time away move faster, and players moving down from a major gain 25 points (2026-10-12 together with roster-aware Form, all seasons: cross-league −0.0075, within other leagues −0.0017, domestic and international unchanged). |
| **Market blend** | Prepared (trading forecast) | Symmetric logistic blend of the raw series forecast and Kalshi midpoint; fixed C=1, monthly fits using earlier completed series. Used for five-group fee-aware alert selection and a separate page register, never raw FORGE/Elo scores. Method and limits have a dedicated `market-blend.html` page. Exploratory returns are not established live profitability; [validation](../research/market_blend_validation.md). |
| **Live market blend** | Prepared, disabled (2026-10-18) | Earlier-series-only monthly blend of unshifted live model and last-trade price; 30-second stability and 5-cent after-fee edge. Private shadow/IOC implementation with capped Kelly; historical tape gains do not establish executable profitability. [Review](../live_map_execution.md). |
| **Player Elo** | Shipped (player rating) | Every player's game-length Elo: all five starters move by the team's change, and the rating follows the player through transfers. Records how a player's teams did, not credit within a team. |
| **Form** (Predictive GLORY) | Sunset (still used inside FORGE) | Recent, opponent-adjusted gold/objective stats weighted to predict the next game, relative to the team's league, in Elo points. Alone it predicts no better than Elo within a league and worse between leagues; its page stays up under Sunset stats. |
| **FORGE** (Form + Elo; was GlorELO+) | Shipped (headline forecast) | Elo + Form within a league, Elo between leagues, with a head-to-head win probability. Release 2026-10-15: international-only regional forecast calibration, broad 2022+ LL −0.0175 (series-cluster −0.0272 to −0.0075); major-v-major gain and Kalshi comparison remain uncertain. Beats Elo domestically (log loss −0.0027, −0.0038 to −0.0015); equals it internationally. Inside non-major leagues (own weights, 2026-10-06) beats Elo on each league's curve (−0.0018, −0.0025 to −0.0011). Since 2026-10-12 Form forgets part of a team's stats when its lineup changes (FORGE within other leagues −0.0012 held out). |
| **GLORY+** | Folded into GLORY | GLORY adjusted by opponents' pre-game Elo; `glory_plus.html` redirects to GLORY |
| **GLORY (unadjusted)** | Sunset | The original GLORY with no opponent adjustment; page kept on Sunset stats |
| **GLORB** (Baseline) | Sunset | Same features as GLORY with equal weights. On its own it predicts no better than win % so far. Its page stays up under Sunset stats. |
| **Prop projections** | On the site (`props.html`, 2026-10-12); not yet tested against lines | A player's kills, assists, deaths, CS and fantasy points in a map and over a series' first maps, as a distribution: recent player, team and opponent rates, mixed over a win and a loss by the Elo win chance. Each stat has its own half-life (kills 8 games, assists 16, deaths 32, CS 4). Beats the player's last 10, season and league-role averages on 2024+ major and international games (`docs/props_report.md`). The Props page sets it beside Underdog, PrizePicks and Pick6 lines and keeps a record from 12 Oct 2026. |
| **In-game win chance** (gold, Elo, objectives and momentum) | Release prepared 2026-10-17; live research preview | Fixed 2024 feed fit, Jan–Jun 2025 calibration; gold lead/share, pre-series Elo, raw objective gaps and three-minute gold momentum, with time interactions (`time_model_objectives_v1.json`). Held-out feed maps: −0.0136 log loss (−0.0170 to −0.0100) versus v1; ECE 0.0182. Estimated clock, 0–40 minutes. V1 stays for pre-map calls and unavailable objective counters; series shift remains. [Release validation](../research/live_model_release.md); no prospective edge claim. |
| **AURA** (Attributable Utility via Role Analytics) | Shipped (player season stat) | Each player's share of the team's win chance at 15 minutes, from their gaps to the lane opponent (gold, XP, CS, kills, deaths, assists), plus a quarter of their change to 25 minutes beyond their teammates'. Shown per major-league player-season (20+ games) in win-chance points per game, with Role Z and role rank. Calibrated; follows a player to a new team better than lane gold or win % (`docs/aura_report.md`). |

Season stats (GLORY; sunset: Record, Luck) describe a team-season with hindsight and are judged on stability and fit to that season's results (`scripts/evaluate_season_stats.py`). Forecasts (FORGE, Elo; sunset: Form) predict the next game from earlier games only and are judged by the backtest (`scripts/evaluate_metrics.py`). No forecast takes a season stat as input. A metric changes only when its benchmark improves significantly over the current version on the games the change targets, with no section significantly worse (see the rule in `AGENTS.md`).

Each published stat answers one question: GLORY, how well did a team play this season? FORGE, who wins if two teams play today? Team Elo, how strong is a team now, judged by its results? Player Elo, how have a player's teams done across a career? AURA, how much did a player's own play swing their team's chances? The header's Teams and Players menus and the home contents show these questions next to the names.

Predictions (2026-10-03) put the forecasts to work on real fixtures: every scheduled match between two rated teams (schedule from Leaguepedia) gets each team's series chance, saved before the match and scored against the result. It is a use of FORGE and Elo, not a new metric. The market benchmark (`docs/market_report.md`, 2026-10-04) judges it against Kalshi's prices: in major leagues FORGE ties the market a day out but trails it at the close (late news); in other leagues and across leagues the market is clearly better.

Scope: season stats cover the 4 major leagues (LCK, LPL, LEC, LCS), 2014 to present; Elo, Form and FORGE cover every region (FORGE ratings on each league's own scale). Data comes from Oracle's Elixir and refreshes daily via CI.

## Product principles

- **Explain the number.** Every metric page should say what the metric is, how to read it, and what it can't tell you.
- **Comparisons across eras and regions are the point.** UI should make cross-year and cross-league filtering effortless.
- **Static first.** No backend. All interactivity is client-side over JSON embedded in the page.
- **Honest about uncertainty.** Small samples (`minimum_matches`) and known biases (playoff bracket strength, region strength) should be visible, not hidden.

## Known open questions

- Whether GLORY should use logistic rather than linear regression (the README says logistic; the code uses `LinearRegression`). Form already uses logistic weights.
- AURA's open design questions: how to credit junglers and supports beyond their lane, and whether to adjust for champion matchups.
