from __future__ import annotations

from typing import Annotated

import typer

from trobz_deploy.utils.config import load_config
from trobz_deploy.utils.executor import Executor, ExecutorError


def _get_unit_line(executor: Executor, instance_name: str) -> str:
    try:
        raw = executor.capture(
            f"systemctl --user show {instance_name} --property=ActiveState,SubState,ActiveEnterTimestamp"
        )
    except ExecutorError:
        return "unknown"
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
    return unit_line


def _get_git_info(executor: Executor, instance_path: str) -> tuple[str, str, str]:
    remote_url = executor.capture("git remote get-url origin", cwd=instance_path)
    branch = executor.capture("git rev-parse --abbrev-ref HEAD", cwd=instance_path)
    commit = executor.capture("git rev-parse --short HEAD", cwd=instance_path)
    return remote_url, branch, commit


def status(
    ctx: typer.Context,
    instance_name: Annotated[str, typer.Argument()],
    ssh_host: Annotated[str | None, typer.Argument()] = None,
    ssh_port: Annotated[int | None, typer.Option("-p", "--port", help="SSH port on the remote host.")] = None,
    watch: Annotated[
        bool,
        typer.Option("--watch", help="Stream service logs with journalctl after showing status."),
    ] = False,
) -> None:
    """Show status of a deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)

    # Resolve ssh_host/ssh_port: CLI arg > config value
    eff_ssh_host: str | None = ssh_host if ssh_host is not None else cfg.get("ssh_host")
    eff_ssh_port: int | None = ssh_port if ssh_port is not None else cfg.get("ssh_port")

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    home_dir = executor.capture("echo $HOME")
    instance_path = f"{home_dir}/{instance_name}"

    # Step 2: Verify instance directory exists
    try:
        executor.run(f"test -d {instance_path}")
    except ExecutorError:
        msg = f"Instance directory not found: ~/{instance_name}"
        typer.echo(typer.style(msg, fg="red"), err=True)
        raise typer.Exit(code=1) from None

    # Step 3: Git info (skipped for no-repo service instances)
    has_repo = bool(cfg.get("repo_url"))
    remote_url = branch = commit = None
    if has_repo:
        try:
            remote_url, branch, commit = _get_git_info(executor, instance_path)
        except ExecutorError as exc:
            msg = f"Failed to get git info: {exc}"
            typer.echo(typer.style(msg, fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 4: systemd unit status
    unit_line = _get_unit_line(executor, instance_name)

    typer.echo(f"Instance:  {instance_name}")
    if has_repo:
        typer.echo(f"Remote:    {remote_url}")
        typer.echo(f"Branch:    {branch} ({commit})")
    typer.echo(f"Unit:      {unit_line}")

    if watch:
        executor.watch_logs(instance_name)
