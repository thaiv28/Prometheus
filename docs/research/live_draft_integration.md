# API draft v2: private live integration

Prepared on `live-draft-v2`, main base `f522db3`, research base `f999333`.
The worker records the v2 candidate alongside current predictions. Published
map, pregame and series chances remain unchanged. No video input is involved.

## Input and inference contract

The existing Riot window supplies champion, role, participant ID, player name
and esports player ID. Exact normalized names resolve within the team's earlier
history first; a unique global identity handles transfers. Known team codes
handle unspaced tags such as `IGRookie`. Collisions remain unresolved. Riot and
OE IDs are never equated. Five distinct roles on each side, unique participants,
players and champions are required; champion tokens use a small explicit alias
map for Riot internal names such as MonkeyKing → Wukong.

The daily live-input artifact exports v2's four historical features using only
earlier UTC days. Sparse residuals retain v2's shrinkage constants. The worker
performs lookups and frozen inference; no new provider request, DB read or fit.
The first complete received observation freezes features and shift, bounded
by when the worker loaded its model/history. Recovered metadata cannot backdate
that input availability. Later
conflicting/invalid metadata stops subsequent candidate use without revising
previous calls. Restart reuses the map context. Model/map mismatches, stale
history, incomplete identities or missing objectives retain existing fallbacks.

The candidate is exactly the tested objective/momentum + v2 shift + shift×time
fit: live train 2024, calibrate 2025 H1; calibration/test draft weights fit
2019–2024. It embeds the unchanged production parent. The worker declines to
run this candidate against a different parent. The private call journal stores
candidate calls, input context and fallback reason; public model outputs stay
on the parent. Its retrospective gain was −0.00302 log loss (95% −0.00582 to
−0.00043); see [v3 comparison](live_draft_v3.md). No new feature tuning occurred.

## Validation

- Actual API: 20 bounded historical window requests, 17 complete identity
  resolutions and three conservative name fallbacks. Transfers and unspaced
  tags account for most initially unresolved drafts. These are historical
  requests with first-window availability proxies, not original receipt times.
- Prior-day history parity: all four features on 20 sampled real maps agree
  with frozen research inputs within 4.4e-14. The whole current day is excluded.
- Native benchmark: 1,665 maps, 54,557 calls, 3,344 pre-map records. On a copy
  enriched with those 17 API drafts, the current CI comparator passes every
  guard (pooled checkpoint delta −0.0002, 95% −0.0007 to +0.0003). All other
  maps fall back. Pregame and pre-map calls are identical. This is a functional
  check with limited coverage, not a new significant accuracy result.
- Recorded KC–C9 map 5: 5,743 actual collector frames and real receipt times,
  complete draft resolved, 26 candidate calls. Three-run median complete-map
  replay: baseline 40.88 ms, candidate 44.82 ms. Parallel scoring adds about
  45 ms to the existing ten-second model cycle; quote-only cycles are unchanged.
- Daily export: 14.01 s before key caching, 11.56 s after; about 18.3 MB including
  global name aliases. One SQL pass; no new CI job or dependency. The extra work
  is in the main-only input export. PR builds/hourly work do not run it.

Identity collisions, receipt gating, contradictory metadata, map reuse,
whole-day causality, rolling-window boundaries, side orientation, exact
fallbacks, private journaling and export inference parity have focused tests.
Final full suite, CI and measured Actions timings are recorded in the work log.

## Reproduction

Use an isolated DB and preserve the frozen research caches as gitignored data.
Normal production history export is `scripts/export_live_inputs.py --out …`.
To export the frozen candidate from the original research inputs:

```bash
uv run python scripts/research/freeze_live_draft.py \
  --games data/research/draft_v2/player_feats_games.pkl \
  --fit data/research/live_draft_v3/v2_research.json
```

To build a **separate** benchmark copy with a bounded API screen:

```bash
uv run python scripts/prepare_draft_benchmark.py --fetch --limit 20 \
  --games data/research/draft_v2/player_feats_games.pkl \
  --out data/research/draft_api/benchmark.json.gz
uv run python scripts/evaluate_live.py \
  --data data/research/draft_api/benchmark.json.gz --dump /tmp/draft-base/live
uv run python scripts/evaluate_live.py \
  --data data/research/draft_api/benchmark.json.gz \
  --model prometheus/live/time_model_draft_v2.json --dump /tmp/draft-head/live
uv run python scripts/compare_benchmarks.py /tmp/draft-base /tmp/draft-head
```

The helper never replaces the pinned file; omit `--fetch` to reuse cached API
responses. It validates both Riot sides and a unique OE game before exporting
minimal lookup rows. Its metadata retains response hashes and historical timing
provenance. Do not republish this small functional sample as prospective evidence.

## Before activation

Collect private calls on untouched matches, measure identity coverage and input
age, audit real receive-time gating and UTC rollover fallbacks, then compare
candidate/base accuracy and calibration on the same maps. Expand the pinned
benchmark with actual observed draft availability and run the existing guarded
comparison through the production inference path. Activation is a separate
change after that evidence; this PR provides usable observation and replay.
