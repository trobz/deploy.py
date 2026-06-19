from __future__ import annotations

from typing import Annotated

import typer

from trobz_deploy.utils.config import DeployType, load_config, normalize_hosts, resolve_options
from trobz_deploy.utils.executor import Executor, ExecutorError, watch_logs_multi


def restart(
    ctx: typer.Context,
    instance_name: Annotated[str, typer.Argument()],
    ssh_host: Annotated[str | None, typer.Argument()] = None,
    deploy_type: Annotated[
        DeployType | None,
        typer.Option("--type", help="Deployment type (auto-detected from instance name prefix if omitted)."),
    ] = None,
    ssh_port: Annotated[int | None, typer.Option("-p", "--port", help="SSH port on the remote host.")] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help=(
                "Stream service logs with journalctl after restarting. "
                "Also merge with odoo and click-odoo-update logs if applicable."
            ),
        ),
    ] = False,
) -> None:
    """Restart the systemd unit for a deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)
    try:
        opts = resolve_options(
            cfg,
            instance_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            deploy_type=deploy_type.value if deploy_type else None,
        )
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    eff_ssh_port: int | None = opts.get("ssh_port")

    try:
        host_specs = normalize_hosts(opts.get("ssh_host"), opts.get("ssh_user"))
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    multi_host = len(host_specs) > 1
    watch_targets: list[tuple[Executor, str, str]] = []

    for i, host_spec in enumerate(host_specs):
        if multi_host:
            typer.secho(
                f"\n=== Host {i + 1}/{len(host_specs)}: {host_spec['host'] or 'localhost'} ===", fg="blue", bold=True
            )

        executor = Executor(host_spec["host"], ctx.obj["verbose"], ssh_port=eff_ssh_port)

        typer.secho(f"\nRestarting {instance_name!r}…", fg="green")
        try:
            executor.run(f"systemctl --user restart {instance_name}")
        except ExecutorError as exc:
            typer.echo(typer.style(f"Restart failed: {exc}", fg="red"), err=True)
            raise typer.Exit(code=1) from exc

        typer.secho(f"\nInstance {instance_name!r} restarted.", fg="green")

        if watch or host_spec["watch"]:
            watch_targets.append((executor, opts["type"], instance_name))

    if watch_targets:
        watch_logs_multi(watch_targets)
