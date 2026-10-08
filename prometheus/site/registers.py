"""Register rows and the home and rankings pages."""

import os

import numpy as np
import pandas as pd

from prometheus.forge import (
    CROSS_REGION_ELO_WEIGHT,
    ELO_WEIGHT,
    forge_ratings,
)
from prometheus.ranking import get_glory_ranking
from prometheus.site import config as site_config
from prometheus.site.config import (
    ACTIVE_WINDOW,
    ELO_METRICS,
    FORECASTS,
    FORGE_COLUMNS,
    HOME_TOP,
    METRICS,
    PLAYER_METRICS,
    SECTIONS,
)
from prometheus.site.render import env, slugify, write
from prometheus.types import ALL_MAJOR_LEAGUES, INTERNATIONAL_LEAGUES


def rankings(
    games,
    minimum_matches,
    z_scores,
    baseline=False,
    opponent_adjusted=False,
    record=None,
):
    return get_glory_ranking(
        year=sorted(games),
        league=ALL_MAJOR_LEAGUES,
        games=games,
        baseline=baseline,
        z_scores=z_scores,
        minimum_matches=minimum_matches,
        opponent_adjusted=opponent_adjusted,
        record=record,
    )


def forecast_records(now, seasons, rating_cols):
    """Rows for a forecast page: `now` rows (current ratings) then team-season rows.

    A `now` row is shown by default when it is `active` (missing means active).
    """
    rows = []
    for df, is_now in ((now, True), (seasons, False)):
        for r in _records(df):
            r["now"] = is_now
            r["active"] = bool(r.get("active", True))
            r["latest_date"] = str(r["latest_date"])[:10]
            for col in rating_cols:
                r[col] = round(float(r[col]), 1)
            rows.append(r)
    return rows


def _records(df):
    df = df.copy()
    df["slug"] = df["teamname"].apply(slugify)
    df["year"] = df["year"].astype(int)
    return df.to_dict(orient="records")


def _rating_bar(values):
    """Bar lengths (0-100) on the scale the metric's own page uses: whole hundreds
    of Elo points around every value in its register."""
    lo = np.floor(values.min() / 100) * 100
    hi = np.ceil(values.max() / 100) * 100
    return lambda v: round(float((v - lo) / (hi - lo) * 100), 1)


def render_index(
    forge_rows,
    team_elo_rows,
    player_rows,
    entry_counts,
    forge_config,
    last_update,
    fixtures=None,
):
    """Home: FORGE's head to head and top teams, then the top of team and player Elo.

    Each `*_rows` argument holds the register's "now" rows (every current team or
    player); the active ones lead the tables, scaled like their own pages.
    """

    def top(rows, value_key):
        df = pd.DataFrame(rows)
        bar = _rating_bar(df[value_key])
        df = df[df["active"]].sort_values(value_key, ascending=False).head(HOME_TOP)
        return [{**r, "bar": bar(r[value_key])} for r in df.to_dict(orient="records")]

    forge_now = [r for r in forge_rows if r["now"]]
    write(
        os.path.join(site_config.OUTPUT_DIR, "index.html"),
        env.get_template("index.html.j2").render(
            page_key="index",
            root_path="",
            last_update=last_update,
            sections=SECTIONS,
            entry_counts=entry_counts,
            forge=FORECASTS["forge"],
            forge_top=top(forge_now, "forge"),
            forge_rows=sorted(forge_now, key=lambda r: -r["forge"]),
            forge_config=forge_config,
            fixtures=fixtures or [],
            team_elo=ELO_METRICS["game_length_elo"],
            team_elo_top=top([r for r in team_elo_rows if r["now"]], "elo"),
            player_elo=PLAYER_METRICS["player_elo"],
            player_elo_top=top([r for r in player_rows if r["now"]], "elo"),
        ),
    )


def render_rankings_page(metric, rows, config, filters):
    write(
        os.path.join(site_config.OUTPUT_DIR, f"{metric['key']}.html"),
        env.get_template("rankings.html.j2").render(
            page_key=metric["key"],
            root_path="",
            metric=metric,
            rows=rows,
            config=config,
            filters=filters,
        ),
    )


def season_page(key, df, columns, value_key, domain=None):
    config = {
        "valueKey": value_key,
        "columns": columns,
        "defaultSort": value_key,
        "kind": "season",
    }
    if domain is not None:
        config["domain"] = domain
    render_rankings_page(
        METRICS[key],
        _records(df),
        config,
        {
            "years": sorted(int(y) for y in df["year"].unique()),
            "leagues": sorted(df["league"].unique()),
        },
    )


def active(df):
    """True for rows whose last game is within ACTIVE_WINDOW of the newest game."""
    played = pd.to_datetime(df["latest_date"])
    return played >= played.max() - ACTIVE_WINDOW


def forge_register(forms_now, forms_seasons, latest_elos, season_elos, majors):
    """FORGE for every team with Form, each on its home league's scale: now (active
    teams, current Elo) and at the end of each season (that year's season-end Elo).

    Returns (now, seasons, rows, page config, filters). The config carries each
    league's slope (log-odds per point of FORGE gap) for the head to head.
    """
    # A team whose only games one year were at an international event has no
    # league scale, so it is left out.
    domestic = lambda forms: forms[~forms["home"].isin(INTERNATIONAL_LEAGUES)]
    now = forge_ratings(domestic(forms_now), latest_elos)
    now = now[active(now)].reset_index(drop=True)
    seasons = forge_ratings(domestic(forms_seasons), season_elos)
    rows = forecast_records(
        now.drop(columns="slope"),
        seasons.drop(columns="slope"),
        ("forge", "elo", "form"),
    )
    slopes = (
        pd.concat([now, seasons]).drop_duplicates("league").set_index("league")["slope"]
    )
    config = {
        "valueKey": "forge",
        "columns": FORGE_COLUMNS,
        "defaultSort": "forge",
        "kind": "rating",
        "leagueScales": True,
        "majorLeagues": list(majors),
        "weights": {
            "elo": ELO_WEIGHT,
            "crossRegionElo": CROSS_REGION_ELO_WEIGHT,
            "leagues": {l: float(slopes[l]) for l in sorted(slopes.index)},
        },
    }
    filters = {
        "years": sorted(int(y) for y in seasons["year"].unique()),
        "leagues": [l for l in majors if l in slopes.index]
        + sorted(set(slopes.index) - set(majors)),
    }
    return now, seasons, rows, config, filters
