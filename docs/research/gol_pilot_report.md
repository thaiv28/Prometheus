# gol.gg historical objective pilot

Small purposively selected sample across 2022–2025, not a representative coverage estimate. Public HTML only; no documented API used, no OCR, browser automation or model training. Raw source HTML and hashes are cached in gitignored data/gol_pilot/.

## Finding

7/8 sampled games have validated timelines; 7 match OE. 42 tower/dragon/Baron total checks and 42 gold cross-checks were recorded. Maximum absolute gold difference from OE: 0. Exported 21 matched checkpoint candidates. This is a feasibility result, not representative coverage or a model benchmark.

## Method

Parse timeline HTML using event columns and icon filenames: action, taking side, game-clock seconds, player and target. Read team identities from blue/red headers rather than title ordering. Plates and inhibitors are separate from towers; Elder is separate from elemental dragons, but included when validating the displayed final dragon total. Unknown actions, malformed/empty timelines, duplicate IDs, unordered or post-end events are rejected. Reconstructed tower/dragon/Baron totals must match both side summaries before checkpoint export. End-game totals are validation targets, never predictor inputs.

Match OE conservatively by blue/red team names, nearby calendar date, duration within one second, winner and all five starter names on each side. Ambiguous or missing matches are retained as unmatched; no fuzzy guesses. Map number is recorded but OE lacks a directly comparable map number, so duration/rosters distinguish games. Gold graph role arrays are parsed as inert numeric data with checked role order and side colors. Export only unique 10/15/20-minute labels; skip duplicate final-minute labels rather than infer their timestamp. Compare graph gold with OE snapshots where present. Objective checkpoints use events strictly before the minute and exclude ended games. Events exactly at a checkpoint have only second precision, so affected rows are flagged and excluded from the training-ready set. Training-ready rows also require an unambiguous OE match and both sides’ gold agreeing exactly with OE.

## Game inventory

| gol_id | sample | date | blue_team | red_team | status | timeline_valid | unknown_events | match_status | gold_status | oe_gameid | error |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 37756 | LCK 2022 | 2022-02-23 | T1 | DWG KIA | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | ESPORTSTMNT03_2568861 |  |
| 35845 | LCK 2022; Elder | 2022-01-16 | Gen.G eSports | DWG KIA | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | ESPORTSTMNT01_2702340 |  |
| 46778 | LEC 2023 | 2023-02-26 | G2 Esports | MAD Lions | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | ESPORTSTMNT04_2668245 |  |
| 53542 | Worlds 2023; Elder | 2023-10-19 | G2 Esports | Dplus KIA | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | ESPORTSTMNT03_3216935 |  |
| 62081 | LCK 2024 | 2024-08-17 | FearX | T1 | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | LOLTMNT02_157857 |  |
| 53778 | LPL 2024 | 2024-01-22 | Bilibili Gaming | Top Esports | unavailable |  |  |  | missing_gold_graph |  | No event timeline; never interpret missing data as zero |
| 69531 | LTA North 2025 | 2025-07-27 | Team Liquid | 100 Thieves | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | LOLTMNT01_270271 |  |
| 64875 | First Stand 2025 | 2025-03-11 | Top Esports | Team Liquid | valid | True | 0.0 | matched_date_duration_sides_result_rosters | ok | LOLTMNT01_214082 |  |

## Final-total validation

| gol_id | side | objective | observed | expected | matches |
| --- | --- | --- | --- | --- | --- |
| 37756 | blue | tower | 9 | 9 | True |
| 37756 | blue | dragon | 2 | 2 | True |
| 37756 | blue | baron | 2 | 2 | True |
| 37756 | red | tower | 2 | 2 | True |
| 37756 | red | dragon | 1 | 1 | True |
| 37756 | red | baron | 0 | 0 | True |
| 35845 | blue | tower | 10 | 10 | True |
| 35845 | blue | dragon | 2 | 2 | True |
| 35845 | blue | baron | 2 | 2 | True |
| 35845 | red | tower | 5 | 5 | True |
| 35845 | red | dragon | 5 | 5 | True |
| 35845 | red | baron | 1 | 1 | True |
| 46778 | blue | tower | 8 | 8 | True |
| 46778 | blue | dragon | 4 | 4 | True |
| 46778 | blue | baron | 1 | 1 | True |
| 46778 | red | tower | 2 | 2 | True |
| 46778 | red | dragon | 0 | 0 | True |
| 46778 | red | baron | 0 | 0 | True |
| 53542 | blue | tower | 10 | 10 | True |
| 53542 | blue | dragon | 5 | 5 | True |
| 53542 | blue | baron | 1 | 1 | True |
| 53542 | red | tower | 4 | 4 | True |
| 53542 | red | dragon | 1 | 1 | True |
| 53542 | red | baron | 2 | 2 | True |
| 62081 | blue | tower | 4 | 4 | True |
| 62081 | blue | dragon | 0 | 0 | True |
| 62081 | blue | baron | 0 | 0 | True |
| 62081 | red | tower | 10 | 10 | True |
| 62081 | red | dragon | 3 | 3 | True |
| 62081 | red | baron | 2 | 2 | True |
| 69531 | blue | tower | 9 | 9 | True |
| 69531 | blue | dragon | 2 | 2 | True |
| 69531 | blue | baron | 1 | 1 | True |
| 69531 | red | tower | 2 | 2 | True |
| 69531 | red | dragon | 3 | 3 | True |
| 69531 | red | baron | 0 | 0 | True |
| 64875 | blue | tower | 8 | 8 | True |
| 64875 | blue | dragon | 2 | 2 | True |
| 64875 | blue | baron | 1 | 1 | True |
| 64875 | red | tower | 1 | 1 | True |
| 64875 | red | dragon | 1 | 1 | True |
| 64875 | red | baron | 0 | 0 | True |

## Gold cross-check against OE

| gol_id | oe_gameid | minute | side | gol_gold | oe_gold | difference |
| --- | --- | --- | --- | --- | --- | --- |
| 37756 | ESPORTSTMNT03_2568861 | 10 | blue | 18491.0 | 18491.0 | 0.0 |
| 37756 | ESPORTSTMNT03_2568861 | 10 | red | 17385.0 | 17385.0 | 0.0 |
| 37756 | ESPORTSTMNT03_2568861 | 15 | blue | 26702.0 | 26702.0 | 0.0 |
| 37756 | ESPORTSTMNT03_2568861 | 15 | red | 25820.0 | 25820.0 | 0.0 |
| 37756 | ESPORTSTMNT03_2568861 | 20 | blue | 35295.0 | 35295.0 | 0.0 |
| 37756 | ESPORTSTMNT03_2568861 | 20 | red | 33239.0 | 33239.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 10 | blue | 14942.0 | 14942.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 10 | red | 15808.0 | 15808.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 15 | blue | 23721.0 | 23721.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 15 | red | 24848.0 | 24848.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 20 | blue | 34449.0 | 34449.0 | 0.0 |
| 35845 | ESPORTSTMNT01_2702340 | 20 | red | 34651.0 | 34651.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 10 | blue | 16003.0 | 16003.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 10 | red | 15456.0 | 15456.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 15 | blue | 25683.0 | 25683.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 15 | red | 23174.0 | 23174.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 20 | blue | 37980.0 | 37980.0 | 0.0 |
| 46778 | ESPORTSTMNT04_2668245 | 20 | red | 31992.0 | 31992.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 10 | blue | 16620.0 | 16620.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 10 | red | 15096.0 | 15096.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 15 | blue | 26587.0 | 26587.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 15 | red | 24212.0 | 24212.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 20 | blue | 37531.0 | 37531.0 | 0.0 |
| 53542 | ESPORTSTMNT03_3216935 | 20 | red | 32717.0 | 32717.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 10 | blue | 14956.0 | 14956.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 10 | red | 16641.0 | 16641.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 15 | blue | 26157.0 | 26157.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 15 | red | 26274.0 | 26274.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 20 | blue | 34375.0 | 34375.0 | 0.0 |
| 62081 | LOLTMNT02_157857 | 20 | red | 38364.0 | 38364.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 10 | blue | 15548.0 | 15548.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 10 | red | 15783.0 | 15783.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 15 | blue | 23757.0 | 23757.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 15 | red | 23782.0 | 23782.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 20 | blue | 32202.0 | 32202.0 | 0.0 |
| 69531 | LOLTMNT01_270271 | 20 | red | 34492.0 | 34492.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 10 | blue | 16384.0 | 16384.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 10 | red | 15611.0 | 15611.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 15 | blue | 24894.0 | 24894.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 15 | red | 23384.0 | 23384.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 20 | blue | 36836.0 | 36836.0 | 0.0 |
| 64875 | LOLTMNT01_214082 | 20 | red | 32245.0 | 32245.0 | 0.0 |

## Limits and next decision

A passed totals check supports parser consistency but does not independently prove every event timestamp. Audit a sample against the rendered timeline and assess representative league/year coverage before bulk acquisition. Missing histories and unsupported icons remain explicit failures. Dragon soul, buff expiration and patch-specific objective rules are not inferred yet. Keep OE gold for training until graph timestamps agree; this pilot creates candidate objective features only, with no forecast adoption. Historical features added now need development testing before another evaluation; the 2026 data has already been viewed.

## Reproduction

`.venv/bin/python scripts/research/pilot_gol.py` reprocesses the cached default sample offline. Add `--fetch` to obtain uncached pages; requests are sequential, at least one second apart, follow robots.txt and stop on authentication/rate-limit responses. `--samples PATH` accepts a JSON array of gol_id/sample objects, bounded to 12 games. Outputs games/events/validation/checkpoints/gold_comparison/training_candidates CSVs plus manifest. No DB or published metric changes.

New HTTP requests in this run: 0.
