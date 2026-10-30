# New esport playbook

How to take a new esport from nothing to a Kalshi-traded rating model, the way `cs2-model` and `valorant-model` were built. An agent given a game name should run this from Phase 0 to the end, stopping only at the **Human stops** below. Reference repos: `../cs2-model` (Liquipedia data, no per-player stats) and `../valorant-model` (VLR.gg data, per-player stats, holdout already opened). Copy from them (read `origin/main`; local checkouts may lag); don't rewrite what they already solved.

Throughout, `<game>` is the slug (`cs2`, `valorant`, …), `<pkg>` the package (`promcs`, `promval`), `<GAME>` the Kalshi code (`KXCS2GAME`).

## Ground rules

- Work in worktrees (global `AGENTS.md`). In the new model repo, merge branches straight to `main` (as in cs2-model); Prometheus and infra changes go through PRs.
- The model repo follows its own `AGENTS.md` once Phase 1 creates it: work log, research ledger, steering budgets, raw-first data, polite network.
- Every model test is judged by the two-stage benchmark and recorded in `docs/research/README.md`, adopted or not.
- Every model update reports log loss vs Kalshi by tier and full-Kelly returns (raw and blended, LoL caps, depth-capped), in the work log and to the user.
- Never select, tune or fit on the holdout. It is opened once, in Phase 5.
- Keep a running status file, `docs/steering/current_state.md`, saying which phase you are in, so another agent can resume.

## Human stops

Stop, report what is done and exactly what is needed, and wait. Nothing else needs the user.

| # | When | What the user does |
|---|---|---|
| H1 | Phase 0 says no-go | Accepts the verdict or names another data source |
| H2 | Phase 1, after `gh repo create` | Sets secret `AWS_ROLE_ARN`, variable `DATA_BACKUP_BUCKET`, secret `PROMETHEUS_DISPATCH_TOKEN`. Until then work offline; CI-only steps wait. |
| H3 | A data source needs a paid key, a login, or its terms forbid automated access | Decides; never work around terms (HLTV is not scraped) |
| H4 | Phase 5 gate fails | Reads the verdict; the playbook ends here |
| H5 | Phase 6, infra PR opened | Merges it and runs the CDK deploy |
| H6 | Phase 6, workflows ready | Adds cron-job.org dispatches for `refresh-db.yml` and `feed.yml` |
| H7 | Phase 7, candidate-only period done | Configures the game's bankroll in the execution config and flips mode (demo, then live) with `kalshi-execution-control.yml` |

The agent may on its own: create the GitHub repo, open the holdout once, open infra PRs, and open and merge Prometheus PRs (games stay disabled in the execution config).

## Phase 0: Feasibility (half a day)

Answer three questions and write them in the new repo's `product.md` (or, if no-go, in a short report to the user, H1).

1. **Markets.** Kalshi public API: does a series market (`KX<GAME>GAME`) exist, and maps (`KX<GAME>MAP`)? First listing date, markets per day, pregame vs in-play volume, median pregame volume by tier. CS2's study (2026-10-28) is the template: ~50 series/day, tier 2/3 pregame median under $500. No series market: no-go.
2. **Data.** A source with, per map: date (with timezone), teams, map score, and ideally round score and five-player lineups; per-player stats are a bonus (they enabled Valorant's form and KDA gains). Prefer Liquipedia's MediaWiki API (`action=query` wikitext only, 2 s between requests, CC BY-SA credit) when the game has a wiki; otherwise a stats site whose terms allow polite caching (VLR.gg). Check robots and terms. Needs at least ~3 years of history before Kalshi's first listing. Open a finished tier-1 and a finished tier-3 event and confirm the results are really in the source (Dota 2's Liquipedia wikitext holds only match IDs for tier-1 games; winners come from OpenDota). Then count the source's games by month against Kalshi's events by tournament: a source can go thin for recent months (OpenDota's pro list did from June 2026).
3. **Windows.** Fix the dates now and never move them: seed (all earlier history), stage 1 (≥2 years, outcomes only, ends before Kalshi has ~6 months of quotes), stage 2 (to the holdout start, needs ≥6 months of Kalshi quotes so monthly blends fit), holdout. The holdout must hold at least 300 linked series with a tradeable quote in the set you will trade. If past data allows that, end it at the scaffold date (as Valorant did: 2026-07-01 on, 653 matches). If not, start it at the scaffold date; Phase 5 then waits for the data to accrue (report the expected date, then continue Phases 1–4).

## Phase 1: Scaffold the model repo

Copy the newer of the two reference repos for the data source type (cs2-model for Liquipedia, valorant-model for a stats site):

- `AGENTS.md` (edit: what this is, data source rules, window dates), `README.md`, `pyproject.toml` (package `<pkg>`, CLI `prom<abbr>`), `.githooks/`, `.github/workflows/ci.yml`, `scripts/work_log.py`, `tests/test_steering.py`.
- `docs/steering/{product,tech,current_state,deployment}.md`, empty `work_log.md` and `work_log_archive.md`, `docs/research/README.md` with the rules header.
- `uv sync`, `git config core.hooksPath .githooks`, tests green, first commit.
- `gh repo create thaiv28/<game>-model --private --source . --push`. Then H2 (don't block on it; keep going offline).

## Phase 2: Data

Order matters: everything later rebuilds offline from the raw cache.

1. **Crawler** (`<pkg>/<source>/`): raw responses saved unchanged (gzip) under `data/<source>/`, with an index; never re-fetch finished events; injectable `get` so tests use saved fixtures; `PARSER_VERSION` bumped on any parser output change. First full crawl can take hours: run it in the background and build the parser against fixtures meanwhile.
2. **Kalshi collector** (`<pkg>/kalshi/`, copy from cs2-model): market catalogs, final trades and hourly candles, active books. Settled markets older than a few months come from Kalshi's historical endpoints. Back up to `s3://$DATA_BACKUP_BUCKET/<game>-model/kalshi/` once H2 is done (`scripts/kalshi_data.sh push`).
3. **DB** (`scripts/001_create_tables.sql`, numbered loaders, `setup_db.sh`): `events`, `teams`, `players`, `matches`, `maps`, `rosters`/`player_maps`, `kalshi_markets`, `team_aliases`, `kalshi_links`. UTC ISO times with `Z`. Tiers mapped to tier1/tier2/tier3/unknown; international flag. Parse errors counted to a file, not fatal.
4. **Linker** (copy `link.py`): exact → alias → anchor → fuzzy passes within ±30 h, settlement cross-checked against winners, `db/link_report.txt`. Target ≥65% of series linked (CS2: 5,138 of 7,907); read the failure list and fix the top reasons (aliases, name normalization, game-specific words) before modelling.
5. Record table counts, link rates and crawl time in the work log.

## Phase 3: Baseline benchmark

Port `scripts/evaluate_elo.py`, `<pkg>/{evaluation,backtest,blend,quotes}.py` and `<pkg>/ratings/` from the reference repo, then run:

- Models: coin, `team_elo`, `player_round_glicko` (player round Elo with RD; team units if the data has no lineups). Stage 1 tunes each on the standard grids; stage 2 runs frozen.
- Kalshi: tradeable quote (first hourly bid/ask ≥30 min after listing and ≥2 h before start, spread ≤0.06; checked against later quotes with `--robustness` so the veto isn't priced in), raw and walk-forward monthly blend, flat and Kelly returns, depth-capped.
- Write `docs/elo_backtest.md` and a ledger entry. Expect player Glicko to beat team Elo clearly (CS2: 0.6404 vs 0.6623 stage-1 map log loss). If it doesn't, check the data (lineups, dates, duplicate matches) before going on.

## Phase 4: Refinement ladder

Test these in order, each over the current best model, under the reference repo's Model change rules (stage-1 paired-bootstrap interval excludes 0 on the targeted sections, ≥0.0005 gain for an added parameter, no guarded section significantly worse; then stage 2 not significantly worse, including blended vs Kalshi). Widen a grid when it picks an edge value and retest. Stop when the ladder is done: that is the plateau.

| # | Idea | Prior result |
|---|---|---|
| 1 | Rookie discount (log1p penalty on players with few maps) | Adopted in LoL, CS2 (200 / 400 maps), Valorant (150 / 200) |
| 2 | Tier K multipliers (smaller K in low tiers) | Adopted in CS2 (tier3 × 0.75) |
| 3 | Series temperature per best-of (stage-1 fit) | Adopted in Valorant (Bo3 0.79, Bo5 0.68) and CS2 |
| 4 | Season and inactivity reversion toward init | Part of Valorant's `tier_revert` |
| 5 | Player form layer (recent per-player rating) | Adopted in Valorant; skip without per-player stats |
| 6 | Performance bonus in player updates (KDA vs role/agent expectation) | Adopted in Valorant (perf_k 7); skip without stats |
| 7 | Regional layer (cross-region effects, ridge 4) | Rejected in both (below 0.0005); test once |
| 8 | Calibration by tier × LAN | Rejected in CS2; test once |
| 9 | Online K multiplier | Rejected in CS2; test once |

After the ladder: adopt the winner as `models.ADOPTED`, refresh `docs/elo_backtest.md`, and name the **trade set** (e.g. series, domestic only) from stage-2 evidence. The trade set is fixed before the holdout opens. Valorant dropped international series because they lost on stage 2.

## Phase 5: Holdout verdict

Run `evaluate_elo.py --holdout` once on the frozen adopted model and the last pre-holdout blend fits; write `docs/elo_holdout.md` and the ledger entry.

**Gate (all on the trade set, after fees, depth-capped):** blended flat ROI's 95% interval excludes 0. Report alongside it: raw and blended log loss vs Kalshi by tier, LoL-capped Kelly from $50, monthly breakdown, and any single month driving the result. Valorant passed with blended series +17.0% [+1.0, +33.7].

Fail: write the verdict in `current_state.md` and the ledger, report to the user (H4), and stop. Don't retune and reopen.

## Phase 6: Trading infrastructure

Only after the gate passes. Reuse the CS2 and Valorant wiring throughout.

**Model repo** (copy from cs2-model):

- `<pkg>/feed.py` and `<pkg>/trading.py`: `feed-state` snapshot (`feed/state.pkl.gz`), `export` (public site feed `feed/<game>.json`, version 1), private `feed/candidates.json` (raw series chances keyed by Kalshi team names, group `<game>-series`), `feed/blend_artifact.json` (`game-blend-v1`, monthly earlier-only fits, clip 0.01). Edit the Kalshi rules regex for the game's wording.
- Workflows: `kalshi-collect.yml` (6-hourly), `refresh-db.yml` (hourly crawl, input-hash cache, seed tarball), `feed.yml` (10 minutes, DB-free, dispatches Prometheus `games.yml`). All use OIDC in us-west-2 and keys under `<game>-model/`. Measure their runtime.

**Prometheus** (PR, merge yourself). The game list is currently hard-coded as `{"cs2", "valorant"}`; if it still is, first replace those sets with one registry (slug → series ticker, rules word, groups), then add the game:

- `prometheus/game_blends/<game>.json` (copied from the model repo's `blend_artifact.json`) and a test fixture.
- `prometheus/market_blend.py`, `prometheus/execution/core.py` (allowed games, `ACCOUNT#<game>` in the account scan), `deploy/execution/handler.py` (allowed games for `GAME_BLEND_KEYS`).
- `prometheus/alert_contract.py`: series ticker, rules word, `GAME_GROUPS`, `TRADE_GROUPS` (exclude groups outside the trade set).
- `scripts/game_feeds.sh` `GAMES` (`<game>:<game>-model`) for the Other games pages.
- Tests: `tests/test_execution_games.py` (own bankroll, losses can't touch League or the other games), `tests/test_games.py`, `tests/test_deploy_games.py`.
- Docs: `deployment.md` (Other games, execution), `current_state.md`, `docs/kalshi_execution.md`, work log. Site copy review per Prometheus `AGENTS.md` if the game page shows anything new.
- The game starts disabled in the execution config.

**Infra** (`project-platform-infrastructure`, PR only): add `<game>-model/feed/candidates.json` to `GAME_CANDIDATE_KEYS` and `<game>: <game>-model/feed/blend_artifact.json` to `GAME_BLEND_KEYS` in `lib/prometheus-execution-stack.ts`, plus any bucket permissions the model repo's role needs. Then H5 and H6.

## Phase 7: Candidate-only run and handoff

With the workflows live and the game still disabled, check for at least a week (or 50 fixtures): candidates are fresh (≤3 h), the Lambda resolves the Kalshi markets (read-only `PublicKalshi.resolve`), team aliases don't collide across games (League aliases apply only to League), and the frozen calls match the model repo's feed. Fix and record anything that fails.

Then report to the user (H7): gate numbers, trade set, proposed bankroll ($50 seed, League's limits: $250 per order and fixture, $1k exposure, $2k per day, same Kelly settings), what was checked, and what was not. The user configures and flips the mode.

## Final report

At every stop and at the end, give: phase reached, gate numbers, links to `elo_backtest.md` and `elo_holdout.md`, the ledger count of stage-2 looks, open human stops, and anything unverified.
