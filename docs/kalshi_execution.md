# Kalshi execution

Prepared implementation; **not deployed or activated**. No credentials installed and no orders placed. The initial central mode is `off`. This is an executor for existing saved proposals, not another paper portfolio. Alerts and their $1 modeled tracking continue independently in every mode.

## Authoritative proposals

`prometheus.alert_contract.saved_alerts` reads the private, successfully persisted `prometheus/predictions/predictions.json` object. New `alert` records pin schema version, fixture/alert identity, backed canonical team, both canonical teams, first fixture start and event ticker in `alert.execution`; probability/ask remain the original saved values. Provider-ID, ordering and later fixture changes do not alter the pinned identity. Legacy posted `international_paper_alert` is recognized, never rewritten; unposted `paper_alert` is excluded. No issue prose, public export, reconstructed candidate or current selector is an execution instruction.

The six groups share one notification policy (>5-point edge, 6h, fresh ask and complete results). Grouping is for reporting. Execution applies additional current account/book/fee/spending controls to the saved proposal; a notification does not guarantee an order.

## Runner and durable state

A 5-minute EventBridge rule invokes a Python 3.12 Lambda independently of EC2, GitHub runner timing and site builds. Each run reads the latest private log, covering both daily and hourly successful saves. Retries and missed runs are safe within the explicitly configured alert-age limit. Every mode change sets a new activation timestamp, so enabling live cannot purchase old alerts. No synchronous invocation or extra dependency is added to normal site/price jobs.

The retained encrypted DynamoDB table has `pk`/`sk` string keys and point-in-time recovery. Separate demo/live namespaces hold intent, active pointers, fixture/event fences, UTC-day spending, account exposure, latest skips and individual fill/settlement evidence. Intent plus spending reservations and both duplicate fences are atomic before submission; a conditional claim permits only one submitter. Stable client order IDs supplement these durable guards. No automatic retry sends a second order after an uncertain response. Unknown outcomes keep their entire reservation until exchange evidence resolves them; “not found” alone never releases it. Fences have no TTL.

The package exports the same 37 explicit team aliases used by alerts; the runtime applies these fixed aliases without fuzzy matching or loading site dependencies. Market resolution requires the exact event, two unambiguous canonical team outcomes and matching fixture time/rules. It rediscovers the executable route: backed team YES, or opponent NO; the saved event ticker/aggregate ask is not itself an executable market. Fresh books, actual tick grids, authoritative event fee-override history, announced series/event fee changes through fixture start and account data are read before submission. The capped IOC limit never exceeds the original ask or configured price cap; it uses available size at the selected price, without walking to worse levels. Partial fills are retained; the canceled/unfilled remainder is never reissued. Whole-contract orders can still receive fractional fills, so fee reservations conservatively include fragmentation/rounding and require verified account balance precision.

Order creation uses the documented [V2 event order endpoint](https://docs.kalshi.com/api-reference/orders/create-order-v2), fixed-point price/count and YES-book `bid`/`ask` direction. Current [fixed-point](https://docs.kalshi.com/getting_started/fixed_point_migration) and [fee rounding](https://docs.kalshi.com/getting_started/fee_rounding) rules are part of the fee bound; actual fill fees and settlement evidence remain private. Fee profiles come from [event override history](https://docs.kalshi.com/api-reference/events/get-event-fee-changes) and [series fee changes](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes).

## Modes and pause

- `off`: submit nothing. With an empty ledger, do not read the large log or credentials. Continue reconciling prior demo/live intents and positions; cancel only tracked outstanding orders when found. Keep uncertain reservations. Never liquidate existing positions. Alerts and existing paper tracking remain active.
- `demo`: use demo credentials/API and private demo ledger. It creates actual demo orders, not another local paper mode.
- `live`: use live credentials/API and private live ledger. Requires explicit valid limits and a fresh activation epoch. Credentials do not migrate between environments.

Changing environment pauses old-environment orders and continues reconciliation there. IOC orders normally leave no resting quantity; an unexpectedly resting tracked order is canceled and re-read before releasing any remainder. Pause takes effect at the next invocation (normally within 5 minutes); the mode/config is also fetched immediately before every submission. An in-flight HTTP request cannot be recalled by a mode change. Existing filled positions remain held until settlement. Scalar/fair-price settlement releases exposure only with a finalized exact market, explicit settlement value and verified private cash-settlement evidence; ambiguous, netted or missing/archived private evidence stays reserved for manual review. A source-log outage still runs existing-intent reconciliation before reporting failure for retry.

## Configuration required before activation

The infrastructure branch in `project-platform-infrastructure` defines `ThaivPrometheusExecution` only. Base: `c615e0f`, then merged infrastructure main `fcb5f12` (PR #15), including the existing live stack. This task does not deploy it. Prepare the following explicitly:

1. Build the isolated runtime zip from the reviewed application commit: `bash deploy/execution/package.sh /tmp/prometheus-execution.zip`. It contains only the adapter/executor/handler and signing dependency, no DB, saved log, `.env`, credentials or site output. The deployment artifact goes in the existing **private** artifacts bucket at `prometheus/execution/releases/<zip SHA256>.zip`.
2. Separately create API credentials for the intended demo/live account and store each as a Secrets Manager JSON secret with `key_id` and `private_key_pem`. For demo-only setup, the separate live secret can remain empty; do not install live credentials before a separately authorized live rollout. Do not put keys in GitHub variables, the prediction log or application `.env`. Use the minimum order/read/cancel scopes the API supports for the account. If using a customer-managed KMS key, supply the narrowly scoped decrypt permission separately; the prepared stack assumes the normal Secrets Manager managed key.
3. Supply stack parameters `ArtifactsBucketName`, immutable `CodeObjectKey`, the reviewed upload’s `CodeObjectVersion`, `demoSecretArn` and `liveSecretArn`. Store the secrets in `us-west-2`, the runner’s region. The table/config/schedule/private failure queue and exact-ARN IAM grants are created only by a separately authorized targeted deployment. Never deploy all application stacks for this change.
4. Configure the SSM parameter `/prometheus/execution/config` with the fields below **while keeping mode off**. No spending values are provided by the implementation. Configure the GitHub variables `KALSHI_EXECUTION_CONTROL_ROLE_ARN` and `KALSHI_EXECUTION_CONFIG_PARAMETER` from the stack outputs. The dedicated main-branch OIDC control role can only read/write this one parameter; it cannot read credentials, invoke trades or change the ledger.
5. After separate demo validation, use the manual **Kalshi execution mode** workflow’s `off`/`demo`/`live` dropdown. It validates explicit limits, preserves them and writes a fresh activation timestamp. Live remains a separate user decision; nothing in this implementation switches it on automatically.

| Field | Meaning |
|---|---|
| `mode` | `off`, `demo` or `live`; initial `off` |
| `activation_at` | Timezone-aware timestamp set by manual control; new proposals must be at/after it (minute-resolution saved alerts in the activation minute may conservatively be skipped) |
| `max_alert_age_seconds` | Maximum age of a saved alert when submitting, including retries/missed runs |
| `max_quote_age_seconds` | Maximum age of the freshly fetched executable book |
| `max_price` | Absolute dollar price cap per backed contract, inside (0,1); original ask also caps it |
| `min_after_fee_edge` | Required probability minus current price and conservative per-contract fees |
| `fee_rate_upper_bound` | Explicit bound on supported current quadratic fee rate; metadata above it is rejected |
| `balance_precision_usd` | Verified account precision: 0.0001 for Direct or 0.01 otherwise; no inferred default |
| `order_budget_usd` | Maximum cost plus reserved fees on one order |
| `fixture_budget_usd` | Maximum cost plus fees for a fixture; only one order/fixture is permitted |
| `daily_budget_usd` | UTC-day gross spend plus unresolved reservations; settlement does not replenish it |
| `max_exposure_usd` | Maximum open exposure/reservations including account positions and resting orders |
| `min_balance_usd` | Cash that must remain after reservation |
| `max_contracts` | Positive whole-contract order cap; actual fills may be fractional |

The fee bound deliberately does not count on later rebates. Non-Direct cent-aligned accounts may have no executable edge under the conservative fractional-fill bound. Existing account exposure and local reservations are counted conservatively, potentially twice while exchange views lag; this can skip viable orders rather than exceed limits.

## Verification boundary

Mocked tests cover the saved-alert adapter/identity, V2 payload/direction, books, limits, conditional reservations, concurrent claims, configuration changes, timeouts, incomplete fills, cancellations, fees and settlements. Final local application suite: 623 passed, including 77 executor/API tests and 6 runner/control boundary tests. Both pending actual public fixtures resolved to exact YES/opponent-NO routes in about 1.3 seconds each (six unauthenticated reads); no account requests or orders. A local CDK synthesis/test checks off default, retained private storage, scheduling, exact-resource permissions and the control-role boundary. All 15 infrastructure tests and full synthesis pass. The local full site build runs without importing the executor. The 5.0 MB, 178-file Lambda zip was inspected for private inputs and smoke-tested in isolated Python: off-mode imports load no site or signing dependencies. Linux native wheels are packaged, but AWS runtime behavior remains unverified.

Still unverified: deployed IAM/KMS access, real DynamoDB transactions, Lambda packaging on AWS, scheduler/retry timing, account signing permissions/precision, actual demo orders/fills/cancellations and settlement. Public market reads can verify metadata shape but cannot establish authenticated execution correctness. Before any live activation, validate these in demo, inspect the private ledger/failure queue, prove off/pause and timeout recovery, and explicitly choose account limits. Do not delete ledger fences or clear unknown reservations merely to retry an order; resolve exchange evidence first.
