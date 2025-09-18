from enum import Enum

import typer
from rich.console import Console
from rich.table import Table

from prometheus.ranking import get_glory_ranking
from prometheus.types import Metric, League
from typing import Annotated

app = typer.Typer()
console = Console()


@app.command("rankings")
def rankings(
    metric: Annotated[Metric, typer.Argument(help="Metric to rank (e.g. glory)")],
    league: Annotated[
        list[League], typer.Option(help="List of leagues to filter")
    ] = None,
    year: Annotated[int, typer.Option(help="Year to filter")] = None,
    n: Annotated[int, typer.Option(help="Number of results to show")] = 10,
):
    """Fetch and display rankings."""
    try:
        match metric:
            case "glory":
                df = get_glory_ranking(year=year, league=league)
            case _:
                typer.echo(f"Metric {metric} not supported.")
    except ValueError:
        typer.echo("No data found for given criteria.")
        raise typer.Exit(code=1)

    df = df.head(n)

    title = f"{metric.upper()} Rankings"
    filter_strs = []
    if league:
        filter_strs.append(", ".join(l.value for l in league))
    if year:
        filter_strs.append(str(year))

    title += " (" + " | ".join(filter_strs) + ")"

    table = Table(title)
    table.add_row(df.to_string(float_format=lambda _: "{:.2f}".format(_)))
    console.print(table)


@app.command("weights")
def weights():
    """Fetch and display model weights."""
    typer.echo("Fetching weights...")


if __name__ == "__main__":
    app()
