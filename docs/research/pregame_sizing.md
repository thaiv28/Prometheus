# Pregame sizing and live overlap

2026-10-26. Run `python scripts/research/pregame_sizing.py REBUILT_CSV`.
Earlier-only monthly blend; positive after-fee edge; allowed groups and Cloud9
veto. Four-hour settlement; $50 seed/order/exposure, $100 daily spend.

2026-05–09: 1,231 series, 726 picks; flat ROI +9.1%, mean edge 3.2¢,
mean price 0.59. Multiples measure bankroll; largest is stake/free capital.
Bootstrap: 400 week resamples, seed 0.

| Kelly | Series cap | Ends | Worst DD | Largest | Bets | Boot 5% | Median | 95% | P(lose) |
|---|---|---|---|---|---|---|---|---|---|
| 1.0 | None | 13.80× | 50% | 41% | 453 | 1.20× | 12.29× | 25.62× | 4% |
| 1.0 | 20% | 14.01× | 51% | 20% | 465 | 2.06× | 11.71× | 25.28× | 4% |
| 1.0 | 10% | 13.37× | 54% | 10% | 521 | 2.37× | 12.28× | 24.98× | 2% |
| 1.0 | 5% | 7.91× | 38% | 5% | 641 | 1.93× | 8.84× | 20.61× | 1% |
| 0.5 | None | 6.62× | 66% | 28% | 660 | 0.71× | 7.46× | 18.02× | 9% |
| 0.5 | 10% | 7.12× | 56% | 10% | 659 | 1.25× | 7.75× | 17.76× | 4% |
| 0.25 | None | 2.30× | 44% | 17% | 720 | 0.74× | 2.61× | 7.57× | 9% |
| 0.25 | 10% | 2.71× | 43% | 10% | 718 | 0.99× | 3.01× | 8.17× | 5% |
| 0.25 | 5% | 2.94× | 34% | 5% | 720 | 1.21× | 3.07× | 7.48× | 3% |

Limits: five months; the edge rule was chosen on these data. $50 order/exposure
caps bind as bankroll grows. Anti-NA international veto and depth are not modeled.
Forward returns remain unknown.

Pinned live data (1,352 maps): 88% of live bets backed the pre-map model's side.
Replacing that prior with the pre-map market yielded 41 bets, −21.7% ROI
(95% CI −45.3% to +1.7%). Same-team contracts offset live targets: 4.6 filled pregame contracts cover a target <=4.6; target 6 buys 1.4.
