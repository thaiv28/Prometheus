**FAIL: primary ΔLL +0.001283 (-0.000775 to +0.003397); retrospective, research only.**

# Champion scaling in the live model

Protocol fixed before scoring: primary champion H=365 days; A champion H=730; B champion-by-role H=365. No variants selected after scoring. Feed train/calibration/test maps: 2757/1819/3893; test ≤40 minutes. Control uses the deployed 20-feature recipe; candidates add blue-minus-red summed slopes and gap×time. StandardScaler, L2 C=1, equal map weights, Platt calibration. Missing ten-champion rosters give zero gap; no rows dropped.

Residuals subtract a no-intercept pre-2024 Elo logistic fit. Length is centered on league/year median, divided by 600. Slopes use strictly earlier UTC days, exponential decay and ridge 25, computed with cumulative moments.

LL is map-weighted. Δ=candidate−control; 95% paired whole-series bootstrap intervals use 2,000 draws, seed 42. Pass requires primary All upper bound <0 and no reported primary slice lower bound >0. Secondaries are descriptive, never adopted. No multiple-comparison adjustment.

| Model | LL | Brier | ECE10 | gap / gap_time signs |
|---|---:|---:|---:|---|
| control | 0.465625 | 0.154081 | 0.020546 | — |
| primary | 0.466908 | 0.154561 | 0.021268 | − / + |
| secondary_a | 0.467399 | 0.154808 | 0.021024 | + / + |
| secondary_b | 0.466869 | 0.154567 | 0.020486 | + / + |

Signs are standardized logistic coefficients before Platt calibration.

| Slice | Maps | Primary ΔLL (95% CI) | A ΔLL (95% CI) | B ΔLL (95% CI) |
|---|---:|---|---|---|
| All | 3893 | +0.001283[-0.000775,+0.003397] | +0.001774[-0.000413,+0.003940] | +0.001244[-0.000877,+0.003484] |
| 0–10 | 3893 | +0.000336[-0.000498,+0.001151] | +0.000992[-0.000247,+0.002179] | +0.000518[-0.000541,+0.001544] |
| 10–20 | 3892 | +0.001183[-0.001036,+0.003542] | +0.001673[-0.000760,+0.004073] | +0.000871[-0.001586,+0.003316] |
| 20–30 | 3886 | +0.001218[-0.001749,+0.004241] | +0.001601[-0.001233,+0.004592] | +0.000960[-0.001947,+0.004011] |
| 30+ | 2158 | +0.004327[-0.000637,+0.009498] | +0.003913[-0.000848,+0.008722] | +0.005064[+0.000314,+0.010026] |
| LPL | 944 | +0.002727[-0.001507,+0.007160] | +0.002804[-0.001835,+0.007403] | +0.002723[-0.001757,+0.007284] |
| LCK | 687 | +0.004504[-0.000229,+0.009284] | +0.005637[+0.000473,+0.010806] | +0.003096[-0.001826,+0.007870] |
| LEC | 443 | +0.003587[-0.002869,+0.010371] | +0.003178[-0.003423,+0.010030] | +0.005922[-0.000196,+0.012496] |
| LCS | 253 | -0.002139[-0.010387,+0.006152] | -0.001361[-0.010164,+0.007064] | -0.000310[-0.009602,+0.008955] |
| Other majors | 773 | -0.002059[-0.005970,+0.001862] | -0.001707[-0.006125,+0.002654] | -0.002356[-0.006585,+0.001992] |
| International | 305 | +0.005492[-0.001762,+0.013332] | +0.007902[+0.000576,+0.016230] | +0.004932[-0.002765,+0.012879] |
| Other | 488 | -0.003701[-0.009053,+0.001771] | -0.003625[-0.009393,+0.001922] | -0.004266[-0.009814,+0.001550] |
| Known | 3893 | +0.001283[-0.000775,+0.003397] | +0.001774[-0.000413,+0.003940] | +0.001244[-0.000877,+0.003484] |
| Unknown | 0 | n/a | n/a | n/a |
| 2026 | 2836 | +0.001886[-0.000686,+0.004314] | +0.002195[-0.000462,+0.004717] | +0.001660[-0.001146,+0.004228] |

Known/Unknown use each candidate's roster availability (B also requires roles).

| Test league | Maps | Missing champion rosters |
|---|---:|---:|
| CBLOL | 247 | 0 |
| EWC | 49 | 0 |
| FST | 45 | 0 |
| LCK | 687 | 0 |
| LCP | 376 | 0 |
| LCS | 253 | 0 |
| LEC | 443 | 0 |
| LJL | 197 | 0 |
| LPL | 944 | 0 |
| LTA | 22 | 0 |
| LTA N | 65 | 0 |
| LTA S | 63 | 0 |
| MSI | 125 | 0 |
| PCS | 135 | 0 |
| VCS | 156 | 0 |
| Worlds | 86 | 0 |

Persistence, unweighted 2022–2023 vs 2024–2025, ridge 25, ≥50 games in both: n=138, Pearson=0.1290, Spearman=0.1241. Weak persistence suggests noise.

Top/bottom ten as of 2026-10-01 (strictly earlier days), H=365, ≥30 raw games:

| Entity | Champion name | Slope | Σw | Raw games |
|---|---|---:|---:|---:|
| Yuumi | Yuumi | +0.0891 | 287.1 | 4139 |
| Lissandra | Lissandra | +0.0774 | 260.6 | 4375 |
| Soraka | Soraka | +0.0756 | 95.0 | 1222 |
| Ornn | Ornn | +0.0737 | 1274.4 | 11601 |
| Milio | Milio | +0.0633 | 1145.9 | 2613 |
| Dr. Mundo | Dr. Mundo | +0.0582 | 580.7 | 2742 |
| Galio | Galio | +0.0570 | 1409.8 | 9196 |
| Shaco | Shaco | +0.0568 | 12.7 | 95 |
| Sivir | Sivir | +0.0539 | 1448.5 | 8912 |
| Malphite | Malphite | +0.0520 | 403.9 | 2771 |
| Heimerdinger | Heimerdinger | -0.0413 | 76.6 | 1045 |
| Vel'Koz | Vel'Koz | -0.0426 | 41.8 | 670 |
| Jayce | Jayce | -0.0461 | 2096.4 | 11985 |
| Olaf | Olaf | -0.0470 | 864.0 | 8180 |
| Pyke | Pyke | -0.0484 | 355.6 | 2225 |
| Gnar | Gnar | -0.0490 | 2386.8 | 15595 |
| Tryndamere | Tryndamere | -0.0526 | 75.1 | 928 |
| Bard | Bard | -0.0553 | 1741.5 | 5594 |
| Singed | Singed | -0.0590 | 20.7 | 309 |
| Lux | Lux | -0.0805 | 179.7 | 2405 |

Limits: July-2025+ outcomes were viewed in earlier studies, so this is retrospective regardless of the verdict. Oracle's Elixir lacks champions for many historical LPL games, although every test map here has complete rosters (the Unknown slice is empty). Game length is an outcome-side quantity used only from earlier games; league/year centering follows the fixed protocol. Slopes are associations, not causal champion effects. No market/trading check; no production model changed.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_champ_scaling.py
```
