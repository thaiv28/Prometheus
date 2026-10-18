# Draft v2: market edge under stricter fills

Protocol fixed in `scripts/research/draft_market_edge.py` before scoring. All choices use maps before 2026-05-01; second-half results never select settings. Twelve cap/edge settings per entry (three fitted capped weights × four edges). Both halves were previously viewed in v2; this is retrospective research, not a fresh holdout.

4,670 unique cached priced OE games; 1 duplicate baseline row removed. Offline cached trades only. Entry times use OE's approximate map start. Primary: −60 s, trades at most 30 s old, a same-side trade in the next 15 s, worse of nearby costs. Fixed side and quarter-Kelly size precede the fill; adverse fills are retained. Per-contract taker fees round upward to a cent. ROI uses all-in dollars, as does Kelly growth. Sensitivities use the primary settings unchanged.

Kalshi's coefficient is fixed at 1; shift weight in [0,2] has ridge penalty 4. Before-2025 priced maps: unavailable. No order-book/queue/size evidence; nearby trades do not demonstrate an executable fill. Fractional bankroll accounting ignores simultaneous exposure.

## Entry -60 seconds (primary)

Recent market-price coverage: first half 395, second half 1,195 maps.

| Cap | Fitted weight | Edge | First-half bets | First-half ROI | Total log growth |
|---:|---:|---:|---:|---:|---:|
| 0.25 | 0.000 | 0.02 | 0 | — | +0.0000 |
| 0.25 | 0.000 | 0.03 | 0 | — | +0.0000 |
| 0.25 | 0.000 | 0.05 | 0 | — | +0.0000 |
| 0.25 | 0.000 | 0.10 | 0 | — | +0.0000 |
| 0.50 | 0.105 | 0.02 | 0 | — | +0.0000 |
| 0.50 | 0.105 | 0.03 | 0 | — | +0.0000 |
| 0.50 | 0.105 | 0.05 | 0 | — | +0.0000 |
| 0.50 | 0.105 | 0.10 | 0 | — | +0.0000 |
| 1.00 | 0.131 | 0.02 | 0 | — | +0.0000 |
| 1.00 | 0.131 | 0.03 | 0 | — | +0.0000 |
| 1.00 | 0.131 | 0.05 | 0 | — | +0.0000 |
| 1.00 | 0.131 | 0.10 | 0 | — | +0.0000 |

Inconclusive: no setting had 30 first-half fill proxies; no primary policy selected.

No policy means zero second-half bets and zero total Kelly log growth; per-bet ROI, growth intervals, favourite/long-shot returns and fill sensitivities are not estimable. The development minimum is retained unchanged.

### Forecast diagnostics (all three declared caps; none selected)

| Cap | Slice | Maps | Fitted − v2 weight-one shift LL (95%) | Fitted − Kalshi LL (95%) |
|---:|---|---:|---|---|
| 0.25 | all | 1195 | -0.0009 (-0.0075 to +0.0056) | +0.0000 (+0.0000 to +0.0000) |
| 0.25 | major leagues | 600 | -0.0052 (-0.0147 to +0.0044) | +0.0000 (+0.0000 to +0.0000) |
| 0.25 | LPL | 183 | -0.0011 (-0.0182 to +0.0155) | +0.0000 (+0.0000 to +0.0000) |
| 0.25 | international | 154 | +0.0061 (-0.0120 to +0.0237) | +0.0000 (+0.0000 to +0.0000) |
| 0.25 | other leagues | 441 | +0.0025 (-0.0080 to +0.0118) | +0.0000 (+0.0000 to +0.0000) |
| 0.25 | 2026 | 1195 | -0.0009 (-0.0075 to +0.0056) | +0.0000 (+0.0000 to +0.0000) |
| 0.50 | all | 1195 | -0.0014 (-0.0074 to +0.0044) | -0.0005 (-0.0012 to +0.0001) |
| 0.50 | major leagues | 600 | -0.0053 (-0.0139 to +0.0033) | -0.0001 (-0.0011 to +0.0008) |
| 0.50 | LPL | 183 | -0.0015 (-0.0169 to +0.0133) | -0.0004 (-0.0021 to +0.0013) |
| 0.50 | international | 154 | +0.0048 (-0.0116 to +0.0205) | -0.0013 (-0.0031 to +0.0005) |
| 0.50 | other leagues | 441 | +0.0017 (-0.0076 to +0.0100) | -0.0008 (-0.0018 to +0.0003) |
| 0.50 | 2026 | 1195 | -0.0014 (-0.0074 to +0.0044) | -0.0005 (-0.0012 to +0.0001) |
| 1.00 | all | 1195 | -0.0015 (-0.0073 to +0.0041) | -0.0006 (-0.0015 to +0.0002) |
| 1.00 | major leagues | 600 | -0.0053 (-0.0135 to +0.0031) | -0.0001 (-0.0013 to +0.0011) |
| 1.00 | LPL | 183 | -0.0017 (-0.0165 to +0.0128) | -0.0006 (-0.0028 to +0.0017) |
| 1.00 | international | 154 | +0.0045 (-0.0112 to +0.0196) | -0.0017 (-0.0040 to +0.0007) |
| 1.00 | other leagues | 441 | +0.0014 (-0.0076 to +0.0095) | -0.0010 (-0.0023 to +0.0003) |
| 1.00 | 2026 | 1195 | -0.0015 (-0.0073 to +0.0041) | -0.0006 (-0.0015 to +0.0002) |

### Second-half movement toward the draft shift

All eligible maps, independent of the unselected betting policy. Positive means price moves in the shift's direction. Close trades must be ≤30 seconds old; values are probability units. This is price movement rather than executable CLV. No selected bets exist for after-fee CLV.

| Slice | Map time | Maps with close | Movement (series-bootstrap 95%) |
|---|---|---:|---|
| all | +1 min | 1047 | +0.0067 (+0.0037 to +0.0099) |
| all | +3 min | 1035 | +0.0076 (+0.0036 to +0.0116) |
| all | +5 min | 1033 | +0.0051 (-0.0012 to +0.0117) |
| major leagues | +1 min | 590 | +0.0081 (+0.0045 to +0.0119) |
| major leagues | +3 min | 575 | +0.0087 (+0.0036 to +0.0137) |
| major leagues | +5 min | 574 | +0.0090 (+0.0012 to +0.0171) |
| LPL | +1 min | 175 | +0.0062 (-0.0006 to +0.0130) |
| LPL | +3 min | 169 | +0.0118 (+0.0029 to +0.0208) |
| LPL | +5 min | 168 | +0.0123 (-0.0014 to +0.0263) |
| international | +1 min | 143 | +0.0014 (-0.0063 to +0.0090) |
| international | +3 min | 141 | -0.0035 (-0.0136 to +0.0063) |
| international | +5 min | 143 | -0.0141 (-0.0313 to +0.0017) |
| other leagues | +1 min | 314 | +0.0066 (-0.0004 to +0.0129) |
| other leagues | +3 min | 319 | +0.0104 (+0.0017 to +0.0190) |
| other leagues | +5 min | 316 | +0.0066 (-0.0062 to +0.0195) |

## Entry +45 seconds (secondary)

Recent market-price coverage: first half 714, second half 1,871 maps.

| Cap | Fitted weight | Edge | First-half bets | First-half ROI | Total log growth |
|---:|---:|---:|---:|---:|---:|
| 0.25 | 0.208 | 0.02 | 0 | — | +0.0000 |
| 0.25 | 0.208 | 0.03 | 0 | — | +0.0000 |
| 0.25 | 0.208 | 0.05 | 0 | — | +0.0000 |
| 0.25 | 0.208 | 0.10 | 0 | — | +0.0000 |
| 0.50 | 0.335 | 0.02 | 3 | -0.4048 | -0.0141 |
| 0.50 | 0.335 | 0.03 | 0 | — | +0.0000 |
| 0.50 | 0.335 | 0.05 | 0 | — | +0.0000 |
| 0.50 | 0.335 | 0.10 | 0 | — | +0.0000 |
| 1.00 | 0.363 | 0.02 | 8 | +0.0192 | +0.0124 |
| 1.00 | 0.363 | 0.03 | 1 | +0.7857 | +0.0143 |
| 1.00 | 0.363 | 0.05 | 0 | — | +0.0000 |
| 1.00 | 0.363 | 0.10 | 0 | — | +0.0000 |

Inconclusive: no setting had 30 first-half fill proxies; no primary policy selected.

No policy means zero second-half bets and zero total Kelly log growth; per-bet ROI, growth intervals, favourite/long-shot returns and fill sensitivities are not estimable. The development minimum is retained unchanged.

### Forecast diagnostics (all three declared caps; none selected)

| Cap | Slice | Maps | Fitted − v2 weight-one shift LL (95%) | Fitted − Kalshi LL (95%) |
|---:|---|---:|---|---|
| 0.25 | all | 1871 | +0.0001 (-0.0044 to +0.0044) | -0.0011 (-0.0019 to -0.0003) |
| 0.25 | major leagues | 785 | -0.0051 (-0.0118 to +0.0024) | -0.0004 (-0.0016 to +0.0008) |
| 0.25 | LPL | 266 | -0.0019 (-0.0138 to +0.0097) | -0.0008 (-0.0030 to +0.0014) |
| 0.25 | international | 179 | +0.0024 (-0.0109 to +0.0157) | -0.0016 (-0.0039 to +0.0008) |
| 0.25 | other leagues | 907 | +0.0042 (-0.0016 to +0.0103) | -0.0017 (-0.0028 to -0.0006) |
| 0.25 | 2026 | 1871 | +0.0001 (-0.0044 to +0.0044) | -0.0011 (-0.0019 to -0.0003) |
| 0.50 | all | 1871 | -0.0006 (-0.0042 to +0.0028) | -0.0018 (-0.0035 to -0.0001) |
| 0.50 | major leagues | 785 | -0.0047 (-0.0101 to +0.0010) | -0.0001 (-0.0028 to +0.0025) |
| 0.50 | LPL | 266 | -0.0021 (-0.0115 to +0.0071) | -0.0011 (-0.0056 to +0.0035) |
| 0.50 | international | 179 | +0.0013 (-0.0092 to +0.0120) | -0.0026 (-0.0078 to +0.0023) |
| 0.50 | other leagues | 907 | +0.0026 (-0.0020 to +0.0075) | -0.0032 (-0.0056 to -0.0010) |
| 0.50 | 2026 | 1871 | -0.0006 (-0.0042 to +0.0028) | -0.0018 (-0.0035 to -0.0001) |
| 1.00 | all | 1871 | -0.0007 (-0.0042 to +0.0025) | -0.0020 (-0.0038 to -0.0000) |
| 1.00 | major leagues | 785 | -0.0045 (-0.0095 to +0.0009) | +0.0002 (-0.0029 to +0.0031) |
| 1.00 | LPL | 266 | -0.0022 (-0.0112 to +0.0066) | -0.0011 (-0.0061 to +0.0039) |
| 1.00 | international | 179 | +0.0009 (-0.0088 to +0.0109) | -0.0030 (-0.0087 to +0.0026) |
| 1.00 | other leagues | 907 | +0.0023 (-0.0021 to +0.0069) | -0.0036 (-0.0062 to -0.0011) |
| 1.00 | 2026 | 1871 | -0.0007 (-0.0042 to +0.0025) | -0.0020 (-0.0038 to -0.0000) |

### Second-half movement toward the draft shift

All eligible maps, independent of the unselected betting policy. Positive means price moves in the shift's direction. Close trades must be ≤30 seconds old; values are probability units. This is price movement rather than executable CLV. No selected bets exist for after-fee CLV.

| Slice | Map time | Maps with close | Movement (series-bootstrap 95%) |
|---|---|---:|---|
| all | +1 min | 1680 | -0.0004 (-0.0019 to +0.0012) |
| all | +3 min | 1445 | +0.0001 (-0.0030 to +0.0033) |
| all | +5 min | 1455 | -0.0015 (-0.0066 to +0.0034) |
| major leagues | +1 min | 757 | -0.0012 (-0.0031 to +0.0007) |
| major leagues | +3 min | 729 | +0.0002 (-0.0038 to +0.0043) |
| major leagues | +5 min | 741 | +0.0004 (-0.0060 to +0.0066) |
| LPL | +1 min | 247 | +0.0004 (-0.0026 to +0.0038) |
| LPL | +3 min | 232 | +0.0057 (-0.0015 to +0.0125) |
| LPL | +5 min | 237 | +0.0066 (-0.0046 to +0.0178) |
| international | +1 min | 172 | -0.0012 (-0.0046 to +0.0021) |
| international | +3 min | 165 | -0.0055 (-0.0130 to +0.0021) |
| international | +5 min | 165 | -0.0207 (-0.0347 to -0.0070) |
| other leagues | +1 min | 751 | +0.0007 (-0.0022 to +0.0036) |
| other leagues | +3 min | 551 | +0.0018 (-0.0042 to +0.0074) |
| other leagues | +5 min | 549 | +0.0016 (-0.0074 to +0.0108) |

## Book coverage and limits

Local pre_quotes.jsonl files found: 0. No saved pre-map books in the searched local data directories; remote backup storage was not inspected.

This tests trades as conservative fill proxies. It cannot verify asks, available depth, latency, partial fills, champion availability before the start, or prospective profitability. Market prices are not the book. The 12 development settings and descriptive slices create selection uncertainty; reported intervals condition on the selected first-half policy. No production changes, weights, site or CI jobs.

Offline run wall time: 0.0 s (timed before report bootstraps).
