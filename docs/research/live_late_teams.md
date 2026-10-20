FAIL: primary team H=180 +0.000034 (-0.000150 to +0.000215) log loss; research only.

# Live late-game teams and players

Protocol fixed before scoring: primary team H=180 days; secondary A team H=90, B team H=365, C players H=180. Feed train 2024, calibration 2025 H1, test July 2025 onward through 40 minutes. Control: deployed 20-feature objective/momentum recipe refit; candidates add gap and gap×time. StandardScaler, L2 logistic C=1, equal map weights, calibration-only Platt layer.

History: pre-2024 no-intercept Elo logistic residual; league-year median-centered length/600. Centered slope, ridge 25; earlier UTC days, exponential cumulative moments. Side score: one team slope or five player slopes. Missing IDs/rosters: zero gap, rows retained. Unseen entities: zero slopes; require ten distinct player IDs.

Control sanity PASS (LL 0.465625; expected 0.4675±0.003). train: 2757 maps/86709 rows; calibration: 1819 maps/57067 rows; test: 3893 maps/123954 rows.

| Model | LL | Brier | ECE10 | gap/gap×time signs |
|---|---|---|---|---|
| control | 0.465625 | 0.154081 | 0.020546 | — |
| team_180 | 0.465659 | 0.154083 | 0.021104 | −/+ |
| team_90 | 0.465571 | 0.154046 | 0.020906 | −/+ |
| team_365 | 0.465648 | 0.154053 | 0.021065 | −/+ |
| player_180 | 0.465519 | 0.154043 | 0.020627 | −/+ |

Per-map LL delta versus control; 95% paired whole-series bootstrap, 2,000 draws, seed 42. Negative favors candidate. Cells: delta [interval]; empty slices are N/A. Known/unknown is candidate-specific.

| Slice (maps: team/player) | Primary | A | B | C |
|---|---|---|---|---|
| All (3893/3893) | +0.00003[-0.00015,+0.00021] | -0.00005[-0.00021,+0.00010] | +0.00002[-0.00028,+0.00033] | -0.00011[-0.00026,+0.00004] |
| 0–10 (3893/3893) | +0.00023[-0.00030,+0.00078] | +0.00006[-0.00032,+0.00046] | -0.00008[-0.00075,+0.00062] | -0.00011[-0.00025,+0.00003] |
| 10–20 (3892/3892) | +0.00009[-0.00004,+0.00024] | -0.00013[-0.00029,+0.00004] | +0.00006[-0.00025,+0.00039] | -0.00001[-0.00017,+0.00015] |
| 20–30 (3886/3886) | +0.00004[-0.00013,+0.00020] | +0.00006[-0.00002,+0.00015] | +0.00032[+0.00019,+0.00046] | -0.00004[-0.00034,+0.00027] |
| 30+ (2158/2158) | -0.00010[-0.00055,+0.00038] | -0.00005[-0.00033,+0.00024] | +0.00013[-0.00020,+0.00046] | -0.00043[-0.00098,+0.00014] |
| LPL (944/944) | +0.00034[-0.00005,+0.00075] | +0.00028[-0.00009,+0.00066] | +0.00053[-0.00004,+0.00109] | -0.00032[-0.00056,-0.00006] |
| LCK (687/687) | +0.00006[-0.00029,+0.00044] | -0.00001[-0.00035,+0.00032] | -0.00019[-0.00085,+0.00051] | -0.00004[-0.00041,+0.00037] |
| LEC (443/443) | -0.00032[-0.00074,+0.00011] | -0.00016[-0.00053,+0.00022] | -0.00060[-0.00145,+0.00025] | +0.00015[-0.00027,+0.00057] |
| LCS (253/253) | -0.00037[-0.00101,+0.00029] | -0.00025[-0.00085,+0.00036] | -0.00084[-0.00237,+0.00061] | +0.00040[-0.00034,+0.00117] |
| Other majors (773/773) | -0.00002[-0.00049,+0.00046] | -0.00019[-0.00056,+0.00017] | +0.00021[-0.00061,+0.00110] | -0.00013[-0.00046,+0.00020] |
| International (305/305) | -0.00001[-0.00067,+0.00065] | -0.00018[-0.00076,+0.00038] | +0.00033[-0.00090,+0.00152] | -0.00055[-0.00131,+0.00010] |
| Other (488/488) | +0.00004[-0.00035,+0.00044] | -0.00027[-0.00062,+0.00008] | -0.00013[-0.00079,+0.00049] | +0.00002[-0.00022,+0.00026] |
| Known (3893/3893) | +0.00003[-0.00015,+0.00021] | -0.00005[-0.00021,+0.00010] | +0.00002[-0.00028,+0.00033] | -0.00011[-0.00026,+0.00004] |
| Unknown (0/0) | N/A | N/A | N/A | N/A |
| 2026 (2836/2836) | -0.00001[-0.00021,+0.00020] | -0.00009[-0.00028,+0.00009] | -0.00004[-0.00041,+0.00031] | -0.00007[-0.00025,+0.00011] |

Pass requires the primary all-map interval below zero and no reported slice interval above zero. Harm slices: none. Secondaries are descriptive, never adopted.

Coverage (known/total maps; train, calibration, test): team_180 2757/2757, 1819/1819, 3893/3893; player_180 2757/2757, 1819/1819, 3893/3893.

Persistence: unweighted 2022–2023 versus 2024–2025 slopes, ridge 25, ≥50 games in each window.

| Entity | n | Pearson | Spearman |
|---|---|---|---|
| team | 174 | 0.2612 | 0.2689 |
| player | 891 | 0.0960 | 0.0930 |

As of 2026-10-01, H=180, ≥30 earlier raw games; latest earlier names. Counts: weighted/raw.

| team top 10 | Slope | Games | team bottom 10 | Slope | Games |
|---|---|---|---|---|---|
| GnG Amazigh | +0.1094 | 66.6/208 | Nongshim Esports Academy | -0.1416 | 97.1/599 |
| Nongshim RedForce Academy | +0.1073 | 73.7/340 | SU Esports | -0.1006 | 53.6/80 |
| Weibo Gaming | +0.1051 | 88.5/611 | eSuba | -0.1001 | 81.1/548 |
| SN CyberCore Esports | +0.1015 | 40.2/79 | UCAM Esports | -0.0903 | 78.2/435 |
| Team WE | +0.0971 | 111.5/1122 | Team Phantasma | -0.0901 | 73.0/462 |
| HANJIN BRION Challengers | +0.0934 | 65.5/468 | Galions Sharks | -0.0885 | 24.5/35 |
| KT Rolster | +0.0881 | 102.7/1327 | Nongshim RedForce | -0.0867 | 94.7/629 |
| GiantX | +0.0875 | 67.3/196 | JD Gaming | -0.0862 | 136.7/1166 |
| G3V E-sports | +0.0865 | 16.9/31 | Misa Esports | -0.0854 | 51.1/228 |
| Leviatan | +0.0812 | 38.9/250 | T1 Esports Academy Rookies | -0.0846 | 90.0/447 |

| player top 10 | Slope | Games | player bottom 10 | Slope | Games |
|---|---|---|---|---|---|
| Jiejie | +0.1383 | 83.5/717 | Janus | -0.1482 | 88.9/285 |
| Anechek | +0.1258 | 15.7/105 | Lucy | -0.1420 | 79.7/206 |
| Enoch | +0.1141 | 55.4/99 | SeTab | -0.1344 | 93.7/537 |
| Zika | +0.1107 | 69.2/545 | MihawK | -0.1246 | 86.1/240 |
| Erha | +0.1106 | 100.5/383 | Jinbeom | -0.1218 | 80.0/304 |
| Jasten | +0.1057 | 27.9/54 | Pleata | -0.1202 | 105.3/662 |
| Xiaohu | +0.1049 | 88.6/1337 | Vetheo | -0.1025 | 48.3/382 |
| c0st0m | +0.1030 | 36.8/82 | Mita | -0.1013 | 58.5/126 |
| Monki | +0.1022 | 106.3/402 | 113 | -0.0988 | 73.5/452 |
| Cube | +0.1016 | 110.2/776 | IlllIma | -0.0976 | 36.3/293 |

Limits: retrospective test previously viewed in earlier studies; no multiple-comparison adjustment. LPL champion coverage gaps in Oracle's Elixir also limit player-history/roster coverage. Game length is an outcome-side quantity used only from earlier games; league-year centering uses the specified full-year median. Weak persistence suggests noise rather than a stable trait. No market/trading check; no production changes.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_late_teams.py
```
