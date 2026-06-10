from __future__ import annotations

from importlib.metadata import version
from typing import Annotated

import typer

from trobz_deploy.command.configure import configure
from trobz_deploy.command.restart import restart
from trobz_deploy.command.status import status
from trobz_deploy.command.update import update

app = typer.Typer(help="Deploy and manage applications on remote servers over SSH.")


def version_callback(value: bool):
    if value:
        typer.echo(f"trobz-deploy {version('trobz-deploy')}")
        raise typer.Exit()


@app.callback()
def cli(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            callback=version_callback,
            is_eager=True,
            help="Display the trobz-deploy version.",
        ),
    ] = False,
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
