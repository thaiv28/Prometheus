"""GlorELO+: a forecast rating that blends GLORY+ with Elo.

Both teams' GLORY+ (this season so far) and current Elo go into one logistic win
curve. Its weights come from the rolling backtest in `scripts/evaluate_metrics.py`
(fit on GLORY+ and live Elo gaps over every major-league game since 2014). Rerun
that script and copy its "GlorELO+ weights" line here to refresh them.

The blend is published on the Elo scale: 400 points of gap means 10-to-1 odds,
and the average major-league team this season sits at 1500.
"""

import math

import pandas as pd

# Log-odds of winning per point of gap, from the backtest.
GLORY_PLUS_WEIGHT = 0.00976
ELO_WEIGHT = 0.00636

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
