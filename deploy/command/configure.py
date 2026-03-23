from __future__ import annotations

from typing import Any

import click

from deploy.utils.addons import get_addons_path
from deploy.utils.config import load_config, resolve_options
from deploy.utils.executor import Executor, ExecutorError
from deploy.utils.render import render_unit
from deploy.utils.venv import setup_odoo_venv, setup_python_venv


def _is_git_repo(executor: Executor, path: str) -> bool:
    try:
        executor.run(f"test -d {path}/.git")
    except ExecutorError:
        return False
    else:
        return True


@click.command()
@click.argument("instance_name")
@click.argument("ssh_host", required=False)
@click.argument("repo_url", required=False)
@click.option(
    "--type",
    "deploy_type",
    type=click.Choice(["odoo", "python", "service"]),
    default=None,
    help="Deployment type (auto-detected from instance name prefix if omitted).",
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
    "--force",
    is_flag=True,
    default=False,
    help="Re-run setup steps even if the instance directory already exists.",
)
@click.pass_context
def configure(  # noqa: C901
    ctx: click.Context,
    instance_name: str,
    ssh_host: str | None,
    repo_url: str | None,
    deploy_type: str | None,
    ssh_port: int | None,
    force: bool,
) -> None:
    """Configure a new deployment instance."""
    cfg = load_config(ctx.obj["config"], instance_name)
    try:
        opts = resolve_options(
            cfg,
            instance_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            repo_url=repo_url,
            deploy_type=deploy_type,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_repo_url: str | None = opts.get("repo_url")
    eff_type: str = opts["type"]

    if not eff_repo_url:
        msg = "repo_url is required. Provide it as an argument or set it in deploy.yml."
        raise click.ClickException(msg)

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    instance_path = f"$HOME/{instance_name}"

    # Step 2: Clone repository
    if _is_git_repo(executor, instance_path):
        if not force:
            msg = f"Instance directory already exists: ~/{instance_name}\nUse --force to skip cloning and re-run setup."
            raise click.ClickException(msg)
        click.echo("Directory exists, skipping clone (--force).")
    else:
        click.echo(f"Cloning {eff_repo_url} into ~/{instance_name} …")
        try:
            executor.run(f"git clone {eff_repo_url} $HOME/{instance_name}")
        except ExecutorError as exc:
            msg = f"Git clone failed: {exc}"
            raise click.ClickException(msg) from exc

    # Step 3: Set up environment
    click.echo(f"Setting up {eff_type} environment …")
    addons_path: str | None = None
    try:
        if eff_type == "odoo":
            setup_odoo_venv(executor, instance_path)
            addons_path = get_addons_path(executor, instance_path)
        elif eff_type == "python":
            setup_python_venv(executor, instance_path, force=force)
        else:  # service
            build_cmd: str | None = opts.get("build")
            if not build_cmd:
                msg = "build command is required for service type. Set it in deploy.yml."
                raise click.ClickException(msg)
            executor.run(build_cmd, cwd=instance_path)
    except ExecutorError as exc:
        raise click.ClickException(str(exc)) from exc

    # Step 4: Install systemd unit
    click.echo("Installing systemd unit …")
    venv_path = f"{instance_path}/.venv"
    exec_start: str = opts.get("exec_start", "")

    template_vars: dict[str, Any] = {
        "instance_name": instance_name,
        "instance_path": instance_path,
    }
    if eff_type == "odoo":
        template_vars["venv_path"] = venv_path
        template_vars["addons_path"] = addons_path
    elif eff_type == "python":
        template_vars["venv_path"] = venv_path
        template_vars["exec_start"] = exec_start
    else:
        template_vars["exec_start"] = exec_start

    try:
        unit_content = render_unit(eff_type, **template_vars)
    except Exception as exc:
        msg = f"Template rendering failed: {exc}"
        raise click.ClickException(msg) from exc

    unit_dir = "$HOME/.config/systemd/user"
    unit_path = f"{unit_dir}/{instance_name}.service"
    try:
        executor.run(f"mkdir -p {unit_dir}")
        executor.write_file(unit_content, unit_path)
        executor.run("loginctl enable-linger")
        executor.run("systemctl --user daemon-reload")
        executor.run(f"systemctl --user enable --now {instance_name}")
    except ExecutorError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Instance {instance_name!r} configured successfully.")
