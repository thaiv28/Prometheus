# Execution timing: alert cap, age limit and deciding up to start, 2026-10-20

Question: should the executor buy only at or under the alert's cost within an hour of the alert, or whenever the blended net edge is still positive up to start? `scripts/research/execution_timing.py` replays the executor's rule (blended chance minus cost minus `core.fee_bound` > 0, packaged monthly snapshots) on hourly Kalshi closes from 12h before start, using the calibration audit's `rebuilt.csv` calls. Rules were fixed before scoring; no fitting, no games from the 2026-10-20 holdout. One contract per bet, 7% paper fees; intervals resample weeks.

1253 series, 2026-05-01 to 2026-10-20 (exclusive), trade groups; rebuilt.csv SHA256 6812d0fc53890822.

| Policy | Bets | Profit ($/contract) | ROI (95%) | CLV | Median lead |
|---|---:|---:|---:|---:|---:|
| Alert (≥6h lead, buy at once) | 488 | +19.12 | +6.4% (-0.2% to +12.7%) | +0.017 | 12h |
| Anytime (first edge up to start) | 586 | +24.41 | +7.1% (+0.9% to +13.3%) | +0.014 | 12h |
| … added: first edge under 6h | 98 | +5.29 | +11.8% (-9.7% to +32.3%) | +0.003 | 0h |
| Delay 1h, capped at alert cost | 363 | +7.15 | +3.3% (-4.4% to +10.5%) | +0.014 | 11h |
| Delay 1h, uncapped | 421 | +13.67 | +5.4% (-1.7% to +11.9%) | +0.015 | 11h |
| … added: cost above alert | 58 | +6.52 | +18.4% (+3.8% to +38.1%) | +0.020 | 11h |
| Delay 2h, capped at alert cost | 311 | +5.95 | +3.2% (-6.1% to +12.8%) | +0.012 | 10h |
| Delay 2h, uncapped | 404 | +9.99 | +4.1% (-4.1% to +11.6%) | +0.012 | 10h |
| … added: cost above alert | 93 | +4.05 | +7.1% (-8.4% to +22.4%) | +0.012 | 10h |
| Delay 3h, capped at alert cost | 253 | -1.00 | -0.7% (-9.3% to +9.0%) | +0.005 | 9h |
| Delay 3h, uncapped | 382 | +8.48 | +3.7% (-4.6% to +11.8%) | +0.008 | 9h |
| … added: cost above alert | 129 | +9.48 | +12.1% (-1.4% to +24.9%) | +0.014 | 9h |

Reading:

- **The cost cap drops good bets.** At every delay, the bets it blocks (cost above the alert's, edge still positive) made money: +18.4% at 1h (+3.8% to +38.1%), +7.1% and +12.1% at 2h and 3h with intervals spanning zero, all with positive CLV.
- **Deciding up to start adds 98 bets** at +11.8%, but the interval (−9.7% to +32.3%) spans losses and CLV is near zero (+0.003): mostly last-hour buys at sharp prices. No evidence they help or hurt.
- None of the policy differences is significant; the overall rule is +6–7% with an interval touching zero, as in the [blend validation](market_blend_validation.md).

Limits: the grid starts 12h before start (raw chances use ratings before that day), while real alerts can fire days earlier; hourly closes, not executable books; no vetoes, sizing or slippage; group selection reused this sample.
