# Selected 30-second strategy: implementation validation

Implementation branch `live-map-trading`, base research `e35e5d0` and main
`f522db3`. The user selected this sensitivity after seeing historical results;
it is not an independent confirmation or a new optimized strategy.
[Contract/rollout](../live_map_execution.md), [original research](live_trading.md).

## Historical numerical parity

Input calls are the original 32,158 earlier-only calls from 1,352 maps / 655
series, March–October 2026. The production blend and shared entry kernel reproduce
all 189 selected 30-second entries, sides and tape costs. Maximum monthly
probability difference: 5.6e-16.

| Pricing convention (trade tapes only) | Entries | All-in flat ROI | Series-bootstrap 95% interval |
|---|---:|---:|---|
| Original rounded ordinary fee | 189 | +21.05% | +1.83% to +41.61% |
| Existing fragmentation-aware executor fee reserve | 130 | +25.70% | +1.48% to +51.28% |

The second row is a fee-policy sensitivity, not an executable-price backtest.
Neither row reconstructs historical asks, depth, receipt age, fills or actual
settlement time. Provider pagination/freshness and the one-candidate delivery
path cannot be inferred from those tapes. Production is stricter and can skip
these entries. Returns retain repeated-test/model-selection limitations.

For completeness, historical **30-second** Kelly paths differ from the original
21-second primary result discussed earlier. With $100 seed, ordinary paper fees,
continuous quantities and end+5min settlement proxy:

| Sizing | Ending bankroll | Cost-valued maximum drawdown |
|---|---:|---:|
| Tenth Kelly | $215.30 | 15.24% |
| Quarter Kelly | $540.71 | 35.06% |
| Half Kelly | $1,432.48 | 60.73% |
| Full Kelly | $1,264.61 | 89.84% |
| Quarter, 1% map / 2% series caps | $146.25 | 6.37% |

These are observed idealized paths, not expected returns. The implementation caps
against **free capital**, incorporates the conservative fee reserve, respects
real depth and shares pregame commitments; it does not reproduce these dollar
paths as a promise or use the historical best fraction to select sizing.

## Inference parity and measured cost

On a real recorded KC–MVK map 2 (7,768 frames), enabling private model inputs
preserves default prediction values exactly. An otherwise skipped final frame
sharing the same receipt cannot borrow the previous frame's model prediction.
The measurement derives its start from the first stored clock estimate solely
for a same-input CPU comparison; this does not validate the estimated clock.

- Existing complete-history timeline pass: median 53.19ms, five warm runs.
- Additional private observation: median 55.02ms, five warm runs, once per feed update.
- Shared policy evaluation: median 0.059ms, 100 warm runs.
- Disabled: no additional market requests, observer replay or AWS delivery.
- Enabled: up to two bounded trade GETs per eligible two-second cycle until the
  first candidate, plus candidate-only S3/SQS and consumer revalidation calls.
  Source freshness/window checks precede the extra GETs. Actual provider/queue
  latency is unmeasured and must be checked in shadow after rollout.
- New series exposure is one extra item within existing DynamoDB transactions,
  not another transaction request; real AWS latency has not been measured.

Full local checks and the package checksum are recorded in the newest work-log
entry. No normal publish/hourly fitting or DB read, new dependency, CI job or
benchmark step was introduced. Forecast and season-stat scripts were rerun with
a read-only SQLAlchemy connection to the existing DB (22.10s / 3.76s), producing
temporary reports; no core forecast/season weights changed or shared DB rebuilt.

## Scope of verification

Tests cover coefficient chronology/symmetry, 30s boundaries/deduplication, source
identity and stale/invalid observations, actual-ask/fee gating, preserved personal
vetoes, exact map/parent rules, private S3-before-SQS delivery, restart fencing,
queue provenance/type checks, shadow's prohibition on credentials/private APIs,
mode activation, post-claim expiry, shared reservations/races, partial fills,
exactly-once settlement, and duplicate uncertain submissions/relisted events.
CloudFormation is linted locally; no AWS resources or account settings were
changed. Transport/IAM permissions, actual request cadence, queue latency and
live shadow/order/fill behavior remain rollout checks, not completed evidence.

Final local suite: **827 passed, 2 skipped in 8.66s**. The two optional signing
cases pass separately with pinned cryptography (0.13s). The source-only Linux
package is 5,031,248 bytes / 189 files; exact source-content parity, private-input
exclusion and isolated scheduled/SQS OFF smoke tests pass. No pandas/numpy/
sklearn/cryptography import is needed for those disabled paths.

Package SHA256: `8bbe0120b01b21a7bf7d2d57abc671f2e9c2c7af087a670250ff07838051b9e8`.
Source SHA256: `313a9553af741966810d3d7de00ca4b5853b6c9ca6f2132199acf7c7fb9f775a`.

Explicit November refit exports nine valid earlier-only snapshots into a
review-only temporary artifact. The committed artifact retains the eight tested
March–October fits; absent months still reject signals until a reviewed refit.
