# Draft tracks: combination protocol

Fixed on 2026-10-17 before reading any track's scored result. Base: `draft-v2` at `5811254`.

The four pre-map feature tracks are composition, form, meta and player features. Each track's **whole predeclared primary feature block** qualifies for combination only when its candidate minus v2 log-loss interval is strictly below zero both on all 2021–2026 test maps and on test maps before 2025, and no named league slice (majors, LPL, international, other leagues) is significantly worse. This is a joint test of a fixed block, not evidence that every individual column helps. Never choose a subset using scored coefficients or exploratory ablations. If no block qualifies, retain v2 and do not invent a v3 variant.

Join qualified blocks on OE game ID. Require unique game IDs, identical baseline columns/results/production calls, and complete training/test game coverage. Retain v2's four original columns and add all qualifying columns in one logistic model, using `draft_walkforward._fit` and its unchanged annual folds (2019 through Y−1 → Y, test years 2021–2026). No new constants, tuning or post-score removal of blocks. Compare against a separately refit v2 on precisely the same rows, using `draft_walkforward.paired` (2,000 series-bootstrap draws). Report all, majors, LPL, international, other leagues, every test year and before 2025. Report fitted weights and coverage. A favourable v3 needs the same all/before-2025 improvement and no significantly worse league slice; otherwise retain v2.

Market execution, series-score and live-prior tracks answer separate questions and do not enter this pre-map feature union. Summarize all seven verdicts independently. No published model/weight/site changes.

Both track selection and v3 are retrospective. Selecting blocks using these years means the v3 comparison is a follow-up on viewed data, including the pre-2025 slice; its ordinary intervals condition on that selection and are not independent confirmation or multiplicity adjusted. Future validation remains necessary for a fresh confirmatory claim. Do not push branches without the user's go-ahead, per the handoff.
