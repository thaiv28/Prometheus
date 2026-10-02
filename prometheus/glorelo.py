"""GlorELO+: the headline forecast, Elo plus league-relative Form.

Between two teams from the same home league, the chance to win one game is a
logistic curve on their Elo gap and their Form gap (see `prometheus/form.py`).
Between leagues, Form doesn't compare (each team's Form is measured against its
own league), so the chance comes from Elo alone, on a curve fit to past games.

A team's GlorELO+ rating is its Elo plus its Form in Elo points
(`FORM_WEIGHT / ELO_WEIGHT` per unit of Form), so the same-league win chance is
`1 / (1 + exp(-ELO_WEIGHT * rating gap))`.

The weights are fit by the rolling backtest in `scripts/evaluate_metrics.py` and
live in `glorelo_weights.json`. `--write-weights` refreshes them; CI runs
`--check-weights` and warns when a refit would move one by more than
`WEIGHT_TOLERANCE`.
"""

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from prometheus.form import league_relative, load_weights as load_form_weights, scores

WEIGHTS_PATH = Path(__file__).with_name("glorelo_weights.json")
# A refit that moves any weight by more than this share is flagged in CI.
WEIGHT_TOLERANCE = 0.10


def load_weights(path=WEIGHTS_PATH):
    """The tracked blend weights: log-odds of winning per point of gap."""
    return json.loads(Path(path).read_text())


def save_weights(weights, path=WEIGHTS_PATH):
    """Write refit weights (rounded as the backtest reports them) to the tracked file."""
    rounded = {key: round(float(value), 6) for key, value in weights.items()}
    Path(path).write_text(json.dumps(rounded, indent=2) + "\n")


def weight_changes(old, new):
    """Relative change of each weight, for example 0.12 for a 12% move."""
    return {key: abs(new[key] - old[key]) / abs(old[key]) for key in old}


_WEIGHTS = load_weights()
ELO_WEIGHT = _WEIGHTS["elo_weight"]
FORM_WEIGHT = _WEIGHTS["form_weight"]
CROSS_REGION_ELO_WEIGHT = _WEIGHTS["cross_region_elo_weight"]
# Elo points per unit of Form (log-odds against the league average).
FORM_POINTS = FORM_WEIGHT / ELO_WEIGHT


def win_probability(rating, opponent_rating, same_league=True, elo=None, opponent_elo=None):
    """Chance that a team beats an opponent in one game on a neutral side.

    Same home league: from the GlorELO+ ratings. Different leagues: from Elo alone.
    """
    if same_league:
        gap = ELO_WEIGHT * (rating - opponent_rating)
    else:
        gap = CROSS_REGION_ELO_WEIGHT * (elo - opponent_elo)
    return 1 / (1 + math.exp(-gap))


def team_forms(states, form_weights=None):
    """Current and season-end Form for every team, league-relative.

    Args:
        states: `form.form_states` output for every game so far.
    Returns:
        (now, seasons). `now`: one row per teamid with teamname, home, year (of its
        last game), latest_date, form (log-odds vs its league this season or its
        last season), form_games. `seasons`: one row per team-year with the state
        after the team's last game that year, against that league-season's average.
    """
    if form_weights is None:
        form_weights = load_form_weights()["weights"]
    states = states.assign(pre_score=scores(states, form_weights, "pre_"))
    states["post_score"] = scores(states, form_weights, "post_")
    league_mean = states.groupby(["home", "year"])["pre_score"].mean().rename("league_mean")

    last = states.groupby(["teamid", "year"]).tail(1).join(league_mean, on=["home", "year"])
    seasons = last.assign(form=last["post_score"] - last["league_mean"])
    seasons = seasons.rename(columns={"date": "latest_date"})[
        ["teamid", "teamname", "home", "year", "latest_date", "form"]
    ]

    now = states.groupby("teamid").tail(1)
    newest = league_mean.reset_index().sort_values("year").groupby("home").tail(1).set_index("home")["league_mean"]
    now = now.assign(form=now["post_score"] - now["home"].map(newest), latest_date=now["date"])
    now = now[["teamid", "teamname", "home", "year", "latest_date", "form", "form_games"]]
    return now.reset_index(drop=True), seasons.reset_index(drop=True)


def glorelo_ratings(forms, elos):
    """GlorELO+ ratings: each team's Elo plus its Form in Elo points.

    Args:
        forms: Rows from `team_forms` (teamname, home, form, ...).
        elos: `get_latest_elos` or `get_season_elos` rows (teamname, elo, ...),
            matched on team name (and year when both have one).
    Returns:
        DataFrame with teamname, league, year, form (Elo points), elo, glorelo and
        latest_date, highest rating first.
    """
    keys = ["teamname", "year"] if "year" in elos.columns and "year" in forms.columns else ["teamname"]
    e = elos.drop_duplicates(keys)[keys + ["elo"]]
    df = forms.drop_duplicates(keys).merge(e, on=keys, how="inner")
    df = df.rename(columns={"home": "league"})
    df["form"] = FORM_POINTS * df["form"]
    df["glorelo"] = df["elo"] + df["form"]
    cols = ["teamname", "league", "year", "form", "elo", "glorelo", "latest_date"]
    return df[cols].sort_values("glorelo", ascending=False).reset_index(drop=True)
