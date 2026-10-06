# gol.gg training-data collection

Status: selected_events_download_complete. New HTTP requests this batch: 178. 1778 downloaded maps, 1451 verified games, 4308 training rows at 10/15/20 minutes. Discovery/download errors recorded: 0. LPL excluded as requested. 2026 excluded. This is a partial acquisition dataset, not a fitted model or a complete season corpus.

## Download inventory

| league | year | status | games |
| --- | --- | --- | --- |
| LCK | 2022 | valid | 212 |
| LCK | 2023 | rejected_timeline | 2 |
| LCK | 2023 | valid | 216 |
| LCK | 2024 | valid | 210 |
| LCK | 2025 | unavailable | 4 |
| LCK | 2025 | valid | 218 |
| LCS | 2022 | rejected_timeline | 2 |
| LCS | 2022 | valid | 90 |
| LCS | 2023 | valid | 93 |
| LCS | 2024 | valid | 57 |
| LCS | 2025 | unavailable | 1 |
| LCS | 2025 | valid | 64 |
| LEC | 2022 | rejected_timeline | 9 |
| LEC | 2022 | valid | 81 |
| LEC | 2023 | valid | 46 |
| LEC | 2024 | valid | 46 |
| LEC | 2025 | unavailable | 1 |
| LEC | 2025 | valid | 105 |
| Worlds | 2022 | valid | 80 |
| Worlds | 2023 | valid | 79 |
| Worlds | 2024 | valid | 82 |
| Worlds | 2025 | unavailable | 1 |
| Worlds | 2025 | valid | 79 |

## Dataset and validation

`data/gol_training/training_dataset.csv` contains verified gold snapshots, stored pre-match Elo, strictly past objective counts/gaps and winner labels, with OE/gol.gg IDs, dates, league and map/series provenance in the accompanying games/samples files. Checkpoints must match OE gold exactly and have no objective at the exact second boundary. Final counts validate extraction and are absent from predictor columns. Explicit series links discover every map; IDs are never guessed. Map numbers are checked against those links. Missing data, unknown icons, unmatched rosters and failed totals remain outside the training dataset. Team/player identities and winner/date/league columns are metadata or labels, not proposed numeric predictors.

All raw pages and hashes are retained. Games/events/validation/gold_comparison/checkpoints/training_candidates CSVs and detail_report.md preserve exclusions. Per-event discovery errors and the precise stop reason live in progress.json. Stored Elo was verified against chronological replay in the earlier experiment; source DB hash is recorded. No DB writes, model fitting, or forecast changes.

## Resume

`.venv/bin/python scripts/collect_gol_training.py --fetch --max-requests 300 --delay 2` resumes from cached pages. Default is offline. Public requests are serial, at least two seconds apart, with a per-run request budget. Stop on 401/403/429 or a transport/DNS error and preserve progress; honor Retry-After before a later invocation, no automatic retries, concurrency, alternate identity or bypass. Order interleaves the 16 audited non-LPL event strata, so a partial run reaches multiple leagues/years. Additional splits/playoffs/MSI are future acquisition work. The default corpus covers the audit's selected spring/Worlds events and later maps, not every 2022–2025 event.

Before fitting objective models, spot-check timeline timestamps and inspect coverage/exclusions. Use chronological splits and identical game cohorts for gold+Elo versus gold+Elo+objectives; this collection does not establish predictive improvement.
