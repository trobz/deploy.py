from __future__ import annotations

import click

from deploy.utils.config import load_config
from deploy.utils.executor import Executor, ExecutorError


@click.command()
@click.argument("instance_name")
@click.argument("ssh_host", required=False)
@click.option(
    "-p",
    "--port",
    "ssh_port",
    type=int,
    default=None,
    help="SSH port on the remote host.",
)
@click.pass_context
def status(
    ctx: click.Context,
    instance_name: str,
    ssh_host: str | None,
    ssh_port: int | None,
) -> None:
    """Show status of a deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)

    # Resolve ssh_host/ssh_port: CLI arg > config value
    eff_ssh_host: str | None = ssh_host if ssh_host is not None else cfg.get("ssh_host")
    eff_ssh_port: int | None = ssh_port if ssh_port is not None else cfg.get("ssh_port")

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    instance_path = f"$HOME/{instance_name}"

    # Step 2: Verify instance directory exists
    try:
        executor.run(f"test -d {instance_path}")
    except ExecutorError:
        msg = f"Instance directory not found: ~/{instance_name}"
        raise click.ClickException(msg) from None

    # Step 3: Git info
    try:
        remote_url = executor.capture("git remote get-url origin", cwd=instance_path)
        branch = executor.capture("git rev-parse --abbrev-ref HEAD", cwd=instance_path)
        commit = executor.capture("git rev-parse --short HEAD", cwd=instance_path)
    except ExecutorError as exc:
        msg = f"Failed to get git info: {exc}"
        raise click.ClickException(msg) from exc

    # Step 4: systemd unit status
    unit_line = "unknown"
    try:
        raw = executor.capture(
            f"systemctl --user show {instance_name} --property=ActiveState,SubState,ActiveEnterTimestamp"
        )
        props: dict[str, str] = {}
        for line in raw.splitlines():
            if "=" in line:
                key, _, val = line.partition("=")
                props[key.strip()] = val.strip()

        active = props.get("ActiveState", "unknown")
        sub = props.get("SubState", "unknown")
        ts = props.get("ActiveEnterTimestamp", "")
        # Timestamp format: "Mon 2026-03-09 08:12:03 UTC"
        since = " ".join(ts.split()[1:3]) if ts else ""
        unit_line = f"{active} ({sub})"
        if since:
            unit_line += f" since {since}"
    except ExecutorError:
        pass

    click.echo(f"Instance:  {instance_name}")
    click.echo(f"Remote:    {remote_url}")
    click.echo(f"Branch:    {branch} ({commit})")
    click.echo(f"Unit:      {unit_line}")
