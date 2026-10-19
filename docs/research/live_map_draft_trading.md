# Draft v2 live-map trading comparison

Prepared 2026-10-19 on `live-map-trading`, integrating main `bc02c4e` (PR #92).
The original implementation is based on research `e35e5d0` / main `f522db3`.
The user authorized merge and live activation **conditional on improving benchmarks**.
That condition fails: keep this PR unmerged and live-map execution disabled.
No production configuration, infrastructure, credential or order was changed.

## Fixed comparison

Use the existing 30-second policy, 5-cent net edge, minutes 5–30, no series shift,
unchanged sizing and monthly equal-map logistic fits (C=1, no intercept), only
series completed more than 24 hours before the month. Change only the frozen
raw-model input to PR #92's draft v2. Do not tune rules, features, slices or
exclusions after scoring. Pair the same map-minute calls, weight maps equally,
and bootstrap whole series 2,000 times with the original fixed seed.

Input: the original 1,666-map pinned asset; frozen four-feature draft game table
from the merged research, whole-current-day exclusion and pre-2025 draft weights.
Unambiguous blue/red/date joins cover 1,663 maps. This is an **OE draft proxy**;
it assumes picks are available from map start and does not establish actual API
identity or receipt availability. Three missing/ambiguous joins retain the exact
parent model **and parent blend**, rather than refitting their fallback.
All routes keep the whole cohort. Evaluated: 1,352 maps / 655 series / 32,158 calls.
The artifact records data, DB, draft feature, model and parent-blend hashes.

## Results

| Metric | Original 30s blend | Draft v2 blend |
|---|---:|---:|
| Historical paper entries | 189 | 219 |
| Flat-dollar ROI, after ordinary modeled fees | +21.05% | +18.74% |
| Whole-series 95% interval | +1.83% to +41.61% | −0.76% to +38.18% |
| Two-minute price change toward our side | +1.24 cents | +0.67 cents |

The paired equal-map log-loss change is **−0.00133**, 95% **−0.00437 to +0.00174**:
improvement is inconclusive. FST worsens significantly on its 24 maps:
**+0.02692** (+0.01188 to +0.04563). Other named leagues and the early/mid/late
bands have no significantly worse result. The gain and no-regression requirements
both fail. The earlier broad draft-v2 research gain does not imply incremental
gain after blending with market prices. No benchmark override is appropriate.

ROI uses the same $1 all-in stake per entry as the original report; it is not
return from buying one contract per entry. Entry sets differ, so their separate
ROI intervals are not a paired significance test of strategy returns. Trade
prices are not executable asks; depth, fills, fees under fragmented execution,
source receipt and queue latency are absent. These repeatedly reviewed historical
results provide no untouched or prospective confirmation.

## Review implementation

The private worker uses its already-resolved/frozen draft context when ready at
the frame's receipt. Signals include the pinned model/context, exact input
features, earlier-day history and blue-oriented FORGE prior. Consumer recomputes
the prior shift and map probability, verifies model/artifact/parent hashes,
map identity, history day, readiness and invalidation at both receipt and current
decision time, then uses separate draft
monthly coefficients. Missing/conflicting draft metadata selects the unchanged
objective/momentum model and original blend. Missing snapshot months fail closed.
Neither route changes public page calls or adds online fitting/DB/provider reads.

The existing quarter-Kelly/map/series/global limits, vetoes, immutable candidate
and duplicate fences, actual-book/fee guards, modes and transport remain intact.
The isolated package includes `draft.py`, the frozen draft model and its blend;
source fingerprints and publish filters cover them. This also supplies timeline's
new dependency on `draft.py` following the main merge.

This artifact explicitly records `improvement_gate: false`. It is exported for
review/reproduction, not permission to activate. Existing off-by-default controls
remain. Merge/deployment/activation await a new justified improving candidate and
successful CI and rollout verification; they have not been scheduled automatically.

## Reproduce

```bash
uv run python scripts/research/live_map_draft.py \
  --data /path/to/live_maps-0705f02b1edf.json.gz \
  --db /path/to/prometheus.db \
  --games /path/to/player_feats_games.pkl \
  --out-dir data/research/live_map_draft \
  --artifact /tmp/live_map_draft_blend.json
uv run pytest -q
uv run ruff check
uv run ruff format --check
bash deploy/execution/package.sh /tmp/live-map-execution.zip
```

The script rejects unpinned cohorts/features, writes only explicit outputs and
exports the review artifact even when its gate fails. Its comparison JSON keeps
every named slice. Local comparison wall time: 10.49 s. No CI job or runtime
research dependency is added. Final checks and Actions timings are in the work log.

## Final local validation

873 tests pass in 11.01 s; the two optional real signing tests pass separately
in 0.16 s. Ruff format/check, shell syntax, whitespace and 110 relative document
links pass. Shared runtime blend matches all 32,158 replay rows within 1.12e-16.

The API-enriched native replay scores 1,665 maps / 54,557 calls / 3,327 pre-maps
and passes all existing Live comparator guards. Only 17 January maps have API
drafts; all later API-absent maps retain the parent exactly. This limited screen
checks inference/fallback behavior, not improvement of the trading strategy.
Parent/candidate replay takes 1.60 s / 1.55 s; the small timing difference is noise.

The Linux executor zip has 192 files / 5,038,625 bytes. Source-content parity,
private-input exclusion and isolated scheduled/SQS OFF smoke pass, including
loading the draft artifact without numpy/pandas/sklearn/cryptography. Package
SHA256: `ac8c5a027af42fb0c3c710772428060faf7892e73e096280183185b3dc27ac6b`.
No deployment, account reads/settings, order submission or activation occurred.
