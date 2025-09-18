from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from prometheus.ranking import get_glory_ranking
from prometheus.types import Metric, League
from typing import Annotated
from prometheus.utils import filter_leagues, print_rankings_table

app = typer.Typer()
console = Console()


@app.command("rankings")
def rankings(
    metric: Annotated[Metric, typer.Argument(help="Metric to rank")],
    league: Annotated[list[League], typer.Option(help="List of leagues to filter")] = [
        League.MAJOR
    ],
    year: Annotated[
        list[int], typer.Option(help="Year to filter. Default all years")
    ] = None,
    n: Annotated[int, typer.Option(help="Number of results to show")] = 10,
):
    """Fetch and display rankings."""
    # TODO: add support for range of years. ex: (2021 - 2023) vs (2021, 2022, 2023)
    filtered_leagues = filter_leagues(league, year)
    try:
        match metric:
            case "glory":
                df = get_glory_ranking(year=year, league=filtered_leagues)
            case "glorb":
                df = get_glory_ranking(
                    year=year, league=filtered_leagues, baseline=True
                )
            case _:
                typer.echo(f"Metric {metric} not supported.")
    except ValueError:
        typer.echo("No data found for given criteria.")
        raise typer.Exit(code=1)

    print_rankings_table(df, metric, league, year, n, console)


@app.command("weights")
def weights():
    """Fetch and display model weights."""
    typer.echo("Fetching weights...")


if __name__ == "__main__":
    app()
