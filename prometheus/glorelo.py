"""GlorELO+: a forecast rating that blends GLORY+ with Elo.

Both teams' GLORY+ (this season so far) and current Elo go into one logistic win
curve. Its weights come from the rolling backtest in `scripts/evaluate_metrics.py`
(fit on GLORY+ and live Elo gaps over every major-league game since 2014) and live
in `glorelo_weights.json`. Refresh them with
`scripts/evaluate_metrics.py --write-weights`; CI runs `--check-weights` and warns
when a refit would move them by more than `WEIGHT_TOLERANCE`.

The blend is published on the Elo scale: 400 points of gap means 10-to-1 odds,
and the average major-league team this season sits at 1500.
"""

import json
import math
from pathlib import Path

import pandas as pd

WEIGHTS_PATH = Path(__file__).with_name("glorelo_weights.json")
# A refit that moves either weight by more than this share is flagged in CI.
WEIGHT_TOLERANCE = 0.10


def load_weights(path=WEIGHTS_PATH):
    """The tracked GlorELO+ weights: log-odds of winning per point of gap."""
    return json.loads(Path(path).read_text())


def save_weights(weights, path=WEIGHTS_PATH):
    """Write refit weights (rounded as the backtest reports them) to the tracked file."""
    rounded = {key: round(float(value), 5) for key, value in weights.items()}
    Path(path).write_text(json.dumps(rounded, indent=2) + "\n")


def weight_changes(old, new):
    """Relative change of each weight, for example 0.12 for a 12% move."""
    return {key: abs(new[key] - old[key]) / abs(old[key]) for key in old}


_WEIGHTS = load_weights()
GLORY_PLUS_WEIGHT = _WEIGHTS["glory_plus_weight"]
ELO_WEIGHT = _WEIGHTS["elo_weight"]

ELO_SCALE = 400 / math.log(10)
CENTER = 1500


def glorelo_ratings(glory_plus, latest_elos):
    """Current GlorELO+ rating for every team with both a GLORY+ score and an Elo.

    Args:
        glory_plus: GLORY+ rankings for one season (teamname, league, score, ...).
        latest_elos: Output of `get_latest_elos` (teamname, elo, latest_date, ...).
    Returns:
        DataFrame with teamname, league, year, glory_plus, elo, glorelo and
        latest_date, highest rating first.
    """
    elos = latest_elos.drop_duplicates("teamname").set_index("teamname")
    df = glory_plus[["teamname", "league", "year", "score"]].rename(
        columns={"score": "glory_plus"}
    )
    df = df.drop_duplicates("teamname").join(
        elos[["elo", "latest_date"]], on="teamname", how="inner"
    )
    log_odds = GLORY_PLUS_WEIGHT * df["glory_plus"] + ELO_WEIGHT * df["elo"]
    df["glorelo"] = CENTER + ELO_SCALE * (log_odds - log_odds.mean())
    return df.sort_values("glorelo", ascending=False).reset_index(drop=True)


def win_probability(rating, opponent_rating):
    """Chance that a team beats an opponent on a neutral side, from GlorELO+ ratings."""
    return 1 / (1 + 10 ** ((opponent_rating - rating) / 400))
