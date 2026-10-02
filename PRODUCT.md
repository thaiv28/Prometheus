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
- Pages: home, one rankings page per metric, grouped as season stats (GLORY, GLORB, GLORY+) and forecasts (GlorELO+, Game-Length Elo), and one page per team with history charts.
- Visitors arrive on desktop and on phones (for example, links shared in Discord or Reddit threads), so wide tables must work on small screens.

## Capabilities and Constraints

- **Metrics:** GLORY (regression-weighted team score, roughly 0–100), GLORB (equal-weight baseline), Era Z and League Z (z-scores), GLORY+ (GLORY adjusted for opponent Elo), Game-Length Elo (shorter wins move ratings more), and GlorELO+ (a forecast rating blending GLORY+ and Elo, with a head-to-head win probability). Season stats describe how well a team played; forecasts predict the next game and are judged by the backtest in `scripts/evaluate_metrics.py`. AURA (a player metric) is still research and not on the site.
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
