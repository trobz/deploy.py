from __future__ import annotations

from typing import Annotated

import typer

from trobz_deploy.utils.config import load_config
from trobz_deploy.utils.executor import Executor, ExecutorError


def restart(
    ctx: typer.Context,
    instance_name: Annotated[str, typer.Argument()],
    ssh_host: Annotated[str | None, typer.Argument()] = None,
    ssh_port: Annotated[int | None, typer.Option("-p", "--port", help="SSH port on the remote host.")] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", help="Stream service logs with journalctl after restarting."),
    ] = False,
) -> None:
    """Restart the systemd unit for a deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)

    eff_ssh_host: str | None = ssh_host if ssh_host is not None else cfg.get("ssh_host")
    eff_ssh_port: int | None = ssh_port if ssh_port is not None else cfg.get("ssh_port")

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)

    typer.secho(f"\nRestarting {instance_name!r}…", fg="green")
    try:
        executor.run(f"systemctl --user restart {instance_name}")
    except ExecutorError as exc:
        typer.echo(typer.style(f"Restart failed: {exc}", fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(f"\nInstance {instance_name!r} restarted.", fg="green")

    if watch:
        typer.secho("\nWatching service logs (Ctrl+C to stop)…", fg="cyan")
        try:
            executor.stream(f"journalctl --user -u {instance_name} -f")
        except KeyboardInterrupt:
            typer.echo()
