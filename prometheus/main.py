import datetime
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from prometheus.elo import get_latest_elos, get_season_elos
from prometheus.form import form_states, load_form_games, opponent_adjust
from prometheus.forge import FORM_POINTS, forge_ratings, team_forms
from prometheus.ranking import get_glory_ranking, load_glory_games
from prometheus.season import get_luck, get_record, load_season_games
from prometheus.types import Metric, League, ScoreCols
from prometheus.utils import filter_leagues, parse_years, print_rankings_table

app = typer.Typer()
console = Console()


def _forecast(metric, years, leagues):
    """FORGE or Form for today's teams, or at the end of each season in `years`."""
    now, seasons = team_forms(form_states(opponent_adjust(load_form_games())))
    forms = now if years is None else seasons[seasons["year"].isin(years)]
    forms = forms[forms["home"].isin([l.value for l in leagues])]
    if metric == Metric.form:
        df = forms.rename(columns={"home": "league"}).assign(form=lambda d: FORM_POINTS * d["form"])
        return df[["teamname", "form", "year", "league"]].sort_values("form", ascending=False).reset_index(drop=True)
    elos = get_latest_elos("game_length") if years is None else get_season_elos("game_length")
    df = forge_ratings(forms, elos)
    return df[["teamname", "forge", "form", "elo", "year", "league"]].reset_index(drop=True)


@app.command("rankings")
def rankings(
    metric: Annotated[Metric, typer.Argument(help="Metric to rank")],
    league: Annotated[list[League], typer.Option(help="List of leagues to filter")] = [
        League.MAJOR
    ],
    year: Annotated[
        list[str],
        typer.Option(
            help="Year or range (2021-2023); repeat for more. Default all years, "
            "or now for forecasts (forge, form)"
        ),
    ] = None,
    n: Annotated[int, typer.Option(help="Number of results to show")] = 10,
    sort_by: Annotated[
        ScoreCols,
        typer.Option(help="Column to sort by (glory and glorb only)", show_default=True),
    ] = "score",
):
    """Fetch and display rankings."""
    try:
        years = parse_years(year)
    except ValueError as e:
        raise typer.BadParameter(str(e), param_hint="--year")
    filtered_leagues = filter_leagues(league, years)
    names = [l.value for l in filtered_leagues]
    try:
        match metric:
            case Metric.forge | Metric.form:
                df = _forecast(metric, years, filtered_leagues)
            case Metric.record:
                df = get_record(load_season_games(years), minimum_matches=5, leagues=names)
                df = df[["teamname", "record", "win_pct", "games", "year", "league"]].reset_index(drop=True)
            case Metric.luck:
                df = get_luck(load_glory_games(years), minimum_matches=5)
                df = df[df["league"].isin(names)][["teamname", "luck_wins", "win_pct", "expected", "games", "year", "league"]]
                df = df.sort_values("luck_wins", ascending=False).reset_index(drop=True)
            case _:
                df = get_glory_ranking(
                    year=years,
                    league=filtered_leagues,
                    baseline=metric == Metric.glorb,
                    # GLORY is opponent-adjusted; the sunset GLORB is not.
                    opponent_adjusted="record" if metric == Metric.glory else False,
                    minimum_matches=5,
                    sort_by=sort_by,
                    z_scores=True,
                )
    except ValueError:
        typer.echo("No data found for given criteria.")
        raise typer.Exit(code=1)

    print_rankings_table(df, metric.value, league, years, n, console)


@app.command("predict")
def predict(
    days: Annotated[int, typer.Option(help="Days ahead to show, from today (UTC)")] = 1,
    league: Annotated[list[str], typer.Option(help="Only these leagues (e.g. LCK, Worlds); repeat for more")] = None,
    major: Annotated[bool, typer.Option(help="Only major leagues and international events")] = False,
):
    """Predict upcoming pro matches: each team's chance to win the series and one game.

    Reads the schedule from Leaguepedia and rates both teams with today's FORGE
    (same major league) or Elo; doesn't touch the prediction log.
    """
    from prometheus import schedule

    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        fixtures = schedule.fetch_schedule(now.date(), (now + datetime.timedelta(days=days)).date() + datetime.timedelta(days=1))
    except Exception as e:  # network or rate limit
        typer.echo(f"Couldn't read the schedule from Leaguepedia: {e}")
        raise typer.Exit(code=1)
    ratings = schedule.current_ratings(form_states(opponent_adjust(load_form_games())))
    preds = schedule.predict(fixtures[fixtures["start"] > now], ratings, schedule.TeamMatcher(ratings.reset_index()))
    shown = [p for p in preds if p["matched"]
             and (not league or p["league"] in league)
             and (not major or schedule.is_major(p))]

    table = Table(title=f"Predictions, next {days} day{'s' if days != 1 else ''}")
    for col, justify in (("Start (UTC)", "left"), ("League", "left"), ("Team 1", "right"), ("Series", "center"),
                         ("Team 2", "left"), ("Bo", "right"), ("One game", "right"), ("By", "left")):
        table.add_column(col, justify=justify)
    for p in shown:
        s1 = round(100 * p["p_series"])
        g1 = round(100 * p["p_game"])
        table.add_row(
            p["start"].replace("T", " ").rstrip("Z"), p["league"],
            schedule.display_name(p, 1), f"{s1}–{100 - s1}", schedule.display_name(p, 2),
            str(p["best_of"]), f"{g1}–{100 - g1}", "FORGE" if p["method"] == "forge" else "Elo",
        )
    console.print(table)
    skipped = len(preds) - sum(p["matched"] for p in preds)
    if skipped:
        console.print(f"{skipped} scheduled matches have a team we don't rate.")


@app.command("weights")
def weights():
    """Fetch and display model weights."""
    typer.echo("Fetching weights...")


if __name__ == "__main__":
    app()
