# Draft composition profiles

One frozen candidate; protocol in `scripts/research/draft_composition.py`. Walk-forward fits use 2019 through the preceding year. Differences are candidate minus v2; 95% intervals resample league/day/team-pair series. Negative favours the candidate.

**Verdict: inconclusive; exclude the whole three-feature block from v3.** Neither the all-games nor pre-2025 primary interval excludes zero. The international subgroup gain does not qualify the block under the rule fixed before scoring; no individual feature was selected afterward.

| Slice | Games | v2 LL | Candidate LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.607068 | +0.000008 (-0.000072 to +0.000085) |
| major leagues | 10,808 | 0.620044 | 0.619907 | -0.000137 (-0.000322 to +0.000045) |
| LPL | 4,470 | 0.623064 | 0.623054 | -0.000010 (-0.000299 to +0.000277) |
| international | 1,696 | 0.593760 | 0.593231 | -0.000529 (-0.001019 to -0.000018) |
| other leagues | 51,134 | 0.604756 | 0.604813 | +0.000057 (-0.000025 to +0.000146) |
| before 2025 | 44,450 | 0.608084 | 0.608074 | -0.000010 (-0.000104 to +0.000087) |
| 2021 | 11,802 | 0.618341 | 0.618491 | +0.000150 (+0.000060 to +0.000245) |
| 2022 | 12,050 | 0.605447 | 0.605290 | -0.000158 (-0.000303 to -0.000031) |
| 2023 | 10,750 | 0.609970 | 0.609982 | +0.000013 (-0.000225 to +0.000263) |
| 2024 | 9,848 | 0.596960 | 0.596916 | -0.000044 (-0.000280 to +0.000191) |
| 2025 | 9,761 | 0.607608 | 0.607635 | +0.000026 (-0.000197 to +0.000239) |
| 2026 | 9,427 | 0.601660 | 0.601734 | +0.000074 (-0.000114 to +0.000261) |

## Added-feature coefficients

| Test year | scaling | scaling_strength | early |
|---|---:|---:|---:|
| 2021 | -0.06181 | +0.04468 | +0.01858 |
| 2022 | +0.01525 | -0.10754 | -0.03942 |
| 2023 | +0.18645 | -0.08708 | -0.05114 |
| 2024 | +0.14464 | -0.06462 | -0.04796 |
| 2025 | +0.08340 | -0.04753 | -0.05552 |
| 2026 | +0.05051 | -0.03957 | -0.05449 |

## Limits

Scaling is an observational duration profile: winners affect game length; it does not identify causal late-game power. Lane snapshots are sparse in LPL; missing champion-role history is shrunk to zero, not a reason to exclude current LPL games. Damage mix was not implemented because the built DB lacks physical/magic damage. No production metric, weights or site changed. All periods are retrospective; 2025-26 helped choose v2. The production call's own fitted weights are not vintage artifacts.

Feature construction and scoring: 76.9 s (bootstrap reporting excluded); no new CI job or production-build work.

Historical player-row lane-snapshot coverage: 89.9%.
