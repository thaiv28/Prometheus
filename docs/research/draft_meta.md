# Draft meta: fixed walk-forward candidate

Fixed protocol, written before test scoring (2026-10-17).

One primary candidate: v2 plus patch_meta, local_meta, priority; no tuning or
variant search. Patch meta = (current-patch WAE + .5 previous-patch WAE) /
(current count + .5 previous count + 50), champion-role, earlier UTC days only.
Previous patch means the numeric predecessor observed BEFORE the day, not a
future vocabulary. local_meta is a 60-day champion-role WAE in the same league,
shrink 50. Priority is current plus half previous patch's historical pick+ban
count for the picked champion, divided by similarly weighted maps + 20.
Missing patches/bans fall back to zero. All five roles summed blue-minus-red.
Keep v2's original four features. Fit 2019..Y-1 and test Y=2021..2026 using the
same logistic settings and games as v2; bootstrap whole series via v2.paired.
Report patch first three observed calendar days separately. These are historical
OE patch labels, not verified game-day publication times. 2025-26 already viewed
in choosing v2; earlier test years reported independently. Research only.

Feature construction/scoring: 178.6 seconds (cached FORGE; bootstrap reporting excluded). One candidate, no exploratory variants.

| Slice | Games | v2 LL | Candidate LL | Candidate − v2 (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.60706 | 0.60719 | +0.00013 (-0.00002 to +0.00027) |
| major leagues | 10,808 | 0.62004 | 0.62012 | +0.00008 (-0.00030 to +0.00045) |
| LPL | 4,470 | 0.62306 | 0.62349 | +0.00042 (-0.00019 to +0.00105) |
| international | 1,696 | 0.59376 | 0.59321 | -0.00055 (-0.00133 to +0.00026) |
| other leagues | 51,134 | 0.60476 | 0.60492 | +0.00016 (-0.00000 to +0.00033) |
| before 2025 | 44,450 | 0.60808 | 0.60829 | +0.00021 (+0.00002 to +0.00041) |
| 2021 | 11,802 | 0.61834 | 0.61856 | +0.00022 (-0.00028 to +0.00077) |
| 2022 | 12,050 | 0.60545 | 0.60556 | +0.00011 (-0.00023 to +0.00045) |
| 2023 | 10,750 | 0.60997 | 0.61020 | +0.00023 (-0.00009 to +0.00058) |
| 2024 | 9,848 | 0.59696 | 0.59725 | +0.00029 (-0.00001 to +0.00059) |
| 2025 | 9,761 | 0.60761 | 0.60763 | +0.00002 (-0.00023 to +0.00028) |
| 2026 | 9,427 | 0.60166 | 0.60153 | -0.00013 (-0.00038 to +0.00011) |
| first three patch days | 25,088 | 0.60009 | 0.60012 | +0.00003 (-0.00020 to +0.00027) |
| later patch days | 38,550 | 0.61159 | 0.61179 | +0.00020 (+0.00000 to +0.00040) |

## Fitted added-feature weights

| Year | patch_meta | local_meta | priority |
|---|---:|---:|---:|
| 2021 | +0.6656 | -0.5921 | -0.0264 |
| 2022 | +0.6414 | -0.2974 | -0.0014 |
| 2023 | +0.5331 | -0.2841 | +0.0007 |
| 2024 | +0.4749 | -0.2071 | -0.0099 |
| 2025 | +0.3836 | -0.1783 | -0.0099 |
| 2026 | +0.3540 | -0.0944 | -0.0128 |

Verdict: reject the whole predeclared block for v3. Pooled gain is inconclusive and pre-2025 log loss is significantly worse. The first three patch days show no gain. No alternative subset was tried.

Limits: patch labels are historical OE metadata; publication timing is unverified. Priority uses pick/ban frequency, not within-draft pick order. FORGE upstream weights were fit using years included here. No prospective or trading-edge claim.
