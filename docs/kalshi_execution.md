# Kalshi execution

Deployed 2026-10-16 in **off** mode (`ThaivPrometheusExecution`, us-west-2). The live credential is installed in Secrets Manager; demo remains empty. Approved limits are now saved while off: $50 seed/full Kelly, $50 order/fixture/exposure, $100 gross UTC-day spend, Direct-member 0.0001 precision. The new blended/Kelly runtime was deployed automatically after PR #69 (`3eb6baf`). No orders placed by this rollout. Two deployed off-mode smoke invocations and a local signed live balance-read check passed. User elected to skip demo after code/test review. Runtime, saved limits and read-only live authentication were verified during rollout; the user subsequently reported funding and enabled live (activation observed 2026-10-17 02:54:45 UTC). The 0.01-contract update below remains prepared, not deployed. This is an executor for existing saved proposals, not another paper portfolio. Alerts and their $1 modeled tracking continue independently in every mode.

## Authoritative proposals

`prometheus.alert_contract.saved_alerts` reads the private, successfully persisted `prometheus/predictions/predictions.json` object. New `alert` records pin schema version, fixture/alert identity, backed canonical team, both canonical teams, first fixture start and event ticker in `alert.execution`; probability/ask remain the original saved values. Provider-ID, ordering and later fixture changes do not alter the pinned identity. Legacy posted `international_paper_alert` is recognized, never rewritten; unposted `paper_alert` is excluded. No issue prose, public export, reconstructed candidate or current selector is an execution instruction.

Five groups share one notification policy: positive blended edge above ask plus estimated fees, 6h, fresh midpoint/ask and complete results. Major/minor domestic and every international group qualify; other cross-league fixtures do not. New proposals freeze raw and blended inputs and the monthly snapshot. Historical records retain their original terms. Execution skips every Cloud9 fixture (either side), and at international events any bet against a North American team (LCS, NA LCS, LTA N or NACL). Alerts still include those signals. Home leagues are pinned by canonical team name; missing international homes skip execution. Execution applies additional current account/book/fee/spending controls to the saved proposal; a notification does not guarantee an order.

## Runner and durable state

A 5-minute EventBridge rule invokes a Python 3.12 Lambda independently of EC2, GitHub runner timing and site builds. Each run reads the latest private log, covering both daily and hourly successful saves. Retries and missed runs are safe within the explicitly configured alert-age limit. Every mode change sets a new activation timestamp, so enabling live cannot purchase old alerts. No synchronous invocation or extra dependency is added to normal site/price jobs.

The retained encrypted DynamoDB table has `pk`/`sk` string keys and point-in-time recovery. Separate demo/live namespaces hold intent, active pointers, fixture/event fences, UTC-day spending, account exposure, latest skips and individual fill/settlement evidence. Intent plus spending reservations and both duplicate fences are atomic before submission; a conditional claim permits only one submitter. Stable client order IDs supplement these durable guards. No automatic retry sends a second order after an uncertain response. Unknown outcomes keep their entire reservation until exchange evidence resolves them; “not found” alone never releases it. Fences have no TTL.

The package exports the same 37 explicit team aliases used by alerts; the runtime applies these fixed aliases without fuzzy matching or loading site dependencies. Market resolution requires the exact event, two unambiguous canonical team outcomes and matching fixture time/rules. It rediscovers the executable route: backed team YES, or opponent NO; the saved event ticker/aggregate ask is not itself an executable market. Fresh books, actual tick grids, authoritative event fee-override history, announced series/event fee changes through fixture start and account data are read before submission. The capped IOC limit never exceeds the original ask or configured price cap. The prepared fractional update compares feasible sizes in 0.01-contract increments on the best level of each route and selects the highest expected log growth, without walking to worse levels. Partial fills are retained; the canceled/unfilled remainder is never reissued. Orders can fill in smaller fragments, so fee reservations conservatively include fragmentation/rounding and require verified account balance precision. The deployed whole-contract release predates the fractional update described below.

Order creation uses the documented [V2 event order endpoint](https://docs.kalshi.com/api-reference/orders/create-order-v2), fixed-point price/count and YES-book `bid`/`ask` direction. Current [fixed-point](https://docs.kalshi.com/getting_started/fixed_point_migration) and [fee rounding](https://docs.kalshi.com/getting_started/fee_rounding) rules are part of the fee bound; actual fill fees and settlement evidence remain private. Fee profiles come from [event override history](https://docs.kalshi.com/api-reference/events/get-event-fee-changes) and [series fee changes](https://docs.kalshi.com/api-reference/exchange/get-series-fee-changes).

## Modes and pause

- `off`: submit nothing. With an empty ledger, do not read the large log or credentials. Continue reconciling prior demo/live intents and positions; cancel only tracked outstanding orders when found. Keep uncertain reservations. Never liquidate existing positions. Alerts and existing paper tracking remain active.
- `demo`: use demo credentials/API and private demo ledger. It creates actual demo orders, not another local paper mode.
- `live`: use live credentials/API and private live ledger. Requires explicit valid limits and a fresh activation epoch. Credentials do not migrate between environments.

Changing environment pauses old-environment orders and continues reconciliation there. IOC orders normally leave no resting quantity; an unexpectedly resting tracked order is canceled and re-read before releasing any remainder. Pause takes effect at the next invocation (normally within 5 minutes); the mode/config is also fetched immediately before every submission. An in-flight HTTP request cannot be recalled by a mode change. Existing filled positions remain held until settlement. Scalar/fair-price settlement releases exposure only with a finalized exact market, explicit settlement value and verified private cash-settlement evidence; ambiguous, netted or missing/archived private evidence stays reserved for manual review. A source-log outage still runs existing-intent reconciliation before reporting failure for retry.

## Configuration required before activation

Infrastructure PR #16 is merged at `349a744`; application PR #65 is merged at `eb11b9e`. The original execution-only deployment used the initial off configuration. Its runtime SHA256 was: `e084ef9506eb5d7c7fed46e89fb30a6d2d34ff74ce817887ef5e8bf027dbbd02`; its private release key and VersionId are pinned in CloudFormation. Deployment used the synthesized CDK template through a reviewed CloudFormation CREATE change set. The following describes setup/redeployment and remaining activation requirements:

1. Build the isolated runtime zip from the reviewed application commit: `bash deploy/execution/package.sh /tmp/prometheus-execution.zip`. It contains only the adapter/executor/handler and signing dependency, no DB, saved log, `.env`, credentials or site output. The deployment artifact goes in the existing **private** artifacts bucket at `prometheus/execution/releases/<zip SHA256>.zip`.
2. Secrets `prometheus/execution/demo` and `prometheus/execution/live` are provisioned. The live value is installed; demo remains empty. For future credential changes, create API credentials for the intended demo/live account and store each as a Secrets Manager JSON secret with `key_id` and `private_key_pem`. For demo-only setup, the separate live secret can remain empty; do not install live credentials before a separately authorized live rollout. Do not put keys in GitHub variables, the prediction log or application `.env`. Use the minimum order/read/cancel scopes the API supports for the account. If using a customer-managed KMS key, supply the narrowly scoped decrypt permission separately; the prepared stack assumes the normal Secrets Manager managed key.
3. Supply stack parameters `ArtifactsBucketName`, immutable `CodeObjectKey`, the reviewed upload’s `CodeObjectVersion`, `demoSecretArn` and `liveSecretArn`. Store the secrets in `us-west-2`, the runner’s region. The table/config/schedule/private failure queue and exact-ARN IAM grants are created only by a separately authorized targeted deployment. Never deploy all application stacks for this change.
4. Configure the SSM parameter `/prometheus/execution/config` with the fields below **while keeping mode off**. No spending values are provided by the implementation. Configure the GitHub variables `KALSHI_EXECUTION_CONTROL_ROLE_ARN` and `KALSHI_EXECUTION_CONFIG_PARAMETER` from the stack outputs. The dedicated main-branch OIDC control role reads/writes this one parameter and reads the executor release metadata; it cannot read credential secrets, invoke trades or change the ledger.
5. The user elected to skip demo on 2026-10-16 after code/test review. Once sizing findings are reviewed and explicit limits/account precision are configured, use the manual **Kalshi execution mode** workflow’s `off`/`demo`/`live` dropdown. It validates explicit limits, preserves them and writes a fresh activation timestamp. Live remains a separate user decision; nothing in this implementation switches it on automatically.

| Field | Meaning |
|---|---|
| `mode` | `off`, `demo` or `live`; initial `off` |
| `activation_at` | Timezone-aware timestamp set by manual control; new proposals must be at/after it (minute-resolution saved alerts in the activation minute may conservatively be skipped) |
| `max_alert_age_seconds` | Maximum age of a saved alert when submitting, including retries/missed runs |
| `max_quote_age_seconds` | Maximum age of the freshly fetched executable book |
| `max_price` | Absolute dollar price cap per backed contract, inside (0,1); original ask also caps it |
| `min_after_fee_edge` | Minimum probability minus current price and conservative per-contract fees; zero permitted, but net edge must still be strictly positive |
| `fee_rate_upper_bound` | Explicit bound on supported current quadratic fee rate; metadata above it is rejected |
| `balance_precision_usd` | Verified account precision: 0.0001 for Direct or 0.01 otherwise; no inferred default |
| `order_budget_usd` | Maximum cost plus reserved fees on one order |
| `fixture_budget_usd` | Maximum cost plus fees for a fixture; only one order/fixture is permitted |
| `daily_budget_usd` | UTC-day gross spend plus unresolved reservations; settlement does not replenish it |
| `max_exposure_usd` | Maximum open exposure/reservations including account positions and resting orders |
| `min_balance_usd` | Cash that must remain after reservation |
| `max_contracts` | Positive whole-number quantity ceiling; the prepared update sizes orders in 0.01 increments below it |
| `starting_bankroll_usd` | Explicit strategy capital; e.g. 50 for the requested $50 start, not the entire exchange balance |
| `kelly_fraction` | Explicit capital multiplier in (0,1]; 1 is full Kelly, smaller values scale capital used by the calculation |

The fee bound deliberately does not count on later rebates. Non-Direct cent-aligned accounts may have no executable edge under the conservative fractional-fill bound. Existing account exposure and local reservations are counted conservatively, potentially twice while exchange views lag; this can skip viable orders rather than exceed limits.

## Verification boundary

Mocked tests cover the saved-alert adapter/identity, V2 payload/direction, books, limits, conditional reservations, concurrent claims, configuration changes, timeouts, incomplete fills, cancellations, fees and settlements. Original pre-deployment application suite: 623 passed, including 77 executor/API tests and 6 runner/control boundary tests. Both pending actual public fixtures resolved to exact YES/opponent-NO routes in about 1.3 seconds each (six unauthenticated reads); no account requests or orders. A local CDK synthesis/test checks off default, retained private storage, scheduling, exact-resource permissions and the control-role boundary. All 15 infrastructure tests and full synthesis pass. The local full site build runs without importing the executor. The 5.0 MB, 178-file Lambda zip was inspected for private inputs and smoke-tested in isolated Python: off-mode imports load no site or signing dependencies. The Linux package ran successfully in AWS off mode: cold invocation 3,851 ms plus 109 ms initialization, warm 389 ms, peak 105 MB at 256 MB allocation. Runtime SSM access and both consistent DynamoDB ACTIVE queries succeeded. No secret or source access is needed in empty off mode.

Follow-up review found no blocking defect in identity/route validation, atomic reservations, duplicate fences, uncertain-response handling or pre-submit mode checks. The 86 execution/API/runner/contract cases passed in 1.09 s. The live key parsed locally, was uploaded through stdin without a credential temporary file, and its AWSCURRENT value was verified in memory. A single signed live GET balance request authenticated and parsed successfully; account amounts were suppressed and order endpoints were prohibited. Trading remains off.

Still unverified: runtime credential/source IAM access, real DynamoDB write transactions, retry timing, account precision, actual orders/fills/cancellations and settlement. The first scheduled off invocation and the main-branch off control are verified. Authenticated reads do not establish order/fill correctness. User chose to skip demo; finish the sizing review and explicit account limits before activation, retaining these verification limits. Do not delete ledger fences or clear unknown reservations merely to retry an order; resolve exchange evidence first.

## Blended runtime

The source package adds the monthly artifact and recomputes the saved raw probability against a fresh backed-side market midpoint from narrow two-sided books before evaluating the current ask. Missing/unknown snapshot or missing midpoint cannot fall back to raw odds. Actual execution probability/net edge are retained privately alongside original alert terms. The blended/Kelly zip is now deployed through main publish `38988256036`; code/source checksum and version pinning are verified.

Kelly sizing now uses starting capital plus verified settled profit minus open/reserved cost. Fees are included in the unit cost; the prepared 0.01-grid quantities maximize expected log growth within depth, cash and order/fixture/day/exposure caps. The original sizing change supplied no defaults; the later approved off-only configuration is recorded below. No deposits were made by this rollout. Turning off stops new orders and retains reconciliation of existing positions.

## Kelly bankroll and activation

Original whole-contract support is deployed; approved settings were saved while off, and the user later enabled live. The fractional-grid source update below remains unreleased. Active modes now require explicit `starting_bankroll_usd` and `kelly_fraction` in addition to every existing limit. For the requested starting capital/full-Kelly policy these two fields would be `"50"` and `"1"`; both are installed following the user’s explicit approval. Missing values fail activation. Changing the seed deliberately changes the strategy budget; it is not a top-up mechanism and never deposits money.

Let B = starting capital + ACCOUNT.realized − ACCOUNT.held. Fractional Kelly scales B by `kelly_fraction`; B excludes open commitments and unrealized profits. Price plus conservative per-contract fee bound is c; frozen/refreshed probability is p. Continuous full-Kelly contracts are B*(p−c)/(c*(1−c)). In the prepared fractional update, compare neighbouring feasible 0.01-grid quantities and zero using p*log(1+n*(1−c)/B)+(1−p)*log(1−n*c/B). Skip non-positive growth or any count that exhausts capital on a loss. A positive alert edge may still be too small for a profitable 0.01-contract order.

The ledger atomically checks the observed held/realized values, total strategy capital and all existing caps when reserving. Raced funding snapshots cannot submit. Partial fills release only unused reservation; unknown responses keep funds reserved. Verified settlement credits our fill quantity’s contractual payout minus actual cost/fees, never pooled account revenue. Credit and release use the intent revision transaction, so retries cannot double-compound. Losses reduce future sizes; exhausted capital stops orders. Daily gross-spend caps do not refill on wins.

This is sequential Kelly on free strategy capital under the existing one-order-per-fixture rule, not a joint optimizer of correlated open positions. Account exposure/reservations remain conservatively counted and may suppress bets. The probability estimate and fee bound determine the answer; sizing is not a profitability guarantee. The objective follows [Kelly’s original paper](https://www.princeton.edu/~wbialek/rome/refs/kelly_56.pdf); the fee-aware unit-contract conversion above is our derivation.

## Deploy on merge and configure live

The `Publish` workflow runs `deploy-execution` after the existing checks, beside the site build. A main push touching packaged executor inputs triggers it; the changed-file range covers the entire push. PRs and scheduled site builds never deploy the executor. For repair, dispatch **Publish** on main with `deploy_execution` checked. An obsolete main revision is rejected before deployment. Identical source fingerprints skip the update after runtime verification.

Infrastructure must be merged/deployed first, using **Deploy Prometheus Execution Infrastructure** (`diff`, then `deploy`): the execution-only stack adds `CodeSourceHash`, release tags, the dedicated `DeployRoleArn` output and read access to Lambda release metadata for the control role. Preserve the existing code key/version and all other parameters during this bootstrap. Copy `DeployRoleArn` into `KALSHI_EXECUTION_DEPLOY_ROLE_ARN` and `FunctionName` into `KALSHI_EXECUTION_FUNCTION_NAME`. Existing control/config variables remain required. Bootstrap deployed through infrastructure PR #18 (`1b9f1ab`) and targeted workflow `38987448513`; both new GitHub variables are installed. Application PR #69 is merged (`3eb6baf`); its automatic release and the off-only configuration workflow succeeded.

The deploy role uploads only under private `prometheus/execution/releases/` and can update only this stack/function. The release helper pins the zip checksum and S3 VersionId, reuses the deployed template, and preserves every non-release parameter (including masked secret ARNs). It waits for stack completion and verifies the healthy runtime, package checksum and source tags without invoking the handler. Unexpected current-code drift fails before upload. No mode/configuration/credential/ledger writes are permitted by the release role. Existing live mode would stay live during a later code deployment; switch off first if you want to pause it.

After the first successful deployment:

1. Open **Actions → Configure Kalshi execution → Run workflow**, on `main`. Supply the complete settings JSON below after replacing the account-precision placeholder. This saves limits only while mode is off; it cannot activate trading. Later changes may supply just the changed limit fields. Workflows serialize configuration and mode changes in one concurrency group; direct console/CLI SSM writers must not run concurrently (SSM has no compare-and-swap).
2. Open **Actions → Kalshi execution mode → Run workflow**, on `main`, choose `live`. Activation checks the actual Lambda release fingerprint/checksum and all limits, then sets a fresh activation timestamp. An old or failed deployment cannot be activated by this workflow.
3. To pause, run the same mode workflow with `off`. It remains available without release verification or valid limits. The next scheduled invocation stops submissions and reconciles tracked positions.

Example for review: $50 seed, full Kelly, up to $50 on one order/fixture or open exposure, $100 gross UTC-day spend. These caps allow the starting capital to be used and limit later compounding until raised; they are not installed defaults. Kelly normally sizes below the order ceiling. `daily_budget_usd` is turnover, not a daily loss stop. `min_after_fee_edge: 0` still requires strictly positive net edge.

```json
{
  "starting_bankroll_usd": "50",
  "kelly_fraction": "1",
  "order_budget_usd": "50",
  "fixture_budget_usd": "50",
  "daily_budget_usd": "100",
  "max_exposure_usd": "50",
  "min_balance_usd": "0",
  "max_contracts": 10000,
  "max_price": "0.99",
  "min_after_fee_edge": "0",
  "fee_rate_upper_bound": "0.07",
  "balance_precision_usd": "REPLACE_WITH_VERIFIED_ACCOUNT_PRECISION",
  "max_alert_age_seconds": 3600,
  "max_quote_age_seconds": 30
}
```

Verify `balance_precision_usd` for the actual account: `"0.0001"` for Direct membership, `"0.01"` for non-Direct, per [Kalshi's rounding documentation](https://docs.kalshi.com/getting_started/fee_rounding). Do not choose based on the displayed balance or to make more bets pass. The placeholder intentionally fails validation. Fee rates above the configured bound cause a skip. With the existing conservative rounding bound, a non-Direct account may produce no executable bets; no trade is preferable to treating an unverified precision as fact.

The strategy spends only its seed plus verified profits and never deposits or borrows. Keeping the seed at $50 bounds planned strategy losses relative to inception to that funded capital (including reserved fees), even if the exchange account holds more. It does not enforce a $100 drawdown stop from a later profit peak: that feature is not implemented. Do not raise the seed merely to bypass losses or unresolved reservations. Existing positions/unknown fills can delay further trading and must reconcile from evidence. Full Kelly assumes the estimated probabilities are correct; profitability remains unproven.

## Verified rollout and activation failure (2026-10-16)

Infrastructure PR #18 (`1b9f1ab`) and application PR #69 (`3eb6baf`) are merged. The reviewed infrastructure-only diff/deploy passed (`38987448513`, UPDATE_COMPLETE); both new repository variables are installed. Main publish `38988256036` successfully ran `deploy-execution` in 36 s (4 s packaging, 24 s release/verification), alongside the site build. Runtime SHA256 is `58dc956c33a625cd41cd5c564e24d6950265dd289d1516d2f3001323a7aa2043`, exactly matching the inspected local zip. Source fingerprint `6f6993d62fcf9a8d476082ad07a8eb01a691f787e862efcfb835af84f6820487` and S3 object version are pinned in the stack; function state/update status and release tags match.

The user's attempted **Kalshi execution mode** run `38987614808` failed with `KeyError: max_alert_age_seconds` before writing SSM: the initial config had no limits. AWS authentication was working. The new **Configure Kalshi execution** run `38988387485` succeeded and saved every field of the approved example above (Direct precision `0.0001`), preserving off mode. Independent readback matches the approved JSON; active validation and runtime verification pass without writing live mode. A fresh signed live balance GET authenticated; available cash did not yet cover the planned seed. The user will fund the account manually.

To activate after funding: open **[Kalshi execution mode](https://github.com/thaiv28/Prometheus/actions/workflows/kalshi-execution-control.yml)**, select main, Run workflow, mode **live**. To pause, choose off. No live activation, orders or deposits were performed by this rollout. Actual order/fill/cancel/settlement paths and runtime credential reads remain unverified; the user's demo waiver is unchanged.

## 0.01-contract sizing update (prepared 2026-10-16)

`fractional-kelly`, based on main `1c03850`, changes the quantity grid from whole contracts to 0.01 increments, matching [Kalshi's fixed-point quantities](https://docs.kalshi.com/getting_started/fixed_point_migration). This is independent of `kelly_fraction`: 1 still means full Kelly. The continuous target and expected-log-growth objective are unchanged. Floor depth, the configured quantity ceiling and remaining cash/order/fixture/day/exposure capacity to the grid, then compare neighbouring feasible quantities and zero. A cap below 0.01 yields no order. API counts and sizing evidence are two-decimal strings; arithmetic remains Decimal.

The existing conservative per-unit fee bound is unchanged. At quantity q on the 0.01 grid, there are at most 100*q minimum-size fragments; multiplying the per-unit bound by q still covers each fragment's trade-fee rounding and balance alignment without relying on rebates. Tests exercise both supported account precisions. Finer sizing does not imply a fee discount. A 0.05-contract order partially filled for 0.03 retains only verified filled cost/fees; settlement releases/credits once, and no canceled remainder is reissued. Existing whole-contract intents reconcile at their original quantity; no migration or resizing is performed. `kelly-v1` remains the objective/accounting identifier, with optional `quantity_step: "0.01"` evidence for new plans.

Live mode was observed enabled at `2026-10-17T02:54:45.832381+00:00` following the user's action. This fractional update is source/package only, not deployed; merging its PR triggers the existing automatic release and preserves live mode. No mode, activation epoch, seed/fraction/limits, credentials, ledger or order changes are made by preparing the update. The original stale-alert cutoff and personal vetoes still apply. Live fractional order/fill behavior remains unverified; the user reviews/merges the release.
