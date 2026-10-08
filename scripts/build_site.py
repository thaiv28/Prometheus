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
loads the data once and runs them in order (main).
"""

import datetime
import json
import os

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


def main():
    os.makedirs(site_config.OUTPUT_DIR, exist_ok=True)
    copy_static()
    last_update = datetime.datetime.now().strftime("%B %-d, %Y")
    majors = env.globals["major_leagues"]

    # ---- Season stats ----------------------------------------------------
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

    render_404()
    render_sunset()
    render_redirect("glory_plus", "glory.html", "GLORY+ is now part of GLORY")
    # GlorELO+ was renamed FORGE; keep its old address working.
    render_redirect("glorelo_plus", "forge.html", "GlorELO+ is now FORGE")

    _season_page("glory", glory_df, METRIC_COLUMNS, "score")
    _season_page("record", record_df, RECORD_COLUMNS, "record")
    reach = float(np.ceil(luck_df["luck_wins"].abs().max() / 5) * 5)
    _season_page("luck", luck_df, LUCK_COLUMNS, "luck_wins", domain=[-reach, reach])
    _season_page("glory_unadjusted", glory_unadjusted_df, METRIC_COLUMNS, "score")
    _season_page("glorb", glorb_df, METRIC_COLUMNS, "score")

    # ---- Forecasts -------------------------------------------------------
    # Forecast pages open on "now" rows (current ratings) and also carry one row per
    # team-season (rating at the end of that year) for the season picker.
    cfg = ELO_METRICS["game_length_elo"]
    latest_elos = get_latest_elos(cfg["method"])
    season_elos = get_season_elos(cfg["method"])
    # Every team's current rating is a "now" row, so search finds retired teams;
    # the default view shows only the active ones.
    leagues = set(latest_elos["league"]) | set(season_elos["league"])
    league_order = [l for l in majors if l in leagues] + sorted(leagues - set(majors))
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
            "leagues": league_order,
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
    form_leagues = set(form_now["league"]) | set(form_seasons["league"])
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
            "leagues": [l for l in majors if l in form_leagues]
            + sorted(form_leagues - set(majors)),
        },
    )

    forge, forge_seasons, forge_rows, forge_config, forge_filters = forge_register(
        forms_now, forms_seasons, latest_elos, season_elos, majors
    )
    render_rankings_page(FORECASTS["forge"], forge_rows, forge_config, forge_filters)

    # ---- Players ---------------------------------------------------------
    # One read of the player tables for player Elo, AURA and the game logs.
    player_tables = PlayerTables(cfg["method"], aura.STATS, aura.MINUTES)
    player_history = get_player_history(cfg["method"], player_tables)
    player_latest, player_seasons = get_player_elos(cfg["method"], player_history)
    player_rows, player_pages, listed_players = player_pages_and_rows(
        player_history, player_latest, player_seasons
    )
    player_leagues = {r["league"] for r in player_rows}
    render_rankings_page(
        PLAYER_METRICS["player_elo"],
        player_rows,
        {
            "valueKey": "elo",
            "columns": PLAYER_ELO_COLUMNS,
            "defaultSort": "elo",
            "kind": "rating",
            "entity": "player",
        },
        {
            "years": sorted({int(r["year"]) for r in player_rows if not r["now"]}),
            "leagues": [l for l in majors if l in player_leagues]
            + sorted(player_leagues - set(majors)),
        },
    )

    # AURA per player-season (major leagues), on its own page and on player pages.
    aura_games = aura.get_aura(tables=player_tables)
    aura_seasons = aura.season_aura(aura_games, majors)
    aura_rows, aura_by_player = aura_rows_and_seasons(
        aura_seasons, listed_players.set_index("playerid")["slug"]
    )
    for slug, page in player_pages.items():
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

    # ---- Index and team pages -----------------------------------------------
    elo_history = get_elo_history("game_length")
    rosters = team_rosters(
        player_history,
        listed_players.set_index("playerid")["slug"].to_dict(),
        player_latest.set_index("playerid")["elo"].to_dict(),
    )
    pages = _team_pages(
        glory_all, forge_seasons, forge, elo_history, latest_elos, glory_df, rosters
    )
    write_kalshi_alert(prediction_log, coverage, set(pages))
    predictions = predictions_view(
        prediction_log, set(pages), datetime.datetime.now(datetime.UTC)
    )
    render_predictions(predictions, coverage)
    render_results(predictions)
    with open(os.path.join(site_config.OUTPUT_DIR, "predictions.json"), "w") as f:
        f.write(
            json.dumps(
                markets.published_log(prediction_log),
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
    # The hourly price job (scripts/update_prices.py) replaces this between builds.
    with open(os.path.join(site_config.OUTPUT_DIR, "kalshi.json"), "w") as f:
        f.write(
            json.dumps(
                markets.prices_file(
                    prediction_log, datetime.datetime.now(datetime.UTC)
                ),
                separators=(",", ":"),
            )
        )
    render_index(
        [r for r in forge_rows if r["league"] in majors],
        team_elo_rows,
        player_rows,
        {
            "glory": len(glory_df),
            "forge": len(forge),
            "game_length_elo": len(latest_elos),
            "player_elo": sum(r["now"] and r["active"] for r in player_rows),
            "aura": len(aura_rows),
        },
        forge_config,
        last_update,
        fixtures=predictions["home"],
    )
    add_game_logs(
        pages,
        player_pages,
        states,
        prediction_log,
        listed_players.set_index("playerid")["slug"].to_dict(),
        aura_games,
        player_tables,
    )
    render_team_pages(pages)
    write_team_index(pages)

    render_player_pages(player_pages)
    write_player_index(listed_players)

    print(
        f"Static site generated in {site_config.OUTPUT_DIR}/ ({len(pages)} team pages, {len(player_pages)} player pages)"
    )


if __name__ == "__main__":
    main()
