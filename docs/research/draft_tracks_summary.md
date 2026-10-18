# Draft research tracks: results and v3

All seven tracks are complete, based on `draft-v2` at `5811254`. Each candidate was fixed before scoring. Work stayed in isolated branches; no published metric, weight, site, live runtime or trading configuration changed.

The v3 candidate retains v2's four features and adds the **whole seven-feature player block**. It improves pooled log loss from 0.607059 to 0.605070 on 63,638 walk-forward maps: **−0.001990 (series-bootstrap 95% −0.002518 to −0.001441)**. Before 2025: −0.002198 (−0.002834 to −0.001584). The gain is concentrated in other leagues; major-league improvement remains uncertain. [Full v3 comparison](draft_v3.md), [protocol fixed before track results](draft_v3_protocol.md).

## Seven verdicts

Negative log-loss differences favour the candidate. First four tracks compare the fixed whole feature block plus v2 against v2 on identical maps. Series and live use the different controls stated below. Intervals resample series; they are not multiplicity adjusted.

| Track | All: difference (95%) | Majors: difference (95%) | Before 2025: difference (95%) | Verdict |
|---|---|---|---|---|
| [Composition](draft_composition.md) | +0.000008 (−0.000072, +0.000085) | −0.000137 (−0.000322, +0.000045) | −0.000010 (−0.000104, +0.000087) | Inconclusive; excluded |
| [Player-on-champion recency](draft_form.md) | −0.000103 (−0.000242, +0.000035) | +0.000153 (−0.000244, +0.000532) | −0.000118 (−0.000301, +0.000056) | Inconclusive; excluded |
| [Meta / patch / priority](draft_meta.md) | +0.000131 (−0.000016, +0.000269) | +0.000077 (−0.000297, +0.000449) | +0.000210 (+0.000016, +0.000408) | Reject; worse before 2025 |
| [Player features](draft_player_feats.md) | −0.001990 (−0.002518, −0.001441) | −0.000005 (−0.000954, +0.000965) | −0.002198 (−0.002834, −0.001584) | Qualifies as a whole block; included |
| [Market edge](draft_market_edge.md) | No trading policy selected | No selected bets | No priced maps | Inconclusive; no demonstrated executable edge |
| [Live draft prior](live_draft_prior.md), versus same-row refit | −0.0029 (−0.0055, −0.0003) | −0.0044 (−0.0078, −0.0007) | No test period | Promising against refit; frozen-v1 comparison inconclusive |
| [Series posterior](series_score.md), maps 2+ versus constant first-map call | −0.0055 (−0.0067, −0.0043) | −0.0004 (−0.0028, +0.0020) | −0.0052 (−0.0067, −0.0037) | Keep as a research candidate; adaptation null |

The four pre-map tracks score 63,638 maps; the series track scores 26,885 maps 2+; the live track scores 3,825 feed maps. LPL, international, other-league and annual slices are in the linked reports.

## Interpretation

The player block contains pool breadth, concentration, membership in the player's top three champions, prior champion-specific lane gold/XP above the player's own average, role changes and substitute indicators. Its joint gain does not establish that every column helps individually. LPL lane snapshots cover only 19.9% of current player rows; histories use only observed earlier snapshots, with shrinkage, and the test cohort retains complete-draft LPL maps.

Composition's international subgroup improves, but the fixed all/pre-2025 gates fail. Recency's 30-day half-life was chosen only on 2020 (fit 2019); its test improvement is within noise. Neither subgroup/coefficient inspection selected a new subset. Meta's first three patch days show no reliable gain, and its pre-2025 degradation rules out the whole fixed block.

For the market track, the −60 s entry has 395 first-half maps with a trade no older than 30 s. Shrunk/capped shifts and the fixed fees/nearby-fill requirements yield zero first-half bets at all thresholds; the +45 s secondary entry has at most eight. Neither clears the predeclared minimum of 30. The policy therefore abstains on the second half: zero bets and zero total Kelly growth; per-bet ROI and return intervals are not estimable. Prices move toward the shift by 0.7–0.8 points at +1/+3 minutes, which is not evidence of an executable fill. No local pre-map books were found; remote backup storage was not inspected.

The live experiment uses draft **v2**, not the new player-augmented **v3**. V3 has not been benchmarked inside the live model and no live draft input has been enabled. V2 live draft inputs help most in minutes 0–20. Against frozen v1, however, the all-map interval still crosses zero. Live input computation/identity, a fresh period, and comparison with the current model remain necessary. For series, earlier-only fitted rho is about 0.09; the posterior helps mostly outside the majors. Adding that posterior to v2 improves later-map LL by −0.0050 (−0.0062 to −0.0037), while earlier-draft/reuse adaptation adds no reliable gain. These separate questions did not enter the pre-map v3 union.

## Validation and next work

The [v3 protocol](draft_v3_protocol.md) admitted entire fixed primary blocks only if both all-map and pre-2025 intervals were below zero and no named league slice was significantly worse. Only player features qualify, so v3 is the same player-augmented candidate, with no further selected combination. All four full training/test caches have exactly 80,791 games, including 2019/2020 training rows; baseline columns, outcomes and row order are checked before joining.

This remains retrospective. Selecting blocks using these years means v3's pre-2025 result is no longer an untouched confirmation, even though those years did not select v2's original features. Current FORGE artifacts also inherit their original fitting periods. Ordinary intervals condition on the selected blocks. Confirm on untouched future maps before describing v3 or the live/series candidates as prospectively validated.

Each track passed its full test suite and repository ruff checks. Final integrated suite: **780 passed, 2 skipped in 9.50 s**; format/lint/diff checks pass, all ten research documents' local links resolve, and an exact-source v3 rerun completes in 7.62 s. Baseline review: draft [PR #84](https://github.com/thaiv28/Prometheus/pull/84), all checks green. Published research review: aggregate [PR #89](https://github.com/thaiv28/Prometheus/pull/89); focused player/live/series drafts [#86](https://github.com/thaiv28/Prometheus/pull/86), [#87](https://github.com/thaiv28/Prometheus/pull/87), [#88](https://github.com/thaiv28/Prometheus/pull/88). Integration adds a deterministic parity test for an equivalent faster research bootstrap: identical series draws and row weighting, with per-series sums/counts replacing repeated row concatenations. On 63,638 maps / 37,318 series / 200 identical draws, old 1.413 s → new 0.0316 s; maximum numerical difference 2.71e−20. Actual analyses retain 2,000 draws. Production code and CI job definitions are unchanged.

Next: review the research; decide whether a post-draft map call or live integration is the first product target; collect prospective draft inputs and executable quotes. The series posterior merits a separate production-accuracy study, including home-league tier parity and production/market benchmarks, before changing the shown map chance. No candidate was exported or deployed.

## Local branches and reproduction

The promising track branches and synthesis were pushed for draft review on 2026-10-18 after the user continued beyond the local handoff. Aggregate PR #89 (based on `draft-v2`, PR #84) contains all seven research commits and this synthesis. Focused drafts #86/#87/#88 overlap the aggregate: use one merge path, retaining the aggregate if all evidence is wanted. Null/rejected track branch heads remain local, with their commits preserved in the aggregate. No PR was merged and no model deployed.

| Branch | Completed track commit |
|---|---|
| `research/draft-composition` | `c1c987b` |
| `research/draft-form` | `63f0981` |
| `research/draft-meta` | `602eb25` |
| `research/draft-player-feats` | `b5a2613` |
| `research/draft-market-edge` | `4ae06ed` |
| `research/live-draft-prior` | `f15a8a6` |
| `research/series-score` | `729172b` |

Run each named script in a worktree with its own built DB and the supplied frozen `data/research/draft_v2/forge.pkl`; raw/trade symlinks remain read-only. The live script requires `--rows` pointing to the saved `train_time_model_v2` row cache (input/provenance hashes in its report). The four pre-map scripts save `{composition,form,meta,player_feats}_games.pkl`, including training years. Then:

```bash
uv run python scripts/research/draft_v3.py \
  --block composition data/research/draft_v2/composition_games.pkl scaling,scaling_strength,early \
  --block form data/research/draft_v2/form_games.pkl decayed_exp,recency,share \
  --block meta data/research/draft_v2/meta_games.pkl patch_meta,local_meta,priority \
  --block player_feats data/research/draft_v2/player_feats_games.pkl breadth,depth,top_pool,lane_gold,lane_xp,role_swap,substitute \
  --out docs/research/draft_v3.md
```

The synthesis also writes machine-readable `draft_v3.json`; source-cache hashes are recorded in the report. Preserve worktree caches until the branches are merged or abandoned and data have been moved safely, as the handoff requires.
