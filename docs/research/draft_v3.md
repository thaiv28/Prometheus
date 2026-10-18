# Draft v3: fixed union of qualifying blocks

Selection/scoring protocol: [draft_v3_protocol.md](draft_v3_protocol.md), fixed before reading track results. Every full primary block is supplied. Blocks qualify only on all/pre-2025 benefit with no significantly worse named league slice. Tests reuse viewed outcomes; intervals condition on selection, without multiplicity adjustment.

Identical baseline cohort: 80,791 training/test games, 2019–2026. No production calls are rebuilt.

## Block: composition — excluded

| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.607068 | +0.000008 (-0.000072 to +0.000085) |
| major leagues | 10,808 | 0.620044 | 0.619907 | -0.000137 (-0.000322 to +0.000045) |
| LPL | 4,470 | 0.623064 | 0.623054 | -0.000010 (-0.000299 to +0.000277) |
| international | 1,696 | 0.593760 | 0.593231 | -0.000529 (-0.001019 to -0.000018) |
| other leagues | 51,134 | 0.604756 | 0.604813 | +0.000057 (-0.000025 to +0.000146) |
| before 2025 | 44,450 | 0.608084 | 0.608074 | -0.000010 (-0.000104 to +0.000087) |

## Block: form — excluded

| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.606956 | -0.000103 (-0.000242 to +0.000035) |
| major leagues | 10,808 | 0.620044 | 0.620197 | +0.000153 (-0.000244 to +0.000532) |
| LPL | 4,470 | 0.623064 | 0.622523 | -0.000541 (-0.001195 to +0.000121) |
| international | 1,696 | 0.593760 | 0.593326 | -0.000434 (-0.001509 to +0.000603) |
| other leagues | 51,134 | 0.604756 | 0.604609 | -0.000147 (-0.000298 to +0.000007) |
| before 2025 | 44,450 | 0.608084 | 0.607966 | -0.000118 (-0.000301 to +0.000056) |

## Block: meta — excluded

| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.607190 | +0.000131 (-0.000016 to +0.000269) |
| major leagues | 10,808 | 0.620044 | 0.620120 | +0.000077 (-0.000297 to +0.000449) |
| LPL | 4,470 | 0.623064 | 0.623486 | +0.000422 (-0.000193 to +0.001049) |
| international | 1,696 | 0.593760 | 0.593209 | -0.000551 (-0.001326 to +0.000258) |
| other leagues | 51,134 | 0.604756 | 0.604921 | +0.000165 (-0.000003 to +0.000332) |
| before 2025 | 44,450 | 0.608084 | 0.608294 | +0.000210 (+0.000016 to +0.000408) |

## Block: player_feats — qualifies

| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.605070 | -0.001990 (-0.002518 to -0.001441) |
| major leagues | 10,808 | 0.620044 | 0.620039 | -0.000005 (-0.000954 to +0.000965) |
| LPL | 4,470 | 0.623064 | 0.622378 | -0.000686 (-0.002147 to +0.000793) |
| international | 1,696 | 0.593760 | 0.593012 | -0.000748 (-0.003292 to +0.001900) |
| other leagues | 51,134 | 0.604756 | 0.602306 | -0.002450 (-0.003077 to -0.001802) |
| before 2025 | 44,450 | 0.608084 | 0.605886 | -0.002198 (-0.002834 to -0.001584) |

## Combined candidate

Included columns: breadth, depth, top_pool, lane_gold, lane_xp, role_swap, substitute. Fixed comparison rule: passes retrospectively.

| Slice | Maps | v2 LL | Candidate LL | Difference (series-bootstrap 95%) |
|---|---:|---:|---:|---|
| all | 63,638 | 0.607059 | 0.605070 | -0.001990 (-0.002518 to -0.001441) |
| major leagues | 10,808 | 0.620044 | 0.620039 | -0.000005 (-0.000954 to +0.000965) |
| LPL | 4,470 | 0.623064 | 0.622378 | -0.000686 (-0.002147 to +0.000793) |
| international | 1,696 | 0.593760 | 0.593012 | -0.000748 (-0.003292 to +0.001900) |
| other leagues | 51,134 | 0.604756 | 0.602306 | -0.002450 (-0.003077 to -0.001802) |
| before 2025 | 44,450 | 0.608084 | 0.605886 | -0.002198 (-0.002834 to -0.001584) |
| 2021 | 11,802 | 0.618341 | 0.616103 | -0.002237 (-0.003479 to -0.001050) |
| 2022 | 12,050 | 0.605447 | 0.602645 | -0.002803 (-0.004044 to -0.001589) |
| 2023 | 10,750 | 0.609970 | 0.607973 | -0.001997 (-0.003325 to -0.000765) |
| 2024 | 9,848 | 0.596960 | 0.595328 | -0.001632 (-0.003070 to -0.000275) |
| 2025 | 9,761 | 0.607608 | 0.606028 | -0.001580 (-0.002918 to -0.000181) |
| 2026 | 9,427 | 0.601660 | 0.600230 | -0.001430 (-0.002834 to +0.000035) |

| Test year | intercept | forge_logit | exp | meta | matchup | synergy | breadth | depth | top_pool | lane_gold | lane_xp | role_swap | substitute |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2021 | +0.103144 | +0.799751 | +0.018774 | +0.988886 | +0.210374 | +0.332448 | +0.075864 | +0.012992 | +0.006220 | +0.241785 | +0.229383 | -0.071642 | -0.003566 |
| 2022 | +0.101758 | +0.786043 | +0.015131 | +1.102015 | +0.228945 | +0.293612 | +0.082532 | +0.062074 | +0.005477 | +0.125077 | +0.229277 | -0.101329 | -0.003038 |
| 2023 | +0.093768 | +0.793118 | +0.011853 | +1.035946 | +0.300031 | +0.317415 | +0.086894 | +0.053924 | +0.011923 | +0.118328 | +0.163430 | -0.088529 | -0.010599 |
| 2024 | +0.099417 | +0.784412 | +0.013806 | +1.084024 | +0.311398 | +0.349437 | +0.087003 | +0.060489 | +0.014851 | +0.156914 | +0.129508 | -0.088421 | -0.014746 |
| 2025 | +0.101396 | +0.798549 | +0.012521 | +1.137443 | +0.314965 | +0.348048 | +0.083352 | +0.050107 | +0.013995 | +0.192525 | +0.106280 | -0.098988 | -0.017615 |
| 2026 | +0.106583 | +0.801747 | +0.012284 | +1.095335 | +0.318403 | +0.357062 | +0.081057 | +0.030551 | +0.015165 | +0.146491 | +0.128425 | -0.096467 | -0.015001 |

## Limits

Whole-block significance does not attribute gains to individual columns. Prior annual FORGE calibration/weights are current artifacts, not historical vintages. All periods are retrospective; the v3 block gate viewed the same before-2025 years subsequently reported. Future untouched evaluation is required for confirmation. Market, series and live tracks remain separate; no shipping or trading claim.

## Input provenance

```json
[
  {
    "block": "composition",
    "columns": [
      "scaling",
      "scaling_strength",
      "early"
    ],
    "source": "/Users/tvillalu/repos/Prometheus-draft-composition/data/research/draft_v2/composition_games.pkl",
    "sha256": "8618785f5c2b277ff48ee8cbe5ecee41c9ddc26787d0d8f32e0166e8305ab77e"
  },
  {
    "block": "form",
    "columns": [
      "decayed_exp",
      "recency",
      "share"
    ],
    "source": "/Users/tvillalu/repos/Prometheus-draft-form/data/research/draft_v2/form_games.pkl",
    "sha256": "99f4ea8d6e9701545b29e3bd275c243509fac7b8388df82d1b93b2ec5e5e1597"
  },
  {
    "block": "meta",
    "columns": [
      "patch_meta",
      "local_meta",
      "priority"
    ],
    "source": "/Users/tvillalu/repos/Prometheus-draft-meta/data/research/draft_v2/meta_games.pkl",
    "sha256": "3f6b0ce59077fa95e69aa93b964a5262e41e71e48b263917f51f38570f8df085"
  },
  {
    "block": "player_feats",
    "columns": [
      "breadth",
      "depth",
      "top_pool",
      "lane_gold",
      "lane_xp",
      "role_swap",
      "substitute"
    ],
    "source": "/Users/tvillalu/repos/Prometheus-draft-player-feats/data/research/draft_v2/player_feats_games.pkl",
    "sha256": "b0a7775d5a0709bdd86c89bb607e2f4f9539caee54561994b5bd5cca6e3f1cd6"
  }
]
```
