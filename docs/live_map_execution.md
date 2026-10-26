# Live-map trading: review and rollout

Prepared on `live-map-trading`, based on research `e35e5d0` / main `f522db3`.
No infrastructure, credentials, account settings or orders were changed during
implementation. Existing pregame execution can remain enabled in production;
this strategy is absent/off until explicitly configured and activated.

## Draft v2 not adopted (2026-10-19)

Draft v2 as the model input failed the paired trading benchmark (no significant
gain; FST significantly worse), so its route was removed. The strategy uses the
objective/momentum model only. [Evidence](research/live_map_draft_trading.md).

## Strategy contract

`live-map-30s-v1` is the user's selected historical 30-second sensitivity:

- Individual map winners, estimated minutes 5–30 (research rounding retained).
- Frozen objective/momentum model, dated earlier-day Elo, **no series shift**.
  Public page calls retain their existing series shift; trading separately
  reconstructs the tested inputs and recomputes the pinned model probability.
  Model source-frame identity must match the latest observed source frame; a
  shared receipt timestamp cannot conceal an older successful prediction.
- Monthly earlier-series-only logistic blend on model and **last-trade** log odds.
  It does not substitute midpoint or the pregame market blend. The packaged
  artifact pins model/input/DB hashes, fitting counts and availability cutoffs;
  each signal also pins the artifact content hash.
- At least two distinct trades in the previous 30 seconds, price range <=1 cent,
  latest trade <=10 seconds old. This does not require a trade at each end of
  the window. Both team contracts are read, normalized, deduplicated and sorted.
- Valid objectives, no pause (ten seconds of unchanged gold after two minutes), exact identities and a current book.
  Receipt <=15s, source <=45s, model calculation <=8s, book <=3s; future or
  inconsistent timestamps fail closed. Signals expire eight seconds after
  selection. These are initial engineering limits, not backtest-tuned values.
- At least 5 cents of edge after the executor's **conservative fee reserve**, at
  the worse of the actual ask and the historical tape-cost proxy. Sizing uses
  current executable depth/price and the same fee reserve; no book walking.
- One first qualifying candidate per map on the worker; no later replacement
  after expiry or a rejected first attempt. A physical-map fence (canonical teams, scheduled start and map number), plus
  an exchange-event fence, prevents another submitted order after restarts,
  model releases, provider relisting or uncertain responses. Partial fills are kept; no remainder is reissued.

The ordinary fee used in research is smaller than the fragmentation-aware
execution reserve. The historical tape replay is therefore a parity control,
not a claim that production will fill the same 189 entries. Actual asks, receipt
ages and depth were not available historically. See [research](research/live_trading.md)
and [fixed protocol](research/live_trading_protocol.md). Selecting the 30s
sensitivity is explicitly the user's choice after viewing the comparisons.

The v1 producer fee profile mirrors the approved 0.07 upper rate and 0.0001
Direct-account precision. Different private fee settings reject the candidate
rather than silently changing its original terms. Update both through a reviewed
policy change if the account profile changes.

## Runtime path

1. Opt-in `prometheus.live.signals.Signals` observes the worker's private page
   data. Exact unshifted model inputs are calculated on feed updates, then
   reused on quote cycles until expiry. No additional DB read or online fitting.
   Out-of-window/stale inputs are rejected before extra market requests.
2. It reads both contracts' recent trades (two additional bounded GETs per
   eligible quote cycle), requires complete pagination, and checks the existing
   first-team book. Candidate/skip evidence stays in `data/live/.../trading/`.
   Journal lines carry match/game/map and ship to `/thaiv/prometheus/live/decisions`.
3. The candidate is written locally once, uploaded to the existing **private**
   artifacts bucket at `prometheus/live-trading/signals/<sha256>.json` with
   If-None-Match, then an SQS pointer is sent. Delivery retries reuse the same
   immutable bytes until expiry. No signing key is installed on the worker.
4. A batch-size-one SQS mapping invokes the **existing** execution Lambda. It
   checks the configured queue ARN, fixed bucket/prefix, digest and 128KiB bound;
   invocation data cannot contain an executable order. Disabled mode reads no
   source, account or credential. Malformed/expired entries become private skips;
   transient errors use partial batch failures and the retained dead-letter queue.
5. Consumer reconstructs the original decision, verifies the exact map and parent
   series rules, and fetches new books and both trade tapes. It repeats stability,
   model-age, blend, direction and edge checks using current data. Side changes,
   stale books, missing counters or unknown fee schedules skip the entry.
6. Live submission uses the existing atomic reserve/claim/IOC/reconcile path.
   The handler prints one `{"event": "live_map", ...}` JSON line per signal
   (outcome, result, skip reason) to the executor's CloudWatch log group.
   The ordinary five-minute schedule still reconciles positions; queue entries
   skip that potentially slow scan. Both triggers retain existing reserved
   concurrency and the ledger's independent concurrency protection.

This does not mark the research feed as `live_state_verified=true`, establish a
verified game clock, change public model probabilities.

## Capital and modes

`live_maps` is a separate, explicit nested configuration. Missing means off.
`off`, `shadow`, `live` have separate activation epochs; current global mode and
its activation epoch also gate real orders. Global off prevents all new orders.
A deployment cannot enable this strategy.

Pregame and live maps use one shared free capital pool: starting bankroll +
ACCOUNT.realized − ACCOUNT.held. Pregame retains global Kelly; live-map Kelly
fraction <=0.25, per-map outlay <=1% and map-series outlay <=2% of free capital.
Smaller nested fractions are supported. Global cash, fee precision,
order/fixture/day/exposure caps also apply; there is no separate live-map budget.
Optional global `series_fraction` caps combined pregame `SERIES#` and map
`MAPSERIES#` held cost for the same KXLOLGAME event against free capital.
Absent this key, that cross-strategy cap does not apply. The approved 10% value
will be saved separately through the configuration workflow.

A map order buys its current sized target minus filled contracts backing the
same team on the same series event, across all active pregame and map intents.
For example, 4.6 pregame contracts cover any map target <=4.6; a target of 6
buys only 1.4. Other-team holdings are ignored. Less than 0.01 remaining contracts
skips with `existing_position_covers_target`.

Pregame keeps `FIXTURE#`, `EVENT#` and `SERIES#` reservations. Maps use physical-map
`FIXTURE#`, exchange `MAPEVENT#` and map-only `MAPSERIES#` fences. The pregame-only
exchange fixture-position check still counts positions toward account exposure.
Reservations, partial fills and settlements update held cost atomically alongside
ACCOUNT, DAY and intent; the optional combined series cap is checked before
reservation, not atomically across concurrent pregame and map orders. Legacy
intents with `map_held_before` still release their `LIVE_MAPS` accounting; new
reservations do not write it. Old intents without `series_key` release `SERIES#`.
The existing Cloud9 and international anti-North-America vetoes apply.

Shadow mode uses public Kalshi endpoints only. It records the first proposed IOC
and displayed depth in DynamoDB's `ENV#shadow / MAP#...` namespace, with the source
signal key. It does not reserve live cash, assert fills, compound fictional profit
or access portfolio/signing endpoints. Its proposed sizing uses current ledger
commitments; it is observational validation rather than a simulated portfolio.

## Reviewable deployment pieces

- `deploy/execution/package.sh`: includes only executor, shared strategy/artifact
  and minimal stdlib live-model inference. No DB, .env, local evidence or account
  state. All new runtime inputs enter `release.source_hash` and publish filtering.
- `deploy/execution/live-map-transport.json`: separate CloudFormation transport
  stack, no existing resource ownership transfer. Encrypted retained queues,
  TLS-only policy, exact queue/prefix permissions and disabled-by-default mapping.
  Parameters: existing execution function ARN, its role name, worker role name,
  private bucket name and `QueueConsumerEnabled` (default false). The 900s queue
  visibility requires the existing Lambda timeout to be <=150s (AWS recommends
  six times the function timeout); verify that parameter before deployment.
- Existing `Configure Kalshi execution` saves nested limits **while global off**.
  `Kalshi live-map mode` controls only the nested strategy through the existing
  main-only control role/concurrency group and verified runtime fingerprint.
- Worker service reads optional `LIVE_MAP_SIGNAL_ARGS`; absent means unchanged
  request load. `backup.sh` includes private `trading/` candidate/decision evidence.

## Rollout after code review

1. Review the source diff, test results, deterministic zip contents/checksum and
   transport template. Main merges affecting packaged execution inputs use the
   existing automatic executor release and preserve global trading mode. The new
   strategy still defaults off. No new CI build/job/dependency was added.
2. Review/deploy the separate transport stack with mapping disabled. Confirm
   retained private bucket/queue encryption, function timeout/concurrency, exact
   worker/executor role parameters and the outputs QueueArn/QueueUrl. Do not
   deploy unrelated stacks. The template has not been deployed by this work.
3. Turn global execution off through its existing workflow before changing its
   limits. Save an explicit `live_maps` object using the existing configuration
   workflow, alongside the already approved global settings:

   ```json
   {
     "series_fraction": "0.10",
     "live_maps": {
       "mode": "off",
       "queue_arn": "arn:aws:sqs:us-west-2:ACCOUNT:QUEUE",
       "kelly_fraction": "0.25",
       "map_fraction": "0.01",
       "series_fraction": "0.02"
     }
   }
   ```

   No activation timestamp is supplied here; mode control creates it. Global
   limits and account precision remain explicit existing settings. This nested
   object is a reviewable recommendation, not an installed configuration.
4. Enable the queue mapping in a reviewed transport-stack update, then choose
   `shadow` in **Kalshi live-map mode**. Global execution may remain off for
   shadow observation. Re-enabling pregame execution is a separate existing control.
5. Add this quoted value to the worker's environment file, substituting real
   private outputs, and restart through the reviewed worker rollout:

   ```bash
   LIVE_MAP_SIGNAL_ARGS="--live-map-signals --signal-bucket PRIVATE_BUCKET --signal-queue QUEUE_URL"
   ```

   Local shadow recording without AWS delivery is also available:

   ```bash
   uv run python -m prometheus.live.service --fetch --live-map-signals
   ```

6. Inspect private worker decisions, S3 signals, `ENV#shadow / MAP#...` proposals,
   Lambda skips and queue age/dead letters during actual matches. Measure complete
   source→receipt→calculation→queue→fresh-book→decision latency. Confirm policy
   skips, actual sizes and fee bound before considering live activation. Proposed
   depth is not evidence an IOC would fill; this remains a material limit.
7. After review, enable global demo/live as intended and separately select `live`
   in the live-map workflow. It writes a fresh epoch, preventing old candidates
   from trading. Choose live-map `off` to pause only this strategy, or global
   `off` to pause all new orders. Neither control liquidates filled positions.

## Refit and reproduce

Artifact export is offline and reviewed. It reproduces tested March–October
snapshots from the pinned benchmark; a missing month **skips** rather than
carrying forward a stale snapshot. To add a requested month, use `--as-of`:

```bash
uv run python scripts/fit_live_map_blend.py \
  --data data/live_bench/live_maps.json.gz --db db/prometheus.db \
  --as-of 2026-11-01 --out /tmp/live_map_blend.json
```

Inspect hash/provenance, coefficients and replay before replacing the packaged
artifact. Refresh the pinned input through the existing benchmark process when
more maps are required; no worker or site build refits a blend.

```bash
uv run python scripts/research/live_trading.py \
  --data data/live_bench/live_maps.json.gz --db db/prometheus.db
uv run python scripts/research/replay_live_map_policy.py \
  --calls data/research/live_trading/calls.csv.gz --out /tmp/live-map-parity.json
uv run pytest -q
uv run ruff check
uv run ruff format --check
bash deploy/execution/package.sh /tmp/live-map-execution.zip
```

Local checks, replay results and measured cost are recorded in the newest
work-log entry and [implementation validation](research/live_map_implementation_validation.md).
Actual AWS transport/IAM, worker request latency, live shadow observations and
order/fill behavior require rollout verification; no production checks were
claimed in this implementation.

## Review checklist

- [x] Frozen model/artifact provenance and exact historical 30s numerical parity.
- [x] Shared capital, physical-map/event fences, uncertain-order and settlement checks.
- [x] Shadow isolation and explicit activation; emergency off survives malformed map settings.
- [x] 827 tests pass; two optional signing cases pass separately with pinned dependency.
- [x] Repository lint/format, shell syntax, document links and CloudFormation lint.
- [x] Package source parity, private-input exclusion and isolated OFF smoke tests.
- [x] Copy review: not applicable; no public UI/copy edits.
- [ ] Deployment verification of IAM, queue age, provider latency and real shadow decisions.

The final item is rollout work after code review; no infrastructure or trading
configuration was changed by preparing this implementation.
