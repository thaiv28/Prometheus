# Alive players, Elder/soul and items in the live model

**alive: PASS**, All ΔLL -0.000823[-0.001065,-0.000591].
**alive_respawn: FAIL**, All ΔLL -0.000731[-0.000988,-0.000481].
**elder: FAIL**, All ΔLL +0.000119[-0.000048,+0.000292].
**soul_true: FAIL**, All ΔLL +0.000000[+0.000000,+0.000000].
**items: FAIL**, All ΔLL +0.000119[-0.000042,+0.000281].
**combined: FAIL**, All ΔLL -0.000557[-0.000884,-0.000236].

Fixed candidates: alive; alive_respawn; elder (recent, cumulative); soul_true replacement; items; combined (all additions, soul replacement). Add x and x×time (seconds/1200). Control: deployed 20 inputs, objectives + momentum. No post-scoring selection.

Feed train/calibration/test maps (rows): 2757 (86709)/1819 (57067)/3893 (123954). Train through 2024; calibrate January–June 2025; test July 2025 onward, ≤2400 seconds. StandardScaler, L2 C=1, equal map weights, Platt calibration.

Δ=candidate−control; map-weighted LL, 95% paired whole-series bootstrap, 2,000 draws, seed 42. Pass: All upper <−0.0005 (soul_true: <0), no slice lower >0. Six candidates; no multiple-comparison adjustment. Passing requires live benchmark and trading check before adoption.

Alive: blue−red living players. Respawn: red−blue remaining seconds /60; scaled level timer minus time since first seen dead, reset on increased deaths. Elder_recent: 180 seconds from observed count increase. soul_true: ≥4 non-elder dragons. History uses earlier/current kept samples.

Windows match timeline timestamps; details match window timestamps; fallback nearest ≤10 seconds. Items: exact/latest earlier patch; terminal, purchasable, Rift, ≥2200 gold; exclude Consumable, champion/ally-only, inStore=False. Missing data or unsupported state levels (outside 1–20; 19–20 use the level-18 timer): zero features, separate state/items flags excluded from fitting.

| Model | LL | Brier | ECE10 |
|---|---:|---:|---:|
| control | 0.465625 | 0.154081 | 0.020546 |
| alive | 0.464802 | 0.153795 | 0.020769 |
| alive_respawn | 0.464895 | 0.153827 | 0.020911 |
| elder | 0.465744 | 0.154119 | 0.020442 |
| soul_true | 0.465625 | 0.154081 | 0.020546 |
| items | 0.465744 | 0.154104 | 0.020587 |
| combined | 0.465068 | 0.153881 | 0.021061 |

| Slice | Maps | alive | alive_respawn | elder | soul_true | items | combined |
|---|---:|---|---|---|---|---|---|
| All | 3893 | -0.000823[-0.001065,-0.000591] | -0.000731[-0.000988,-0.000481] | +0.000119[-0.000048,+0.000292] | +0.000000[+0.000000,+0.000000] | +0.000119[-0.000042,+0.000281] | -0.000557[-0.000884,-0.000236] |
| 0–10 | 3893 | +0.000026[-0.000060,+0.000109] | +0.000014[-0.000096,+0.000114] | -0.000124[-0.000174,-0.000077] | +0.000000[+0.000000,+0.000000] | -0.000131[-0.000242,-0.000019] | -0.000117[-0.000251,+0.000017] |
| 10–20 | 3892 | -0.000181[-0.000411,+0.000045] | +0.000003[-0.000261,+0.000270] | -0.000112[-0.000173,-0.000052] | +0.000000[+0.000000,+0.000000] | +0.000563[+0.000126,+0.001006] | +0.000516[-0.000001,+0.001018] |
| 20–30 | 3886 | -0.000762[-0.001337,-0.000176] | -0.000600[-0.001222,+0.000013] | +0.000190[+0.000050,+0.000326] | +0.000000[+0.000000,+0.000000] | +0.000109[-0.000051,+0.000273] | -0.000659[-0.001278,-0.000016] |
| 30+ | 2158 | -0.007142[-0.008811,-0.005546] | -0.007411[-0.009217,-0.005718] | +0.000788[-0.000664,+0.002314] | +0.000000[+0.000000,+0.000000] | -0.000005[-0.000432,+0.000394] | -0.006937[-0.009222,-0.004575] |
| LPL | 944 | -0.001120[-0.001656,-0.000616] | -0.001022[-0.001596,-0.000496] | +0.000135[-0.000031,+0.000306] | +0.000000[+0.000000,+0.000000] | -0.000088[-0.000439,+0.000229] | -0.001122[-0.001736,-0.000508] |
| LCK | 687 | -0.001048[-0.001615,-0.000511] | -0.000949[-0.001536,-0.000416] | +0.000435[-0.000187,+0.001135] | +0.000000[+0.000000,+0.000000] | +0.000467[+0.000090,+0.000844] | +0.000036[-0.000917,+0.000948] |
| LEC | 443 | -0.000862[-0.001583,-0.000177] | -0.000814[-0.001516,-0.000124] | +0.000094[-0.000295,+0.000412] | +0.000000[+0.000000,+0.000000] | +0.000306[-0.000160,+0.000813] | -0.000542[-0.001447,+0.000272] |
| LCS | 253 | -0.000412[-0.001339,+0.000546] | -0.000309[-0.001303,+0.000717] | -0.000034[-0.000535,+0.000478] | +0.000000[+0.000000,+0.000000] | +0.000213[-0.000309,+0.000769] | -0.000271[-0.001511,+0.000892] |
| Other majors | 773 | -0.000947[-0.001429,-0.000471] | -0.000889[-0.001391,-0.000423] | -0.000237[-0.000606,+0.000025] | +0.000000[+0.000000,+0.000000] | +0.000107[-0.000249,+0.000458] | -0.001025[-0.001720,-0.000405] |
| International | 305 | -0.000784[-0.001693,+0.000281] | -0.000590[-0.001572,+0.000501] | +0.000504[-0.000094,+0.001445] | +0.000000[+0.000000,+0.000000] | -0.000046[-0.000660,+0.000557] | -0.000058[-0.001519,+0.001388] |
| Other | 488 | +0.000062[-0.000619,+0.000747] | +0.000162[-0.000537,+0.000879] | +0.000070[-0.000414,+0.000569] | +0.000000[+0.000000,+0.000000] | -0.000070[-0.000485,+0.000367] | -0.000029[-0.001018,+0.000944] |
| Known | 3893 | -0.000823[-0.001065,-0.000591] | -0.000731[-0.000988,-0.000481] | +0.000119[-0.000048,+0.000292] | +0.000000[+0.000000,+0.000000] | +0.000119[-0.000042,+0.000281] | -0.000557[-0.000884,-0.000236] |
| Unknown | 0 | n/a | n/a | n/a | n/a | n/a | n/a |
| 2026 | 2836 | -0.000747[-0.001042,-0.000453] | -0.000642[-0.000943,-0.000344] | +0.000084[-0.000112,+0.000277] | +0.000000[+0.000000,+0.000000] | +0.000242[+0.000065,+0.000426] | -0.000431[-0.000819,-0.000060] |
| Any dead | 3893 | -0.003149[-0.004029,-0.002242] | -0.002972[-0.003926,-0.001981] | +0.000242[-0.000065,+0.000568] | +0.000000[+0.000000,+0.000000] | +0.000068[-0.000145,+0.000276] | -0.002859[-0.003857,-0.001811] |
| Elder taken | 198 | -0.006426[-0.015634,+0.001611] | -0.006282[-0.015127,+0.001794] | +0.007624[-0.014721,+0.029235] | +0.000000[+0.000000,+0.000000] | -0.000427[-0.002789,+0.001815] | -0.001774[-0.024957,+0.020459] |

Cells: ΔLL[95% CI]. Known/Unknown refer to state coverage.

Joined coverage: state 270225/270225, items 270225/270225; 270225 exact/0 nearest windows. Completed-item set sizes: 63–141 across 69 patch files.

Test coverage (league rows:state/items known): CBLOL 7944:7944/7944; EWC 1553:1553/1553; FST 1362:1362/1362; LCK 21863:21863/21863; LCP 11993:11993/11993; LCS 8122:8122/8122; LEC 14566:14566/14566; LJL 6107:6107/6107; LPL 30039:30039/30039; LTA 707:707/707; LTA N 2126:2126/2126; LTA S 2032:2032/2032; MSI 4016:4016/4016; PCS 4014:4014/4014; VCS 4736:4736/4736; Worlds 2774:2774/2774. Total 123954:123954/123954.

Standardized logistic coefficients before Platt calibration (x, x×time):

| Candidate | Added/replacement feature | Coefficients |
|---|---|---:|
| alive | alive | -0.098526, +0.258309 |
| alive_respawn | alive | -0.113052, +0.029339 |
| alive_respawn | respawn | +0.189597, +0.054567 |
| elder | elder_recent | +0.276607, -0.287096 |
| elder | elder | +0.424851, -0.368273 |
| soul_true | soul_true | +0.028673, +0.031383 |
| items | items | +0.168410, -0.153344 |
| combined | soul_true | +0.043380, +0.016600 |
| combined | alive | -0.096248, +0.021811 |
| combined | respawn | +0.171403, +0.064667 |
| combined | elder_recent | +0.260613, -0.265881 |
| combined | elder | +0.401669, -0.347676 |
| combined | items | +0.158950, -0.130675 |

| Test-row description | Value |
|---|---:|
| Any player dead | 22.71% |
| More-alive team won (unequal alive, 25429 rows) | 69.76% |

Limits: retrospective; July-2025+ test viewed by earlier studies. Respawn is estimated; deaths seen at minute resolution. Items follow the patch rule. Levels 19–20 occur (raised cap) and use the level-18 timer. soul_true equals the deployed soul flag on every row (Elder spawns only after a soul), so it changes nothing. Passing needs the live benchmark and trading check. No live benchmark or trading check; research only, no production change.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_state.py
```

[Players-alive confirmation](live_alive_check.md): **overall FAIL** on the pinned live benchmark and trading study; research only.
