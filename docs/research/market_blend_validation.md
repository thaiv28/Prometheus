# Market blend: adoption record, 2026-10-16

Separate trading forecast; raw FORGE/Elo math, saved calls and existing forecast benchmarks are unchanged. This release prepares alerts, page summaries and execution support; it does not activate an account.

The calibration audit rebuilt current calls from earlier-day ratings, on fresh Kalshi books 12 hours before scheduled start. Fixed C=1 logistic regression, no intercept, fits market logit and the raw-minus-market logit gap. Expanding monthly fits use only outcomes available before the month (availability proxy: start+24 hours), minimum 300 series. There are 1,733 priced series and 1,358 later-month validation calls. Raw forecast weights were fit using data that includes some replayed matches; monthly calibration chronology does not remove that limitation.

On the same 1,358 later-month series, blended log loss was 0.5428 versus raw 0.5595: difference −0.0166, paired week-bootstrap 95% interval −0.0231 to −0.0104. Versus a separately calibrated market-only control (0.5448), the blend’s −0.0020 difference was uncertain (−0.0061 to +0.0026); this does not establish independent profitable model information. All 1,358 rolling audit probabilities match the runtime implementation within 1.67e−16.

The packaged artifact pins input SHA256 `6812d0fc538908222136c382612065fb10e56aaa150d413cc61c0972d36e84e9`. October coefficients, trained on 1,729 prior series through September 30: market slope 1.087254056134923, gap slope 0.34280025852274704. Formula:

```
logit(blend) = market_slope * logit(market)
            + gap_slope * (logit(raw) - logit(market))
```

The input to `scripts/fit_market_blend.py` is the audit's `rebuilt.csv`, with unique `event_ticker`, UTC `decision` and `result_available`, raw `p`, midpoint `market`, binary `won`. Data/cache files remain gitignored. Offline export command (with that file available):

```bash
uv run python scripts/fit_market_blend.py --input data/calibration_audit/rebuilt.csv --available-through 2026-10-01
```

Earlier experiments compared raw >5-point picks (716, +$36.78) and blended positive estimated net edge (716, +$42.60). Each modeled pick buys $1 at the ask plus rounded quadratic fees; the blended rule's 5.8% all-in return had a week-bootstrap 95% interval of −0.95% to +13.97%. Profitability is not established by that interval. The user chose the volume rule and these groups:

| Fixture group | Picks | Modeled profit |
|---|---:|---:|
| Major domestic | 171 | +$19.14 |
| Minor domestic | 430 | +$25.09 |
| Major vs major international | 19 | −$0.39 |
| Major vs minor international | 7 | −$0.09 |
| Minor vs minor international | 21 | +$8.37 |
| Other cross-league (excluded) | 68 | −$9.52 |

These exploratory group selections reused the evaluation sample; the international cells are particularly small. They are signal returns before the user's Cloud9/anti-NA execution vetoes. No claimed return after those vetoes, account-level sizing, actual fills or live slippage. Page summaries use their own saved/backtest log cohorts and need not reproduce the research cohort counts.

Missing early midpoint or model snapshot produces no blended estimate. Later closing prices are only used to score CLV. New alerts retain their original raw input, market input and snapshot; historical proposals are never reselected. Runtime refreshes use the same snapshot and raw forecast with a fresh executable market midpoint, then conservative actual fee bounds and explicit account limits. Forward saved alerts and actual private fills will provide the next independent check.
