# Live-map delay and fight-veto research — 2026-10-23

Arriving 5 s later (26 s vs 21 s, production's 30-second rule) cut bets from 183 to 171 and ROI from +21.3% to +8.6%; the paired difference, −1.4¢ per map (95% −3.5¢ to +0.6¢), includes zero. The fixed fight/objective veto reduced profit by 2.0¢ per map (95% −4.0¢ to −0.2¢): the 71 bets it removed were the best (+48.7% ROI, +3.9¢ CLV). No published metric or production behaviour changes.

## Fixed policies and results

Earlier-only monthly blend, first qualifying entry per map at minutes 5–30; valid objectives, non-flat feed, latest trade ≤10 s, ≥2 trades spanning ≤1 cent in the stability window, ≥5-cent after-fee edge. $1 all-in per bet, 7% quadratic fee rounded up to $0.0001 per contract. Production analogue: `signals.py` persists the first qualifying candidate; `live_map.py` also checks actual books and feed freshness. Research retains tape costs.

| policy | bets | ROI (95% CI) | CLV cents (95% CI) | CLV n | blend log loss |
|---|---|---|---|---|---|
| A: lag 21s / 30s window | 183 | +21.3% [-1.5%, +45.3%] | +2.14 [+0.33, +3.98] | 183 | 0.456636 |
| B: lag 26s / 30s window | 171 | +8.6% [-11.9%, +29.6%] | +1.37 [-0.87, +3.52] | 171 | 0.455742 |
| A: lag 21s / 21s window | 277 | +9.4% [-5.9%, +25.1%] | +1.60 [+0.10, +3.19] | 277 | 0.456636 |
| B: lag 26s / 21s window | 255 | +1.3% [-13.9%, +17.4%] | +2.27 [+0.66, +3.98] | 255 | 0.455742 |

Blend log loss averages all eligible scored 5–30-minute rows within each map, then equally across maps, before entry filters.

Veto at lag 21 s, 30-second stability window:

| policy | bets | ROI (95% CI) | CLV cents (95% CI) | CLV n |
|---|---|---|---|---|
| No veto | 167 | +27.8% [+4.7%, +52.3%] | +1.84 [-0.06, +3.71] | 167 |
| Veto | 105 | +12.3% [-13.1%, +38.5%] | +0.03 [-2.45, +2.45] | 105 |
| Original bets vetoed | 71 | +48.7% [+7.1%, +97.0%] | +3.86 [+1.12, +6.81] | 71 |

Veto removes a sample if total kills rose ≥2 since the immediately previous sample of that map, or either team's towers/inhibitors/barons/dragons changed. First samples are retained. Missing counter pairs cannot establish a change. Filter before entry selection; later samples may enter. Original bets vetoed includes entries replaced later.

| B − A | maps | total profit $ | mean $/map (95% CI) | interval includes zero |
|---|---|---|---|---|
| lag 26 − 21s / 30s window | 1772 | -24.165 | -0.0136 [-0.0352, +0.0058] | yes |
| lag 26 − 21s / 21s window | 1772 | -22.755 | -0.0128 [-0.0351, +0.0073] | yes |
| veto − no veto | 1666 | -33.451 | -0.0201 [-0.0397, -0.0021] | no |

Policy ROI and CLV intervals reuse `live_trading.cluster_ci` (2,000 whole-series draws). CLV is backed-side trade price 120 s after arrival minus entry price, in cents. Paired profit uses all common input maps (zero without a bet, including unscored training maps); 2,000 whole-series resamples, seed 0, give the mean per-map difference interval. Total differences are sums of $1-outlay profits, not ROI differences.

## Limits

Minute samples cannot reproduce production's 10-second frames or a precise post-fight cooldown. Trade tapes are not books: no asks, depth, fills, or executable exits. Reused history: the 30-second rule itself was chosen on this history; intervals do not adjust for selection or repeated comparisons. No conclusions use maps starting 2026-10-20 or later; these are removed before fitting and scoring, with a pinned-input assertion.

Measured receipt ages: BLG–MKOI median 25.6 s (204 receipts; p90 29.0), KC–MVK map 3 median 22.1 s (161; p90 26.3); floor about 20 s from the Riot embargo. Ten-second polling adds about 5 s average wait. A 21-vs-26 s comparison is a fixed-lag sensitivity, not a reconstruction of variable receipt times. Stress: an extra 1–5 cents of executable cost can consume the apparent edge; this analysis does not simulate fills or select a stress threshold.

## Inputs and reproduction

`live_maps_lag21.json.gz`: lag 21 s; 1772 input maps, 1436 scored maps, 34129 rows; 1 Elo skips; 0 forward maps excluded; SHA256 `8a0274305d10728a6a32686d57f8e179836bbb1c9c10c6380c7459e0f124aa72`.
`live_maps_lag26.json.gz`: lag 26 s; 1772 input maps, 1436 scored maps, 34141 rows; 1 Elo skips; 0 forward maps excluded; SHA256 `8fba6f169708505979c12bf3e0e8b973d6dfc9f172053c6f6afe1bb0db1f3f8e`.
`live_maps.json.gz`: lag 21 s; 1666 input maps, 1352 scored maps, 32158 rows; 1 Elo skips; 0 forward maps excluded; SHA256 `0705f02b1edf6df391809ba59a34ea4857fe2224757d7c509225e3875692422c`.

DB SHA256 `ad43793934c599eefd0d1b720ba9d559fe345f55b696e63b7af294a6684c2a53`. No new CI job or production workload; research runs offline.

```bash
UV_NO_SYNC=1 uv run python scripts/research/live_latency.py --db db/prometheus.db \
  --data-a data/live_bench/live_maps_lag21.json.gz --data-b data/live_bench/live_maps_lag26.json.gz --data data/live_bench/live_maps.json.gz
```

Real candidates: `uv run python scripts/live_markouts.py --root data/live` reads backups pulled with `scripts/live_data.py pull`. It prints delivery status and backed-side mid minus original ask at 30/60/120 s, using the first quote at/after each horizon and showing its delay. Bo1 uses match-level series quotes. Missing horizons stay blank; summaries count available observations. Candidate markouts are neither fills nor after-fee returns; pre-match fills require the private ledger and are out of scope. No local worker backups were available for this run.
