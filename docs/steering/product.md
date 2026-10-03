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
| **Game-length Elo** | Shipped (forecast) | Elo for every team in every region, built from player ratings (team = average of its five starters), where fast wins move ratings more. International games move a shared league offset, so a region's teams rise or fall together. |
| **Player Elo** | Shipped (player rating) | Every player's game-length Elo: all five starters move by the team's change, and the rating follows the player through transfers. Records how a player's teams did, not credit within a team. |
| **Form** (Predictive GLORY) | Shipped (forecast) | Recent, opponent-adjusted gold/objective stats weighted to predict the next game, relative to the team's league, in Elo points |
| **GlorELO+** | Shipped (forecast) | Elo + Form within a league, Elo alone between leagues, with a head-to-head win probability |
| **GLORY+** | Folded into GLORY | GLORY adjusted by opponents' pre-game Elo; `glory_plus.html` redirects to GLORY |
| **GLORY (unadjusted)** | Sunset | The original GLORY with no opponent adjustment; page kept on Sunset stats |
| **GLORB** (Baseline) | Sunset | Same features as GLORY with equal weights. On its own it predicts no better than win % so far. Its page stays up under Sunset stats. |
| **AURA** (Attributable Utility via Role Analytics) | Research | Player win-probability attribution using 10/15/20/25-minute snapshots (see README) |

Season stats (GLORY; sunset: Record, Luck) describe a team-season with hindsight and are judged on stability and fit to that season's results (`scripts/evaluate_season_stats.py`). Forecasts (GlorELO+, Form, Elo) predict the next game from earlier games only and are judged by the backtest (`scripts/evaluate_metrics.py`). No forecast takes a season stat as input. A metric changes only when its benchmark improves significantly over the current version (see the rule in `AGENTS.md`).

Scope: season stats and GlorELO+ cover the 4 major leagues (LCK, LPL, LEC, LCS), 2014 to present; Elo and Form cover every region. Data comes from Oracle's Elixir and refreshes daily via CI.

## Product principles

- **Explain the number.** Every metric page should say what the metric is, how to read it, and what it can't tell you.
- **Comparisons across eras and regions are the point.** UI should make cross-year and cross-league filtering effortless.
- **Static first.** No backend. All interactivity is client-side over JSON embedded in the page.
- **Honest about uncertainty.** Small samples (`minimum_matches`) and known biases (playoff bracket strength, region strength) should be visible, not hidden.

## Known open questions

- Whether GLORY should use logistic rather than linear regression (the README says logistic; the code uses `LinearRegression`). Form already uses logistic weights.
- Player-level metric design (AURA). The `player_stats` schema exists, and `win_prediction.py` trains an XGBoost win-probability model.
