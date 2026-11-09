# What we bet on

Pre-match Kalshi series only. Live-map trading is outside this table and unchanged. The switch is `PAUSED_SLICES` in `prometheus/alert_contract.py` (`tests/test_execution_games.py` fails if this table misses a paused slice). Alerts and site forecasts still show paused slices; only orders stop. Open positions settle normally.

Evidence as of 2026-11-09. **ROI** is flat $1 per bet after fees (95% interval, resampling weeks). **vs Kalshi** is blended minus Kalshi log loss ×1000; negative beats the market. **Live** is settled P&L and fixtures from 2026-10-22, from the `prometheus-trades` issues.

| Status | Game | Slice | Backtest bets | ROI | vs Kalshi | Live |
|---|---|---|---:|---|---|---|
| On | lol | `major-domestic` | 213 | +12.3% [+4, +20] | −3.2 [−10, +3] | none |
| Off | lol | `minor-domestic` | 452 | −6.9% [−19, +8] | +2.5 [−4, +8] | +$0.61 (1) |
| Off | lol | `major-international` | 27 | −14.5% [−39, +7] | +21.2 [+2, +45] | −$1.65 (12) |
| Off | lol | `mixed-international` | 20 | +63.0% [−11, +223] | −10.3 [−26, +3] | −$3.68 (4) |
| Off | lol | `minor-international` | 9 | +5.3% [−100, +185] | +4.0 [−122, +98] | −$12.72 (1) |
| Off | lol | `other-cross-league` | 54 | −25.1% [−55, +6] | +53.8 [+5, +133] | none (never traded) |
| Off | cs2 | `INTL` | 195 | −4.2% [−20, +16] | +2.7 [−12, +17] | +$6.27 (19) |
| Off | cs2 | `T1` | 123 | +0.3% [−19, +20] | −1.0 [−31, +38] | none |
| On | cs2 | `T2` | 995 | +8.4% [+3, +13] | −9.7 [−16, −3] | +$1.02 (33) |
| On | cs2 | `T3` | 972 | +14.1% [+6, +21] | −19.9 [−29, −10] | +$18.90 (111) |
| On | dota2 | `INTL` | 271 | +5.4% [−8, +18] | −8.2 [−16, −0.3] | +$4.61 (9) |
| On (watch) | dota2 | `T2` | 81 | +11.6% [−4, +35] | −10.0 [−25, 0] | none |
| On | dota2 | `T3` | 191 | +25.5% [+7, +43] | −40.9 [−68, −8] | +$4.23 (54) |
| On (watch) | valorant | `VCT` | 264 | +7.6% [−2, +17] | −8.1 [−20, +2] | −$2.20 (3) |
| On | valorant | `VCL` | 229 | +27.7% [+13, +43] | −21.3 [−41, −3] | none |
| Off | valorant | `GC` | 84 | −0.3% [−25, +26] | +12.0 [−17, +48] | none |
| Off | valorant | `OFF` | 29 | +0.2% [−18, +25] | +8.5 [−18, +20] | none |
| Off | valorant | international | 49 | −5.1% [−41, +35] | +10.9 [−20, +49] | none (never traded) |
| Off | r6 | all | — | holdout gate failed | — | none (never traded) |

`other-cross-league`, Valorant international and R6 were already off. Unknown-section fixtures (`?`) stay on, and Cloud9 and anti-North-America international vetoes still apply.

## How slices were judged

- **On:** ROI significant after multiple-testing correction, or significantly better than Kalshi.
- **On (watch):** positive but unproven.
- **Off:** ROI near or below zero and no better than Kalshi. This means no evidence of an edge, not a proven loss: no segment's ROI is significantly negative. The rule was chosen while looking at the data.

## Turning a slice back on

Show a model change gives the slice a significant gain on games not used to pick it (ROI interval above 0, or log loss significantly below Kalshi), then remove it from `PAUSED_SLICES` and update this table.

## Method and limits

- Each game's adopted replay priced at the first tradeable Kalshi quote; LoL at the saved 12-hour quote. Bets take the larger positive after-fee edge on the walk-forward blended chance.
- Windows: CS2 2026-03-01 to 10-28 (overlaps model selection, so optimistic), Dota 2 02-03 to 10-29, Valorant 04-03 to 10-28, LoL 05-01 to 11-08 (94% reconstructed calls; January to April has no earlier-only blend).
- CS2 top events fall further with at least 5 contracts of depth: `INTL` −8.9%, `T1` −6.3%.
- Live is 18 days; LoL live is nearly all Worlds; 28 of 275 live fixtures have no tier label and are left out of the table.
