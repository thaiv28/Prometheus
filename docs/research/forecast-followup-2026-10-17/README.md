# Forecast research handoff

Packaged October 18, 2026 UTC at the user's request so another agent can inspect the completed research. **Research only: no runtime integration, production coefficient replacement, deployment, trading action, PR or merge is part of this branch.** The user wants experiment results before deciding on further merges. Do not create a reusable research skill.

## Read in this order

1. [Professional draft and rank-specific patch follow-up](draft-rank-followup.md): the most recent findings, ablations, uncertainty and data limitations.
2. [First experiment results](experiment-results.md): broader candidate families and why most did not establish an incremental improvement.
3. [Repository audit and literature research](literature-and-audit.md): original opportunities, references and nearest existing implementations. Read this as historical research; check current source before treating any capability as absent.
4. The original protocols and machine-readable results in [archive/experiments](archive/experiments) and [archive/followup](archive/followup).

These reports are preserved verbatim. Statements such as "no commits" describe the research runs before this packaging commit. Their original archive/reproduction instructions describe a larger data bundle; the GitHub package is a text-only subset, as explained below.

## Revision warning

The experiments used production baseline `ac5745ca1982d7347d7caee2f98f70f7f1832c53` and draft research source `dd84749b364d4580b41e7236ca98188f6a6d6596`. Their restored Oracle's Elixir corpus ends **May 22, 2026**, not October. Production Form/Elo were reused without modifying the tested checkout.

At packaging, remote main had advanced to `0cc01bd944b69065ca4e579cb4c131a1dad5e0c1`; this branch starts there. PRs #78 and #80 are now merged on main. Inspection of the current research index, current-state document and source history confirms the draft research and frozen `scripts/research/draft_model_v1.json` already exist, together with prospective scoring and pre-map book collection. **The archived results do not evaluate that newly frozen model or its larger/current market cohort.** Reconcile `docs/research/draft_score.md`, `docs/research/draft_prospective.md`, the current live benchmark data pin and actual live receipt logs before proposing another implementation. Do not overwrite newer findings with this historical report. No new benchmark was run against that advanced revision as part of packaging.

## Main findings

Negative differences below mean lower pre-match map log loss. Controls are matched FORGE/regional-calibration controls with the same nuisance calibration, not vanilla Elo. Actual champion picks make these **post-draft** forecasts, not night-before forecasts.

| Experiment | Result | Interpretation |
|---|---|---|
| Original six-feature pro draft, annual refits | ΔLL −0.00532 on 21,361 maps, series-bootstrap 95% CI [−0.00642, −0.00429] | Gain survives earlier-year/monthly coefficient refits. Original snapshot cohort excludes LPL. |
| Five-feature full-roster draft, strict prior-day histories | ΔLL −0.00599 on 23,956 maps, CI [−0.00707, −0.00503] | Includes LPL; selected after inspecting ablations, hence exploratory. LPL Δ −0.00758, CI [−0.01126, −0.00392]. |
| Broad draft candidate, international | ΔLL −0.00699 on 449 cross-home international maps | Nine events; event CI [−0.01530, +0.00369], inconclusive. |
| Map-level market blend analogue | Draft contributes favorable point estimates | Refit-training-and-test bootstrap crosses zero; exact production series blend and tradeable edge remain unproven. |
| Master+ vs Diamond+/Platinum+ patch win rates | 75 training / 97 test maps after availability gates | Only patches 16.1/16.2 recovered. No rank tier established a gain; cannot conclude Master+ wins. |

Five broad-coverage features are player-champion experience, player-champion wins above expectation, recent professional champion-role results, lane matchups and teammate champion pairs. The six-feature original additionally uses champion-specific 15-minute gold performance. Full-game roster input avoids its LPL snapshot-coverage exclusion. The real-data outcome intervention and prefix check support earlier-day feature isolation, but do not prove current picks are available at a chosen live quote cutoff.

Solo-queue comparisons normalize each rank population's average win rate and shrink by game counts. A patch being live before pro play is useful, but **eventual full-patch win rates cannot be used before that patch's data collection ends**. The limited historical test admitted totals only after the next patch release plus a day. Daily snapshots with receipt times would permit earlier use without this leakage. Archived public pages retrieved today do not independently establish their historical publication state.

## Next agent's work

1. Audit current main and its already frozen/prospective draft model first. Compare it with the five-feature, full-roster, earlier-day candidate on identical maps and a current-data chronological protocol. Older viewed years are development evidence, not fresh confirmation.
2. Verify actual pick/role receipt times, flex-role resolution and executable quotes after receipt. Main now records pre-map books, but historical OE picks alone do not establish live availability.
3. Test the exact current production **series-level** market blend with training uncertainty, fees and matched availability cutoffs. This archive's monthly map-level blend analogue does not answer that question.
4. Obtain multi-patch, rank-specific, role-specific daily solo-queue snapshots with counts and collection times. Freeze a matched Master+/Diamond+/Platinum+ comparison and pre-draft team-pool exposure versus post-draft picks before scoring. Do not pick a tier from these 97 maps.
5. Report domestic major/minor, international, tournament-entry and event/series clustered uncertainty separately. Preserve all failed/neutral variants and the distinction between measured results and proposed experiments. Bring results to the user before any further production merge.

## Reproduction and package limits

Included: three full reports, original protocols, archived analysis/acquisition scripts, result JSON, source/error manifests and original verification records. [archive-manifest.json](archive-manifest.json) hashes the preserved files. Verification JSON records checks performed during the original runs; it is not a claim that a fresh rerun has occurred on this branch.

Excluded: raw OE CSVs, SQLite DB, derived Parquet matrices/predictions, third-party page bodies, the 84 MB full reproducibility ZIP and third-party API-key-bearing downloader sources. Never commit the repository's ignored `data/`, `db/` or `output/`. Consequently this branch supports complete reading of findings and code, but is **not a self-contained numeric rerun**. Public input availability and exact source hashes must be verified; do not silently replace stale/missing inputs with current snapshots. The full earlier bundle contains cached derived inputs; without it, rebuild them using the archived scripts and pinned inputs. Some historical rank pages may no longer be available.

Scripts are stored as `.py.txt` to preserve the original research code without integrating it into application tooling or CI. Do not execute acquisition or analysis scripts inside the source checkout by guessing their relative paths. Stage the following layout in a separate scratch directory:

```text
scratch/
  prometheus-audit/          # separate clone at the tested baseline
  experiments/              # unpack archive/experiments here
  prior-research/
    experiments -> ../experiments
  followup/                 # unpack archive/followup here
  draft_score_pr78.py        # source from the pinned draft commit
```

Rename archived `.py.txt` files to `.py` when staging. The `prior-research/experiments` symlink lets follow-up scripts reuse the first-stage inputs. Use a separate clone pinned to the tested baseline, `uv sync --frozen`, Python 3.12+, pyarrow and requests in its research environment only, and one BLAS/OMP thread. Fetch the pinned draft source with `git show dd84749b364d4580b41e7236ca98188f6a6d6596:scripts/research/draft_score.py` into both `scratch/draft_score_pr78.py` and `scratch/followup/draft_score_source.py`. Do not invoke that source's main routine. Use [the first-stage instructions](archive/experiments/REPRODUCE.md) and [the follow-up instructions](archive/followup/REPRODUCE.md), with this layout taking precedence.

The first acquisition manifest pins all 13 OE years. The follow-up collector intentionally covers 2014–2025; its `download_needed.py` separately retrieves the pinned 2026 CSV. Verify hashes against the committed manifests before building an **absent, disposable research DB**. The builder refuses an existing DB. Restore/download the ranked source and released market archive referenced in the reports; regenerate prior matrices before follow-up fits. Preserve original manifests elsewhere before running collectors, which overwrite their own output manifests.

Report-generator scripts retain their original output-path assumptions. Treat them as historical source; use the committed reports as the reviewed deliverable. Do not run a generator or validator against production data/settings without inspecting its paths first.
