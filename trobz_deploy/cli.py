from __future__ import annotations

from typing import Annotated

import typer

from trobz_deploy.command.configure import configure
from trobz_deploy.command.restart import restart
from trobz_deploy.command.status import status
from trobz_deploy.command.update import update

app = typer.Typer(help="Deploy and manage applications on remote servers over SSH.")


@app.callback()
def cli(
    ctx: typer.Context,
    config: Annotated[
        str,
        typer.Option(show_default=True, metavar="FILE", help="Path to the configuration file."),
    ] = "deploy.yml",
    verbose: Annotated[
        bool,
        typer.Option("--verbose", help="Print each remote command and its output as it runs."),
    ] = False,
) -> None:
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose


app.command()(configure)
app.command()(update)
app.command()(restart)
app.command()(status)
