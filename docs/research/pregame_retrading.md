# Pre-match re-trading: top-ups, selling, side swaps

2026-11-02. `scripts/research/pregame_retrading.py` replays 8,553 priced series
(2025-11-25 to 2026-10-19; CS2 3,926, LoL 2,397, Dota 2 1,114, domestic Valorant
1,116) on Kalshi hourly bid/ask candles, 48 h before start to the start. Each hour
uses the production blend (frozen raw call, two-sided mid, monthly snapshot).
Bankroll 1 per series, full Kelly with exact held-position sizing, 10% series
loss cap, buys at the ask, sells at the bid, 0.07·c(1−c) fee per order. Paired
against `once` with a 2,000-draw week bootstrap.

| Policy | Orders | P&L/series | vs once [95%] | Log growth vs once [95%] |
|---|---|---|---|---|
| once (first buy, hold) | 5,423 | 40.2 bp | — | — |
| last (one buy, last hour) | 3,920 | 8.3 bp | −31.9 [−42.7, −20.0] | −30.3 [−40.1, −19.5] |
| topup (≤4 same-side buys) | 8,540 | 46.6 bp | +6.4 [+1.0, +11.9] | +0.8 [−4.4, +5.8] |
| trim (topup + sell down) | 9,118 | 43.5 bp | +3.3 [−3.2, +9.5] | −0.7 [−6.7, +5.1] |
| full (either side, swaps) | 9,335 | 43.7 bp | +3.5 [−3.0, +10.1] | −1.0 [−7.1, +5.1] |

At a flat $50 per series: once $1,719, topup $1,994, trim $1,860, full $1,869.
Top-ups raise profit (2,087 of 5,423 traded series added an order) but not
log growth: they add risk at roughly break-even growth. Selling and side swaps
add fees and give back edge; without the 10% cap they lose significantly
(full −16.7 bp log growth [−29.0, −3.9]). Every 24 h, 168 h, no-cap and
no-minimum variant agrees. Per game, only Valorant top-up P&L is significant
alone. The large effect is timing: the first priced hour beats the last by
~30 bp per series, since the market converges on the result near the start.

Limits: hourly closes miss moves inside the hour; no book depth (early
quotes are thin); series don't share a bankroll; blend weights were fit on
overlapping months. Live top-ups never ran before the 2026-11-02 fix: `kalshi.exposure()` rejected
any pre-match order on a fixture already held (`existing_fixture_exposure`).
