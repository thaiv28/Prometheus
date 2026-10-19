# Historical live-map trading study — 2026-10-18

The primary earlier-only blend is promising but inconclusive: 273 entries, +8.9% after-fee flat ROI (95% series-bootstrap -4.8% to +23.9%). Blending improves accuracy over our model alone; its gain over the raw market still includes zero. The 30-second stability sensitivity has a positive ROI interval, but it is one of several comparisons on reused history, not a confirmed superior rule.

Full Kelly is mathematically available, but on this same historical path it falls 94.9% from peak to trough. Quarter Kelly falls 43.0%; a quarter-Kelly allocation capped at 1% per map and 2% per series falls 9.7%. These are observed cost-valued drawdowns under idealized trade prices. No Kelly fraction has a sequential mean log-growth interval excluding zero. Keep the primary rule frozen for an executable-book forward test; no strategy or Kelly fraction is selected by these retrospective returns.

Research only. Protocol fixed before this run: [protocol](live_trading_protocol.md).
The historical input contains trade tapes, not executable books. Every return below is a paper simulation.

Input: 1666 maps / 813 series; earlier-only scored cohort: 1352 maps / 655 series / 32158 calls.
Scored arrivals 2026-03-01T07:07:31.554000+00:00 to 2026-10-11T12:45:51.339000+00:00. Input/model/DB hashes and all ledgers are saved in `data/research/live_trading/`.

## Forecast accuracy

| forecast | log_loss | delta_market | interval |
|---|---|---|---|
| blend | 0.457819 | -0.006428 | [-0.01330705888925276, 0.00020083658818771988] |
| current | 0.466173 | 0.001926 | [-0.008485039049457358, 0.011887715072507226] |
| v1 | 0.480097 | 0.01585 | [0.0036798231933528247, 0.027129944549354322] |
| market | 0.464247 | 0.0 | [0.0, 0.0] |
| market_cal | 0.464862 | 0.000615 | [0.00010506049896781847, 0.0011863522502484826] |

Additional paired blend comparisons:

| control | delta | interval |
|---|---|---|
| current | -0.008354 | [-0.012378757366682324, -0.004380479432976088] |
| market_cal | -0.007043 | [-0.013949996518844576, -0.0004406070086082711] |

Equal-map log loss on every eligible 5–30 minute call, before entry filters. Intervals resample whole series; the market blend is fitted only to earlier completed series. Calibrated-market control uses the same chronology and regularization.

## Entries and flat returns

| strategy | bets | series | Win | ROI (95%) | CLV |
|---|---|---|---|---|---|
| Primary blend | 273 | 242 | 57.9% | +8.9% (-4.8%, +23.9%) | +1.25¢ |
| Current model | 421 | 338 | 60.3% | +7.4% (-4.4%, +21.0%) | +0.61¢ |
| Legacy v1 | 466 | 368 | 50.0% | -6.6% (-17.8%, +5.5%) | +0.84¢ |
| Calibrated market | 0 | — | — | — | — |
| Raw market | 0 | — | — | — | — |
| Blend no stability | 865 | 528 | 53.4% | +7.5% (-1.2%, +17.0%) | +1.12¢ |
| Blend 10s stability | 379 | 298 | 56.2% | +9.1% (-4.1%, +22.6%) | +1.56¢ |
| Blend 30s stability | 189 | 168 | 60.3% | +21.1% (+1.8%, +41.6%) | +1.24¢ |
| Blend net edge 3% | 413 | 337 | 58.4% | +5.7% (-6.8%, +19.7%) | +0.69¢ |
| Blend net edge 10% | 81 | 76 | 55.6% | +24.9% (-6.5%, +59.9%) | +2.63¢ |
| Blend net edge 15% | 20 | 17 | 50.0% | +19.9% (-41.7%, +85.9%) | +5.35¢ |
| Blend reselect +1% cost | 219 | 194 | 57.5% | +8.1% (-7.4%, +24.8%) | -0.47¢ |
| Frozen entries +1% cost | 273 | 242 | 57.9% | +6.3% (-6.9%, +20.6%) | +0.25¢ |
| Blend reselect +2% cost | 171 | 154 | 56.1% | +5.6% (-11.3%, +24.5%) | -1.10¢ |
| Frozen entries +2% cost | 273 | 242 | 57.9% | +3.8% (-8.9%, +17.5%) | -0.75¢ |
| Blend reselect +3% cost | 137 | 123 | 56.9% | +4.7% (-13.4%, +24.8%) | -0.86¢ |
| Frozen entries +3% cost | 273 | 242 | 57.9% | +1.6% (-10.7%, +14.7%) | -1.75¢ |
| Blend reselect +5% cost | 81 | 75 | 55.6% | +7.5% (-18.8%, +35.2%) | -2.43¢ |
| Frozen entries +5% cost | 273 | 242 | 57.9% | -2.6% (-14.1%, +9.8%) | -3.75¢ |

All-in $1 outlay per bet, including 7% quadratic taker fees rounded up per contract to $0.0001. One first entry per map. Primary: earlier-only blend, 5-cent AFTER-fee edge, estimated minutes 5–30, valid objectives, non-flat sample, latest trade within 10 seconds, >=2 trades in 21 seconds within 1 cent. Cost is max(recent backing-side trade, latest side price). CLV uses the trade price 120 seconds later, not an executable exit. Raw market cannot beat its own cost plus fees; that row is a negative control.

Sensitivity rows are exploratory, not a strategy selection. Frozen-entry stresses retain original choices and worsen cost; reselect rows require the same net edge at the stressed price. Neither reconstructs fills, depth, or additional latency.

## Monthly primary results

| month | bets | series | win_rate | price | probability | roi | lo | hi | profit_per_100 | clv | clv_n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-03 | 14 | 13 | 0.5 | 0.40357 | 0.51395 | 0.49547 | -0.46525 | 1.91408 | 49.54733 | 0.00429 | 14 |
| 2026-04 | 54 | 49 | 0.61111 | 0.535 | 0.63998 | 0.16619 | -0.16424 | 0.55796 | 16.6192 | 0.02333 | 54 |
| 2026-05 | 47 | 42 | 0.57447 | 0.5834 | 0.68209 | -0.09236 | -0.33732 | 0.17042 | -9.23556 | 0.01213 | 47 |
| 2026-06 | 17 | 15 | 0.64706 | 0.53235 | 0.63512 | 0.08418 | -0.3139 | 0.4348 | 8.41821 | 0.01353 | 17 |
| 2026-07 | 33 | 31 | 0.60606 | 0.52939 | 0.63545 | 0.28698 | -0.18447 | 0.7727 | 28.69797 | 0.0303 | 33 |
| 2026-08 | 76 | 64 | 0.55263 | 0.52342 | 0.62865 | -0.03047 | -0.24885 | 0.18388 | -3.04663 | -0.00329 | 76 |
| 2026-09 | 29 | 25 | 0.55172 | 0.56621 | 0.659 | 0.11641 | -0.29965 | 0.57123 | 11.64102 | 0.03069 | 29 |
| 2026-10 | 3 | 3 | 0.66667 | 0.59333 | 0.67813 | 0.22152 | -1.0 | 0.93237 | 22.15229 | -0.11667 | 3 |

## League primary results (descriptive)

| league | bets | series | win_rate | price | probability | roi | lo | hi | profit_per_100 | clv | clv_n |
|---|---|---|---|---|---|---|---|---|---|---|---|
| CBLOL | 26 | 24 | 0.53846 | 0.52 | 0.62597 | 0.03357 | -0.40888 | 0.53845 | 3.35745 | 0.015 | 26 |
| EWC | 11 | 10 | 0.54545 | 0.53455 | 0.63126 | 0.21754 | -0.46946 | 1.02896 | 21.75449 | 0.01545 | 11 |
| FST | 9 | 8 | 0.55556 | 0.32444 | 0.4289 | 1.03055 | -0.32618 | 3.20468 | 103.05522 | 0.04778 | 9 |
| LCK | 48 | 42 | 0.625 | 0.55188 | 0.66554 | 0.09883 | -0.19488 | 0.39584 | 9.88305 | 0.01562 | 48 |
| LCP | 19 | 18 | 0.73684 | 0.57737 | 0.67378 | 0.24584 | -0.14849 | 0.63876 | 24.58387 | 0.05368 | 19 |
| LCS | 29 | 28 | 0.48276 | 0.40655 | 0.4998 | 0.14615 | -0.36406 | 0.7372 | 14.61461 | -0.03241 | 29 |
| LEC | 41 | 36 | 0.60976 | 0.58878 | 0.67919 | -0.03354 | -0.27191 | 0.21053 | -3.35358 | 0.00488 | 41 |
| LJL | 1 | 1 | 1.0 | 0.59 | 0.72721 | 0.64745 | 0.64745 | 0.64745 | 64.74465 | 0.17 | 1 |
| LPL | 78 | 64 | 0.55128 | 0.56654 | 0.67378 | 0.0003 | -0.23844 | 0.26826 | 0.03022 | 0.00897 | 78 |
| MSI | 7 | 7 | 0.57143 | 0.49571 | 0.58845 | -0.0278 | -0.63029 | 0.67032 | -2.78047 | 0.06429 | 7 |
| VCS | 4 | 4 | 0.5 | 0.625 | 0.73329 | -0.27466 | -1.0 | 0.45069 | -27.46557 | 0.0175 | 4 |

## Monthly earlier-series-only fits

| month | train_maps | train_series | latest_training_available | market_weight | model_weight | market_only_weight |
|---|---|---|---|---|---|---|
| 2026-03 | 293 | 151 | 2026-02-28T23:28:02.764000+00:00 | 0.19868 | 0.72208 | 0.96844 |
| 2026-04 | 372 | 185 | 2026-03-31T19:53:20.530000+00:00 | 0.21396 | 0.72046 | 0.97166 |
| 2026-05 | 631 | 330 | 2026-04-30T13:19:36.331000+00:00 | 0.31384 | 0.6982 | 1.05401 |
| 2026-06 | 879 | 459 | 2026-05-31T22:33:27.200000+00:00 | 0.34295 | 0.61859 | 1.00694 |
| 2026-07 | 980 | 500 | 2026-06-30T08:01:20.760000+00:00 | 0.34409 | 0.62236 | 1.00946 |
| 2026-08 | 1110 | 565 | 2026-07-31T14:12:49.912000+00:00 | 0.34623 | 0.61488 | 1.00159 |
| 2026-09 | 1459 | 744 | 2026-08-31T23:25:25.468000+00:00 | 0.41253 | 0.54238 | 1.0 |
| 2026-10 | 1642 | 806 | 2026-09-28T23:17:10.135000+00:00 | 0.41953 | 0.52619 | 0.99238 |

## Kelly

| mode | fraction | terminal | multiple | drawdown | placed | limited | largest | max_held | log_growth_lo | log_growth_hi |
|---|---|---|---|---|---|---|---|---|---|---|
| cash reserved | 0.1 | 187.24575 | 1.87246 | 0.19115 | 273 | 0 | 0.0796 | 0.09329 | nan | nan |
| sequential | 0.1 | 187.21753 | 1.87218 | 0.19142 | 273 | 0 | 0.0796 | 0.0796 | -0.00039 | 0.00534 |
| cash reserved | 0.25 | 370.90955 | 3.7091 | 0.42955 | 273 | 0 | 0.199 | 0.23321 | nan | nan |
| sequential | 0.25 | 370.22003 | 3.7022 | 0.43081 | 273 | 0 | 0.199 | 0.199 | -0.00196 | 0.0122 |
| cash reserved | 0.5 | 609.2585 | 6.09258 | 0.70832 | 273 | 0 | 0.39799 | 0.46643 | nan | nan |
| sequential | 0.5 | 601.6788 | 6.01679 | 0.71107 | 273 | 0 | 0.39799 | 0.39799 | -0.00685 | 0.02076 |
| cash reserved | 1.0 | 151.4321 | 1.51432 | 0.94884 | 273 | 0 | 0.79598 | 0.93286 | nan | nan |
| sequential | 1.0 | 139.39257 | 1.39393 | 0.95107 | 273 | 0 | 0.79598 | 0.79598 | -0.02613 | 0.02928 |
| 1% map / 2% series caps | 0.25 | 124.91335 | 1.24913 | 0.09737 | 273 | 273 | 0.01 | 0.02 | nan | nan |

Sequential mean log-growth intervals (columns log_growth_lo/hi) resample series and do not exclude zero for the primary Kelly fractions; cash-reserved results have no uncertainty interval. A terminal multiple is one observed path, not an expected return.

Starts with $100; ideal continuous quantities, same probabilities and entries. `f = fraction × max(0, (p − c)/(1 − c))`, where c includes entry fees, is the fraction of bankroll spent. Sequential settles each bet immediately before the next entry and is an optimistic reference. Cash-reserved simulation keeps spend unavailable until recorded map end +5 minutes, releases winning payout or zero, and sizes from cash + open outlay; it never uses outcomes before settlement. Largest/max-held are fractions of equity; capped case limits outlay to 1% per map and 2% per series. Drawdown uses realized/cost-valued equity, excluding intra-map liquidation risk. This is constrained sequential allocation, not joint portfolio Kelly.

Kelly sensitivity on frozen entry times/sides at worse purchase prices, resizing to the changed fee-inclusive cost (skips if implied edge becomes nonpositive):

| cost_addition | fraction | terminal | multiple | drawdown | placed | limited | largest | max_held |
|---|---|---|---|---|---|---|---|---|
| 0.0 | 0.1 | 187.24575 | 1.87246 | 0.19115 | 273 | 0 | 0.0796 | 0.09329 |
| 0.0 | 0.25 | 370.90955 | 3.7091 | 0.42955 | 273 | 0 | 0.199 | 0.23321 |
| 0.0 | 0.5 | 609.2585 | 6.09258 | 0.70832 | 273 | 0 | 0.39799 | 0.46643 |
| 0.0 | 1.0 | 151.4321 | 1.51432 | 0.94884 | 273 | 0 | 0.79598 | 0.93286 |
| 0.02 | 0.1 | 143.38289 | 1.43383 | 0.1763 | 273 | 0 | 0.07872 | 0.08112 |
| 0.02 | 0.25 | 207.60165 | 2.07602 | 0.39732 | 273 | 0 | 0.19679 | 0.2028 |
| 0.02 | 0.5 | 249.83723 | 2.49837 | 0.66333 | 273 | 0 | 0.39358 | 0.40561 |
| 0.02 | 1.0 | 71.88311 | 0.71883 | 0.92005 | 273 | 0 | 0.78716 | 0.81122 |
| 0.05 | 0.1 | 117.07684 | 1.17077 | 0.13227 | 270 | 0 | 0.07724 | 0.07724 |
| 0.05 | 0.25 | 136.23575 | 1.36236 | 0.30591 | 270 | 0 | 0.19311 | 0.19311 |
| 0.05 | 0.5 | 141.1851 | 1.41185 | 0.53563 | 270 | 0 | 0.38622 | 0.38622 |
| 0.05 | 1.0 | 67.07226 | 0.67072 | 0.82795 | 270 | 0 | 0.77245 | 0.77245 |

## Limits and interpretation

- No historical asks, depth, fills, observed model receipt time or settlement time in this dataset. A stable tape is not a stable book. The 21-second lag is one pilot estimate; cost stresses do not simulate changing feed lag.
- Feed is about one sample a minute. Flat samples and invalid objective counters are excluded; pauses, outages, match identity and clock uncertainty cannot be fully screened. Matching exclusions inherit the pinned benchmark audit (including winner disagreement).
- Current model and historical test have already been examined in research; this is an earlier-only blend backtest on reused history, not untouched confirmation. No series-shift or draft input is added; runtime series-shift parity remains a separate limit.
- Bootstrap intervals preserve within-series dependence but not dependence across dates, teams or model selection. Monthly/league slices and sensitivity comparisons are descriptive and not multiplicity-adjusted.
- Fees assume general 7% taker rate, multiplier 1 throughout; historical market-specific fee changes and actual fill/quantity rounding are not reconstructed. Fractional contracts and unlimited size are research abstractions. [Official fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf); [series fee metadata](https://docs.kalshi.com/api-reference/market/get-series).
- Kelly is usable mathematically, but probabilities and executable costs determine whether its recommended exposure has positive growth. Fractional Kelly reduces exposure; it cannot repair a negative edge. Huge historical compounded multiples do not establish scalable profit.

## Reproduce

```bash
PYTHONPATH=$PWD OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  /Users/tvillalu/repos/Prometheus/.venv/bin/python scripts/research/live_trading.py \
  --data /private/tmp/live_maps-0705f02b1edf.json.gz \
  --db /Users/tvillalu/repos/Prometheus/db/prometheus.db
```

Measured analysis runtime: 6.30s. No production/CI workload or dependency added.
