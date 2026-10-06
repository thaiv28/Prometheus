# Historical objective feature experiment

The primary 15-minute paired interval supports improved log loss on this retrospective cohort. Primary added-minus-control log loss: -0.03418, 95% paired interval [-0.05850, -0.00897]. Lower is better. 10/20-minute comparisons are secondary, not separate adoption tests.

## Fixed method

1031 verified games, LPL excluded. Train calendar 2022–2023, calibrate 2024, evaluate 2025; exact same games for both variants at each minute. C=1 logistic regression, training-only scaling; C=1e6 sigmoid calibration on the separate calibration year. Explicit series IDs stay in one partition; paired 2,000-draw bootstrap resamples league/series clusters, seed 42. Primary comparison uses calibrated probabilities; raw results are reported without selecting between them after scoring.

Predictors: gold and pre-match Elo gaps; added past objective gaps for towers, elemental dragons, Elder, Baron, Herald, grubs and Atakhan. Features constant in training are omitted and recorded in fitted_models.json. In particular, newer objectives absent in 2022–2023 have no learned effects; this experiment cannot assess their separate usefulness. Final totals validate source parsing and never enter the model. Winner/identity/date fields are labels/metadata only.

## Scores

| minute | variant | train_games | calibration_games | test_games | log_loss | raw_log_loss | brier | accuracy | ece10 | delta | low | high |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 10 | gold_elo | 487 | 241 | 295 | 0.5358 | 0.5336 | 0.1818 | 0.7153 | 0.0592 | nan | nan | nan |
| 10 | gold_elo_objectives | 487 | 241 | 295 | 0.5242 | 0.5223 | 0.1767 | 0.7322 | 0.0481 | -0.0116 | -0.0340 | 0.0100 |
| 15 | gold_elo | 485 | 244 | 292 | 0.5418 | 0.5347 | 0.1858 | 0.7123 | 0.0781 | nan | nan | nan |
| 15 | gold_elo_objectives | 485 | 244 | 292 | 0.5076 | 0.5040 | 0.1730 | 0.7295 | 0.0844 | -0.0342 | -0.0585 | -0.0090 |
| 20 | gold_elo | 486 | 244 | 293 | 0.4779 | 0.4748 | 0.1605 | 0.7543 | 0.0490 | nan | nan | nan |
| 20 | gold_elo_objectives | 486 | 244 | 293 | 0.4353 | 0.4345 | 0.1450 | 0.7816 | 0.0359 | -0.0426 | -0.0658 | -0.0209 |

## Learning curves and collection estimates

Learning curves use RAW 2024 predictions from increasing chronological 2022–2023 prefixes, with no calibration fit on the curve's evaluation data. No C, feature, cutoff or model selection is made from 2025 scores. `learning_curves.csv` records the development curves.

| minute | hypothetical_log_loss_gain | estimated_test_games_80pct_power | observed_test_games | observed_series |
| --- | --- | --- | --- | --- |
| 10 | 0.0050 | 11237 | 295 | 148 |
| 10 | 0.0100 | 2810 | 295 | 148 |
| 10 | 0.0200 | 703 | 295 | 148 |
| 15 | 0.0050 | 13519 | 292 | 148 |
| 15 | 0.0100 | 3380 | 292 | 148 |
| 15 | 0.0200 | 845 | 292 | 148 |
| 20 | 0.0050 | 12214 | 293 | 148 |
| 20 | 0.0100 | 3054 | 293 | 148 |
| 20 | 0.0200 | 764 | 293 | 148 |

Power figures are provisional normal-approximation estimates for hypothetical gains, using observed paired series-cluster variance, 80% power / two-sided 5% significance. They concern EVALUATION games in addition to training/calibration data, assume similar future clustering/variance and fixed fitted models, and are not guaranteed minimums. Use them to refine acquisition, not claim accuracy or a market edge.

## Limits and reproduction

Selected spring/Worlds events, uneven league/era coverage, exclusions and small per-league evaluation slices limit generalization. 2025/2026 outcomes were viewed in earlier research; this is a retrospective feature ablation, not an untouched prospective confirmation. Source totals and gold agree where admitted; every objective timestamp has not been independently verified against broadcasts. No forecast adoption, market execution or DB/site changes.

Run `.venv/bin/python scripts/evaluate_gol_objectives.py` after at least 1,000 verified games. Dataset/sample/collection hashes and fixed feature/split settings are saved in manifest.json; metrics, predictions, development curves, power estimates and fitted numeric parameters under gitignored data/gol_objectives/. No automatic reruns on each collection batch; freeze the first experiment before further changes.
