# Prometheus: research directions beyond the current production forecast

Prepared October 17, 2026. Research only.

**Recommendation:** first test adaptive persistence after unexpected performance changes; next test team-specific exposure to newly announced patches. Develop transfer-based performance translation as a separate, slower investigation. Opponent-style interactions warrant a small falsification experiment. Defer large draft simulators, generic score-driven replacements, and hypergraph lineup models until simpler tests establish residual signal.

These are priorities for experiments, not demonstrated improvements. No new model was fitted or backtested in this task.

## 1. Audit boundary and evidence standard

The audit used a separate clean clone of GitHub `main`, pinned to **`ac5745ca1982d7347d7caee2f98f70f7f1832c53`**. The prior local checkout was behind; it was not used as the authority. Repository links below point to that immutable revision. The repository was left unchanged. No commits, PRs, deployments, or reusable skill were created.

I inspected `AGENTS.md`, the product/current-state/technical/deployment steering documents, relevant UI/product/design guidance, the README, the research index, recent work-log entries and topic-specific archived entries. I traced the production Elo, Form, FORGE, schedule/series, regional-calibration and market-blend paths, fitted artifacts, evaluation helpers, and the relevant research reports and harnesses. This is a source/document audit, not a verification of the running deployment or private data.

**Evidence labels used here:**

- **Verified implementation:** present in the inspected code/artifacts at the pinned revision.
- **Repository-reported result:** a number in the committed report or work log, with its original cohort and limitations. It was not independently recomputed here.
- **Literature evidence:** what the linked primary research actually evaluates.
- **Proposed / expected:** my inference about a Prometheus experiment; no measured gain is implied.

The clean clone contains neither the full raw CSV corpus nor `db/prometheus.db`, private market caches, or the original per-fixture experiment exports. I did not reconstruct those inputs or rerun historical benchmarks. Consequently this report supplies experiment specifications, not new confidence intervals, coverage counts, timings, or fitted gains. Small committed fixtures would not support the requested forecasting conclusions.

### Production baseline actually found

| Component | Verified behavior | Consequence for research |
|---|---|---|
| Player-built Elo | Team strength is the mean of five starters plus home-league offset. Normal starters share the same team update; rookie/provisional/away adjustments can change individual steps. | “Add player ratings” is already done; individualized performance evidence is different. |
| Duration evidence | `winner_score` uses `0.825 + 0.175*tanh((1800-duration_seconds)/300)`; K is 20 and update expectations use the 400-point Elo curve. | Another generic margin or faster-K search has a strong negative prior. |
| Rookies / inactivity / transfers | Log rookie discount: 250 points initially, vanishing at 200 games; first 25 updates doubled. First game after time away can move up to 3×; major-to-other move adds 25 stored points. | A change-point model must beat these existing heuristics plus Form, not plain Elo. |
| Form | Twelve historical gold/objective/vision features, opponent-adjusted with pre-game Elo; 20-game half-life, 0.5 annual carry, five-game prior; retained weight reduced by square root of lineup continuity. | Recent performance, shrinkage, and roster-aware forgetting already exist. |
| FORGE | Elo + Form within a home league; cross-home forecasts start from Elo. Major leagues share one blend, non-majors another. Elo-only non-major fallback has shrunk per-league slopes. | Better raw Elo is insufficient if it duplicates Form and worsens FORGE. |
| International overlay | Event-frozen, earlier-completed-event logistic regional residual calibration; separate from online league offsets. Packaged historical snapshots; latest fit through October 2. | Regional corrections are the control, not a novel proposal. |
| Series | Beta-binomial shared chance; rho 0.054 if both homes are major, 0.127 otherwise. | Correlation is already modeled. An added latent uncertainty layer must avoid counting it twice. |
| Market blend | Monthly frozen symmetric logistic market/model blend, separate from raw FORGE/Elo; minimum 300 earlier series per snapshot. | Any new model-plus-market claim needs a calibrated market-only comparator. |
| GLORY / AURA | GLORY is a hindsight season statistic; AURA is a player season statistic, with a predictive extension still proposed. | Neither published full-season output is a valid pre-match feature. |

Sources: [Elo](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/elo.py), [Form](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/form.py), [FORGE](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/forge.py), [schedule](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/schedule.py), [regional calibration](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/regional_calibration.py), [market blend](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/prometheus/market_blend.py).

### Metrics that must not be conflated

| Committed comparison | Cohort / result | Interpretation |
|---|---|---|
| Headline forecast backtest | 16,810 major domestic maps, 2014–2026: Elo 0.6312, FORGE 0.6285; paired FORGE−Elo −0.0027, 95% interval [−0.0038, −0.0015]. | Small but meaningful existing domestic gain. |
| Same report, international | 1,024 selected maps: current Elo/FORGE 0.6222. | A different cohort and protocol from the regional study below. |
| Non-major domestic backtest | 69,736 maps: per-league Elo 0.6094, FORGE 0.6076; delta −0.0018 [−0.0025, −0.0011]. | Relevant incumbent for minor domestic experiments. |
| Regional-overlay validation | 1,006 eligible cross-region maps since 2022: 0.591756 → 0.574292, delta −0.0175; series interval [−0.0272, −0.0075], event interval [−0.0276, −0.0065]. | Already implemented. Major-v-major series interval and 2026-only interval include zero. |
| International market validation | 76 common timed series at 12h: calibrated 0.554163, old Elo 0.551022, Kalshi 0.534863. | No demonstrated calibrated-model advantage over Kalshi. |
| Entry diagnostic before overlay | 33 cross-region series: Elo 0.5737, close 0.4204. | Four events, no actual Worlds in that priced cohort; selected retrospective slice, not a confirmed current-baseline deficit. |
| Market blend | 1,358 rolling validation series: blend 0.5428 vs raw 0.5595; against calibrated market-only 0.5448, delta −0.0020 [−0.0061, +0.0026]. | Better than raw does not establish independent information beyond market. |

Sources: [metric backtest](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/metric_backtest.md), [regional validation](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/regional_calibration_validation.md), [international interpretation](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/international_model_proposal.md), [blend validation](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/market_blend_validation.md).

**Evaluation caveat verified in code:** `out_of_year_probabilities` trains on every other year, including later years. `out_of_year_form` does likewise for first-stage Form weights. These avoid using the held-out year's own labels in those fits, but are not strict historical forecasting simulations. The benchmark also has eligibility restrictions such as five earlier major-league games and uses actual starters for native pre-game ratings; scheduled forecasts use earlier-day main-roster information. These are different prediction tasks. Some research already includes nested chronological sensitivities. A new experiment must keep the native guard and add an earlier-only evaluation; it must not describe the existing headline numbers as wholly forward-chaining evidence.

Several documents retain historical status language: the research index's original “not shipped” experience/away/roster entries are superseded by its combined-change entry and current defaults. The README's international/cross-league summary also retains some pre-overlay numbers. Code, artifacts, dated adoption reports, and cohort definitions take precedence. I did not edit these discrepancies under the research-only instruction.

## 2. Ranked shortlist

Ranks reflect expected incremental forecasting value, feasibility, and evidence together. They are ordinal judgments, not estimated log-loss improvements. Every candidate has a substantial chance of no useful improvement.

| Rank | Direction / category | Expected increment over current model | Most relevant slice | Novelty relative to audited repo | Decision |
|---|---|---|---|---|---|
| 1 | Adaptive persistence / probabilistic change points | Small overall; potentially larger just after genuine breaks | Minor domestic, roster transitions; later international fixtures | No change-point mechanism found; distinct from fixed forgetting/away factors | First experiment |
| 2 | Team-specific patch exposure and adaptation | Small overall; potentially concentrated at tournament entry | International entry and first matches on a patch | Patch context is mentioned broadly; exposure-weighted pre-event covariates not found | First external-data experiment |
| 3 | Transfer-bridge performance translation | Small broad effect; potentially useful for movers and sparse region links | Minor/cross-league, entry rosters with imports | Learns from pre/post-move performance observations, not offset transport alone | Feasibility/data screen, then pilot |
| 4 | Opponent-style interactions beyond scalar strength | Probably small; upside uncertain | Repeated domestic matchups, exploratory international | No non-transitive matchup mechanism found | Cheap constrained falsification |
| 5 | Pre-series draft opportunity cost under fearless | Low expected near-term return; substantial conditional upside | Bo5 / fearless series, patch transitions | Pool entropy/burn tested; explicit role-specific remaining options not tested | Defer until draft-value signal exists |
| 6 | Score-driven joint observation model | Low until an observation adds residual signal | Broad, if identifiable | GAS itself overlaps Elo; richer observation likelihood would differ | Conditional methods experiment |
| 7 | Higher-order lineup interactions / hypergraphs | Low with current roster variation | Roster changes, mainly minors | Beyond planned pairwise synergy, but identification is weak | Defer; audit design rank first |

### 1 — Adaptive persistence: distinguish a new regime from ordinary noise

**Mechanism and target.** Maintain a small correction to current production log-odds whose persistence can switch between “stable” and “changed.” After several surprising completed games, infer increased probability that the team's old strength no longer applies. A mixture transition could use a tightly concentrated innovation for ordinary evolution and a wider innovation for a genuine break. Start with a team-level residual, not an overhaul of player/region states.

Unlike a uniformly higher K, this retains long memory when justified and shortens it selectively. Unlike roster-aware Form, it can recognize a break without a roster change and can decline to reset after a nominal change that produces no evidence. A returning player already receives faster updates; the novelty is learning persistence from predictive surprises, with uncertainty over whether a break happened.

**Evidence.** Adams & MacKay's [Bayesian Online Changepoint Detection (2007)](https://arxiv.org/abs/0710.3742) supplies run-length inference, not sports validation. Altamirano, Briol & Knoblauch's [robust BOCPD (ICML 2023)](https://proceedings.mlr.press/v202/altamirano23a.html) addresses outlier robustness and scaling. A closer empirical analogue is Macrì-Demartino, Egidi & Torelli's [dynamic Bradley–Terry model (2026)](https://doi.org/10.1186/s40537-026-01486-6): team/time-specific spike-and-slab innovation precisions, tested on held-out NBA stages with modest Brier improvements over constant/stochastic innovation comparators. Its MCMC/smoothing analysis is not an online LoL proof. No independent replication of this specific transfer was located.

**Nearest Prometheus work.** Higher K was rejected because domestic FORGE worsened; fixed away multipliers and roster forgetting shipped. The international Bayesian residual proposal already exists. This candidate should therefore be scoped as *change-point adaptation in residual team performance*, with constant-variance and fixed-reset controls, rather than relabeling regional uncertainty as new.

**Data and timing.** OE results and historical roster identities suffice for a basic pilot. A patch-triggered hazard needs the actually announced competition patch; OE's eventual current-game patch must not masquerade as information available 12h earlier. No current-game stats enter a prediction. Start with conservative next-day availability; receipt-time evidence would enable finer updates later.

**Minimum experiment.** Hold production Elo/FORGE and international overlay fixed as an offset. Compare: no correction; ordinary slow Gaussian residual; one fixed fast residual; deterministic roster reset; two-innovation mixture. Use only a small predeclared hyperparameter set, tuned on older chronological folds. Add historical performance residuals only after the result-only mixture wins. Compare no event trigger versus roster-triggered hazard separately. Report first 1/3/5/10 maps after a known roster change and all maps, plus international entry/later slices.

**Risks / cost / expected gain.** Several maps in one series are not several independent break discoveries. Heavy-tailed observations and series-level updates guard against false resets after one upset. Team, player and regional terms are confounded; constrain the residual mean and shrink strongly. Break episodes, not 100,000 maps, determine power. A capped run-length filter or two-state approximation is modest computationally; no timing has been measured. A full joint player-level BOCPD model is unnecessary initially. Expected benefit is small after Form, with more plausible concentrated gains in volatile minor teams. It cannot infer the direction of an unseen pre-tournament change from zero new evidence.

### 2 — Patch exposure: forecast which teams lose usable strengths before the tournament starts

**Mechanism and target.** Build a pre-event exposure score from each expected starter's earlier champion-by-role usage and announced champion changes between the team's last played patch and the event patch. For example, sum historical pick shares times signed buff/nerf indicators; keep net exposure and absolute disruption separate. Test whether the effect fades with completed games on the new patch.

This supplies information before an entry match. Merely increasing rating uncertainty cannot identify which team benefits from a rule change. A global patch dummy also cannot distinguish two teams at the same event.

**Evidence.** Claypool et al.'s [2017 patch study](https://web.cs.wpi.edu/~claypool/papers/lol-crawler-journal/pre-proof.pdf) links patch descriptions and gameplay over a large player corpus, while showing why simplistic buff counts can mislead. Kwak's [October 2026 Worlds preprint](https://arxiv.org/abs/2610.07427) examines 1,097 Worlds games and 215 team-years, with team-specific exposure to previously unplayed changes. Its win association is inconclusive: approximately +1.3 percentage points per SD, interval −0.9 to +3.7. This is direct LoL evidence that exposure can be constructed, not evidence that it improves forecasts. It is new, exploratory, and not independently replicated. Governance/descriptive results and quarterfinalist anecdotes do not validate a predictive feature.

**Nearest Prometheus work.** Champion main effects, lane matchups, and champion×state slopes were studied primarily in *in-game snapshot* models. Pool depth beyond experience failed. None is a test of earlier champion usage interacted with subsequently announced patch changes. General patch context is already a future-work suggestion, so the novelty is the precise exposure mechanism and entry-time evaluation, not the word “patch.”

**Data and timing.** Historical champions, roles, dates, and patches are available in OE raw files; the core DB does not retain every needed raw field. Official Riot patch notes, announcement timestamps, competition patch/rule announcements, and disabled champions require external sources. Pin notes as available then, including relevant hotfixes. The live-server patch release date alone does not establish the competition patch. Use the last known lineup; treat the actual future starters as an explicitly labeled oracle sensitivity only.

**Minimum experiment.** Freeze an auditable directional coding scheme, initially just clear direct champion buffs/nerfs; do not tune an LLM's labels against winners. Fit one or two strongly shrunk coefficients on top of the calibrated production international logit and domestic FORGE. Compare baseline; generic patch-transition indicator; exposure; exposure plus new-patch experience. Include a matched-complexity placebo that permutes changes across champions within patch. Preserve old-pool experience and depth controls. Test completed earlier events/patch blocks, with separate entry and adaptation endpoints. Do not select historical pool windows using the final test events.

**Risks / cost / expected gain.** Patch changes target the prior meta, so exposure correlates with prior success, specialization, and region. Item/system effects can offset champion changes; start with transparent partial coverage and report exclusions. Thousands of maps do not create thousands of independent patch shocks. Use event and patch-block sensitivity, strong pooling, and no team-specific patch coefficient. Parsing/coding/competition-patch provenance dominate cost; inference is cheap. This has the best chance here of supplying genuinely new directional entry information, but the null-heavy direct evidence means expected broad gain remains small and uncertainty high.

### 3 — Transfer bridges: learn what a performance signal means after moving leagues

**Mechanism and target.** Use players observed before and after a home-league move as imperfect bridges between competitive environments. Model a compact role-conditioned performance signal as player ability plus team context, opponent context, patch/era effects and league-specific measurement effects. Within-league team moves estimate ordinary transition noise; cross-league moves additionally inform translation. Use the learned distribution to construct a *small predictive correction* for a known incoming roster, initially without feeding it back into existing offsets.

This is different from assuming an imported player carries exactly the right absolute Elo or adding the same 25 points to every move down. It also differs from league-offset experiments that learn only from cross-home match results. The genuinely added observations are individual performance histories across moves.

**Evidence.** Shaikh's [cross-league football translation study (2026)](https://doi.org/10.1177/22150218261481583) uses 174 attacking/midfield and 106 defensive training transfers, with 45/35 held-out transfers. It demonstrates some calibrated performance-translation intervals, not a match-forecasting gain; some defensive coverage is poor and ridge/boosting can match or beat point accuracy. All destinations are the Premier League. Minka, Cleven & Zaykov's [TrueSkill 2 (2018)](https://www.microsoft.com/en-us/research/wp-content/uploads/2018/03/trueskill2.pdf) provides a complementary construction: historical individual statistics inform latent performance linked to winning. Its Halo results do not establish expected gains for pro LoL. No replicated LoL bridge-to-win-probability result was located.

**Nearest Prometheus work.** Player Elo transfers, move-down bonuses and rejected link-offset replays are directly relevant. Predictive AURA and individual credit are already roadmap items. The proposed distinction is *jointly separating league-dependent measurement from transferable player signal*, with within-league movers as a control. Simply averaging AURA into Elo would be a familiar backlog experiment, not this new mechanism. AURA's existing substitution result is approximately null beyond Player Elo; that lowers expectations.

**Data and timing.** OE identities, roster histories and raw player statistics can support a first pass. Snapshot gaps are interpretable but unevenly covered, especially historical LPL; full-game K/D/A/CS cover more games but are more outcome/role dependent. Pick one signal first. All post-move observations must precede the forecast; labels can concern the player's next several maps, but those maps must all have completed before a training example is admitted. Current destination team outcomes or season-end AURA cannot enter its opening forecast.

**Minimum experiment.** First count qualifying bridges by direction, role, year, and unique player, and identify disconnected league components. Compare no translation, current fixed move bonus, pooled translation, role-pooled translation and only then shrunk source/destination effects. Use domestic movers to measure generic transfer disruption. Hold out entire transfer episodes chronologically; include a same-input ridge control. Stage 1 forecasts post-move performance with proper predictive scores. Stage 2 uses cross-fitted predicted corrections in the pre-match win model. Passing stage 1 alone is insufficient. Keep offsets/rookie rules fixed for attribution; only a later experiment changes their feedback.

**Risks / cost / expected gain.** Movers are selected; promotions, demotions, role changes and benching are confounded with ability. A stable player effect cannot simply be assumed across a transfer. Repeated maps from one move cannot create independent bridge evidence. Five teammates' correlated stats must not be treated as five independent skill observations. Use player/episode clusters and pooled priors; retain unobserved/failed transfers in coverage reporting. A small mixed model is practical offline; full Bayesian multivariate dynamic inference is more expensive and should wait. Expected gain is concentrated in moves and sparse cross-league links, with especially uncertain transfer to elite international entry teams.

### 4 — Opponent-style interactions: allow a matchup to differ from scalar ranking

**Mechanism and target.** Add a tightly constrained antisymmetric interaction of historical team style vectors to production log-odds. If `z_A` and `z_B` are lagged style features, a term `z_A' W z_B`, with `W = -W'`, reverses correctly when teams swap and allows matchup advantages that no scalar strength difference can represent. Begin with two or three predeclared style dimensions, not hundreds of team-identity embeddings.

Possible histories include relative early aggression, objective tradeoffs and conversion patterns after controlling for Elo/opponents. A self-performance feature says a team is generally better; the interaction asks whether *this opponent's* tendencies make that strength more or less effective.

**Evidence.** Chen & Joachims' [2016 blade–chest paper](https://www.cs.cornell.edu/~tj/publications/chen_joachims_16a.pdf) models intransitive matchups. It reports stronger StarCraft effects but limited Dota log-likelihood gains and little Dota accuracy gain; importantly, its general setup uses random match splits, not the required chronological test. Spearing et al.'s [baseball extension](https://arxiv.org/abs/2103.12094), subsequently published in JCGS, supplies additional empirical evidence for deviations from Bradley–Terry. Neither establishes a LoL residual beyond player Elo plus Form, and changing rosters/styles make transfer uncertain.

**Nearest Prometheus work.** Form and FORGE use linear gaps; they do not contain this cross-opponent interaction. In-game champion matchup effects concern a different mechanism and prediction time. Team familiarity/pairwise teammate synergy do not capture A-versus-B tactical compatibility. Raw early-game diffs already failed as added linear Form inputs; that is a necessary control, not proof these interactions work.

**Data and timing.** OE alone can support aggregate histories; richer movement/vision/objective timing would require additional data. Missing historical snapshots limit common coverage. Every style state must use completed earlier maps; current game's gold, champions or final objective counts are unavailable features. No direct H2H identity term initially.

**Minimum experiment.** Fit baseline; baseline + linear style gaps; baseline + a single antisymmetric interaction; and the interaction with style vectors shuffled among similarly rated teams in the same earlier period. Construct/standardize styles inside the training fold, with opponent/strength adjustment. Use one fixed small dimensionality and strong ridge shrinkage. Evaluate new opponent pairs separately from repeats and stable rosters separately from changed rosters. Freeze embeddings/features before new events.

**Risks / cost / expected gain.** Schedule structure can generate apparent cycles; time drift can make an earlier weak team and later strong team look intransitive. Few cross-region encounters cannot identify unrestricted region-style matchups. Interactions can absorb league imbalance or patch effects. Treat preliminary residual associations as exploratory, not as an extra feature search over the test set. A few interaction coefficients are cheap; unrestricted embeddings have high overfitting risk. Expected average improvement is probably small. A stable chronological null is a good reason to stop rather than scale the architecture.

### 5 — Draft opportunity cost: integrate expected remaining options before a fearless series

**Mechanism and target.** Predict not just how many champions a roster has used, but how much competitive value it is likely to retain after contested picks and bans across a series. Role-specific redundancy matters: losing one essential option in one role may matter more than broad entropy elsewhere. Integrate over plausible future drafts to obtain pre-series win probability; do not condition it on the realized drafts.

**Evidence.** Chen et al.'s [JueWuDraft (2020/2021)](https://arxiv.org/abs/2012.10171) explicitly models multi-round drafting with long-term value in Honor of Kings. It validates a drafting system, not calibrated pre-series LoL forecasts. The [2026 player-conditional champion ranking preprint](https://arxiv.org/abs/2605.18338) offers a style/mastery decomposition but only a single-player sanity case; it is not empirical justification for adopting a forecasting feature. No convincing independent evidence of incremental pre-series log-loss improvement over a FORGE-like baseline was located.

**Nearest Prometheus work.** The series study tested pool depth, burn, format and lead; the later pool-depth report found effectively no benefit beyond experience. Beta-binomial correlation is already present. Therefore “add fearless” or “add champion-pool size” should not be repeated. The new quantity would be *expected role-specific loss of usable draft value*, estimated before play. It must also beat simple depth, experience and current rho controls.

**Data and timing.** Raw OE has historical picks/bans, roles and champions; verified competition rules, disabled champions and event patch need external provenance. Champion definitions/attributes may need official versioned data. Pick order and flexible role assignment can be incomplete. At 12h, neither the actual game-1 draft nor future depleted pool is known. Unknown side choice must be marginalized. Later-map forecasts may use completed drafts but belong to a separate endpoint.

**Minimum experiment.** First test a compact pre-series “weakest-role redundancy / overlap” summary with equal player-champion values, then add shrunk historical player-champion performance residuals. Compare each to experience + entropy controls atop the current series model. Only if those summaries help, fit a historical drafting policy and a compact value model, cross-fit both, and marginalize drafts with bounded Monte Carlo. Use actual drafts only for a separately labeled post-draft diagnostic; never call that pre-match performance. Integrate common skill uncertainty consistently with rho.

**Risks / cost / expected gain.** “Never picked” does not mean “cannot play”; scrims and deliberate concealment are unobserved. Proficiency is confounded with selection, teammates, opponents and champion strength. Fearless and era shifts coincide; actual rule labels are preferable to labeling a whole split by observed repeats. Only a limited number of recent Bo5 series identifies long-horizon depletion. A compact screen is cheap, but full draft learning/simulation is high effort. Given the failed simple depth/burn evidence, expected near-term return is low; defer a full simulator.

## 3. The other two handoff leads: worth understanding, low priority

### 6 — Score-driven latent ratings: require a new likelihood, not a new name for Elo

For Bernoulli observations with logit strength gap, the score with respect to that gap is `y - p`. A constant-step score update therefore reproduces the essential Elo mechanism. Scaling the score and fitting persistence may differ numerically, but does not automatically add information beyond tuned Elo and Form.

Creal, Koopman & Lucas' [GAS foundation](https://doi.org/10.1002/jae.1279) formalizes likelihood-score updates. Koopman & Lit's [2019 football study](https://research.vu.nl/ws/files/151597369/Forecasting_football_match_results_in_national_league_competitions_using_scoredriven_time_series_models.pdf) evaluates six leagues with seven forecast seasons: richer count observations outperform reducing scores to result categories, and computation is efficient. Its betting tables report losses; “best betting model” must not be translated into profitable forecasting. Football goals determine the winner; LoL kills do not. That domain difference is fundamental.

A potentially distinct LoL experiment would use a robust *joint observation model* for result and one compact performance statistic, including shared game noise, with likelihood-dependent updates and strength/style separation. OE alone supplies historical observations, all available only after completion. The nearest existing work includes Form, many margins, conditional tempo and rejected larger K. The exact update must be compared algebraically and empirically to these before a new system is justified.

Minimum ablations: current baseline; Bernoulli-score equivalent control; fitted persistence/scaling only; one additional observation with fixed update; then the joint likelihood. Fit observation loadings and scales only on earlier folds. Keep the international overlay and roster rules identical. Judge winner log loss, not improved fit to kills/duration. Share a game-level shock instead of treating correlated stats as independent. Use regularization toward the Bernoulli-only control and compare chronology/series-cluster intervals. Filtering can be linear in games with fixed small state dimension; offline optimization multiplies cost and has not been timed.

**Verdict:** do not prioritize generic GAS as an independent “new predictor.” Pursue only after evidence of a residual observation signal, potentially arising from candidate 3. Expected incremental benefit is low/unknown. The source literature motivates an experiment, not replacing FORGE.

### 7 — Hypergraph adjusted plus-minus: identification before sophistication

Josephs & Upton's [Hypergraph adjusted plus-minus](https://arxiv.org/html/2403.20214v3), with [journal DOI](https://doi.org/10.1515/jqas-2024-0057), jointly represents individuals, lower-order groups and full lineups, including graph-based regularization. It uses NBA lineup data; that is far richer within-team substitution variation than a usual LoL starting five. The revised paper also reports year-to-year rank stability and first-half-to-second-half plus-minus prediction, with favorable results for its methods. Those are performance/ranking endpoints, not pre-match winner log loss. No directly relevant LoL follow-up forecast replication was found.

The nearest Prometheus backlog already includes familiarity, role weights and pairwise synergy. Higher-order effects would differ, but if the same five always appear together, individual, pair, triple and five-player indicators are collinear. Ridge picks a decomposition; it does not reveal which interaction caused success. More matches with exactly that five improve its team estimate without identifying the decomposition. OE supplies roster/outcome rows; no external data is necessary for an initial identifiability audit. Future starters remain unknown at an early forecast cutoff.

Before fitting: count lineup transitions, independently varying duos/trios, connected player components and effective design rank using earlier data. Require a realistic transfer/substitution prediction task. Then compare player-only, player + familiarity, player + one lineup residual, pairs, and at most one prespecified role trio with stronger shrinkage at higher orders. Use chronological whole-episode holdouts, report unseen lineup coverage, and retain team-context controls. A logistic lineup-effect analogue is an adaptation, not a literal application of basketball scoring-margin APM.

Sparse fitting is possible, but the combination count and graph construction can grow rapidly. The main obstacle is identification and generalization, not compute. Substitution selection and unknown starters compound the problem. **Expected incremental benefit is low at present; defer unless the design audit reveals enough independent variation.** This is the lowest-priority handoff lead.

## 4. Already implemented/tested — do not pursue as new research

| Idea | Audited status / reason to exclude | What would constitute a materially different experiment? |
|---|---|---|
| Opponent-adjusted stats / recent Form / Elo+Form | Implemented. | New observations or mechanisms beyond linear historical stat gaps. |
| Player Elo / roster continuity / rookies / faster post-inactivity updates | Implemented with the details above. | Probabilistic break selection, individualized observations, or genuinely available pre-match lineup news. |
| Persistent regional residual calibration | Implemented; broad 2022+ gain already counted. | Proper uncertainty integration or a separately justified new covariate, compared against the overlay. |
| Recency-weighted regional correction | Tested; weaker and not significantly better overall. | A justified structural innovation model, not another half-life sweep. |
| Single-offset replacement / recalibration | Tested. Replacements lost overlay gains; the recalibrated one-state arm failed within-other-league safeguards. | Explicitly isolate transfer feedback or independent bridge observations. |
| Alternative margins, objective/kill/gold composites, larger K | Many variants tested. Larger K duplicates Form; some worsen FORGE. | New observation likelihood with independent signal, and exact fixed-baseline ablations. |
| Conditional tempo surprise | Tested. Conditional centering worsened the same fixed steep curve; curve shape explains the apparent gain. The fixed curve shipped. | Not another centered-duration proxy; a different identified observation mechanism. |
| Early-game diffs added to Form | Tested; no significant gain. | Opponent-style interactions or player portability, with linear feature controls. |
| Ridge / fewer Form stats / pooled or minor-specific weights | Tested; at best about −0.0003 non-major FORGE, not adopted. | A new conditional mechanism, not coefficient cleanup or interpreting negative coefficients away. |
| Blue-side term | Update tests mostly null; game-1 side not reliably known before match. | Timestamped side-choice input for a separately defined later cutoff. |
| Independent-game series correction | Beta-binomial already implemented. More elaborate rho variants did not beat tier rho. | A separately identifiable draft/skill uncertainty component; avoid double counting. |
| Pool entropy / burn / experience | Tested. Depth adds effectively nothing after experience in the relevant follow-up. | Role-specific usable option value, not pool size renamed. |
| Champion effects / lane matchup / champion×state slopes | In-game studies inconclusive or worse; not a blanket negative result for every pre-series draft model. | Pre-event patch exposure or marginalized unknown draft, on the proper cutoff. |
| Market blending | Implemented; independent edge over calibrated market-only remains uncertain. | New signal that improves raw forecasts and also survives the market-only comparison. |
| Supply future actual starters or current-map draft | Not valid at an earlier forecast cutoff; Leaguepedia starters were investigated and dropped. | A proven timestamped source or explicit marginalization over uncertainty. |

Key reports: [research index](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/README.md), [conditional-tempo attribution](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/elo_tempo_validation.md), [duration adoption](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/duration_curve_adoption.md), [pool depth](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/pool_depth_report.md), [series independence](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/research/series_independence.md), [archived work log](https://github.com/thaiv28/Prometheus/blob/ac5745ca1982d7347d7caee2f98f70f7f1832c53/docs/steering/work_log_archive.md).

## 5. Existing backlog worth testing, but not newly discovered

**Regional posterior predictive integration and shrunk team residuals.** These are explicitly proposed in `international_model_proposal.md`. They remain sensible controls for entry overconfidence, but uncertainty alone cannot correct an incorrectly ordered favorite. Integrate a regional-state draw once per series, preserve its covariance, and estimate residual rho on earlier data. Compare posterior mean versus integrated probabilities to isolate uncertainty from better means. Do not change player-transfer feedback in the same experiment.

**Predictive AURA / player credit.** Already proposed, with the season-level substitution check providing little support beyond Player Elo. A simple earlier-only predictive AURA blend is the prerequisite control for any elaborate player-observation model. Better player-season correlation does not guarantee better team-win log loss.

**Familiarity, role weights, Form effective-game gating, fitted update scale, per-league FORGE blends.** All appear in future work. They may be cheap, useful falsification controls, but should not displace mechanisms that add new information merely because they are easy to enumerate. Familiarity's in-sample z near 2 followed many residual screens. A significance interval after repeated search is not untouched confirmation.

**Elite-tail / region-dispersion modeling.** An exploratory idea is to let domestic deviations translate differently across regions rather than adding only a regional mean. Baio & Blangiardo's [hierarchical football work](https://gianluca.statistica.it/research/football/) warns that pooling can overshrink extreme teams. That is an analogy, not evidence of a Prometheus failure: current Elo is not the same hierarchical shrinkage model. Existing league-part scaling and Form normalization tests lower expectations. International representatives are highly selected, so separate region-tail slopes would be weakly identified; do not add them without a residual diagnostic on earlier events. Not in the main shortlist.

A September 2026 professional-LoL paired-comparison preprint (`arXiv:2609.08060`) also surfaced during the scan. Search indexing supplied an abstract, but the primary paper could not be retrieved. I excluded its numerical claims from the evidence supporting this ranking; it is a follow-up reading lead, not a validated comparison.

## 6. Common experiment contract

### Forecast targets and fair controls

Keep three tasks separate: (1) 12h pre-series probability, (2) map 1 before play, and (3) later-map probability after already completed maps. A later-map update or post-draft classifier cannot count as improvement in task 1.

For every shortlisted method compare on identical fixtures:

1. The pinned production algorithm and artifacts, including the regional overlay and current series conversion, as an explicitly retrospective current-model replay.
2. A **same-architecture earlier-only baseline** with every fitted stage using only earlier available outcomes. Refit Form's opponent adjustment, stat weights, FORGE curves, league slopes, calibration, and candidate hyperparameters inside the chronology. Fit meta-models on earlier cross-fitted predictions.
3. The smallest added-mechanism control: fixed reset for change points; generic patch transition for exposure; fixed move adjustment for bridges; linear style gaps for interactions; entropy/experience for drafts.
4. On priced common cohorts: market at the same 12h cutoff; calibrated market-only; existing blend; candidate-plus-market. Closing prices remain a separate tougher comparison, not an early feature.

The first preserves the user's real incumbent. The second determines whether the apparent increment survives an honest information boundary; they answer different questions and should both be reported.

### Chronology and availability

Use expanding annual folds for broad development and completed-event folds for international validation. Hyperparameter tuning must be nested within earlier data; keep all maps of a series together for outer fitting. An event held out from parameter fitting may permit updates from its completed maps for sequential forecasts; report that separately from a frozen tournament-entry forecast.

The already viewed 2022–2026 history is development evidence even if refitted chronologically. Freeze the winner and feature definitions before genuinely untouched future fixtures. Do not call a repeatedly consulted 2026 subset a fresh holdout. Start-date ordering is not a result-availability timestamp. Prefer archived receipt times; otherwise impose and disclose a conservative next-day rule and test reasonable availability sensitivities. The market-blend report's start+24h proxy is not proof every source was available then.

Historical actual starters are an oracle control, not the primary early forecast roster. Whole-season home labels can define retrospective cohort membership but cannot supply future home information to the predictor. Record unmatched teams, missing patch announcements and unavailable stats rather than selectively dropping hard cases without coverage accounting.

### Slices and scoring

Primary score is mean natural-log loss, candidate minus baseline; negative is better. Report Brier and calibration intercept/slope/reliability plots with uncertainty. ECE is descriptive and bin-sensitive, especially in small slices. Accuracy is secondary.

Always report major domestic, minor domestic, recognized international cross-home, and other cross-league. Within internationals report major-major, major-minor, minor-minor and senior/academy separately where possible. Define entry in advance: the existing “no previous event game day for either team” proxy, plus a clearly distinguished actual first-appearance definition if timestamped results permit. Neither is automatically “round 1.” Show entry versus later fixtures and counts of maps, series, events and independent episodes.

Do not aggregate overlapping slices as if they were disjoint new evidence. Give game-weighted and equal-series-weighted sensitivity so long series do not dominate silently. Keep map-1 and series comparisons on a shared coverage cohort when interpreting series conversion.

### Dependence, power and adoption

Use paired bootstrap loss differences on shared fixtures: series clusters for maps, event sensitivity for internationals, and league/split or time-block sensitivity domestically. For patch features also assess patch/event blocks; for transfers resample player/episode units. Four priced events cannot support a reliable asymptotic story; report leave-one-event-out influence and wide uncertainty. Bootstrap intervals conditional on fitted predictions omit model-selection and fitting uncertainty; supplement with repeated outer folds/refit sensitivity where feasible.

No universal sample target is justified. From pilot paired cluster losses, estimate the standard error of the mean difference and the number of *independent clusters* needed for a predeclared useful effect. For planning only, an approximately normal 80%-power two-sided test needs a true effect around 2.8 times the current standard error; cluster imbalance and tiny event counts can invalidate that approximation. More maps in the same few events may add much less power than a new event.

Predeclare one primary endpoint per candidate and a small ablation set. Correct for or explicitly disclose selection across variants; require untouched confirmation rather than promoting the best of many nominal 95% intervals. Keep the repository's same-game improvement/no-significant-regression guards, while adding chronological and clustered checks. A guard that only prevents significant harm does not itself establish benefit. Estimate fit/replay/storage costs in a future pilot; no CI/build-time addition is justified by this report.

## 7. Recommended next sequence

1. **Freeze the evaluation contract and baseline exports.** Preserve revision, data hashes, artifacts, original saved forecasts and common fixture cohorts. Produce the current-model replay and earlier-only same-architecture baseline. This is measurement work, not a claim of model improvement.
2. **Run one small adaptive-persistence experiment.** Result-only residual mixture against constant/fast/fixed-reset controls. Continue only if it improves current FORGE rather than just raw Elo, without guard regressions.
3. **Build a bounded patch-exposure dataset.** Audit official patch availability and code clear champion changes without outcomes. Test one or two exposure coefficients against generic patch-transition controls. Give international entry its own predeclared endpoint.
4. **Audit transfer bridges and run a small style-interaction screen.** Bridge counts determine whether candidate 3 is estimable; the style experiment can falsify candidate 4 cheaply. Do not jointly add them before isolated effects are understood.
5. **Revisit sophisticated likelihoods or draft simulation only after their precursor signal survives.** GAS needs a useful extra observation; draft search needs evidence beyond depth/experience; hypergraphs need independent lineup variation.
6. **Freeze the surviving model for future events.** Use untouched timestamped forecasts and market quotes to confirm incremental log loss. Only after the research concludes revisit whether this workflow should become a reusable skill.

No implementation or repository mutation is authorized by this sequence. It is a concrete research agenda for a subsequent approved experiment phase.
