# Live map trading protocol — 2026-10-18

Declared before this experiment's scoring. Research only; no deployment, model,
account settings or orders change. Runtime base f522db3. Input is the pinned
1,666-map trade-tape benchmark, SHA256
0705f02b1edf6df391809ba59a34ea4857fe2224757d7c509225e3875692422c.

Primary: current frozen objective/momentum model; estimated minutes 5–30;
one first qualifying entry per map, either side (largest net edge); hold to
settlement. Monthly expanding logistic blend, no intercept, C=1, market and
model log odds. Each map has total fitting weight one. Fit only series whose
last recorded map ended at least 24h before month start; minimum 100 series
and 200 maps. Whole series excluded from their own fit. Compare on identical
eligible months against raw current model, raw v1 and an earlier-only fitted
market-only calibration. No hyperparameter selection on these results.

Require valid objective inputs, non-flat source sample, finite market price
at arrival (source+21s), at least two trades in previous 21s spanning <=1 cent,
last trade <=10s old, and a backing-side trade no older than that window.
Cost proxy is max(backing trade cost, latest side price). Net edge >=5 cents
per $1 payout AFTER 7% quadratic taker fee, rounded up to 0.0001 dollars per
contract. Flat returns assume continuously divisible contracts and $1 total
outlay including fee; actual lot/fill-level rounding and available depth unknown.
This is a tape proxy, never an asserted executable ask.

Secondary sensitivities: no stability filter; 10/30s windows; 3/10/15-cent
net edges; +1/+2/+3/+5-cent purchase-cost stresses (both frozen entries and
entry selection rechecked). These do not select a winning strategy. Historical
book depth, actual receipt age, outages and order fills cannot be reconstructed
from this input. Invalid matching exclusions inherit the pinned data audit.

Report per-map averaged log loss, paired series-bootstrap blend-minus-market
intervals, fixed-$1 all-in ROI with 2,000 whole-series bootstrap draws, CLV and
monthly results. No claim of untouched holdout: base model/test have already
been examined in prior research.

Kelly fractions 0.1/0.25/0.5/1, same selected entries and fee-inclusive costs;
fraction of bankroll at risk f=max(0,(p-cost)/(1-cost)). Compare ideal sequential
compounding against event-time cash reservations (settlement proxy recorded
map end+5min, no early reuse). Start $100, no leverage, continuous quantities,
no liquidity or order caps; also report quarter Kelly with 1% map/2% series
outlay caps. Drawdowns are on cost-valued equity, not live liquidation value.
The settlement proxy does not claim historical exchange settlement latency.
