# New esport playbook

How to take a new esport from nothing to a Kalshi-traded rating model, the way `cs2-model` and `valorant-model` were built. An agent given a game name should run this from Phase 0 to the end, stopping only at the **Human stops** below. Reference repos: `../cs2-model` (Liquipedia data, no per-player stats), `../valorant-model` (VLR.gg data, per-player stats) and `../dota2-model` (Liquipedia series + OpenDota games and players; binary game outcomes; the most recent full run, 2026-10-29/30, and the one this playbook was tested on). Copy from them (read `origin/main`; local checkouts may lag); don't rewrite what they already solved.

Throughout, `<game>` is the slug (`cs2`, `valorant`, …), `<pkg>` the package (`promcs`, `promval`), `<GAME>` the Kalshi code (`KXCS2GAME`).

## Ground rules

- Work in worktrees (global `AGENTS.md`). In the new model repo, merge branches straight to `main` (as in cs2-model); Prometheus and infra changes go through PRs.
- The model repo follows its own `AGENTS.md` once Phase 1 creates it: work log, research ledger, steering budgets, raw-first data, polite network.
- Every model test is judged by the two-stage benchmark and recorded in `docs/research/README.md`, adopted or not.
- Every model update reports log loss vs Kalshi by tier and full-Kelly returns (raw and blended, LoL caps, depth-capped), in the work log and to the user.
- Never select, tune or fit on the holdout. It is opened once, in Phase 5.
- Keep a running status file, `docs/steering/current_state.md`, saying which phase you are in, so another agent can resume.
- Commit only when `pytest` passes: gate the commit on the test result in the same command (`R=$(uv run pytest -q | tail -1); case "$R" in *failed*|*error*) stop;; *) commit;; esac`). Dota merged one red commit by chaining commit after `tail`.
- Never print a secret. Commands the user runs with `!` echo into the transcript; read keys from `.env` and pipe them (`grep … | cut -d= -f2- | gh secret set NAME`). Prometheus and the model repos are public: docs say where a secret lives, never its value (no bucket names, ARNs, account IDs or keys).
- Verify a worker's output live before merging (run the export, the gate, the parser on real data): offline tests passed while live runs showed a broken seed and a misleading counter.

## Human stops

Stop, report what is done and exactly what is needed, and wait. Nothing else needs the user.

| # | When | What the user does |
|---|---|---|
| H1 | Phase 0 says no-go | Accepts the verdict or names another data source |
| H2 | Phase 1, after `gh repo create` | Adds the new repo to the shared fine-grained token (see **Where things live**) so it can be the repo's `PROMETHEUS_DISPATCH_TOKEN` and the cron-job.org bearer. The agent sets `AWS_ROLE_ARN` and `DATA_BACKUP_BUCKET` itself; if AWS SSO has expired the user runs `! aws sso login`. Until then work offline. |
| H3 | A data source needs a paid key, a login, or its terms forbid automated access | Decides; never work around terms (HLTV is not scraped) |
| H4 | Phase 5 gate fails | Chooses: stop; keep the model frozen and recheck the same gate after more holdout months; or override and go to Phase 6 candidate-only (Dota: gate missed by 0.4 points with a significant log-loss edge; the user overrode). Ask with `AskUserQuestion`. |
| H5 | Phase 7, candidate-only period done | Configures the game's bankroll in the execution config and flips mode (demo, then live) with `kalshi-execution-control.yml` |

The agent may on its own: create the GitHub repo, open the holdout once, open and merge Prometheus and infra PRs (games stay disabled in the execution config), deploy the execution infra, and create the cron-job.org jobs.

- **Infra deploy (no human step).** After the infra PR's checks pass, merge it, dispatch `deploy-prometheus-execution.yml` with `operation=diff`, and read the diff. Deploy (`operation=deploy`) when it changes only what the PR meant to: for a new game, the Lambda's `GAME_CANDIDATE_KEYS`/`GAME_BLEND_KEYS` and read access to those two `<game>-model/feed/` objects. Anything else (deleted or replaced resources, new roles or permissions beyond those objects, other stacks) is a stop: report it instead of deploying. Check the deploy run succeeded.
- **cron-job.org (no human step).** The API key is saved (see **Where things live**); create the jobs as described there and confirm the first dispatched runs appear in the repo's Actions.

## Phase 0: Feasibility (half a day)

Answer three questions and write them in the new repo's `product.md` (or, if no-go, in a short report to the user, H1).

1. **Markets.** Kalshi public API (live `/markets` holds only about two months of settled markets; older ones are on `/historical/markets`; 2025 markets' rules give a date without a time): does a series market (`KX<GAME>GAME`) exist, and maps (`KX<GAME>MAP`)? First listing date, markets per day, pregame vs in-play volume, median pregame volume by tier. CS2's study (2026-10-28) is the template: ~50 series/day, tier 2/3 pregame median under $500. No series market: no-go.
2. **Data.** A source with, per map: date (with timezone), teams, map score, and ideally round score and five-player lineups; per-player stats are a bonus (they enabled Valorant's form and KDA gains). Prefer Liquipedia's MediaWiki API (`action=query` wikitext only, 2 s between requests, CC BY-SA credit) when the game has a wiki; otherwise a stats site whose terms allow polite caching (VLR.gg). Check robots and terms. Needs at least ~3 years of history before Kalshi's first listing. Open a finished tier-1 and a finished tier-3 event and confirm the results are really in the source (Dota 2's Liquipedia wikitext holds only match IDs for tier-1 games; winners come from OpenDota). Then count the source's games by month against Kalshi's events by tournament: a source can go thin for recent months (OpenDota's pro list did from June 2026).
3. **Windows.** Fix the dates now and never move them: seed (all earlier history), stage 1 (≥2 years, outcomes only, ends before Kalshi has ~6 months of quotes), stage 2 (to the holdout start, needs ≥6 months of Kalshi quotes so monthly blends fit), holdout. The holdout must hold at least 300 linked series with a tradeable quote in the set you will trade. If past data allows that, end it at the scaffold date (as Valorant did: 2026-07-01 on, 653 matches). If not, start it at the scaffold date; Phase 5 then waits for the data to accrue (report the expected date, then continue Phases 1–4).

## Phase 1: Scaffold the model repo

Copy the newer of the two reference repos for the data source type (cs2-model for Liquipedia, valorant-model for a stats site):

- `AGENTS.md` (edit: what this is, data source rules, window dates), `README.md`, `pyproject.toml` (package `<pkg>`, CLI `prom<abbr>`), `.githooks/`, `.github/workflows/ci.yml`, `scripts/work_log.py`, `tests/test_steering.py`.
- `docs/steering/{product,tech,current_state,deployment}.md`, empty `work_log.md` and `work_log_archive.md`, `docs/research/README.md` with the rules header.
- `uv sync`, `git config core.hooksPath .githooks`, tests green, first commit.
- `gh repo create thaiv28/<game>-model --public --source . --push` (public like cs2-model and valorant-model: Actions minutes are free on public repos; private data goes to S3, never the repo, and `.env` stays gitignored). Then H2 (don't block on it; keep going offline).

## Phase 2: Data

Order matters: everything later rebuilds offline from the raw cache.

1. **Crawler** (`<pkg>/<source>/`): raw responses saved unchanged (gzip) under `data/<source>/`, with an index; never re-fetch finished events; injectable `get` so tests use saved fixtures; `PARSER_VERSION` bumped on any parser output change. First full crawl can take hours: run it in the background and build the parser against fixtures meanwhile.
2. **Kalshi collector** (`<pkg>/kalshi/`, copy from cs2-model): market catalogs, final trades and hourly candles, active books. Settled markets older than a few months come from Kalshi's historical endpoints. Back up to `s3://$DATA_BACKUP_BUCKET/<game>-model/kalshi/` once H2 is done (`scripts/kalshi_data.sh push`).
3. **DB** (`scripts/001_create_tables.sql`, numbered loaders, `setup_db.sh`): `events`, `teams`, `players`, `matches`, `maps`, `rosters`/`player_maps`, `kalshi_markets`, `team_aliases`, `kalshi_links`. UTC ISO times with `Z`. Tiers mapped to tier1/tier2/tier3/unknown; international flag. Parse errors counted to a file, not fatal.
4. **Linker** (copy `link.py`): exact → alias → anchor → fuzzy passes within ±30 h, settlement cross-checked against winners, `db/link_report.txt`. Target ≥65% of series linked (CS2: 5,138 of 7,907); read the failure list and fix the top reasons (aliases, name normalization, game-specific words) before modelling.
5. Record table counts, link rates and crawl time in the work log.

Traps met so far:
- **Liquipedia.** Stage subpages are often linked only through per-series tab templates: list every article once (`list=allpages`, ns 0, ~170 requests) and keep titles under a tournament root. Clean link titles (drop `#fragment`, collapse spaces) or one page loads twice. Retry dropped connections (`RemoteDisconnected`). Some wikis keep matches in the `Match:` namespace (ID pages per bracket) rather than inline.
- **Keep unresolved series** (NULL winner) in the DB: later fetchers and Kalshi links need them.
- **Per-game sources are slow on free tiers.** OpenDota free is 2,000 calls/day (~8 days for Dota's 15,000 missing games); a paid key cost ~$1.30 and took hours (H3). Ask early.
- **Local setup.** macOS has no `timeout`. A worktree's `data` is a symlink: ignore `data`, not `data/`, or it gets committed.

## Phase 3: Baseline benchmark

Port `scripts/evaluate_elo.py`, `<pkg>/{evaluation,backtest,blend,quotes}.py` and `<pkg>/ratings/` from the reference repo, then run:

- Models: coin, `team_elo`, `player_round_glicko` (player round Elo with RD; team units if the data has no lineups). Stage 1 tunes each on the standard grids; stage 2 runs frozen.
- Kalshi: tradeable quote (first hourly bid/ask ≥30 min after listing and ≥2 h before start, spread ≤0.06; checked against later quotes with `--robustness` so the veto isn't priced in), raw and walk-forward monthly blend, flat and Kelly returns, depth-capped.
- Write `docs/elo_backtest.md` and a ledger entry. Expect player Glicko to beat team Elo clearly (CS2: 0.6404 vs 0.6623 stage-1 map log loss; Dota: 0.6216 vs 0.6501 game log loss). If it doesn't, check the data (lineups, dates, duplicate matches) before going on.
- **Stage-2 looks are a budget.** For stage-1-only runs pass `--validate-from <holdout start>` (empty stage 2, no look). Take the first stage-2 look only on complete data (Dota waited for the OpenDota top-up: stage-1 loss moved 0.6294 → 0.6216). Widen any grid whose choice sits on an edge, then pin the base.
- Stage-1 paired tables must split by section (adoption needs every guarded section); the CS2 benchmark showed only "all" until Dota fixed it.

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

Dota 2 (2026-10-30): 1+2+9 together adopted (stage 1 −0.0122, every tier; online K 0.75, tier-3 K 0.75 only help with rookie); tier-target reversion adopted at the 0.0005 bar (stage 2 +0.0004 n.s.); form layer (KDA per minute) adopted on stage 2; KDA bonus, reversion to start, regional and calibration rejected. Layers are fitted on stage 1 but the benchmark scores them only on stage 2, which is weaker evidence: say so in the ledger.

After the ladder: adopt the winner as `models.ADOPTED`, refresh `docs/elo_backtest.md`, and name the **trade set** (e.g. series, domestic only) from stage-2 evidence. The trade set is fixed before the holdout opens. Valorant dropped international series because they lost on stage 2.

## Phase 5: Holdout verdict

Run `evaluate_elo.py --holdout` once on the frozen adopted model and the last pre-holdout blend fits; write `docs/elo_holdout.md` and the ledger entry.

**Gate (all on the trade set, after fees, depth-capped):** blended flat ROI's 95% interval excludes 0. Report alongside it: raw and blended log loss vs Kalshi by tier, LoL-capped Kelly from $50, monthly breakdown, and any single month driving the result. Valorant passed with blended series +17.0% [+1.0, +33.7].

Fail: write the verdict in `current_state.md` and the ledger, report to the user (H4), and stop. Don't retune and reopen. Kalshi may list a game's low tiers only late (Dota's EPL leagues from Sep 2026), so most of the market edge can sit in the holdout alone: report the by-tier and by-month split.

## Phase 6: Trading infrastructure

Only after the gate passes (or the user overrides at H4). Reuse the CS2, Valorant and Dota wiring throughout; dota2-model is the most complete template (gated feed, incremental fetch, listing modes).

**Model repo** (copy from cs2-model):

- `<pkg>/feed.py` and `<pkg>/trading.py`: `feed-state` snapshot (`feed/state.pkl.gz`), `export` (public site feed `feed/<game>.json`, version 1), private `feed/candidates.json` (raw series chances keyed by Kalshi team names, group `<game>-series`), `feed/blend_artifact.json` (`game-blend-v1`, monthly earlier-only fits, clip 0.01). Edit the Kalshi rules regex for the game's wording.
- Workflows: `kalshi-collect.yml` (6-hourly), `refresh-db.yml` (every 3 hours, input-hash cache, seed tarball), `feed.yml` (every 15 minutes behind a stdlib change gate, DB-free, dispatches Prometheus `games.yml` only when the public feed changed). Follow **CI cost rules** below. All use OIDC in us-west-2 and keys under `<game>-model/`. Measure their runtime.

**Prometheus** (PR, merge yourself). Non-League games live in one registry, `prometheus/other_games.py` (since PR #140). Adding a game:

- One `OtherGame` entry: slug, series ticker, rules word (as in Kalshi's rules text), alert groups and trade groups (the trade set), repo, dashboard label/emoji/color, and `kalshi_slug` = Kalshi's series title in slug form (`GET /series/<ticker>` title "Dota 2 Game" → `dota-2-game`).
- `prometheus/game_blends/<game>.json` (copied from the model repo's `blend_artifact.json`) and a test fixture. Without the packaged blend, `saved_candidates` silently drops every candidate.
- `scripts/game_feeds.sh` `GAMES` (`<game>:<game>-model`) for the Other games pages.
- Tests: `tests/test_execution_games.py` (own bankroll, losses can't touch League or the other games), `tests/test_games.py`, `tests/test_deploy_games.py`.
- Docs: `deployment.md` (Other games, execution), `current_state.md`, `docs/kalshi_execution.md`, work log. Site copy review per Prometheus `AGENTS.md` if the game page shows anything new.
- The game starts disabled in the execution config.

**Infra** (`project-platform-infrastructure`, PR only): add `<game>-model/feed/candidates.json` to `GAME_CANDIDATE_KEYS` and `<game>: <game>-model/feed/blend_artifact.json` to `GAME_BLEND_KEYS` in `lib/prometheus-execution-stack.ts`, plus any bucket permissions the model repo's role needs. Then merge, diff and deploy as in **Human stops** (no human step), and create the cron-job.org jobs.

Check the wiring live before the first scheduled run: a real `export`, then Prometheus's `saved_candidates` on its `candidates.json` (needs the packaged blend), then read-only `PublicKalshi.resolve` on each event with a parsed test config. Dota: 10 candidates → 20 proposals; 6 resolved, 4 thin books, 0 identity failures.

Seed S3 before the first scheduled run: the Kalshi archive (`kalshi manifest` + `kalshi_data.sh push`), the raw source prefixes, and `seed/raw.tar.zst`. On a Mac build the tarball with `COPYFILE_DISABLE=1 tar --no-mac-metadata --no-xattrs`: plain macOS `tar` adds `._*` files that break cache loaders and get synced back to S3 (dota2-model, 2026-10-30).

### CI cost rules

Scheduled jobs run thousands of times a month, so design them for cost before writing them, and record the estimate and the measured minutes in the model repo's `deployment.md` Cost section.

- **Public repo.** Standard runners are free on public repos; on private repos GitHub bills each job rounded up to a whole minute. A 10-minute job on a private repo is ≥ 4,320 billed minutes a month on its own.
- **Cadence follows the consumer.** Execution candidates only need to be younger than the Lambda's `CANDIDATE_MAX_AGE` (3 h) and to pick up new fixtures; site prices are the only reason for minutes-level runs. Ratings change only when results land.
- **Gate before setup.** A stdlib script that checks whether inputs changed (source revision IDs, Kalshi's open events) runs before checkout of the full repo and `uv sync`, and ends the run in seconds when nothing changed, with a forced run often enough to keep candidates fresh.
- **Fetch incrementally.** Ask sources for revision IDs first and download only changed content; cache listings; never refetch finished games.
- **Skip unchanged work.** Cache builds by input hash; skip uploads whose content hash matches; dispatch downstream only on change.
- **Cheap setup.** `uv sync --frozen --no-dev` with the uv cache, sparse checkout where possible, `timeout-minutes` on every job; docs-only pushes run only lint and the steering test.
- **Backups don't double the schedule.** GitHub's own schedule is a fallback for cron-job.org: hourly for the feed, every 6 h for the refresh, not the same cadence.
- **Rebuild once.** Rebuild the DB a second time (after a per-game top-up) only when the top-up saved something.

Dota measured: cold feed 248 s on GitHub (64 page fetches), next run 39 s (1 fetched, 63 reused); gate with nothing changed 3 s locally; first `refresh-db` 770 s.

## Phase 7: Candidate-only run and handoff

With the workflows live and the game still disabled, check for at least a week (or 50 fixtures): candidates are fresh (≤3 h), the Lambda resolves the Kalshi markets (read-only `PublicKalshi.resolve`; `no_two_sided_blend_quote` is expected for thin books: the blend needs a contract quoted within 10¢, so count it separately from identity failures), team aliases don't collide across games (League aliases apply only to League), and the frozen calls match the model repo's feed. Fix and record anything that fails.

Then report to the user (H5): gate numbers, trade set, proposed bankroll ($50 seed, League's limits: $250 per order and fixture, $1k exposure, $2k per day, same Kelly settings), what was checked, and what was not. The user configures and flips the mode.

## Where things live

Values are not written here (this repo is public); each line says where to get one.

- **AWS account and region:** us-west-2; GitHub OIDC role = the control-plane `ThaivProjectPlatform-GitHubDeploymentRole…` (trusts every `thaiv28/*` repo on `main`, read/write on the artifacts bucket). Find its ARN with `aws iam list-roles --query "Roles[?contains(RoleName,'ThaivProjectPlatform-GitHubDeploymentRole')].Arn"`. Set it as the new repo's `AWS_ROLE_ARN`.
- **Artifacts bucket:** `gh variable get DATA_BACKUP_BUCKET -R thaiv28/cs2-model`; set the same variable on the new repo. Each game writes only under `<game>-model/`.
- **Shared fine-grained GitHub token:** one token (Actions read and write) whose repository access covers Prometheus and every model repo. It is each model repo's `PROMETHEUS_DISPATCH_TOKEN` and the `Authorization: Bearer` header of every cron-job.org job. A new game extends its repository access (H2); the value never changes, and the agent copies it from an existing cron-job.org job through the API.
- **cron-job.org:** the owner's account. API key: `~/.config/cron-job.org/api_key` on the owner's Mac (mode 600, outside every repo; never print it). List jobs with `GET https://api.cron-job.org/jobs` and create with `PUT /jobs` (`Authorization: Bearer $(cat ~/.config/cron-job.org/api_key)`), copying an existing model-repo job's headers (they carry the shared GitHub token, which the owner calls the "prices trigger token"). Each job is `POST https://api.github.com/repos/thaiv28/<game>-model/actions/workflows/<file>/dispatches`, body `{"ref":"main"}`, header `Authorization: Bearer <shared GitHub token>`; feed every 15 minutes, refresh every 3 hours.
- **Execution infra:** `project-platform-infrastructure`, `lib/prometheus-execution-stack.ts` (`GAME_CANDIDATE_KEYS`, `GAME_BLEND_KEYS`); deploy with the `deploy-prometheus-execution.yml` dispatch (`diff`, then `deploy`).
- **Paid data keys:** in the model repo's gitignored `.env` and as a repo secret of the same name (Dota: `OPENDOTA_API_KEY`).

## Final report

At every stop and at the end, give: phase reached, gate numbers, links to `elo_backtest.md` and `elo_holdout.md`, the ledger count of stage-2 looks, open human stops, and anything unverified.
