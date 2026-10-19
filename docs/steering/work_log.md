# Work log

Newest first. One entry per substantive change, at most 150 words: what changed, the checks actually run, remaining limits. Put detail in the docs or reports the entry names. Older entries move to [the archive](work_log_archive.md) automatically (see `AGENTS.md`, Work log).

## 2026-10-19 — Remove draft v2 from map trading; add a $15 live-map budget

User asked to drop draft v2 (no trading gain; FST significantly worse) and cap live-map trading at $15. The draft route is gone from `live_map.py`, `live/signals.py`, `pyproject.toml` and the README; `live_map_draft_blend.json` deleted; the executor zip, release hash and publish filter drop the draft model and blend but keep `live/draft.py` (imported by `live/timeline.py`). New required `live_maps.budget_usd` for shadow and live map modes: the ledger's `LIVE_MAPS` row tracks held cost and realized profit, and a map order is capped at budget + realized − held, reserved in the same transaction as ACCOUNT. Loss can't exceed the budget; profit extends it; pregame unaffected. Docs suggest `"budget_usd": "15"`; nothing configured in AWS. Checks: 862 passed, 2 skipped; two budget tests fail with their guards removed; ruff; `package.sh` builds without draft files. Limit: the shared 1%/2% caps (about $0.50 a map) still apply; not deployed.

## 2026-10-19 — Review draft v2 for the 30-second trading blend

User asked to merge and activate PR #92's draft model only if benchmarks improved. Integrated main `bc02c4e` into `live-map-trading`; signals used the frozen ready draft with separate earlier-only monthly fits, and absent or conflicting drafts kept the original inference. Fixed, untuned comparison (1,352 maps, 655 series): log loss −0.00133 (−0.00437 to +0.00174); FST significantly worse, +0.02692 (+0.01188 to +0.04563); flat ROI +18.74% vs original +21.05%. Gate FAIL: no merge, deploy or activation; evidence in `docs/research/live_map_draft_trading.md`. Checks: 873 passed, 2 skipped (signing tests pass with pinned cryptography); ruff; 110 links; runtime blend matches the replay within 1.12e-16; package SHA256 `ac8c5a02…`. No UI or CI change.

## 2026-10-19 — Cut agents' token use: lean AGENTS.md, rotating log, doc budgets

Branch `token-diet`, base `b0acbac` (main). Docs and tooling only; no metric, build or CI change.
- `AGENTS.md` 4.1k → 2.3k words: read only the docs a change touches and the newest 5 log entries (`scripts/work_log.py recent 5`). Layout, metric change rules and benchmark commands moved to `tech.md`.
- `tech.md` 17.1k → 8.9k words (Codex, via the delegate skill): history and research cut to pointers.
- `.githooks/pre-commit` runs `work_log.py rotate`: past 15 entries, the newest 10 stay. Moved 68; no heading or line lost.
- Kept entries shortened to 150 words (originals at `b0acbac`); main's six from PR #94 too.
- `test_steering.py`: word budgets for changed steering docs and new entries.

Checks: pytest 794 passed, 2 skipped; ruff; `git diff --check`. Hook not yet run on a real commit.

## 2026-10-19 — Ship Glicko-1-style player RD and non-major update slope in Elo

Branch `elo-glicko-scale`, based on `bc02c4e` (main) with `future-win-share`, `elo-glicko` and `elo-fitted-scale` merged.
Published jointly tuned constants: player RD (new/floor/reference/growth per
√day) `(280,140,140,10)`, information .125, non-major domestic expected-score
slope .0065; majors/international retain ln(10)/400, K 20 everywhere.
Glicko-1-style RD scales each player's move independently by RD²/floor²,
grows while inactive and shrinks with games. It replaces provisional and
time-away factors (defaults now 0/0); rookie discount and move-down bonus stay.
No volatility or g(RD). `LEGACY_ELO` preserves the previous defaults for
research; team-Elo comparison disables RD and the non-major slope.
Research event-slope callbacks discard engine overrides and disable its slope.

Held-out 2022+ evidence from [joint tuning](../research/elo_glicko_scale.md),
combined vs previous published: other-league Elo −0.0033, FORGE −0.0014,
cross-league Elo −0.0028; domestic/international within noise. Main guarded
sections pass. The manager decision adopts the combination despite the
nine-game international roster-change regression versus RD alone
(Elo +0.0078, FORGE +0.0050); historical holdouts were repeatedly viewed,
intervals are individual-game bootstraps, not series-clustered.

Paired native check (manager): `evaluate_metrics.py --dump` with the previous Elo (base) and this branch (head), same games, `compare_benchmarks.py`: no guarded value significantly worse. Domestic Elo −0.0009 (−0.0014 to −0.0003), domestic FORGE −0.0000 (−0.0003 to +0.0003), international FORGE/Elo +0.0002 (−0.0005 to +0.0008), cross-league Elo −0.0015 (−0.0026 to −0.0004), other-league per-league Elo −0.0024 (−0.0029 to −0.0019), other-league FORGE −0.0009 (−0.0013 to −0.0005). The table below compares the old report with the new one and is unpaired (the old report has 33 fewer international games), which is why international FORGE looks worse there.

Full headline log losses, git HEAD report → regenerated 2026-10-19 report:

| Section | Before | After |
|---|---:|---:|
| Domestic FORGE | 0.6285 | 0.6284 |
| International FORGE | 0.6222 | 0.6252 |
| Cross-league Elo | 0.5906 | 0.5894 |
| Other-league Elo, per league | 0.6094 | 0.6070 |
| Other-league FORGE | 0.6076 | 0.6066 |

Domestic games remain 16,810; international 1,024 → 1,057, cross-league
10,184 → 10,241, other-league 69,736 → 69,760. These full-report differences
include newer games and are not paired causal estimates; the fixed-cohort
research above supports adoption. Domestic Elo 0.6312 → 0.6303; plain team
Elo stays 0.6346. FORGE vs per-league Elo in other leagues is now within
noise (−0.0003, −0.0009 to +0.0002).

Refit `forge_weights.json`, `form_weights.json`, `league_curves.json`:

`elo_weight` 0.005259 → 0.005458; `form_weight` 0.453359 → 0.410363; `cross_region_elo_weight` 0.008587 → 0.008466; `other_league_elo_weight` 0.010123 → 0.010009; `other_league_forge_elo_weight` 0.007842 → 0.008263; `other_league_form_weight` 0.377375 → 0.281251.
Form stat weights: gpm 0.005216 → 0.005230; kills_per_10 -0.002481 → -0.002698; turrets_per_10 0.731225 → 0.729604; baron_per_10 -1.276508 → -1.289016; dragon_per_10 0.634214 → 0.635374; atakhans 0.628078 → 0.607944; heralds_per_10 0.359372 → 0.361201; firstherald -0.438688 → -0.434983; firstdragon -0.403949 → -0.407468; firstbaron -0.100573 → -0.088851; firsttower 0.140000 → 0.139796; visionscore_per_10 0.013992 → 0.013743. Half-life/carry/prior/roster settings unchanged.
League curves: 95 slopes changed; range 0.006785–0.013859 → 0.007151–0.012827.

Timing (VECLIB_MAXIMUM_THREADS=1): DB rebuild 32.15 s; standalone
`004_bootstrap_elo.py` 11.38 s. Load + compute replay (no DB writes, sequential one-liners): legacy 5.53 s,
new 6.48 s (+0.95 s, 17%).
RD adds per-player state work to the existing bootstrap for the significant
forecast gains above; no dependency, job or CI step added. Actions timings
remain to be observed in CI.

Checks actually run:

- `PATH="$PWD/.venv/bin:$PATH" bash scripts/setup_db.sh`: PASS, 205,871 team-game rows.
- `VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/evaluate_metrics.py --write-weights --out docs/metric_backtest.md`: PASS.
- `VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/evaluate_season_stats.py --out docs/season_stats_report.md`: PASS.
- `.venv/bin/python -m pytest -q` (VECLIB_MAXIMUM_THREADS=1): PASS, 861 passed, 2 skipped; existing CPU-count warning.
- `.venv/bin/ruff format && .venv/bin/ruff check`: PASS.
- Arithmetic tests cover default RD, event slope dispatch (canonical international
  label `Worlds`; `WLDs` is not in this repo's enum), and legacy first-game discount.
  Two research arithmetic tests explicitly retain legacy settings.
- `VECLIB_MAXIMUM_THREADS=1 PREDICTIONS_FETCH=0 .venv/bin/python scripts/build_site.py`: PASS; home, FORGE, team Elo and player Elo output spot-checked for complete HTML and finite numeric JSON values.
- Final document links and diff checked.

Frozen artifacts (regional calibration, market blend, props weights, live
time models) were not refit; inputs unavailable here, left to CI benchmarks.
No UI source changes or commit. Site output was checked structurally, not visually;
CI benchmark results and Actions timings remain unverified locally.

## 2026-10-19 — Joint tune: Glicko RD + non-major update scale (research)

Research in the supplied `Prometheus-elo-glicko-scale` worktree, with its own DB;
no commit or published default changes. `elo_glicko_scale.py` imports the v2
Glicko scoring/prefix/roster helpers and fitted-scale non-major config/grid.
Protocol fixed before scoring: six RD settings (floor 140/180/220, new twice
floor, reference=floor, growth 10, information .125/.0625), then 16 non-major
slope {ln(10)/400,.0065,.0070,.0080} × K {20,22,24,28} settings on G*.
One upper-edge extension only (.0090 and/or K 32, new Cartesian cells).
Published rookie discount retained; provisional/away multipliers disabled;
major/international slope and base K remain native. Tune through 2021 on
weighted domestic + other-league Elo loss; freeze choices before 2022+ scoring.
Reuses v2 curve/Form/FORGE refits and paired-game 95% bootstrap comparisons,
including known-five-starter-change slices. Every replay's wall time is recorded.

G* remains the v2 winner: RD `(280,140,140,10)`, information .125;
training objective .62002411. S*: non-major slope .0065, K 20; combined
objective .61999453. No upper-edge extension triggered (22 tuning cells).
The RD floor remains on the lower boundary. Report:
[`elo_glicko_scale.md`](../research/elo_glicko_scale.md).

Held out 2022–2026, Δ log loss (95% paired-game CI): (a) G* versus
published; (b) G*+S* versus published; (c) G*+S* versus G*.

| Section | (a) | (b) | (c) |
|---|---|---|---|
| Elo, domestic | -0.00051 (-0.00132, +0.00026) | -0.00072 (-0.00158, +0.00007) | -0.00022 (-0.00037, -0.00007) |
| Elo, international | +0.00039 (-0.00094, +0.00176) | +0.00027 (-0.00093, +0.00150) | -0.00013 (-0.00066, +0.00045) |
| FORGE, domestic | +0.00014 (-0.00036, +0.00061) | +0.00007 (-0.00045, +0.00056) | -0.00007 (-0.00017, +0.00002) |
| FORGE, international | -0.00013 (-0.00100, +0.00076) | +0.00010 (-0.00077, +0.00096) | +0.00023 (-0.00007, +0.00058) |
| Elo, other leagues | -0.00283 (-0.00347, -0.00220) | -0.00329 (-0.00403, -0.00257) | -0.00047 (-0.00064, -0.00030) |
| FORGE, other leagues | -0.00108 (-0.00155, -0.00062) | -0.00142 (-0.00199, -0.00088) | -0.00034 (-0.00049, -0.00020) |
| Elo, cross-league | -0.00068 (-0.00222, +0.00091) | -0.00283 (-0.00471, -0.00104) | -0.00215 (-0.00279, -0.00154) |

**Ship G* only**, computed by the script. The combined design beats G*
significantly on Elo cross-league and Elo/FORGE within other leagues, and
no full-section regression is significant. However, the all-reported-section
guard also includes the roster-change slices: versus G*, international
roster-change Elo is +.00777 (+.00140, +.01433), FORGE +.00502
(+.00050, +.00979), on only nine games. Thus (c) fails the no-regression
guard; (a) passes, including all roster slices. Roster-change other-league
gains for (a): Elo −.00269 (−.00421, −.00116), FORGE −.00169
(−.00289, −.00051). Report contains all three complete roster tables.

Timing: median 1.89 s across all 27 replays (prefix and full mixed);
full published/G*/combined replays 3.92/4.17/4.30 s; total run 134.9 s.
Only an opt-in research script and one small config test were added;
no publish/hourly/benchmark job, dependency or production build work added.

Checks actually run (all PASS):

- `VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_glicko_scale.py --out docs/research/elo_glicko_scale.md`.
- `.venv/bin/python -m pytest -q tests/research/test_elo_glicko_scale.py`: 1 passed.
- `.venv/bin/python -m pytest -q`: 857 passed, 2 skipped, 1 environment CPU-count warning; 9.44 s.
- `.venv/bin/ruff format && .venv/bin/ruff check`: clean (final run: 332 files unchanged).
- Exact selected prefix/full parity; final diff and new-document links checked.

Limits: individual-game intervals, no series clustering or multiplicity
adjustment; the nine-game international roster slice is small. Inherited
leave-one-year-out calibration is not an earlier-only deployment simulation;
historical holdouts have been repeatedly viewed. No production adoption,
existing-report edits, DB rebuild, site build or commit performed.

Manager decision (same day): ship G*+S*. The script's verdict counted the roster-change slices as guarded sections; the predeclared rule (and CI's guard) covers the main sections, where (b) and (c) have no significantly worse section and (c) gains significantly in cross-league Elo (−0.0022), within-other-league Elo and FORGE, and domestic Elo. The only significant regression is the international roster-change slice, nine games (Elo +0.0078, FORGE +0.0050), too few to support a guard. Recorded here so the override is explicit.

## 2026-10-19 — Non-major-only Elo update scale / K (research follow-up)

Branch `elo-fitted-scale`, builds on committed first run `313d9de`; changes left
uncommitted as requested. Third design in `elo_fitted_scale.py`: non-major
domestic slope {ln(10)/400,.0070,.0085,.0103} × K {20,24,28,32}, majors and
international slope ln(10)/400 and K 20. Reuse opt-in event slopes and
`league_factors`, leaving international callbacks and offset rules native.
One predeclared boundary extension: .0045/.0121 or K 16/36 on the selected
lower/upper edge; score new Cartesian cells once, selected through 2021 only.
Same objective, held-out sections and curve/FORGE refits as the first run.
Adds current-data 20/28 and tuned K-only controls, plus the existing recent
roster-change slice without extra replay/DB work. Published behavior untouched.

Training winner: other slope .0070 / K 24, objective .620996 (published
.621480). Interior optimum: no extension needed. Regenerated report:
[`elo_fitted_scale.md`](../research/elo_fitted_scale.md).

Held out 2022–2026, Δ LL versus published (paired-game bootstrap 95% CI):
Elo domestic +.000051 (−.000216, +.000339), international +.000243
(−.000280, +.000776); FORGE domestic +.000086 (−.000087, +.000272),
international same as Elo; other-league Elo −.001899 (−.002351, −.001428),
FORGE −.000812 (−.001167, −.000456); cross-league Elo −.003496
(−.004760, −.002196). Recent roster-change slice (2,527 major/international
games, either lineup changed <5 games ago): Elo +.000199 (−.000375, +.000773),
FORGE +.000232 (−.000130, +.000597), both inside noise.
**Passes the requested significance rule:** gains in both targeted sections,
no reported section significantly worse; the earlier uniform/tier designs
still fail domestic FORGE. Recommendation: **iterate**, no production release
in this research change; confirm with earlier-only calibration and native
release guards, plus series-cluster sensitivity. Historical holdout has been
repeatedly viewed; international calibration is disabled equally for all arms
as in the first run, so this is published ratings with refitted curves, not
today's calibrated international forecast.

Slope adds beyond K: the current-data K-only tuning winner is K-major 20 /
K-other 28 (objective .621141). Compared directly with that arm, the new design
improves other-league Elo −.000531 (−.000733, −.000339), FORGE −.000767
(−.000926, −.000616), cross-league Elo −.002633 (−.003660, −.001646),
and domestic FORGE −.000379 (−.000599, −.000181), all significant.
This compares jointly tuned slope/K with tuned K-only, not a fixed-K slope
ablation. Surprise: K-only 20/28 significantly hurts domestic Elo (+.001015)
and FORGE (+.000465) despite native major callbacks; changed incoming player
ratings and refitted curves can propagate across leagues. Offset rules remain
native, not identical offset values after changed history. The older
`elo_k_tier.md` includes 20/28 in tuning but only reports selected 28/28 held
out; the new same-data 20/28 control avoids conflating baseline versions.
No new production bug found; the existing frozen international-calibration
artifact incompatibility and pandas input-cast warning remain documented.

Checks: 67 focused Elo/harness tests pass in 0.98 s; full suite 802 passed,
2 skipped, 1 existing loky CPU-count warning in 22.43 s under shared load
(first run recorded 799 / 2 skipped in 10.28 s; not an isolated cost estimate).
Three added research tests cover grid/extension scope, exact native-option
parity and hand-calculated mixed-event slope/K updates; isolated run 3 passed
in 0.92 s including startup, one call .01 s and two <.005 s. Default full replay
reproduction max error 1.14e−12 across 205,858 team-games. Repository-wide ruff
format/check and whitespace pass. Relative file links in all changed docs pass.
41 grid replays of 102,929 games: median 7.06 s, range 3.63–10.18 s;
selected non-major arm 3.90 s; whole experiment 400.6 s, all with
VECLIB_MAXIMUM_THREADS=1. No production/CI/publish/hourly work, new dependency,
DB change, or fitted artifact change. No Actions timing: branch not pushed.

Native check (manager, same day): `bootstrap_elo` patched in a throwaway worktree (`elo-nonmajor-native`, not merged) to use slope .0070 and K 24 in non-major domestic games, `004_bootstrap_elo.py` rerun, then `evaluate_metrics.py --dump` on base and candidate and `compare_benchmarks.py`. No guarded value significantly worse. Cross-league Elo −0.0022 (−0.0030 to −0.0014), within other leagues per-league Elo −0.0012 (−0.0016 to −0.0009), within other leagues FORGE −0.0004 (−0.0006 to −0.0002); domestic FORGE +0.0001 (−0.0000 to +0.0002), international FORGE/Elo +0.0003 (−0.0000 to +0.0005). Unguarded: international Form +0.0004 (worse; not a published forecast) and other-league Elo on the 400-point curve +0.0011 (expected, the ratings spread more). These rolling sections include the tuning years. Still to check before shipping: `evaluate_markets.py` (our calls vs Kalshi), the published `league_curves.json`/FORGE refit, and the international calibration fitted on the old scale.

## 2026-10-19 — Elo expected-score scale with K retuned (research)

Branch `elo-fitted-scale`, based on `177004c` (future-work documentation).
Fixed grid: update slope {ln(10)/400, .0070, .0085, .0100} × K {12,16,20,24,28};
plus .0085 major/international and .0103 other-domestic slopes with the same K grid.
Tune through 2021 with the existing games-weighted domestic + other-league Elo
objective; shared harness refits the forecast curves and FORGE blends.
Published behavior, DB and fitted weight artifacts unchanged. Report:
[`elo_fitted_scale.md`](../research/elo_fitted_scale.md). Best uniform .0070 / K 24
(train LL .620959 vs published .621480); tier .0085/.0103 selects K 20.

Held out 2022–2026, uniform Δ LL (paired game bootstrap, 95% CI): Elo domestic
+.000599 (−.000373, +.001650), international +.002774 (−.000835, +.006651);
FORGE domestic +.000975 (+.000361, +.001647), international +.002774
(−.000835, +.006651); other-league Elo −.001959 (−.002417, −.001479),
FORGE −.000842 (−.001200, −.000477); cross-league Elo −.004108
(−.005615, −.002553). Tier also fails: domestic FORGE +.001015
(+.000287, +.001807), despite significant other-league/cross-league gains.
Verdict: drop the proposed change; both violate the no-regression significance
rule. No significant major-league Elo/international gain. Held-out descriptive
refit slopes for the uniform winner: majors/international .00939438, other
pooled .01060021, still steeper than update .0070. Duration-weighted update
scores are not binary outcomes, so equality is not required.

Evaluation issue found: the newer international calibration artifact replaces
refitted FORGE probabilities with its frozen old-scale slope. Disable it locally
for both baseline and variants; no published setting or shared scorer changed.
This baseline means published ratings with refitted curves, not today's
calibrated international calls. Keep prior harness limits explicit: out-of-year
fits can use later held-out seasons, other-league FORGE Form weights use all
other years, intervals resample games rather than series, repeated historical
research is not an untouched holdout. One pandas cast warning during input load.

Default reproduction max error 1.14e−12 over 205,858 team-games. Replay median
4.85 s (4.69–6.07 s), 102,929 games; experiment 195.1 s with
VECLIB_MAXIMUM_THREADS=1. No build/CI job, dependency, DB read or runtime fitting
added to production. Unit checks cover exact default arithmetic, a hand-made
slope/K update and event-slope override order. Full suite: 799 passed, 2 skipped,
1 warning in 13.64 s; focused Elo/harness: 64 passed in 4.74 s. Repository-wide
ruff format/check and git diff whitespace pass. Final full-suite confirmation: 799 passed, 2 skipped, 1 existing loky CPU-count
warning in 10.28 s. Same suite excluding the seven added cases: 792 passed,
2 skipped in 8.96 s (separate runs under shared load; not an isolated cost
estimate). All seven added case durations are individually <5 ms; selected
run 0.68 s including startup. That small test cost buys default-parity and
scale/row-order guards; the research grid is never run by CI. Changed-document
relative file links (all five documents), ruff format/check and whitespace pass.
No Actions timing is available because this branch is not pushed, as requested.
The sandbox rejects index.lock writes in the main repo's external worktree metadata;
the reviewed change is committed on `elo-fitted-scale` in a temporary Git repository
and exported as `/tmp/elo-fitted-scale.bundle`. The actual worktree branch ref
remains at the base until that bundle is applied.

## 2026-10-19 — Player Elo RD v2: reference tied to floor

Branch `elo-glicko`, based on `177004c` (future-work documentation on
main `b0acbac`), in the pre-existing dedicated worktree. V1 was confounded:
reference above floor reduced veteran K to about 9 or 5 instead of 20.
All v1 numbers remain under **v1 (flawed: reference above floor)** in the
[generated report](../research/elo_glicko.md) and [archive](../research/elo_glicko_v1.md).

V2 fixes reference=floor. Fixed before tuning: floor 60/80/100, new/floor
1.5/2/2.5, growth 10/20/35, information 0.25/0.5/1 (243 settings across
replacement keep/drop rookie discount and on-top arms), with one predeclared
local Cartesian boundary extension per arm (25 additional settings, 268 total).
V1 side normalization also moved settled K when lineup uncertainty differed;
v2 applies weights independently per player. An initial tuning attempt keeping
normalization was aborted before any held-out scoring; its scores were discarded
and the same grid restarted. `player_rd_normalize=True` retains v1 compatibility.
`player_rd_information` slows shrinkage; default `player_rd=None` stays published.
At E=.5 without inactivity, information .25 stretches RD 250→100 from 11 to 41 games.

Tuned on 2014–2021 only, frozen before 2022–2026 scoring. Winner replaces
provisional/away, keeps rookie discount: new=280, floor=reference=140,
c=10, information=.125. Tuning loss 0.620024 vs published 0.621480.
Initial winner (new=200, floor=100, c=10, information=.25) was on three
boundaries. After the one extension, floor/information remain on expanded
boundaries: explicitly unresolved, not a bracketed optimum. Floor and information
trade off via information × floor²; a future grid can use dimensionless parameters.

Held-out Δ log loss vs published, paired game bootstrap 95% interval:

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62229 | -0.00051 (-0.00132 to +0.00026) |
| Elo, international | 589 | 0.61851 | +0.00039 (-0.00094 to +0.00176) |
| FORGE, domestic | 7,728 | 0.62003 | +0.00014 (-0.00036 to +0.00061) |
| FORGE, international | 589 | 0.61144 | -0.00013 (-0.00100 to +0.00076) |
| Elo, other leagues | 37,272 | 0.60410 | -0.00283 (-0.00347 to -0.00220) |
| FORGE, other leagues | 37,272 | 0.60121 | -0.00108 (-0.00155 to -0.00062) |
| Elo, cross-league | 5,442 | 0.57353 | -0.00068 (-0.00222 to +0.00091) |

Roster-change slice: domestic 703, international 9, other leagues 6,814,
cross-league 682 games. Other-league Elo −0.00269 (−0.00421 to −0.00116)
and FORGE −0.00169 (−0.00289 to −0.00051), both significant. All other
slice intervals span zero; international has only nine games. On-top RD
improves other-league Elo significantly (−0.00147) but FORGE is inside the
noise; dropping the discount significantly harms other-league Elo/FORGE and
cross-league Elo. Full tables and all tuning scores are in the report.

**Verdict: passes the AGENTS.md significance gate** (two targeted gains,
no significant guarded regression). **Recommendation: iterate on the remaining
boundary optimum before choosing production constants; no published change here.**
V1's negative conclusion about uncertainty is superseded. This is Glicko-style
RD, not full Glicko-2: no g(RD), volatility estimation or league RD. Shared
harness probability curves/blends fit out of year within partitions; the
other-league helper's Form feature fits use all other major-league years,
including tuning years. Not an expanding-window deployment simulation. Intervals
are over games rather than series and are not multiplicity-adjusted.

Checks actually run: all 205,858 DB team-games reproduce (max |Δ| 1.14e-12).
The chronological tuning prefix (49,342 of 102,929 games) matches the full
published replay exactly; all three selected RD prefixes also match full
replays exactly. Focused suite 56 passed in 0.90 s; full suite **816 passed,
2 skipped** in 16.67 s; final confirmation after report/timing helper edits:
**816 passed, 2 skipped in 9.56 s** (existing sandbox core-detection warning).
Earlier v1 full suite was 804 / 2 in 13.31 s; these concurrent-machine runs
cannot isolate the extra test cost. Tiny examples cover information arithmetic,
floor timing, mixed settled/rookie direct weights, v1 normalization, unchanged
default, invalid options and cohort/grid/prefix/alignment guards.
Repository-wide ruff format/check, script --help, local document links and
whitespace checks pass.

Main experiment: 772.8 s (12.9 min), 268 prefix replays median 1.84 s
(1.78–4.25 s). Selected full RD replays 3.93–4.06 s; initial baseline 6.88 s
faced different machine load. A paired AB/BA/AB check (three runs each) gives
published median 3.54 s and selected RD 3.87 s (+0.33 s, +9.3%).
This overhead applies only to an RD replay; production/CI keep the disabled path.
No added CI step, dependency, production fit or DB read. The opt-in mechanism
adds no per-game RD computation to published calls. No DB/schema, published
metric/weights, site or build change; no rebuild/refit needed for this research.
Used `.venv/bin/python` and `VECLIB_MAXIMUM_THREADS=1`; uv crashes in this sandbox.
All edits remain uncommitted by request; no push or PR.

Native check (manager, same day): the v2 winner (RD 280/140/140, c 10, information 0.125, provisional and away factors off) applied in `bootstrap_elo` in a throwaway worktree (`elo-combo-native`, not merged), Elo rebuilt, `evaluate_metrics.py --dump` on base and candidate, `compare_benchmarks.py`: no guarded value significantly worse. Within other leagues per-league Elo −0.0022 (−0.0026 to −0.0017), FORGE −0.0007 (−0.0011 to −0.0004); domestic Elo −0.0007 (−0.0012 to −0.0002), domestic FORGE +0.0000 (−0.0003 to +0.0003); international −0.0000 (−0.0007 to +0.0007); cross-league −0.0003 (−0.0013 to +0.0007). Combined with the non-major update scale (`elo-fitted-scale`; each tuned alone, not jointly): cross-league −0.0019 (−0.0035 to −0.0004), other-league Elo −0.0020, other-league FORGE −0.0003 (−0.0009 to +0.0002), domestic Elo −0.0006; the gains overlap rather than add. The rolling sections include the tuning years. Before shipping: one more extension of floor/information (both on the boundary), `--write-weights` and `league_curves.json` refit, `evaluate_markets.py`. Note that v2 player moves are not zero-sum between teams when their RDs differ (as with the published provisional factor).

## 2026-10-19 — Future work: player win share and Elo rating model

Branch `future-win-share`, based on `b0acbac` (main). Documentation only: added two Future work items to `docs/steering/current_state.md`: splitting Elo changes among starters by their share of an in-game lead (gold difference at 15/20 minutes or similar), and the Elo rating model (expected score on the fitted slope with K retuned; Glicko-2-style uncertainty; later TrueSkill Through Time or dynamic Bradley-Terry). No code changed; no checks beyond reading the rendered Markdown.

## 2026-10-18 — Prepare API draft v2 as a private live candidate

Branch `live-draft-v2` (PR #92), base `f999333`, updated with main `b0acbac`. `live.draft` resolves all ten Riot participants to OE players by role, side, champion and exact names (team-scoped first; no fuzzy matching); failures fall back to the current model. The first valid receipt freezes the draft shift, later conflicts stop its use, and the context persists across restarts. One read-only SQL pass exports the v2 histories (earlier UTC days) in the daily ratings artifact (about 12 s more on main's export, 18 MB); the worker reads no DB. `time_model_draft_v2.json` runs as a private shadow (`calls.jsonl`); public calls unchanged. `evaluate_live.py --model` and `prepare_draft_benchmark.py` replay it. Checks: 20-map API sample, 17 resolved; features reproduce within 4.4e-14; 822 passed, 2 skipped; ruff; CI passed on PR #92; replay +4 ms per map. Limit: availability timing is a proxy; upload and reload timing unmeasured.
