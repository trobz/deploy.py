from __future__ import annotations

from typing import Annotated, Any

import typer

from trobz_deploy.utils.config import DeployType, load_config, normalize_hosts, resolve_options
from trobz_deploy.utils.executor import Executor, ExecutorError, watch_logs_multi


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


def _perform_status(
    opts: dict[str, Any],
    instance_name: str,
    host_label: str | None = None,
) -> Executor:
    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")

    executor = Executor(eff_ssh_host, opts["verbose"], ssh_port=eff_ssh_port)
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
    has_repo = bool(opts.get("repo_url"))
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

    if host_label:
        typer.echo(f"Host:      {host_label}")
    typer.echo(f"Instance:  {instance_name}")
    if has_repo:
        typer.echo(f"Remote:    {remote_url}")
        typer.echo(f"Branch:    {branch} ({commit})")
    typer.echo(f"Unit:      {unit_line}")

    return executor


def status(
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
                "Stream service logs with journalctl after showing status. "
                "Also merge with odoo and click-odoo-update logs if applicable."
            ),
        ),
    ] = False,
) -> None:
    """Show status of a deployment instance."""
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
    opts["verbose"] = ctx.obj["verbose"]

    try:
        host_specs = normalize_hosts(opts.get("ssh_host"), opts.get("ssh_user"))
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    multi_host = len(host_specs) > 1
    watch_targets: list[tuple[Executor, str, str]] = []

    for i, host_spec in enumerate(host_specs):
        if multi_host and i:
            typer.echo()

        host_opts = dict(opts)
        host_opts["ssh_host"] = host_spec["host"]
        host_label = (host_spec["host"] or "localhost") if multi_host else None

        executor = _perform_status(host_opts, instance_name, host_label)

        if watch or host_spec["watch"]:
            watch_targets.append((executor, opts["type"], instance_name))

    if watch_targets:
        watch_logs_multi(watch_targets)
