# League-offset uncertainty

Selected `{'league_rd': (120.0, 80, 1, 1)}`; initial {'coordinates': (80, 1.5, 1, 1), 'objective': 0.6196320220477082}; 15 extension cells. Tuning objective 0.61963202.

League-offset Glicko-style uncertainty, opt-in against published player Elo.

Fixed 54-cell grid: floor {20,40,80}, new/floor {1.5,2.5,4}, growth
{1,3,6}, information {.25,1}. One local Cartesian edge extension uses
floor 10/160, ratio 1.1/6, growth 0/12, information .125/2. Select only
on <=2021 games-weighted domestic, international, within-other and
cross-league Elo losses. Freeze selection before scoring 2022+.

Usage: VECLIB_MAXIMUM_THREADS=1 .venv/bin/python scripts/research/elo_offset_rd.py
Native checks are separate; this script never writes Elo tables or weights.


## Held out 2022+

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | -0.00002 (-0.00005 to +0.00001) |
| Elo, international | 589 | 0.61877 | -0.00007 (-0.00021 to +0.00005) |
| FORGE, domestic | 7,728 | 0.62010 | -0.00002 (-0.00004 to +0.00001) |
| FORGE, international | 589 | 0.61154 | +0.00000 (-0.00010 to +0.00011) |
| Elo, other leagues | 37,272 | 0.60081 | -0.00000 (-0.00002 to +0.00002) |
| FORGE, other leagues | 37,272 | 0.59979 | -0.00000 (-0.00002 to +0.00002) |
| Elo, cross-league | 5,442 | 0.57070 | -0.00033 (-0.00049 to -0.00016) |

## Roster-change slices

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | -0.00000 (-0.00011 to +0.00011) |
| Elo, international | 9 | 0.78976 | +0.00001 (-0.00072 to +0.00079) |
| FORGE, domestic | 703 | 0.58950 | +0.00000 (-0.00007 to +0.00009) |
| FORGE, international | 9 | 0.78809 | +0.00000 (-0.00052 to +0.00056) |
| Elo, other leagues | 6,814 | 0.58324 | -0.00001 (-0.00006 to +0.00004) |
| FORGE, other leagues | 6,814 | 0.58221 | -0.00000 (-0.00004 to +0.00004) |
| Elo, cross-league | 682 | 0.53321 | -0.00050 (-0.00108 to +0.00007) |

## Method and limits

Reuses elo_glicko sections, leave-one-year-out curves and replay-specific Form/FORGE fits. Within-other Form features use other major years including tuning years. Not a chronological deployment simulation. Individual-game paired-bootstrap 95% intervals, no clustering or multiplicity adjustment; historical holdouts were viewed in prior research. Calibration remains on here. Exact selected prefix/full parity passes. League uncertainty only changes cross-home international offset updates; player RD and non-major slope retain published defaults.

Held-out targeted gate: PASS (international/cross-league gain, no section significantly worse). Native verdict (elo_offset_rd_native.md): offset RD fails the rule (two guarded within-other-league rows about 2e-5 worse over all years, despite a -0.00022 cross-league gain); removing the calibration fails (cross-league significantly worse with or without RD).

Paired full-replay timing check (three runs each, order AB/BA/AB): published median 5.24 s (5.19–5.43); selected RD median 5.16 s (5.07–5.22). Use this paired check for overhead; the initial replay and later selected replays can face different concurrent machine load.


## Tuning audit

| Coordinates (floor, ratio, growth, info) | Objective |
|---|---:|
| [20, 1.5, 1, 0.25] | 0.61973500 |
| [20, 1.5, 1, 1] | 0.61972571 |
| [20, 1.5, 3, 0.25] | 0.61973506 |
| (20, 1.5, 3, 1) | 0.61972943 |
| (20, 1.5, 6, 0.25) | 0.61973495 |
| (20, 1.5, 6, 1) | 0.61972781 |
| (20, 2.5, 1, 0.25) | 0.62089125 |
| (20, 2.5, 1, 1) | 0.62041524 |
| (20, 2.5, 3, 0.25) | 0.62104960 |
| (20, 2.5, 3, 1) | 0.62085635 |
| (20, 2.5, 6, 0.25) | 0.62107413 |
| (20, 2.5, 6, 1) | 0.62091152 |
| (20, 4, 1, 0.25) | 0.62299877 |
| (20, 4, 1, 1) | 0.62147304 |
| (20, 4, 3, 0.25) | 0.62449712 |
| (20, 4, 3, 1) | 0.62276793 |
| (20, 4, 6, 0.25) | 0.62470533 |
| (20, 4, 6, 1) | 0.62362538 |
| (40, 1.5, 1, 0.25) | 0.61971411 |
| (40, 1.5, 1, 1) | 0.61966921 |
| (40, 1.5, 3, 0.25) | 0.61972916 |
| (40, 1.5, 3, 1) | 0.61971542 |
| (40, 1.5, 6, 0.25) | 0.61972943 |
| (40, 1.5, 6, 1) | 0.61971703 |
| (40, 2.5, 1, 0.25) | 0.62025533 |
| (40, 2.5, 1, 1) | 0.61988087 |
| (40, 2.5, 3, 0.25) | 0.62060057 |
| (40, 2.5, 3, 1) | 0.62007607 |
| (40, 2.5, 6, 0.25) | 0.62085635 |
| (40, 2.5, 6, 1) | 0.62046213 |
| (40, 4, 1, 0.25) | 0.62133991 |
| (40, 4, 1, 1) | 0.62037618 |
| (40, 4, 3, 0.25) | 0.62171167 |
| (40, 4, 3, 1) | 0.62053553 |
| (40, 4, 6, 0.25) | 0.62276793 |
| (40, 4, 6, 1) | 0.62111837 |
| (80, 1.5, 1, 0.25) | 0.61964688 |
| (80, 1.5, 1, 1) | 0.61963202 |
| (80, 1.5, 3, 0.25) | 0.61970225 |
| (80, 1.5, 3, 1) | 0.61963718 |
| (80, 1.5, 6, 0.25) | 0.61971542 |
| (80, 1.5, 6, 1) | 0.61970119 |
| (80, 2.5, 1, 0.25) | 0.61985665 |
| (80, 2.5, 1, 1) | 0.61968969 |
| (80, 2.5, 3, 0.25) | 0.61991898 |
| (80, 2.5, 3, 1) | 0.61970108 |
| (80, 2.5, 6, 0.25) | 0.62007607 |
| (80, 2.5, 6, 1) | 0.61978196 |
| (80, 4, 1, 0.25) | 0.62035542 |
| (80, 4, 1, 1) | 0.61998254 |
| (80, 4, 3, 0.25) | 0.62040777 |
| (80, 4, 3, 1) | 0.61999642 |
| (80, 4, 6, 0.25) | 0.62053553 |
| (80, 4, 6, 1) | 0.62006888 |
| (80, 1.5, 1, 2) | 0.61964426 |
| (80, 1.5, 0, 1) | 0.61963230 |
| (80, 1.5, 0, 2) | 0.61964469 |
| (80, 1.1, 1, 1) | 0.61964481 |
| (80, 1.1, 1, 2) | 0.61964554 |
| (80, 1.1, 0, 1) | 0.61964529 |
| (80, 1.1, 0, 2) | 0.61964602 |
| (160, 1.5, 1, 1) | 0.61964802 |
| (160, 1.5, 1, 2) | 0.61965060 |
| (160, 1.5, 0, 1) | 0.61964813 |
| (160, 1.5, 0, 2) | 0.61965072 |
| (160, 1.1, 1, 1) | 0.61964643 |
| (160, 1.1, 1, 2) | 0.61964634 |
| (160, 1.1, 0, 1) | 0.61964655 |
| (160, 1.1, 0, 2) | 0.61964646 |
