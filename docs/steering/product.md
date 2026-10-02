# Product

## Vision

Prometheus is a public, browsable stat site for League of Legends esports, similar to FanGraphs or Basketball-Reference. It focuses on **advanced, cross-region, cross-era metrics** rather than raw box scores. It answers questions like "Was 2024 Gen.G better than 2021 FPX?" and "How dominant was this team relative to its league?"

## Audience

- Esports fans and analysts who already know the game and want deeper numbers than a stat dump.
- The author's portfolio. The site is a showcase hosted at **prometheus.thaiv.dev**.

## Metrics (current and planned)

| Metric | Status | What it measures |
|---|---|---|
| **GLORY** (Global League Offensive Rankings Yield) | Shipped | Per-season regression weights on gold/objective rates, applied to team-season averages and scaled to roughly 0–100 |
| **GLORB** (Baseline) | Shipped; sunset planned | Same features as GLORY with equal weights. A comparison baseline for GLORY with little value on its own; see Future work in `current_state.md`. |
| **GLORY+** | Shipped | GLORY with each game's stats adjusted for the opponent's pre-game Elo |
| **Era Z / League Z** | Shipped | Z-scores of a team's score within its year (all major leagues) and within its league |
| **Game-length Elo** | Shipped (forecast) | Elo for every team in every region, where fast wins move ratings more. International games move a shared league offset, so a region's teams rise or fall together. |
| **GlorELO+** | Shipped (forecast) | This season's GLORY+ blended with current Elo on the Elo scale, with a head-to-head win probability |
| **AURA** (Attributable Utility via Role Analytics) | Research | Player win-probability attribution using 10/15/20/25-minute snapshots (see README) |

Season stats (GLORY, GLORB, GLORY+) describe how well a team played and are judged mainly on consistency. Forecasts (Elo, GlorELO+) predict the next game and are judged by the backtest in `scripts/evaluate_metrics.py`.

Scope: season stats cover the 4 major leagues (LCK, LPL, LEC, LCS), 2014 to present; Elo covers every region. Data comes from Oracle's Elixir and refreshes daily via CI.

## Product principles

- **Explain the number.** Every metric page should say what the metric is, how to read it, and what it can't tell you.
- **Comparisons across eras and regions are the point.** UI should make cross-year and cross-league filtering effortless.
- **Static first.** No backend. All interactivity is client-side over JSON embedded in the page.
- **Honest about uncertainty.** Small samples (`minimum_matches`) and known biases (playoff bracket strength, region strength) should be visible, not hidden.

## Known open questions

- Whether GLORY should use logistic rather than linear regression (the README says logistic; the code uses `LinearRegression`).
- Player-level metric design (AURA). The `player_stats` schema exists, and `win_prediction.py` trains an XGBoost win-probability model.
