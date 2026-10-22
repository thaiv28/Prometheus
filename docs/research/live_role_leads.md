**FAIL: primary ΔLL +0.000623 (+0.000230 to +0.001030); retrospective, research only.**

# Role leads in the live model

Protocol fixed before scoring: primary five role gold gaps; level five level gaps; cs five CS gaps; totals summed level and CS gaps; all fifteen role gaps. Each adds x and x×time; no variants selected after scoring. Feed train/calibration/test maps (rows): 2757 (86709)/1819 (57067)/3893 (123954). Train through 2024, calibrate January–June 2025, test July 2025 onward, ≤2400 seconds. Control uses the deployed objectives + momentum recipe (20 inputs). StandardScaler, L2 C=1, equal map weights, Platt calibration.

Blue-minus-red totalGold/1000, level, creepScore/10 for top/jungle/mid/bottom/support; time=seconds/1200. Metadata comes from any available raw window. Match the window's first frame exactly to the timeline timestamp, otherwise nearest within 10 seconds (first frame only). Missing file/window, incomplete measurements or missing/duplicate roles on either side give all-zero gaps, role_known=False; no rows dropped. role_known is excluded from features.

LL is map-weighted. Δ=candidate−control; 95% paired whole-series bootstrap intervals use 2,000 draws, seed 42. Pass requires primary All upper bound <−0.0005 and no primary slice lower bound >0. Others are descriptive only, never adopted. No multiple-comparison adjustment.

| Model | LL | Brier | ECE10 |
|---|---:|---:|---:|
| control | 0.465625 | 0.154081 | 0.020546 |
| primary | 0.466248 | 0.154285 | 0.019906 |
| level | 0.464492 | 0.153695 | 0.019944 |
| cs | 0.466391 | 0.154300 | 0.020380 |
| totals | 0.465116 | 0.153864 | 0.020386 |
| all | 0.466061 | 0.154165 | 0.020852 |

| Slice | Maps | Primary ΔLL (95% CI) | Level | CS | Totals | All |
|---|---:|---|---|---|---|---|
| All | 3893 | +0.000623[+0.000230,+0.001030] | -0.001134[-0.001932,-0.000311] | +0.000766[+0.000034,+0.001511] | -0.000509[-0.001211,+0.000173] | +0.000436[-0.000843,+0.001734] |
| 0–10 | 3893 | -0.000185[-0.000457,+0.000079] | -0.000647[-0.001120,-0.000169] | -0.000353[-0.000732,+0.000020] | -0.000375[-0.000791,+0.000070] | -0.000280[-0.001194,+0.000613] |
| 10–20 | 3892 | +0.000688[+0.000153,+0.001219] | -0.000522[-0.001351,+0.000285] | +0.000919[-0.000021,+0.001903] | -0.000074[-0.001043,+0.000863] | +0.000417[-0.001127,+0.001942] |
| 20–30 | 3886 | +0.001181[+0.000641,+0.001760] | -0.001687[-0.003400,-0.000059] | +0.001929[+0.000794,+0.003059] | -0.000663[-0.002006,+0.000672] | +0.000915[-0.001240,+0.003030] |
| 30+ | 2158 | +0.001722[+0.000370,+0.003038] | -0.003338[-0.006751,+0.000053] | +0.001109[-0.001183,+0.003478] | -0.001832[-0.003976,+0.000146] | +0.001449[-0.003341,+0.006168] |
| LPL | 944 | +0.000894[+0.000157,+0.001642] | -0.000902[-0.002555,+0.000715] | +0.001524[-0.000013,+0.002993] | -0.000032[-0.001585,+0.001426] | +0.000738[-0.001817,+0.003276] |
| LCK | 687 | +0.000192[-0.000804,+0.001212] | -0.000517[-0.002596,+0.001506] | -0.000354[-0.001975,+0.001263] | -0.000598[-0.002516,+0.001203] | +0.001474[-0.001684,+0.004754] |
| LEC | 443 | +0.000777[-0.000603,+0.002139] | -0.000160[-0.002502,+0.002157] | +0.000816[-0.001048,+0.002681] | +0.000263[-0.001610,+0.002117] | +0.001867[-0.001999,+0.005800] |
| LCS | 253 | +0.001542[+0.000109,+0.003169] | +0.001023[-0.002530,+0.004559] | +0.003518[+0.000303,+0.006938] | +0.001127[-0.001336,+0.003582] | +0.004924[+0.000461,+0.009614] |
| Other majors | 773 | +0.000480[-0.000283,+0.001275] | -0.002737[-0.004793,-0.000805] | -0.001228[-0.003006,+0.000615] | -0.001794[-0.003370,-0.000181] | -0.002280[-0.005169,+0.000572] |
| International | 305 | +0.000370[-0.001088,+0.001800] | -0.003321[-0.006085,-0.000780] | -0.000572[-0.003222,+0.002335] | -0.004006[-0.006276,-0.001875] | -0.002335[-0.006389,+0.001889] |
| Other | 488 | +0.000471[-0.000691,+0.001827] | -0.000544[-0.002668,+0.001535] | +0.003397[+0.001403,+0.005551] | +0.001367[-0.000477,+0.003229] | +0.000799[-0.002695,+0.004307] |
| Known | 3893 | +0.000623[+0.000230,+0.001030] | -0.001134[-0.001932,-0.000311] | +0.000766[+0.000034,+0.001511] | -0.000509[-0.001211,+0.000173] | +0.000436[-0.000843,+0.001734] |
| Unknown | 0 | n/a | n/a | n/a | n/a | n/a |
| 2026 | 2836 | +0.000568[+0.000067,+0.001059] | -0.001336[-0.002301,-0.000425] | +0.000663[-0.000259,+0.001583] | -0.000351[-0.001066,+0.000388] | +0.000259[-0.001255,+0.001711] |

Known/Unknown refer to row-level role coverage.

| Test league | Maps | Rows | Rows with unknown roles |
|---|---:|---:|---:|
| CBLOL | 247 | 7944 | 0 |
| EWC | 49 | 1553 | 0 |
| FST | 45 | 1362 | 0 |
| LCK | 687 | 21863 | 0 |
| LCP | 376 | 11993 | 0 |
| LCS | 253 | 8122 | 0 |
| LEC | 443 | 14566 | 0 |
| LJL | 197 | 6107 | 0 |
| LPL | 944 | 30039 | 0 |
| LTA | 22 | 707 | 0 |
| LTA N | 65 | 2126 | 0 |
| LTA S | 63 | 2032 | 0 |
| MSI | 125 | 4016 | 0 |
| PCS | 135 | 4014 | 0 |
| VCS | 156 | 4736 | 0 |
| Worlds | 86 | 2774 | 0 |

Test known roles: 123954/123954 rows. Across joined maps: 8469 raw files; 270225 exact, 0 nearest, 0 unknown rows.

Primary standardized logistic coefficients before Platt calibration:

| Added column | Coefficient |
|---|---:|
| gold_top | +0.497240 |
| gold_top_time | -0.293293 |
| gold_jungle | +0.315897 |
| gold_jungle_time | -0.166748 |
| gold_mid | +0.489653 |
| gold_mid_time | -0.298095 |
| gold_bottom | +0.491377 |
| gold_bottom_time | -0.306926 |
| gold_support | +0.239983 |
| gold_support_time | -0.058869 |

Limits: retrospective; July-2025+ test outcomes were viewed by earlier studies. Participant gold overlaps team gold lead already in the model. No trading check; no production change.

Reproduce:
```bash
OPENBLAS_NUM_THREADS=4 PYTHONPATH=$PWD uv run python scripts/research/live_role_leads.py
```
