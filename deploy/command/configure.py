from __future__ import annotations

from typing import Any

import click

from deploy.utils.config import load_config, resolve_options
from deploy.utils.executor import Executor, ExecutorError
from deploy.utils.render import render_unit
from deploy.utils.venv import setup_odoo_venv, setup_package_venv, setup_python_venv


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
@click.option(
    "--repo-subdir",
    "repo_subdir",
    default=None,
    help="Subdirectory within the repo to use as the service root (for monorepos).",
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
    repo_subdir: str | None,
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
            repo_subdir=repo_subdir,
        )
    except ValueError as exc:
        raise click.ClickException(click.style(str(exc), fg="red")) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_repo_url: str | None = opts.get("repo_url")
    eff_type: str = opts["type"]
    eff_requirement: str | None = opts.get("requirement")

    if eff_type == "python" and eff_requirement and eff_repo_url:
        msg = click.style(
            "requirement and repo_url are mutually exclusive for python type.",
            fg="red",
        )
        raise click.ClickException(msg)

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    home_dir = executor.capture("echo $HOME")
    instance_path = f"{home_dir}/{instance_name}"
    eff_repo_subdir: str | None = opts.get("repo_subdir")
    service_path = f"{instance_path}/{eff_repo_subdir}" if eff_repo_subdir else instance_path

    # Step 2: Set up instance directory
    if eff_type == "python" and eff_requirement:
        # Package mode: create directory directly, no git clone
        try:
            executor.run(f"test -d {instance_path}")
            if not force:
                msg = click.style(
                    f"Instance directory already exists: ~/{instance_name}\nUse --force to re-run setup.",
                    fg="yellow",
                )
                raise click.ClickException(msg)
            click.secho("\nDirectory exists, skipping mkdir (--force).", fg="yellow")
        except ExecutorError:
            click.secho(f"\nCreating instance directory ~/{instance_name}…", fg="green")
            executor.run(f"mkdir -p {instance_path}")
    else:
        if not eff_repo_url:
            msg = click.style(
                "repo_url is required. Provide it as an argument or set it in deploy.yml.",
                fg="red",
            )
            raise click.ClickException(msg)

        # Repo mode: clone
        if _is_git_repo(executor, instance_path):
            if not force:
                msg = click.style(
                    f"Instance directory already exists: ~/{instance_name}\n"
                    "Use --force to skip cloning and re-run setup.",
                    fg="yellow",
                )
                raise click.ClickException(msg)
            click.secho("\nDirectory exists, skipping clone (--force).", fg="yellow")
        else:
            click.secho(f"\nCloning {eff_repo_url} into ~/{instance_name}…", fg="green")
            try:
                executor.run(f"git clone {eff_repo_url} $HOME/{instance_name}")
            except ExecutorError as exc:
                msg = click.style(f"Git clone failed: {exc}", fg="red")
                raise click.ClickException(msg) from exc

    if eff_type == "odoo":
        executor.run(
            "if [ -f addons/repos.yaml ]; then cd addons/ && gitaggregate -c repos.yaml; fi",
            cwd=instance_path,
        )

    # Step 3: Set up environment
    click.secho(f"\nSetting up {eff_type} environment…", fg="green")
    try:
        if eff_type == "odoo":
            setup_odoo_venv(executor, instance_path)
        elif eff_type == "python":
            if eff_requirement:
                setup_package_venv(executor, instance_path, eff_requirement, force=force)
            else:
                setup_python_venv(executor, service_path, force=force)
                executor.run(
                    "if [ -f .env.example ] && [ ! -f .env ]; then cp .env.example .env; fi",
                    cwd=service_path,
                )
        else:  # service
            build_cmd: str | None = opts.get("build")
            if not build_cmd:
                msg = click.style(
                    "build command is required for service type. Set it in deploy.yml.",
                    fg="red",
                )
                raise click.ClickException(msg)
            executor.run(build_cmd, cwd=service_path)
    except ExecutorError as exc:
        raise click.ClickException(click.style(str(exc), fg="red")) from exc

    # Step 4: Install systemd unit
    click.secho("\nInstalling systemd unit…", fg="green")
    unit_instance_path = instance_path if eff_requirement else service_path
    venv_path = f"{unit_instance_path}/.venv"

    template_vars: dict[str, Any] = {
        "instance_name": instance_name,
        "instance_path": unit_instance_path,
    }
    if eff_type == "odoo":
        template_vars["venv_path"] = venv_path
        odoo_addons_path = executor.capture("which odoo-addons-path")
        template_vars["odoo_addons_path"] = odoo_addons_path
    else:
        exec_start: str = opts.get("exec_start", "")
        if not exec_start and not eff_requirement:
            res = executor.capture(
                "if [ -f server.py ]; then echo server.py; fi",
                cwd=service_path,
            )
            if res == "server.py":
                exec_start = "python server.py"
        if not exec_start:
            msg = click.style(
                "exec_start is required for service or python type. Set it in deploy.yml.",
                fg="red",
            )
            raise click.ClickException(msg)
        if eff_type == "python":
            template_vars["venv_path"] = venv_path
        template_vars["exec_start"] = exec_start

    try:
        unit_content = render_unit(eff_type, **template_vars)
    except Exception as exc:
        msg = click.style(f"Template rendering failed: {exc}", fg="red")
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
        raise click.ClickException(click.style(str(exc), fg="red")) from exc

    click.secho(f"\nInstance {instance_name!r} configured successfully.", fg="green")
