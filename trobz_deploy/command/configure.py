from __future__ import annotations

import secrets
from typing import Annotated, Any

import typer

from trobz_deploy.utils.config import DeployType, load_config, parse_step_option, resolve_options, validate_step_slugs
from trobz_deploy.utils.executor import Executor, ExecutorError
from trobz_deploy.utils.render import render_unit
from trobz_deploy.utils.venv import setup_odoo_venv, setup_package_venv, setup_python_venv


def _is_git_repo(executor: Executor, path: str) -> bool:
    try:
        executor.run(f"test -d {path}/.git")
    except ExecutorError:
        return False
    else:
        return True


def _postgres_user_exists(executor: Executor, instance_name: str) -> bool:
    result = executor.capture(
        f"psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='{instance_name}'\" -d postgres"  # noqa: S608
    )
    return result.strip() == "1"


def _ensure_postgres_user(executor: Executor, instance_name: str) -> None:
    """Create a Postgres superuser role named after the instance, if it doesn't already exist."""
    if _postgres_user_exists(executor, instance_name):
        return

    typer.secho(f"\nCreating Postgres user {instance_name!r}…", fg="green")
    password = secrets.token_urlsafe(16)
    executor.run(f"createuser --no-createrole --superuser {instance_name}")
    executor.run(f'psql -d postgres -c "ALTER ROLE \\"{instance_name}\\" WITH PASSWORD \'{password}\'"')
    typer.secho(
        f"Created Postgres user {instance_name!r} with password:\n  {password}\n"
        "Save this password now — it will not be shown again.",
        fg="yellow",
    )


CONFIGURE_STEPS = {
    "dir": "Setting up instance directory",
    "pg": "Ensure postgres role exists",
    "gitaggregate": "Run gitaggregate if needed",
    "venv": "Creating the venv",
    "unit": "Installing systemd unit",
}


def configure(  # noqa: C901
    ctx: typer.Context,
    instance_name: Annotated[str, typer.Argument()],
    ssh_host: Annotated[str | None, typer.Argument()] = None,
    repo_url: Annotated[str | None, typer.Argument()] = None,
    deploy_type: Annotated[
        DeployType | None,
        typer.Option("--type", help="Deployment type (auto-detected from instance name prefix if omitted)."),
    ] = None,
    ssh_port: Annotated[int | None, typer.Option("-p", "--port", help="SSH port on the remote host.")] = None,
    repo_subdir: Annotated[
        str | None,
        typer.Option(help="Subdirectory within the repo to use as the service root (for monorepos)."),
    ] = None,
    repo_branch: Annotated[
        str | None,
        typer.Option(help="Git branch to clone and track (defaults to the repository's default branch)."),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help=(
                "Stream service logs with journalctl after a successful configure. "
                "Also merge with odoo and click-odoo-update logs if applicable."
            ),
        ),
    ] = False,
    steps: Annotated[
        str,
        typer.Option(
            "--steps",
            help=f"Comma-separated steps to run, or 'all'. Available: {', '.join(CONFIGURE_STEPS.keys())}.",
        ),
    ] = "all",
    skip_steps: Annotated[
        str | None,
        typer.Option(
            "--except",
            help=f"Comma-separated steps to skip. Available: {', '.join(CONFIGURE_STEPS.keys())}.",
        ),
    ] = None,
) -> None:
    """Configure a new deployment instance."""
    eff_steps = parse_step_option(steps)
    eff_skip_steps = parse_step_option(skip_steps)
    try:
        validate_step_slugs("--steps", eff_steps, CONFIGURE_STEPS, allow_all=True)
        validate_step_slugs("--except", eff_skip_steps, CONFIGURE_STEPS, allow_all=False)
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    def _run_step(slug: str) -> bool:
        return ("all" in eff_steps or slug in eff_steps) and slug not in eff_skip_steps

    cfg = load_config(ctx.obj["config"], instance_name)
    try:
        opts = resolve_options(
            cfg,
            instance_name,
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            repo_url=repo_url,
            repo_branch=repo_branch,
            deploy_type=deploy_type.value if deploy_type else None,
            repo_subdir=repo_subdir,
        )
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_repo_url: str | None = opts.get("repo_url")
    eff_repo_branch: str | None = opts.get("repo_branch")
    eff_type: str = opts["type"]
    _req = opts.get("requirements")
    eff_requirements: list[str] = ([_req] if isinstance(_req, str) else _req) if _req else []

    if eff_type == "python" and eff_requirements and eff_repo_url:
        msg = "requirements and repo_url are mutually exclusive for python type."
        typer.echo(typer.style(msg, fg="red"), err=True)
        raise typer.Exit(code=1)

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    home_dir = executor.capture("echo $HOME")
    instance_path = f"{home_dir}/{instance_name}"
    eff_repo_subdir: str | None = opts.get("repo_subdir")
    service_path = f"{instance_path}/{eff_repo_subdir}" if eff_repo_subdir else instance_path

    # Step 2: Set up instance directory
    if _run_step("dir"):
        if eff_type == "python" and eff_requirements:
            # Package mode: create directory directly, no git clone
            try:
                executor.run(f"test -d {instance_path}")
                msg = f"Instance directory already exists: ~/{instance_name}\nUse --except dir to skip this step."
                typer.echo(typer.style(msg, fg="yellow"), err=True)
                raise typer.Exit(code=1)
            except ExecutorError:
                typer.secho(f"\nCreating instance directory ~/{instance_name}…", fg="green")
                executor.run(f"mkdir -p {instance_path}")
        elif eff_type == "service" and not eff_repo_url:
            # Binary/system service mode: no repo, just ensure a working directory exists
            typer.secho(f"\nCreating instance directory ~/{instance_name}…", fg="green")
            executor.run(f"mkdir -p {instance_path}")
        else:
            if not eff_repo_url:
                msg = "repo_url is required. Provide it as an argument or set it in deploy.yml."
                typer.echo(typer.style(msg, fg="red"), err=True)
                raise typer.Exit(code=1)

            # Repo mode: clone
            if _is_git_repo(executor, instance_path):
                msg = f"Instance directory already exists: ~/{instance_name}\nUse --except dir to skip this step."
                typer.echo(typer.style(msg, fg="yellow"), err=True)
                raise typer.Exit(code=1)

            typer.secho(f"\nCloning {eff_repo_url} into ~/{instance_name}…", fg="green")
            try:
                clone_cmd = f"git clone --recurse-submodules {eff_repo_url} $HOME/{instance_name}"
                if eff_repo_branch:
                    clone_cmd += f" --branch {eff_repo_branch}"
                executor.run(clone_cmd)
            except ExecutorError as exc:
                typer.echo(typer.style(f"Git clone failed: {exc}", fg="red"), err=True)
                raise typer.Exit(code=1) from exc

    # Step 3: Run gitaggregate if needed
    if eff_type == "odoo" and _run_step("gitaggregate"):
        executor.run(
            "if [ -f addons/repos.yaml ]; then cd addons/ && gitaggregate -c repos.yaml; fi",
            cwd=instance_path,
        )

    # Step 3b: Ensure Postgres role exists
    if eff_type == "odoo" and _run_step("pg"):
        try:
            _ensure_postgres_user(executor, instance_name)
        except ExecutorError as exc:
            typer.echo(typer.style(str(exc), fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 4: Set up environment
    if _run_step("venv"):
        typer.secho(f"\nSetting up {eff_type} environment…", fg="green")
        try:
            if eff_type == "odoo":
                setup_odoo_venv(executor, instance_path)
            elif eff_type == "python":
                if eff_requirements:
                    setup_package_venv(executor, instance_path, eff_requirements)
                else:
                    setup_python_venv(executor, service_path)
                    executor.run(
                        "if [ -f .env.example ] && [ ! -f .env ]; then cp .env.example .env; fi",
                        cwd=service_path,
                    )
            else:  # service
                build_cmd: str | None = opts.get("build")
                if build_cmd:
                    executor.run(build_cmd, cwd=service_path)
        except ExecutorError as exc:
            typer.echo(typer.style(str(exc), fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 5: Install systemd unit
    if _run_step("unit"):
        typer.secho(f"\n{CONFIGURE_STEPS['unit']}…", fg="green")
        unit_instance_path = instance_path if eff_requirements else service_path
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
            if not exec_start and not eff_requirements:
                res = executor.capture(
                    "if [ -f server.py ]; then echo server.py; fi",
                    cwd=service_path,
                )
                if res == "server.py":
                    exec_start = "python server.py"
            if not exec_start:
                msg = "exec_start is required for service or python type. Set it in deploy.yml."
                typer.echo(typer.style(msg, fg="red"), err=True)
                raise typer.Exit(code=1)
            if eff_type == "python":
                template_vars["venv_path"] = venv_path
            template_vars["exec_start"] = exec_start

        try:
            unit_content = render_unit(eff_type, **template_vars)
        except Exception as exc:
            typer.echo(typer.style(f"Template rendering failed: {exc}", fg="red"), err=True)
            raise typer.Exit(code=1) from exc

        unit_dir = "$HOME/.config/systemd/user"
        unit_path = f"{unit_dir}/{instance_name}.service"
        try:
            executor.run(f"mkdir -p {unit_dir}")
            executor.write_file(unit_content, unit_path)
            executor.run("loginctl enable-linger")
            executor.run("systemctl --user daemon-reload")
            executor.run(f"systemctl --user enable --now {instance_name}")
        except ExecutorError as exc:
            typer.echo(typer.style(str(exc), fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    typer.secho(f"\nInstance {instance_name!r} configured successfully.", fg="green")

    if watch:
        executor.watch_logs(eff_type, instance_name)
