# gol.gg historical coverage audit

60 sampled series entries across 20 fixed tournament strata (2022–2025). 48 validated timelines, 47 OE matches, 139 training-ready 10/15/20-minute rows. 288 final objective-total checks; 282 OE gold comparisons; 282 exact gold agreements.

## League summary

| league | sampled | valid_timelines | oe_matched | gold_graphs |
| --- | --- | --- | --- | --- |
| LCK | 12 | 12 | 12 | 12 |
| LPL | 12 | 0 | 0 | 0 |
| LEC | 12 | 12 | 11 | 12 |
| LCS | 12 | 12 | 12 | 12 |
| Worlds | 12 | 12 | 12 | 12 |

LPL missing histories remain a separate acquisition gap. For any usable timeline without an OE match, inspect team/player aliases and roster identity before relaxing the join. Verified rows can still be excluded at exact objective boundaries; the table below makes those exclusions explicit.

## Sample and denominators

One explicitly named event per league/year: domestic spring (LCK rounds 1–2, LPL split 2 and LTA North split 2 in 2025) and Worlds main event. Public match-list pages enumerate series, not all maps. Select three series entries per event by SHA-256 ranking with seed 42, then inspect the linked first map; a single-game entry is its sole map. This selection is fixed before fetching timelines, independent of wins or data availability. Failed listings and sampled games remain in the inventory; no replacements. Rates describe sampled first maps in these events, not all maps, splits, leagues, or years. Three per event is a screening sample with substantial uncertainty; no population-wide percentage is claimed.

`listed_series` counts unique dated entries on each selected tournament listing. `sampled` includes unavailable/rejected games. `known_eligible` in coverage.csv counts sampled games with readable duration strictly beyond the checkpoint; unreadable duration remains unknown, not eligible or ineligible. `ready` requires valid objective totals, an unambiguous OE match, exact gold agreement for both sides, and no second-precision objective boundary event. End-game counts are validation targets only. The original purposive pilot is excluded from this audit's sampling denominator.

## Tournament coverage

| league | year | listing_status | listed_series | sampled | valid_timelines | oe_matched | gold_graphs | ready_10m | ready_15m | ready_20m |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LCK | 2022 | ok | 90 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LPL | 2022 | ok | 136 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| LEC | 2022 | ok | 90 | 3 | 3 | 2 | 3 | 2 | 2 | 2 |
| LCS | 2022 | ok | 92 | 3 | 3 | 3 | 3 | 3 | 2 | 3 |
| Worlds | 2022 | ok | 58 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LCK | 2023 | ok | 90 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LPL | 2023 | ok | 136 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| LEC | 2023 | ok | 46 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LCS | 2023 | ok | 93 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| Worlds | 2023 | ok | 40 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LCK | 2024 | ok | 90 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LPL | 2024 | ok | 136 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| LEC | 2024 | ok | 46 | 3 | 3 | 3 | 3 | 2 | 3 | 3 |
| LCS | 2024 | ok | 57 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| Worlds | 2024 | ok | 40 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LCK | 2025 | ok | 91 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LPL | 2025 | ok | 105 | 3 | 0 | 0 | 0 | 0 | 0 | 0 |
| LEC | 2025 | ok | 46 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| LCS | 2025 | ok | 44 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |
| Worlds | 2025 | ok | 40 | 3 | 3 | 3 | 3 | 3 | 3 | 3 |

## Failures and unmatched games

| league | year | gol_id | status | match_status | error |
| --- | --- | --- | --- | --- | --- |
| LPL | 2022 | 37434 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2022 | 38399 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2022 | 37735 | unavailable |  | No event timeline; never interpret missing data as zero |
| LEC | 2022 | 36405 | valid | unmatched |  |
| LPL | 2023 | 46427 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2023 | 46819 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2023 | 47162 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2024 | 55945 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2024 | 54596 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2024 | 55128 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2025 | 66538 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2025 | 66550 | unavailable |  | No event timeline; never interpret missing data as zero |
| LPL | 2025 | 66066 | unavailable |  | No event timeline; never interpret missing data as zero |

## Checkpoint exclusions

| gol_id | minute | matched | gold_verified | objective_boundary_events |
| --- | --- | --- | --- | --- |
| 36405 | 10 | False | False | 0 |
| 36405 | 15 | False | False | 0 |
| 36405 | 20 | False | False | 0 |
| 37035 | 15 | True | True | 1 |
| 56161 | 10 | True | True | 1 |

All sampled game identities, validation results and source hashes are available under gitignored data/gol_coverage/. Detail report: data/gol_coverage/detail_report.md. A valid timeline with a missing graph or failed gold check can still have zero training-ready rows. Missing timelines are never interpreted as zero objectives. Soul and remaining buff duration are not reconstructed. Totals validate parser consistency, not independently every timestamp.

## Reproduction and next decision

Run `.venv/bin/python scripts/audit_gol_coverage.py` to reprocess cached listings/pages without network. Add `--fetch` to fetch only missing public pages (20 listings, at most 60 games / 120 game pages, plus robots.txt; serial requests at least one second apart). Stop on 401/403/429; no retries or bypass. Preserve manifest/sample JSON, raw HTML and hashes. No DB writes or model fitting.

Next expand reliable event strata to additional splits and all map numbers, and investigate explicit parser/matching failures before collecting a training corpus. Do not drop poorly covered regions silently. Use chronological same-game gold+Elo versus gold+Elo+objectives comparisons only after acquisition passes a separate dataset-quality gate. 2026 has already been viewed and is excluded here.

HTTP requests this run: 0. Selection seed: 42.
