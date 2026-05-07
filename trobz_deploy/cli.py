from __future__ import annotations

import click

from deploy.command.configure import configure
from deploy.command.status import status
from deploy.command.update import update


@click.group()
@click.option(
    "--config",
    default="deploy.yml",
    show_default=True,
    metavar="FILE",
    help="Path to the configuration file.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Print each remote command and its output as it runs.",
)
@click.pass_context
def cli(ctx: click.Context, config: str, verbose: bool) -> None:
    """Deploy and manage applications on remote servers over SSH."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = config
    ctx.obj["verbose"] = verbose


cli.add_command(configure)
cli.add_command(update)
cli.add_command(status)
