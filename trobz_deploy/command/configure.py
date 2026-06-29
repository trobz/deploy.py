from __future__ import annotations

import json
import secrets
import shlex
from typing import Annotated, Any

import typer

from trobz_deploy.utils.config import DeployType, load_config, parse_step_option, resolve_options, validate_step_slugs
from trobz_deploy.utils.executor import Executor, ExecutorError
from trobz_deploy.utils.render import render_unit
from trobz_deploy.utils.venv import setup_odoo_venv, setup_package_venv, setup_python_venv


def _is_git_repo(executor: Executor, path: str) -> bool:
    return _file_exists(executor, f"{path}/.git", file_type="d")


def _file_exists(executor: Executor, path: str, file_type: str = "f") -> bool:
    try:
        executor.run(f"test -{file_type} {path}")
    except ExecutorError:
        return False
    else:
        return True


def _postgres_user_exists(executor: Executor, instance_name: str) -> bool:
    result = executor.capture(
        f"psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='{instance_name}'\" -d postgres"  # noqa: S608
    )
    return result.strip() == "1"


def _ensure_postgres_user(executor: Executor, instance_name: str, dry_run: bool = False) -> None:
    """Create a Postgres superuser role named after the instance, if it doesn't already exist."""
    if _postgres_user_exists(executor, instance_name):
        return

    if dry_run:
        typer.secho(f"\n[dry-run] Would create Postgres user {instance_name!r}…", fg="cyan")
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
    "config": "Generating Odoo config",
    "env": "Generating server.env",
    "unit": "Installing systemd unit",
}

ODOO_CONFIG_FILENAME = "odoo.conf"

# Default env vars written to config/server.env for every odoo instance.
# Single-thread the BLAS/OpenMP backends so workers don't oversubscribe cores.
DEFAULT_SERVER_ENV: dict[str, Any] = {
    "OMP_NUM_THREADS": 1,
    "OPENBLAS_NUM_THREADS": 1,
    "NUMEXPR_NUM_THREADS": 1,
    "MKL_NUM_THREADS": 1,
}


def _render_server_env(env: dict[str, Any]) -> str:
    """Render an ``env`` dict as ``KEY=value`` lines for config/server.env."""
    return "".join(f"{key}={value}\n" for key, value in env.items())


# Odoo instance types that map to an odoo-config --preset (see odoo-config overlay.toml).
# The other types (demo, hotfix, test, training) carry no preset.
INSTANCE_PRESETS = ("production", "staging", "integration")


def _detect_preset(instance_name: str) -> str | None:
    """Derive the odoo-config --preset from the instance name (e.g. acme-staging → staging).

    Instance names are dash-separated (e.g. ``openerp-project-integration``).
    """
    tokens = set(instance_name.lower().split("-"))
    return next((p for p in INSTANCE_PRESETS if p in tokens), None)


def _detect_version(executor: Executor, service_path: str, *, dry_run: bool = False) -> str:
    """Read the Odoo version from ``odoo-addons-path --format=json`` in the codebase, else prompt."""
    # OSError covers a missing service_path on the local executor (subprocess cwd= raises
    # before the command runs); the remote executor degrades to a non-zero ExecutorError.
    try:
        out = executor.capture("odoo-addons-path -v --format=json", cwd=service_path, dry_run=dry_run)
        detected = json.loads(out).get("version", "") if out else ""
    except (ExecutorError, OSError, json.JSONDecodeError):
        detected = ""

    return detected or typer.prompt("Target Odoo version", default="19.0")


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
    recreate: Annotated[
        bool,
        typer.Option(
            help="Re-create existing artifacts (venv, odoo-config, systemd unit) instead of skipping them.",
        ),
    ] = False,
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
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Go through all steps without running any writing/destructive commands.",
        ),
    ] = False,
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

    if dry_run:
        typer.secho("\nDry run: no writing/destructive commands will be executed.", fg="cyan")

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
                executor.run(f"mkdir -p {instance_path}", dry_run=dry_run)
        elif eff_type == "service" and not eff_repo_url:
            # Binary/system service mode: no repo, just ensure a working directory exists
            typer.secho(f"\nCreating instance directory ~/{instance_name}…", fg="green")
            executor.run(f"mkdir -p {instance_path}", dry_run=dry_run)
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
                executor.run(clone_cmd, dry_run=dry_run)
            except ExecutorError as exc:
                typer.echo(typer.style(f"Git clone failed: {exc}", fg="red"), err=True)
                raise typer.Exit(code=1) from exc

    # Step 3: Run gitaggregate if needed
    if eff_type == "odoo" and _run_step("gitaggregate"):
        executor.run(
            "if [ -f addons/repos.yaml ]; then cd addons/ && gitaggregate -c repos.yaml; fi",
            cwd=instance_path,
            dry_run=dry_run,
        )

    # Step 3b: Ensure Postgres role exists
    if eff_type == "odoo" and _run_step("pg"):
        try:
            _ensure_postgres_user(executor, instance_name, dry_run=dry_run)
        except ExecutorError as exc:
            typer.echo(typer.style(str(exc), fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 4: Set up environment
    if _run_step("venv"):
        typer.secho(f"\nSetting up {eff_type} environment…", fg="green")
        try:
            if eff_type == "odoo":
                setup_odoo_venv(executor, instance_path, recreate=recreate, dry_run=dry_run)
            elif eff_type == "python":
                if eff_requirements:
                    setup_package_venv(executor, instance_path, eff_requirements, dry_run=dry_run)
                else:
                    setup_python_venv(executor, service_path, recreate=recreate, dry_run=dry_run)
                    executor.run(
                        "if [ -f .env.example ] && [ ! -f .env ]; then cp .env.example .env; fi",
                        cwd=service_path,
                        dry_run=dry_run,
                    )
            else:  # service
                build_cmd: str | None = opts.get("build")
                if build_cmd:
                    executor.run(build_cmd, cwd=service_path, dry_run=dry_run)
        except ExecutorError as exc:
            typer.echo(typer.style(str(exc), fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 5: Generate Odoo config via odoo-config on the target host
    if eff_type == "odoo" and _run_step("config"):
        conf_dir = f"{instance_path}/config"
        conf_path = f"{conf_dir}/{ODOO_CONFIG_FILENAME}"
        conf_exists = _file_exists(executor, conf_path)

        if not conf_exists or recreate:
            typer.secho(f"\n{CONFIGURE_STEPS['config']}…", fg="green")
            version = opts.get("version") or _detect_version(executor, service_path, dry_run=dry_run)

            overrides: dict[str, Any] = {
                "db_user": instance_name,
                "report.url": f"http://{instance_name}:8069",
                "http_interface": instance_name,
                "admin_passwd": secrets.token_urlsafe(24),
            }
            overrides.update(opts.get("config") or {})
            override_args = " ".join(f"--{key}={shlex.quote(str(value))}" for key, value in overrides.items())

            preset = opts.get("preset") or _detect_preset(instance_name)
            preset_arg = f" --preset {shlex.quote(preset)}" if preset else ""

            try:
                executor.run(f"mkdir -p {conf_dir}", dry_run=dry_run)
                if conf_exists:
                    executor.run(f"mv {conf_path} {conf_path}.bak", dry_run=dry_run)
                executor.run(
                    f"odoo-config create --version {shlex.quote(str(version))}{preset_arg} "
                    f"-c {conf_path} {override_args}",
                    dry_run=dry_run,
                )
            except ExecutorError as exc:
                typer.echo(typer.style(str(exc), fg="red"), err=True)
                raise typer.Exit(code=1) from exc

        else:
            typer.secho(
                f"\nConfig {ODOO_CONFIG_FILENAME!r} already exists. Use --recreate to regenerate.",
                fg="yellow",
            )

    # Step 6: Generate config/server.env — default thread limits, enriched by deploy.yml `env`.
    if eff_type == "odoo" and _run_step("env"):
        conf_dir = f"{instance_path}/config"
        env_path = f"{conf_dir}/server.env"
        env_exists = _file_exists(executor, env_path)

        if not env_exists or recreate:
            typer.secho(f"\n{CONFIGURE_STEPS['env']}…", fg="green")
            server_env = {**DEFAULT_SERVER_ENV, **(opts.get("env") or {})}

            try:
                executor.run(f"mkdir -p {conf_dir}", dry_run=dry_run)

                if env_exists:
                    executor.run(f"mv {env_path} {env_path}.bak", dry_run=dry_run)

                executor.write_file(_render_server_env(server_env), env_path, dry_run=dry_run)

            except ExecutorError as exc:
                typer.echo(typer.style(str(exc), fg="red"), err=True)
                raise typer.Exit(code=1) from exc

        else:
            typer.secho(
                "\nserver.env already exists. Use --recreate to regenerate.",
                fg="yellow",
            )

    # Step 7: Install systemd unit
    if _run_step("unit"):
        unit_dir = "$HOME/.config/systemd/user"
        unit_path = f"{unit_dir}/{instance_name}.service"
        unit_file_exists = _file_exists(executor, unit_path)
        if not unit_file_exists or recreate:
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
                        dry_run=dry_run,
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

            try:
                executor.run(f"mkdir -p {unit_dir}", dry_run=dry_run)
                executor.write_file(unit_content, unit_path, dry_run=dry_run)
                if not unit_file_exists:
                    executor.run("loginctl enable-linger", dry_run=dry_run)
                    executor.run("systemctl --user daemon-reload", dry_run=dry_run)
                    executor.run(f"systemctl --user enable --now {instance_name}", dry_run=dry_run)
                else:
                    executor.run("systemctl --user daemon-reload", dry_run=dry_run)
                    executor.run(f"systemctl --user restart {instance_name}", dry_run=dry_run)
            except ExecutorError as exc:
                typer.echo(typer.style(str(exc), fg="red"), err=True)
                raise typer.Exit(code=1) from exc
        else:
            typer.secho(
                f"\nUnit {instance_name!r} already exists. Use --recreate to reconfigure.",
                fg="yellow",
            )

    if dry_run:
        typer.secho(f"\nDry run complete: instance {instance_name!r} was not changed.", fg="green")
    else:
        typer.secho(f"\nInstance {instance_name!r} configured successfully.", fg="green")

    if watch:
        if dry_run:
            typer.secho("Skipping --watch: no service was started in dry-run mode.", fg="yellow")
        else:
            executor.watch_logs(eff_type, instance_name)
