# Draft player-on-champion recency

Protocol fixed in `scripts/research/draft_form.py`. Three half-lives compared only on 2020 (fit 2019); one augmentation scored on test years. Candidate minus v2, 95% league/day/team-pair series bootstrap; negative favours recency.

Selected half-life: 30 days. 2020 development log losses: 30d 0.617581, 90d 0.617876, 180d 0.617859.

**Verdict: inconclusive; exclude the whole three-feature block from v3.** The all-games and pre-2025 primary intervals both include zero; no named league slice is significantly worse. The block and development-only half-life choice were fixed before scoring; no individual feature was selected afterward.

| Slice | Games | v2 LL | Candidate LL | Difference (95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.606956 | -0.000103 (-0.000242 to +0.000035) |
| major leagues | 10,808 | 0.620044 | 0.620197 | +0.000153 (-0.000244 to +0.000532) |
| LPL | 4,470 | 0.623064 | 0.622523 | -0.000541 (-0.001195 to +0.000121) |
| international | 1,696 | 0.593760 | 0.593326 | -0.000434 (-0.001509 to +0.000603) |
| other leagues | 51,134 | 0.604756 | 0.604609 | -0.000147 (-0.000298 to +0.000007) |
| before 2025 | 44,450 | 0.608084 | 0.607966 | -0.000118 (-0.000301 to +0.000056) |
| 2021 | 11,802 | 0.618341 | 0.618419 | +0.000078 (-0.000356 to +0.000506) |
| 2022 | 12,050 | 0.605447 | 0.605325 | -0.000123 (-0.000437 to +0.000184) |
| 2023 | 10,750 | 0.609970 | 0.609877 | -0.000093 (-0.000424 to +0.000237) |
| 2024 | 9,848 | 0.596960 | 0.596585 | -0.000374 (-0.000717 to -0.000040) |
| 2025 | 9,761 | 0.607608 | 0.607605 | -0.000003 (-0.000344 to +0.000330) |
| 2026 | 9,427 | 0.601660 | 0.601520 | -0.000139 (-0.000450 to +0.000172) |

## Added-feature coefficients

| Test year | decayed_exp | recency | share |
|---|---:|---:|---:|
| 2021 | -0.06152 | -0.00701 | +0.10979 |
| 2022 | -0.05282 | -0.00979 | +0.09231 |
| 2023 | -0.04232 | -0.01069 | +0.01265 |
| 2024 | -0.03472 | -0.01052 | -0.02474 |
| 2025 | -0.03519 | -0.01201 | -0.05437 |
| 2026 | -0.02597 | -0.01119 | -0.10159 |

## Limits

Professional games only; this does not measure practice or solo queue. The three correlated features are assessed jointly, not individually selected after test scoring. Unseen champions use capped 365-day recency; inactivity decays both numerator and denominator. No result-above-Elo exploratory candidate was tried. All periods retrospective; 2025-26 were viewed for v2 selection, and production-call weights are not vintage artifacts. No production metric, weights or site changed.

Feature construction and scoring: 344.5 s (bootstrap reporting excluded); no production-build work or CI job added.
