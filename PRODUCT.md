# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary visitors are **League of Legends esports fans and analysts**. They already know the teams, leagues, and the game, and they come to look up rankings and settle arguments. Typical questions are "Was 2024 Gen.G better than 2021 FPX?", "How dominant was this team in its region?", and "Who's actually the strongest team right now?" They come back to it as a reference tool.

The secondary audience is **portfolio viewers**: recruiters and peers looking at the author's work. They need the methodology to be legible and credible, but they are not the primary design target.

## Product Purpose

Prometheus is "sabermetrics for LoL esports." It turns raw Oracle's Elixir match data into advanced team metrics that can be compared across eras and regions, and publishes them as a fast static site at prometheus.thaiv.dev (plus a CLI). Success means a fan can find a team-season, see how it ranks, and understand why, without reading the source code.

## Positioning

Most LoL stat sites dump per-game box scores. Prometheus instead fits **per-season models** that weight gold and objective rates by how much they actually drove wins in that meta (GLORY), so a 2015 team and a 2024 team are each scored against their own era. It then normalizes within year (Era Z) and within league (League Z). The game-length Elo adds a schedule- and opponent-strength view that box scores can't give.

## Operating Context

- Fully static site. It's rebuilt daily by GitHub Actions from the latest Oracle's Elixir CSVs and deployed to prometheus.thaiv.dev (S3 + CloudFront on the thaiv.dev platform).
- All interaction is client-side over JSON embedded in each page: filtering by year and league, team search, sorting, and URL-shareable filter state.
- Pages: home, one rankings page per metric, listed in the header's two menus, **Teams** (GLORY, FORGE, Team Elo) and **Players** (Player Elo), each stat shown with the question it answers; the home page leads with FORGE (head to head and top teams), then Team Elo and Player Elo. A Sunset stats page lists retired metrics (Form, Record, Luck, GLORB, unadjusted GLORY, GLORY+ folded into GLORY), one page per team and one per listed player, each with history charts. A header search jumps to any team's or player's page.
- Visitors arrive on desktop and on phones (for example, links shared in Discord or Reddit threads), so wide tables must work on small screens.

## Capabilities and Constraints

- **Metrics:** GLORY (regression-weighted, opponent-adjusted team score, roughly 0–100, with Era Z and League Z), Game-Length Elo (shorter wins move ratings more; built from player ratings), Player Elo (each player's rating, following them through transfers), and FORGE (Form + Elo, formerly GlorELO+: Elo plus Form, recent stats against the team's league, with a head-to-head win probability); sunset: Form as a page of its own (still FORGE's input), Record (schedule-adjusted results, still GLORY's opponent-strength input), Luck (wins above what play earned), GLORB, unadjusted GLORY, GLORY+. Season stats describe a team-season with hindsight and are judged by stability (`scripts/evaluate_season_stats.py`); forecasts predict the next game from earlier games only and are judged by the backtest (`scripts/evaluate_metrics.py`). AURA (a player metric that would split credit within a team) is still research and not on the site.
- **Coverage:** the site should cover **all regions** present in the data. The Elo page already does. GLORY and GLORB are currently fit and shown for the four major leagues (LCK, LPL, LEC, LCS) only. *Open decision:* how or whether to extend GLORY and GLORB to all regions.
- Data spans 2014 to the present.
- There's no backend, no accounts, and no user-generated content. Anything dynamic is precomputed at build time.
- Stack: Python and Jinja2 static generation, hand-written CSS, and vanilla JS (no build step). Team charts are hand-drawn SVG.
- Terminology: "team-season" (a team in a given year), "split," "major leagues," and the league codes (LCK, LPL, LEC, LCS, …).

## Brand Commitments

- Name: **Prometheus**. Metric names and acronyms are fixed: GLORY (Global League Offensive Rankings Yield), GLORB (Global League Offensive Rankings Baseline), AURA (Attributable Utility via Role Analytics).
- Data attribution to Oracle's Elixir must stay visible.
- The current visual look is explicitly **not** binding. A full redesign is approved.

## Evidence on Hand

- Real rankings for every team-season from 2014 to the present, plus Elo history for about 1,480 teams (all generated from the DB).
- Methodology write-up in `README.md`.
- There are no testimonials, press mentions, or usage numbers. Don't invent any.

## Product Principles

1. **The table is the product.** Rankings must be fast to scan, sort, filter, and share.
2. **Explain every number.** Each metric says what it measures, how to read it, and what it can't capture.
3. **Cross-era, cross-region comparison is the point.** Make it effortless.
4. **Be honest about uncertainty.** Surface sample-size thresholds and known biases instead of hiding them.
5. **Static and fast.** No backend, and pages should load instantly on a phone.
