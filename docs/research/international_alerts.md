# International alert candidates — 2026-10-15

Fixed policy: actual cross-home international series, known start time, strictly more than 5 percentage points over the executable ask, one side per fixture. Primary observation is 12 hours before start (within the existing 6+ hour policy). No lead-time or edge tuning. Production-equivalent persistent regional calibration, only earlier completed events used for coefficients; before-day ratings at the 12h cutoff. Raw Elo is a diagnostic control, not another policy to select.

83 timed cross-region fixtures; 75 have an available fresh ask. Re-read hourly candles from the local cache; only valid two-sided books ending at/before the cutoff and no more than one hour old qualify. Spread at most 10%; use the cheaper equivalent yes/no ask. Missing books are excluded, never replaced with a midpoint. Outcomes/fixture matching were validated by the original regional experiment.

Returns use the existing $1 contract-cost paper convention, plus a separately charged fee: ceil(0.07 × contracts × P × (1−P)) to the cent. ROI below is profit / contract cost (fee is deducted from profit). This is a modeling assumption, not a verified series-specific historical fee/depth/fill record. [Kalshi fee schedule](https://kalshi.com/docs/kalshi-fee-schedule.pdf).

| Slice | Calls | Won | ROI (series 95%) | ROI (event sensitivity 95%) | CLV points (series 95%) | Beat close |
|---|---:|---:|---|---|---|---:|
| Calibrated, fresh asks | 46 | 17 | +43.0% [-34.6%, +138.1%] | [+11.2%, +99.3%] | -0.42 [-2.95, +2.28] | 39.1% |
| Raw Elo control | 46 | 16 | +48.9% [-31.6%, +144.9%] | [+10.3%, +134.8%] | -0.66 [-3.30, +2.22] | 37.0% |
| Esports World Cup 2026 | 8 | 5 | +99.3% [-38.3%, +252.3%] | [+99.3%, +99.3%] | +0.62 [-0.87, +2.16] | 62.5% |
| Mid-Season Invitational 2026 | 9 | 3 | +95.4% [-92.6%, +412.6%] | [+95.4%, +95.4%] | -3.78 [-12.06, +3.89] | 11.1% |
| World Star Challengers Invitational 2026 | 29 | 9 | +11.2% [-68.4%, +116.1%] | [+11.2%, +11.2%] | +0.33 [-2.37, +3.94] | 41.4% |
| Senior events (exclude WSCI) | 17 | 8 | +97.3% [-39.3%, +288.5%] | [+95.4%, +99.3%] | -1.71 [-6.47, +2.37] | 35.3% |
| Remove largest winner (sensitivity only) | 45 | 16 | +14.6% [-46.5%, +90.5%] | [-57.9%, +99.3%] | -0.40 [-2.97, +2.35] | 40.0% |
| Remove two largest winners (sensitivity only) | 44 | 15 | -11.0% [-55.2%, +39.9%] | [-57.9%, +99.3%] | -0.38 [-3.00, +2.56] | 40.9% |
| Pay 1¢ more, original selection | 46 | 17 | +33.0% [-37.0%, +117.7%] | [+3.9%, +91.4%] | -1.42 [-3.95, +1.28] | 30.4% |
| Pay 2¢ more, original selection | 46 | 17 | +24.6% [-39.4%, +100.9%] | [-2.3%, +84.0%] | -2.42 [-4.95, +0.28] | 21.7% |

Intervals resample series (10,000 draws, seed 0); event sensitivity resamples whole event blocks and is unreliable with only a few tournaments. Event rows with one block have degenerate event intervals. Profit is concentrated in long-shot wins; leave-winner-out rows describe fragility, not deployable filters. Negative CLV weakens the profit evidence.

This is retrospective, already-viewed development data through September 30, with no Worlds. Forecast hyperparameters and retrospective best-of reconstruction also limit inference. One 12h observation does not replay the first qualifying hourly alert anywhere 6+ hours out. Quotes do not prove available depth or fills; freshness here means a recent candle close, not a historical live API observation. No significance claim or evidence of improvement in alert returns over raw Elo. Historical candidates must not be inserted into the forward alert record.

Decision: the positive historical return is enough for a separately labeled experimental international paper track, not a demonstrated profitable strategy. Keep the current 5-point/6h live policy fixed, preserve fresh-price/missing-results guards, freeze first terms and model provenance, and compare forward after-fee returns and CLV across completed tournaments before promotion.
