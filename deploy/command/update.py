from __future__ import annotations

import click

from deploy.utils.addons import get_addons_path
from deploy.utils.config import load_config, resolve_options
from deploy.utils.executor import Executor, ExecutorError
from deploy.utils.venv import setup_python_deps


@click.command()
@click.argument("instance_name")
@click.argument("ssh_host", required=False)
@click.option(
    "--type",
    "deploy_type",
    type=click.Choice(["odoo", "python", "service"]),
    default=None,
    help="Deployment type (auto-detected from instance name prefix if omitted).",
)
@click.option(
    "--db",
    default=None,
    help="Override the target database name (Odoo only).",
)
@click.option(
    "-p",
    "--port",
    "ssh_port",
    type=int,
    default=None,
    help="SSH port on the remote host.",
)
@click.option(
    "--ignore-hooks",
    "ignore_hooks",
    is_flag=True,
    default=False,
    help="Skip all hook execution.",
)
@click.pass_context
def update(  # noqa: C901
    ctx: click.Context,
    instance_name: str,
    ssh_host: str | None,
    deploy_type: str | None,
    db: str | None,
    ssh_port: int | None,
    ignore_hooks: bool,
) -> None:
    """Update an existing deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)
    try:
        opts = resolve_options(
            cfg,
            instance_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            deploy_type=deploy_type,
            db=db,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_type: str = opts["type"]
    eff_db: str = opts.get("db", instance_name)
    hooks: dict = opts.get("hooks", {})

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    home_dir = executor.capture("echo $HOME")
    instance_path = f"{home_dir}/{instance_name}"

    def run_hooks(hook_name: str) -> bool:
        """Execute all commands for *hook_name*. Returns True if all succeeded."""
        if ignore_hooks:
            return True
        for cmd in hooks.get(hook_name, []):
            try:
                executor.run(cmd, cwd=instance_path)
            except ExecutorError as exc:
                click.echo(f"Hook {hook_name!r} failed: {exc}", err=True)
                return False
        return True

    # Step 2: pre-update hooks (non-blocking)
    run_hooks("pre-update")

    # Step 3: pre-update-required hooks (blocking on failure)
    if not run_hooks("pre-update-required"):
        run_hooks("pre-update-fail")
        msg = "pre-update-required hook failed. Update aborted."
        raise click.ClickException(msg)

    # Step 4: pre-update-success
    run_hooks("pre-update-success")

    # Step 5: git pull
    try:
        executor.run(f"test -d {instance_path}/.git")
    except ExecutorError:
        msg = f"Instance directory not found or not a git repo: ~/{instance_name}"
        raise click.ClickException(msg) from None

    click.echo("Pulling latest code …")
    try:
        executor.run("git pull", cwd=instance_path)
    except ExecutorError as exc:
        run_hooks("post-update")
        run_hooks("post-update-fail")
        msg = f"git pull failed: {exc}"
        raise click.ClickException(msg) from exc

    # Step 6: Update dependencies / rebuild
    click.echo("Updating dependencies …")
    try:
        if eff_type == "odoo":
            executor.run(
                "if [ -f addons/repos.yaml ]; then cd addons/ && gitaggregate -c repos.yaml; fi",
                cwd=instance_path,
            )
            executor.run("odoo-venv update .venv --backup", cwd=instance_path)
        elif eff_type == "python":
            setup_python_deps(executor, instance_path)
        else:  # service
            build_cmd: str | None = opts.get("build")
            if build_cmd:
                executor.run(build_cmd, cwd=instance_path)
    except ExecutorError as exc:
        run_hooks("post-update")
        run_hooks("post-update-fail")
        msg = f"Dependency update failed: {exc}"
        raise click.ClickException(msg) from exc

    # Step 7: Apply changes
    click.echo("Applying changes …")
    try:
        if eff_type == "odoo":
            addons_path = get_addons_path(executor, instance_path)
            executor.run(
                f"{instance_path}/.venv/bin/click-odoo-update -d {eff_db} --addons-path={addons_path}",
                cwd=instance_path,
            )
        executor.run(f"systemctl --user restart {instance_name}")
    except ExecutorError as exc:
        run_hooks("post-update")
        run_hooks("post-update-fail")
        msg = f"Restart/upgrade failed: {exc}"
        raise click.ClickException(msg) from exc

    # Step 8: post-update hooks
    run_hooks("post-update")
    run_hooks("post-update-success")

    click.echo(f"Instance {instance_name!r} updated successfully.")
