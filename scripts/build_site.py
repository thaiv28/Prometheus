"""
build_site.py: Generates the static site in output/ from db/prometheus.db.
- Computes season stats (GLORY, and the sunset Record, Luck, GLORB and unadjusted
  GLORY) and forecasts (FORGE, Elo, and the sunset Form)
- Computes player stats (Player Elo, and AURA per player-season)
- Fetches upcoming and recent matches from Leaguepedia, predicts them, and keeps
  a prediction log (prometheus.schedule); renders predictions.html
- Renders index.html, one rankings page per metric, and one page per team and player

The parts live in prometheus/site/: config (metric registries, column configs,
paths), render (Jinja environment and small pages), registers (register rows, the
home and rankings pages), teams, players, predictions and gamelogs. This script
loads the data once and runs them in order (main): season stats, forecasts and
players each compute and render their pages and return what later steps need, then
the predictions, the home page and the team and player pages.
"""

import datetime
import json
import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from prometheus import aura, markets
from prometheus.elo import (
    get_elo_history,
    get_latest_elos,
    get_player_elos,
    get_player_history,
    get_season_elos,
)
from prometheus.forge import FORM_POINTS, team_forms
from prometheus.form import form_states, load_form_games, opponent_adjust
from prometheus.player_tables import PlayerTables
from prometheus.ranking import load_glory_games
from prometheus.season import get_luck, get_record, load_season_games
from prometheus.site import config as site_config
from prometheus.site.config import (
    AURA_COLUMNS,
    ELO_COLUMNS,
    ELO_METRICS,
    FORECASTS,
    FORM_COLUMNS,
    LUCK_COLUMNS,
    METRIC_COLUMNS,
    PLAYER_ELO_COLUMNS,
    PLAYER_METRICS,
    RECORD_COLUMNS,
    ROLE_ORDER,
)
from prometheus.site.gamelogs import add_game_logs
from prometheus.site.players import (
    aura_rows_and_seasons,
    player_pages_and_rows,
    render_player_pages,
    write_player_index,
)
from prometheus.site.predictions import (
    predictions_view,
    render_predictions,
    render_results,
    update_predictions,
    warn_missing_results,
    write_kalshi_alert,
)
from prometheus.site.registers import (
    _active,
    _forecast_records,
    _rankings,
    _season_page,
    forge_register,
    render_index,
    render_rankings_page,
)
from prometheus.site.render import (
    copy_static,
    env,
    render_404,
    render_redirect,
    render_sunset,
)
from prometheus.site.teams import (
    _team_pages,
    render_team_pages,
    team_rosters,
    write_team_index,
)


def _league_order(leagues, majors):
    """Major leagues in their usual order, then the rest alphabetically."""
    leagues = set(leagues)
    return [l for l in majors if l in leagues] + sorted(leagues - set(majors))


@dataclass
class SeasonStats:
    glory: pd.DataFrame  # qualified team-seasons (5+ major-league games)
    glory_all: pd.DataFrame  # every team-season, for team pages


@dataclass
class Forecasts:
    latest_elos: pd.DataFrame
    team_elo_rows: list
    states: pd.DataFrame  # Form states before every team-game
    prediction_log: dict
    coverage: dict | None  # None when the schedule fetch was skipped or failed
    forge: pd.DataFrame
    forge_seasons: pd.DataFrame
    forge_rows: list
    forge_config: dict


@dataclass
class Players:
    tables: PlayerTables
    history: pd.DataFrame
    latest: pd.DataFrame
    rows: list  # Player Elo register rows
    pages: dict  # player page context by slug
    slugs: dict  # player id -> slug, for listed players
    listed: pd.DataFrame
    aura_games: pd.DataFrame
    aura_rows: list


def render_fixed_pages():
    render_404()
    render_sunset()
    render_redirect("glory_plus", "glory.html", "GLORY+ is now part of GLORY")
    # GlorELO+ was renamed FORGE; keep its old address working.
    render_redirect("glorelo_plus", "forge.html", "GlorELO+ is now FORGE")


def season_stats() -> SeasonStats:
    """GLORY and the sunset season stats: compute and render their pages."""
    # Read each year's games once and share them across every GLORY variant.
    games = load_glory_games()
    record_all = get_record(load_season_games())
    glory_df = _rankings(games, 5, True, opponent_adjusted="record", record=record_all)
    glory_all = _rankings(
        games, 1, False, opponent_adjusted="record", record=record_all
    )
    glory_unadjusted_df = _rankings(games, 5, True)
    glorb_df = _rankings(games, 5, True, baseline=True)

    # Record covers the same team-seasons as GLORY (5+ major-league games), with
    # GLORY's league; its win % and games count every game of the season.
    record_df = (
        glory_df[["teamname", "year", "league"]]
        .merge(
            record_all.sort_values("games").drop_duplicates(
                ["teamname", "year"], keep="last"
            )[["teamname", "year", "record", "win_pct", "games"]],
            on=["teamname", "year"],
        )
        .assign(
            win_pct=lambda d: (d["win_pct"] * 100).round(1),
            record=lambda d: d["record"].round(1),
        )
    )
    luck_df = get_luck(games, minimum_matches=5).assign(
        win_pct=lambda d: (d["win_pct"] * 100).round(1),
        expected=lambda d: (d["expected"] * 100).round(1),
        luck_wins=lambda d: d["luck_wins"].round(1),
    )[["teamname", "year", "league", "luck_wins", "win_pct", "expected", "games"]]

    _season_page("glory", glory_df, METRIC_COLUMNS, "score")
    _season_page("record", record_df, RECORD_COLUMNS, "record")
    reach = float(np.ceil(luck_df["luck_wins"].abs().max() / 5) * 5)
    _season_page("luck", luck_df, LUCK_COLUMNS, "luck_wins", domain=[-reach, reach])
    _season_page("glory_unadjusted", glory_unadjusted_df, METRIC_COLUMNS, "score")
    _season_page("glorb", glorb_df, METRIC_COLUMNS, "score")
    return SeasonStats(glory=glory_df, glory_all=glory_all)


def forecasts(majors) -> Forecasts:
    """Elo, Form and FORGE pages, and the prediction log brought up to date."""
    # Forecast pages open on "now" rows (current ratings) and also carry one row per
    # team-season (rating at the end of that year) for the season picker.
    cfg = ELO_METRICS["game_length_elo"]
    latest_elos = get_latest_elos(cfg["method"])
    season_elos = get_season_elos(cfg["method"])
    # Every team's current rating is a "now" row, so search finds retired teams;
    # the default view shows only the active ones.
    team_elo_rows = _forecast_records(
        latest_elos.assign(active=_active(latest_elos)), season_elos, ("elo",)
    )
    render_rankings_page(
        cfg,
        team_elo_rows,
        {
            "valueKey": "elo",
            "columns": ELO_COLUMNS,
            "defaultSort": "elo",
            "kind": "rating",
        },
        {
            "years": sorted(int(y) for y in season_elos["year"].unique()),
            "leagues": _league_order(
                set(latest_elos["league"]) | set(season_elos["league"]), majors
            ),
        },
    )

    # Form for every team in every league, as of now and at the end of each season.
    states = form_states(opponent_adjust(load_form_games()))
    forms_now, forms_seasons = team_forms(states)
    games_through = pd.to_datetime(states["date"]).max()
    env.globals["games_through"] = games_through.strftime("%B %-d, %Y")
    prediction_log, coverage = update_predictions(states)
    warn_missing_results(prediction_log, str(games_through)[:10])
    form_now = forms_now.rename(columns={"home": "league"}).assign(
        form=lambda d: FORM_POINTS * d["form"]
    )
    form_seasons = forms_seasons.rename(columns={"home": "league"}).assign(
        form=lambda d: FORM_POINTS * d["form"]
    )
    render_rankings_page(
        FORECASTS["form"],
        _forecast_records(
            form_now.assign(active=_active(form_now)), form_seasons, ("form",)
        ),
        {
            "valueKey": "form",
            "columns": FORM_COLUMNS,
            "defaultSort": "form",
            "kind": "rating",
        },
        {
            "years": sorted(int(y) for y in form_seasons["year"].unique()),
            "leagues": _league_order(
                set(form_now["league"]) | set(form_seasons["league"]), majors
            ),
        },
    )

    forge, forge_seasons, forge_rows, forge_config, forge_filters = forge_register(
        forms_now, forms_seasons, latest_elos, season_elos, majors
    )
    render_rankings_page(FORECASTS["forge"], forge_rows, forge_config, forge_filters)
    return Forecasts(
        latest_elos=latest_elos,
        team_elo_rows=team_elo_rows,
        states=states,
        prediction_log=prediction_log,
        coverage=coverage,
        forge=forge,
        forge_seasons=forge_seasons,
        forge_rows=forge_rows,
        forge_config=forge_config,
    )


def players(majors) -> Players:
    """Player Elo and AURA pages; player pages are rendered later, with game logs."""
    method = ELO_METRICS["game_length_elo"]["method"]
    # One read of the player tables for player Elo, AURA and the game logs.
    tables = PlayerTables(method, aura.STATS, aura.MINUTES)
    history = get_player_history(method, tables)
    latest, seasons = get_player_elos(method, history)
    rows, pages, listed = player_pages_and_rows(history, latest, seasons)
    slugs = listed.set_index("playerid")["slug"]
    render_rankings_page(
        PLAYER_METRICS["player_elo"],
        rows,
        {
            "valueKey": "elo",
            "columns": PLAYER_ELO_COLUMNS,
            "defaultSort": "elo",
            "kind": "rating",
            "entity": "player",
        },
        {
            "years": sorted({int(r["year"]) for r in rows if not r["now"]}),
            "leagues": _league_order({r["league"] for r in rows}, majors),
        },
    )

    # AURA per player-season (major leagues), on its own page and on player pages.
    aura_games = aura.get_aura(tables=tables)
    aura_seasons = aura.season_aura(aura_games, majors)
    aura_rows, aura_by_player = aura_rows_and_seasons(aura_seasons, slugs)
    for slug, page in pages.items():
        page["aura_seasons"] = aura_by_player.get(slug, [])
    reach = float(np.ceil(max(abs(r["aura"]) for r in aura_rows) / 5) * 5)
    render_rankings_page(
        PLAYER_METRICS["aura"],
        aura_rows,
        {
            "valueKey": "aura",
            "columns": AURA_COLUMNS,
            "defaultSort": "aura",
            "kind": "season",
            "entity": "player",
            "domain": [-reach, reach],
        },
        {
            "years": sorted({int(r["year"]) for r in aura_rows}),
            "leagues": [l for l in majors if any(r["league"] == l for r in aura_rows)],
            "roles": ROLE_ORDER,
        },
    )
    return Players(
        tables=tables,
        history=history,
        latest=latest,
        rows=rows,
        pages=pages,
        slugs=slugs.to_dict(),
        listed=listed,
        aura_games=aura_games,
        aura_rows=aura_rows,
    )


def write_json(name, data, **kwargs):
    with open(os.path.join(site_config.OUTPUT_DIR, name), "w") as f:
        f.write(json.dumps(data, separators=(",", ":"), **kwargs))


def predictions_pages(fc: Forecasts, teams) -> dict:
    """The Kalshi alert, the predictions and results pages, and the live JSON files."""
    log = fc.prediction_log
    write_kalshi_alert(log, fc.coverage, teams)
    now = datetime.datetime.now(datetime.UTC)
    predictions = predictions_view(log, teams, now)
    render_predictions(predictions, fc.coverage)
    render_results(predictions)
    write_json("predictions.json", markets.published_log(log), ensure_ascii=False)
    # The hourly price job (scripts/update_prices.py) replaces this between builds.
    write_json("kalshi.json", markets.prices_file(log, now))
    return predictions


def main():
    os.makedirs(site_config.OUTPUT_DIR, exist_ok=True)
    copy_static()
    last_update = datetime.datetime.now().strftime("%B %-d, %Y")
    majors = env.globals["major_leagues"]

    render_fixed_pages()
    seasons = season_stats()
    fc = forecasts(majors)
    pl = players(majors)

    # ---- Team pages, predictions and the home page ----------------------------
    rosters = team_rosters(
        pl.history, pl.slugs, pl.latest.set_index("playerid")["elo"].to_dict()
    )
    pages = _team_pages(
        seasons.glory_all,
        fc.forge_seasons,
        fc.forge,
        get_elo_history("game_length"),
        fc.latest_elos,
        seasons.glory,
        rosters,
    )
    predictions = predictions_pages(fc, set(pages))
    render_index(
        [r for r in fc.forge_rows if r["league"] in majors],
        fc.team_elo_rows,
        pl.rows,
        {
            "glory": len(seasons.glory),
            "forge": len(fc.forge),
            "game_length_elo": len(fc.latest_elos),
            "player_elo": sum(r["now"] and r["active"] for r in pl.rows),
            "aura": len(pl.aura_rows),
        },
        fc.forge_config,
        last_update,
        fixtures=predictions["home"],
    )
    add_game_logs(
        pages,
        pl.pages,
        fc.states,
        fc.prediction_log,
        pl.slugs,
        pl.aura_games,
        pl.tables,
    )
    render_team_pages(pages)
    write_team_index(pages)
    render_player_pages(pl.pages)
    write_player_index(pl.listed)

    print(
        f"Static site generated in {site_config.OUTPUT_DIR}/ ({len(pages)} team pages, {len(pl.pages)} player pages)"
    )


if __name__ == "__main__":
    main()
