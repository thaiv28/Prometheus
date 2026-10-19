# Glicko-2 player volatility (2026-10-19)

Research only; published defaults unchanged. Negative Δ log loss is better.

## Design and fixed protocol

Each player starts at σ0 on the Glicko-2 scale (173.7178 points). Before a game, RD² adds (173.7178σ)² × elapsed whole days / period_days, capped at 280². Published RD floor 140, information .125 and move scaling RD²/140² remain unchanged, as do K 20, rookie discounts, league offsets and non-major update slope .0065. Same-day games add no growth. After growth and before shrink, use φ = RD/173.7178 in the volatility solve; the updated σ affects later games only.

For the game's team expectation E and native game-length soft score s, let b = update_slope × 173.7178, v = 1/[b²E(1−E)], Δ = vb(s−E). Every starter uses this team evidence with their own φ and σ; the opposing side has the same v and Δ². No opponent g(RD) or player-specific E. The [Glickman Illinois step](https://www.glicko.net/glicko/glicko2.pdf) solves for σ with tolerance 1e−6 (the current source PDF is dated 2022; the requested 2013 step is retained). This is volatility added to Elo/RD, not the full Glicko-2 rating update.

Initial grid: τ {.3,.6,1.2} × σ0 {.03,.06,.10} × period_days {7,30} (18 settings). Tune 2014–2021 on the chronological prefix through its final tuning game, including intervening differently labelled seasons; objective: games-weighted domestic + within-other-league Elo log loss. One edge extension uses the initial winner plus its outward neighbor on each boundary axis: τ .15/2.4, σ0 .015/.16, days 3.5/60, all new local Cartesian cells. No second extension. Initial winner (0.3, 0.1, 7); extension 7 cells; selected `{'player_volatility': (0.15, 0.16, 7)}` (objective 0.61998575). Remaining boundary coordinates: tau, sigma0, period_days.

Selection is frozen in `data/research/elo_glicko2/selection.json` before 2022–2026 held-out scoring. Exact prefix/full and native/replay parity passed. Scoring reuses elo_glicko.py: leave-one-year-out curves within each partition, variant-specific Form opponent adjustments and refitted FORGE blends. Within-other-league Form fits use all other major-league years, including tuning years. This evaluates the rating design, not an earlier-only deployment simulation; inherited international calibration remains. Historical holdouts have been viewed in previous research. Intervals are paired individual-game bootstrap 95% CIs; no series clustering or multiplicity correction.

## Tuning

| Stage | (τ, σ0, days) | Objective | Seconds (replay + scoring) |
|---|---|---:|---:|
| Initial | (0.3, 0.03, 7) | 0.62097470 | 4.46 |
| Initial | (0.3, 0.03, 30) | 0.62101296 | 4.31 |
| Initial | (0.3, 0.06, 7) | 0.62080014 | 4.08 |
| Initial | (0.3, 0.06, 30) | 0.62097826 | 3.92 |
| Initial | (0.3, 0.1, 7) | 0.62037344 | 3.59 |
| Initial | (0.3, 0.1, 30) | 0.62088917 | 3.66 |
| Initial | (0.6, 0.03, 7) | 0.62097477 | 4.12 |
| Initial | (0.6, 0.03, 30) | 0.62101297 | 4.75 |
| Initial | (0.6, 0.06, 7) | 0.62080182 | 4.34 |
| Initial | (0.6, 0.06, 30) | 0.62097850 | 4.15 |
| Initial | (0.6, 0.1, 7) | 0.62038441 | 4.08 |
| Initial | (0.6, 0.1, 30) | 0.62089166 | 4.29 |
| Initial | (1.2, 0.03, 7) | 0.62097503 | 4.19 |
| Initial | (1.2, 0.03, 30) | 0.62101302 | 3.89 |
| Initial | (1.2, 0.06, 7) | 0.62080802 | 3.89 |
| Initial | (1.2, 0.06, 30) | 0.62097940 | 3.97 |
| Initial | (1.2, 0.1, 7) | 0.62042226 | 4.01 |
| Initial | (1.2, 0.1, 30) | 0.62089964 | 4.21 |
| Extension | (0.3, 0.1, 3.5) | 0.62003654 | 3.81 |
| Extension | (0.3, 0.16, 7) | 0.61998614 | 3.99 |
| Extension | (0.3, 0.16, 3.5) | 0.62036482 | 3.96 |
| Extension | (0.15, 0.1, 7) | 0.62037062 | 4.14 |
| Extension | (0.15, 0.1, 3.5) | 0.62003431 | 4.44 |
| Extension | (0.15, 0.16, 7) | 0.61998575 | 4.22 |
| Extension | (0.15, 0.16, 3.5) | 0.62038518 | 4.16 |

## Held-out vs published

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 7,728 | 0.62157 | -0.00002 (-0.00010 to +0.00006) |
| Elo, international | 589 | 0.61877 | +0.00008 (-0.00012 to +0.00030) |
| FORGE, domestic | 7,728 | 0.62010 | +0.00003 (-0.00002 to +0.00009) |
| FORGE, international | 589 | 0.61154 | -0.00002 (-0.00015 to +0.00010) |
| Elo, other leagues | 37,272 | 0.60081 | -0.00009 (-0.00013 to -0.00004) |
| FORGE, other leagues | 37,272 | 0.59979 | -0.00001 (-0.00005 to +0.00003) |
| Elo, cross-league | 5,442 | 0.57070 | +0.00008 (-0.00003 to +0.00020) |

## Roster-change slices

Either team changed its known five starters since its previous game. Unknown/incomplete rosters and first appearances do not establish change. Full-section fits are sliced after scoring; slices are reported separately from the seven-section gate.

| Section | Games | Published loss | Δ log loss (95% CI) |
|---|---:|---:|---|
| Elo, domestic | 703 | 0.59448 | -0.00007 (-0.00036 to +0.00025) |
| Elo, international | 9 | 0.78976 | +0.00001 (-0.00326 to +0.00340) |
| FORGE, domestic | 703 | 0.58950 | +0.00000 (-0.00019 to +0.00021) |
| FORGE, international | 9 | 0.78809 | +0.00054 (-0.00185 to +0.00334) |
| Elo, other leagues | 6,814 | 0.58324 | -0.00000 (-0.00011 to +0.00010) |
| FORGE, other leagues | 6,814 | 0.58221 | +0.00002 (-0.00007 to +0.00011) |
| Elo, cross-league | 682 | 0.53321 | +0.00020 (-0.00016 to +0.00058) |

## Season-end volatility by league tier

Posterior σ at each player's last observed game in each held-out calendar year, assigned to that game's home-league tier (major vs other). One player-season per row; inactive players are not carried forward and synthetic team fallback players are excluded. 2026 is partial. Quantiles describe states at last observation, without an extra offseason update. Raw snapshots are saved in the audit CSV.

| Season | Tier | Players | σ p05 | σ p25 | σ median | σ p75 | σ p95 |
|---|---|---:|---:|---:|---:|---:|---:|
| 2022 | Major | 315 | 0.15774 | 0.15854 | 0.15898 | 0.15939 | 0.15975 |
| 2022 | Other | 3,982 | 0.15898 | 0.15960 | 0.15988 | 0.15997 | 0.15999 |
| 2023 | Major | 301 | 0.15752 | 0.15834 | 0.15883 | 0.15924 | 0.15963 |
| 2023 | Other | 3,118 | 0.15880 | 0.15943 | 0.15980 | 0.15995 | 0.15999 |
| 2024 | Major | 301 | 0.15728 | 0.15826 | 0.15877 | 0.15918 | 0.15963 |
| 2024 | Other | 2,953 | 0.15862 | 0.15939 | 0.15982 | 0.15996 | 0.15999 |
| 2025 | Major | 288 | 0.15689 | 0.15802 | 0.15862 | 0.15902 | 0.15987 |
| 2025 | Other | 2,534 | 0.15844 | 0.15930 | 0.15978 | 0.15995 | 0.15999 |
| 2026 | Major | 241 | 0.15650 | 0.15768 | 0.15830 | 0.15863 | 0.15958 |
| 2026 | Other | 2,571 | 0.15839 | 0.15934 | 0.15983 | 0.15997 | 0.15999 |

## Runtime

Paired full-replay timing check (three runs each, order AB/BA/AB): published median 4.72 s (4.68–5.20); selected volatility median 6.90 s (6.18–6.96). Use this paired check for overhead; the initial replay and later selected replays can face different concurrent machine load.

Additional diagnostic replay with player histories: 9.94 s. Diagnostics are collected only when player_records=True; no added CI job or benchmark grid in CI.

## Verdict

Held-out gate: **PASS**. Requires a significant gain in at least one of the seven Elo/FORGE target sections and none significantly worse. Roster slices are reported, not extra gate sections. Final adoption also requires no native guarded value significantly worse; see [native comparison](elo_glicko2_native.md). Keep the published default pending that combined verdict; no parameter or weight file is changed by this research. Remaining boundary optima are unresolved.

