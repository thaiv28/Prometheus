# International model: interpretation and proposed experiments

2026-10-14. The calibration control and persistent/recency-weighted regional corrections are implemented in opt-in research ([first experiment](regional_correction_report.md)); the persistent variant is now implemented for production, with [runtime parity and validation](regional_calibration_validation.md) and [native benchmark guards](regional_calibration_benchmarks.md). Release goes through the ordinary reviewed PR and Publish workflow. Bayesian uncertainty integration and team residuals remain proposed. Diagnostic: [international_market_report.md](international_market_report.md). Reproduction script: [international_markets.py](../../scripts/research/international_markets.py).

## What step 1 established

Current Elo was rebuilt on main `36a1e6e`, including the fixed duration curve, from raw CSVs through 11 October. The saved price cohort stops on 30 September and covers four actual international events: MSI, First Stand, EWC and the academy WSCI. Three LPL regional finals labelled Worlds by OE, plus regional qualifiers, were excluded. Ambiguous fixture joins were rejected, not guessed. There are 104 series (95 cross-region) and 48 map-1 contracts; no actual Worlds matches.

On 95 cross-region series, Elo log loss is 0.5716 versus Kalshi's 0.5269, difference +0.0447 (paired series 95% −0.0389 to +0.1192). This sample does not establish an overall significant deficit under series resampling. Whole-event resampling gives a positive interval, but four events are too few to treat that as strong evidence of generalization.

The largest diagnostic signal is tournament entry: where either team has no previous game day in that event, cross-region Elo is 0.5737 versus 0.4204 over 33 series, difference +0.1533 (+0.0695 to +0.2490). On 62 later fixtures the difference is −0.0131 (−0.1268 to +0.0896). The same directional entry/later pattern appears in each of the four events, with very small event slices. This is an entry proxy, not an identified bracket round: actual group/Swiss/playoff labels are absent. Event coverage starts at the first matched fixture, and same-day earlier games do not count as known under production's day cutoff.

Timing matters too. On the identical 84 exactly timed fixtures, Elo without Form on the published forecast curve trails the close by +0.0336 but the market 12 hours out by only +0.0034. At entry on those common fixtures, Elo's deficit is +0.1592 at the close and +0.1121 at 12h; the latter interval spans zero. Our calls are rebuilt at each cutoff's day, so neither uses games from after that cutoff. They still omit same-day games and news the market may know. The data cannot attribute the market's late improvement to lineups specifically.

This is not obviously a series-conversion problem: map 1 is roughly tied on its smaller sample, and both series and map 1 are within uncertainty on the same 47 fixtures. Different market coverage prevents interpreting the pooled series/map difference as a conversion effect. Existing within-series correlation is already included.

At entry, Elo's favourite wins 66.7% against its mean chance of 72.8%; Kalshi picks the winner 78.8%. Thus calibration may help, but misplaced favourites matter too. A single temperature adjustment preserves Elo's ordering and cannot fix those calls.

Regional and team residuals offer leads, not identified causes. LCK challengers win 75% against Elo's average 60.1% (20 cross-region fixtures); Kalshi averages 78.5%. LPL representatives win 63.6% against 53.0% expected (22 fixtures), with Bilibili Gaming accounting for a large positive team residual. Those participants are selected, and repeated teams/series are dependent. Increasing all LPL ratings on this basis would be unjustified. Senior and academy events must stay separately reported.

## First experiment completed

`regional_correction.py` implements the calibration and regional-mean comparisons below. The fixed nine-setting grid was chosen through 2021, with event coefficients fitted only on completed earlier events. On 1,006 eligible 2022+ cross-region maps, the persistent correction improves log loss by −0.0175 (series-cluster 95% −0.0272 to −0.0075; event-cluster −0.0276 to −0.0065), including entry −0.0338 (−0.0569 to −0.0122). The recency-weighted correction is weaker (−0.0090, interval spans zero); calibration alone adds no significant gain. Annual/tier slices matter: persistent major-v-major −0.0099 has a series-cluster interval spanning zero; 2025 and 2026 gains are also within noise. On the primary 76 priced series 12h out, persistent LL is 0.5542 versus current Elo 0.5510 and Kalshi 0.5349; both paired intervals span zero. This is a historical forecast candidate, not a demonstrated market edge. The persistent variant now has a production implementation; Bayesian/team effects remain unimplemented.

## Single-offset replay completed

The architectural follow-up is now implemented in [learned_offsets.py](../../scripts/research/learned_offsets.py), with [results](learned_offsets_report.md) and [native forecast checks](learned_offsets_guards.md). A fixed-scale forecast-only correction improves 2022+ LL −0.0128, so the earlier gain is not just probability scaling. It can be folded into an effective offset exactly for a fixed rating snapshot. Replacing the offset learner inside a full replay is a different intervention: it changes player updates, transfers and rookie priors, and this experiment also changes historical fitting inputs from day-start to native pre-game ratings.

Straight replacement (ordinary regional increments disabled, absolute offset fits instead) loses the gain: fixed scale +0.0017 versus current Elo on 1,006 2022+ day-before maps; fitted scale +0.0046. The fitted-scale replay significantly worsens native within-other-league Elo and FORGE.

A defined one-state follow-up retains ordinary per-game offset updates and periodically fits absolute offsets, with ridge 4 centred on the current table, then overwrites that same table. There is no separate correction term in forecasts, and probability scaling stays fixed. It improves the broad day-before sample −0.0058 (series-cluster −0.0108 to −0.0007; event-cluster −0.0100 to −0.0007) and native cross-league Elo −0.003755 (−0.005280 to −0.002201), but significantly worsens native within-other-league Elo +0.000387 (+0.000059 to +0.000710). Major-region international gains remain within noise. On the primary 76 series 12h out: 0.5442 versus current Elo 0.5510 and Kalshi 0.5349, both paired differences within uncertainty. **Not adopted:** the regression fails the project's safeguard and no Kalshi edge is demonstrated. This follow-up was specified after viewing the replacement results, so it is exploratory, not an untouched confirmation.

Descriptive roster slices localize most excess loss to recent home-league changes: +0.000700 over 19,751 games, versus −0.000182 over 9,521 games with neither a recent move nor a rookie. This includes promotions/home relabelling and is not causal attribution. The selected production path keeps the two layers with distinct purposes: existing Elo offsets update rating strength, while event-frozen regional calibration corrects residual forecast error. A future single-state experiment could trace how these moves carry regional evidence into player strength. Keep scale calibration separate. No new grid has been run; Bayesian uncertainty and team effects remain unimplemented.

## The model to test

Start with a small dynamic correction to published Elo, rather than replacing its roster machinery immediately:

`logit P(A wins a map) = existing Elo logit + δ_region(A,t) − δ_region(B,t)`

The δ terms are corrections to the region offsets already included in Elo, not a second copy of regional strength. A subsequent variant adds a strongly shrunk team residual `η_A,t − η_B,t`. Ratings and residual states are captured before the game, and all updates occur only after its result becomes available.

The first version asks whether regional error persists across events enough to be forecastable. International results teach the corrections; domestic matches within a region cannot identify its absolute strength, because the regional term cancels. Domestic play continues to update the existing player/roster rating. Regions without cross-region evidence keep a neutral correction with broad uncertainty, not an invented advantage.

Each regional state has a mean, variance and covariance with other regions. Between international meetings its uncertainty grows with elapsed time. An unexpected result moves uncertain states more than well-established states. Keep a reference region fixed, or constrain corrections to sum to zero, so arbitrary global shifts do not masquerade as strength. Track covariance: the uncertainty of an LCK–LPL difference cannot generally be calculated by treating their inferred strengths as independent.

For intuition, an unexpected win by a roster with an established domestic rating but an uncertain regional calibration should update the regional correction more. A win by one unusual or recently changed roster should be allowed to update the team residual instead. This is statistical allocation, not something the result itself uniquely identifies. Shrinkage and comparisons with region-only and team-only variants are essential.

A team residual would decay toward zero and lose persistence after roster changes. It is deliberately delayed until regional correction has been tested: otherwise two components can explain the same few international results, producing attractive but unstable fits. Academy regions remain separate rating pools; LCKC must not inherit a fitted LCK correction automatically.

**Limits:** uncertainty alone does not reveal whether a region improved or declined during isolation. A zero-mean random walk changes confidence, not the expected direction of its strength. Nor can an online model learn a new event from that event's results before the first game. Any improvement at entry must come from better use of earlier cross-region evidence, roster history or additional genuinely pre-match information. Late market information may remain unavailable to us.

## Controlled experiment order

1. Current published Elo, reproduced exactly, plus a simple earlier-fitted cross-region probability scale as a calibration control.
2. Dynamic regional correction, no team residual. Compare persistent correction against time-varying correction on the same fixtures. Test posterior means first to isolate changes in expected strength.
3. Posterior predictive probabilities integrating regional uncertainty. Compare with the same corrected means without integration; this distinguishes better strength estimates from better confidence.
4. Team-only and region-plus-team residuals, heavily shrunk, if the earlier variants show usable signal. Compare each with region-only, especially on first appearances and when representatives change.

Use map win/loss as the initial likelihood. Keep published player updates and their duration evidence fixed, so this is not simultaneously another margin-of-victory experiment. Fit inference settings on older events only. No Kalshi input: it remains the external comparison. A market-plus-model forecast would be a separately named experiment.

Series conversion needs special care. The current beta-binomial rho already models shared series variation. Persistent regional uncertainty must be drawn once for the series, not independently for each map. The uncertainty-integrated variant should average the series-win probability over regional-state draws; residual within-series variation must be fitted on earlier data so it does not count the same uncertainty twice. Report map 1 alongside series results. The initial posterior-mean variant keeps the published conversion fixed for a clean control.

## Evaluation and stopping rules

Use all historical international games to develop the correction, not just the 104 priced series. Expanding-event evaluation must fit hyperparameters and win/series calibration using earlier completed events only. Save forecasts at each tournament's entry, then report sequential later forecasts separately: an event held out for parameter fitting can still permit online learning from its already completed games, provided that distinction is explicit. Predicting an entire event from its opening state is another task and should not be mixed with that sequential score.

Compare candidates with current Elo by paired log loss on identical maps/series, with event-cluster sensitivity and the existing domestic, international, cross-league and other-league guards. The primary market endpoint should be frozen at 12h, with close as a separate, tougher endpoint. Fix the cohort rules and entry slice before running candidates. Report senior and academy events separately. Do not select a winner from many small region-pair slices.

The currently viewed 2026 events are development evidence, not a fresh holdout. A candidate that improves historical international forecasts still needs a frozen prospective record against timestamped Kalshi prices to claim it beats the market. No production adoption unless it clears the repo's benchmark rule. Record replay/build time before adding any production work; this research remains opt-in with no added CI job.
