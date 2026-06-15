from __future__ import annotations

from typing import Annotated

import typer

from trobz_deploy.utils.addons import get_addons_path
from trobz_deploy.utils.config import DeployType, load_config, parse_step_option, resolve_options, validate_step_slugs
from trobz_deploy.utils.executor import Executor, ExecutorError
from trobz_deploy.utils.venv import setup_python_deps, upgrade_package

UPDATE_STEPS = {
    "pull": "Pulling latest code",
    "venv": "Updating dependencies in venv",
    "db": "Updating database(s)",
}


def update(  # noqa: C901
    ctx: typer.Context,
    instance_name: Annotated[str, typer.Argument()],
    ssh_host: Annotated[str | None, typer.Argument()] = None,
    deploy_type: Annotated[
        DeployType | None,
        typer.Option("--type", help="Deployment type (auto-detected from instance name prefix if omitted)."),
    ] = None,
    db: Annotated[
        str | None,
        typer.Option(
            help="Override the target database name (Odoo only). Can be comma-separated for multiple databases."
        ),
    ] = None,
    ssh_port: Annotated[int | None, typer.Option("-p", "--port", help="SSH port on the remote host.")] = None,
    ignore_hooks: Annotated[bool, typer.Option("--ignore-hooks", help="Skip all hook execution.")] = False,
    repo_subdir: Annotated[
        str | None,
        typer.Option(help="Subdirectory within the repo to use as the service root (for monorepos)."),
    ] = None,
    repo_branch: Annotated[
        str | None,
        typer.Option(help="Git branch to pull (defaults to the currently checked-out branch)."),
    ] = None,
    watch: Annotated[
        bool,
        typer.Option(
            "--watch",
            help=(
                "Stream service logs with journalctl after a successful update. "
                "Also merge with odoo and click-odoo-update logs if applicable."
            ),
        ),
    ] = False,
    steps: Annotated[
        str,
        typer.Option(
            "--steps",
            help=f"Comma-separated steps to run, or 'all'. Available: {', '.join(UPDATE_STEPS.keys())}.",
        ),
    ] = "all",
    skip_steps: Annotated[
        str | None,
        typer.Option(
            "--except",
            help=f"Comma-separated steps to skip. Available: {', '.join(UPDATE_STEPS.keys())}.",
        ),
    ] = None,
) -> None:
    """Update an existing deployment instance."""
    eff_steps = parse_step_option(steps)
    eff_skip_steps = parse_step_option(skip_steps)
    try:
        validate_step_slugs("--steps", eff_steps, UPDATE_STEPS, allow_all=True)
        validate_step_slugs("--except", eff_skip_steps, UPDATE_STEPS, allow_all=False)
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
            deploy_type=deploy_type.value if deploy_type else None,
            db=db,
            repo_subdir=repo_subdir,
            repo_branch=repo_branch,
        )
    except ValueError as exc:
        typer.echo(typer.style(str(exc), fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_type: str = opts["type"]
    eff_db: str | list[str] = opts.get("db", instance_name)
    if isinstance(eff_db, str):
        eff_db = eff_db.split(",")
    eff_repo_branch: str | None = opts.get("repo_branch")
    _req = opts.get("requirements")
    eff_requirements: list[str] = ([_req] if isinstance(_req, str) else _req) if _req else []
    hooks: dict = opts.get("hooks", {})

    executor = Executor(eff_ssh_host, ctx.obj["verbose"], ssh_port=eff_ssh_port)
    home_dir = executor.capture("echo $HOME")
    instance_path = f"{home_dir}/{instance_name}"
    eff_repo_subdir: str | None = opts.get("repo_subdir")
    service_path = f"{instance_path}/{eff_repo_subdir}" if eff_repo_subdir else instance_path

    def run_hooks(hook_name: str) -> bool:
        """Execute all commands for *hook_name*. Returns True if all succeeded."""
        if ignore_hooks:
            return True
        for cmd in hooks.get(hook_name, []):
            try:
                executor.run(cmd, cwd=instance_path)
            except ExecutorError as exc:
                typer.echo(
                    typer.style(f"Hook {hook_name!r} failed: {exc}", fg="red"),
                    err=True,
                )
                return False
        return True

    # Step 2: pre-update hooks (non-blocking)
    typer.secho("\nRunning pre-update hooks…", fg="green")
    run_hooks("pre-update")

    # Step 3: pre-update-required hooks (blocking on failure)
    typer.secho("\nRunning pre-update-required hooks…", fg="green")
    if not run_hooks("pre-update-required"):
        run_hooks("pre-update-fail")
        msg = "pre-update-required hook failed. Update aborted."
        typer.echo(typer.style(msg, fg="red"), err=True)
        raise typer.Exit(code=1)

    # Step 4: pre-update-success
    run_hooks("pre-update-success")

    # Step 5+6: Pull/upgrade code and update dependencies
    if eff_type == "python" and eff_requirements:
        # Package mode: upgrade pip package directly, no git pull
        if _run_step("venv"):
            typer.secho(f"\n{UPDATE_STEPS['venv']}…", fg="green")
            try:
                upgrade_package(executor, instance_path, eff_requirements)
            except ExecutorError as exc:
                run_hooks("post-update")
                run_hooks("post-update-fail")
                typer.echo(typer.style(f"Package upgrade failed: {exc}", fg="red"), err=True)
                raise typer.Exit(code=1) from exc
    elif eff_type == "service" and not opts.get("repo_url"):
        # Binary/system service mode: no repo to pull, skip straight to restart
        if _run_step("pull"):
            typer.secho("\nNo repository to update, skipping pull…", fg="yellow")
    else:
        # Repo mode: git pull then update venv
        if _run_step("pull"):
            try:
                executor.run(f"test -d {instance_path}/.git")
            except ExecutorError:
                msg = f"Instance directory not found or not a git repo: ~/{instance_name}"
                typer.echo(typer.style(msg, fg="red"), err=True)
                raise typer.Exit(code=1) from None

            typer.secho(f"\n{UPDATE_STEPS['pull']}…", fg="green")
            try:
                if eff_repo_branch:
                    executor.run(
                        f"git fetch origin && git checkout {eff_repo_branch} && git pull --recurse-submodules",
                        cwd=instance_path,
                    )
                else:
                    executor.run("git pull --recurse-submodules", cwd=instance_path)
            except ExecutorError as exc:
                run_hooks("post-update")
                run_hooks("post-update-fail")
                typer.echo(typer.style(f"git pull failed: {exc}", fg="red"), err=True)
                raise typer.Exit(code=1) from exc

        if _run_step("venv"):
            typer.secho(f"\n{UPDATE_STEPS['venv']}…", fg="green")
            try:
                if eff_type == "odoo":
                    executor.run(
                        "if [ -f addons/repos.yaml ]; then cd addons/ && gitaggregate -c repos.yaml; fi",
                        cwd=instance_path,
                    )
                    executor.run("odoo-venv update .venv --backup --yes", cwd=instance_path)
                elif eff_type == "python":
                    setup_python_deps(executor, service_path)
                else:  # service
                    build_cmd: str | None = opts.get("build")
                    if build_cmd:
                        executor.run(build_cmd, cwd=service_path)
            except ExecutorError as exc:
                run_hooks("post-update")
                run_hooks("post-update-fail")
                typer.echo(typer.style(f"Dependency update failed: {exc}", fg="red"), err=True)
                raise typer.Exit(code=1) from exc

    # Step 7: Update database (Odoo only)
    if eff_type == "odoo" and _run_step("db"):
        try:
            addons_path = get_addons_path(executor, instance_path)
            for db in eff_db:
                typer.secho(f"\nUpdating database {db!r}…", fg="green")
                executor.run(
                    f".venv/bin/click-odoo-update --config config/odoo.conf -d {db}"
                    f" --addons-path={addons_path} --logfile log/upgrade.log",
                    cwd=instance_path,
                )
        except ExecutorError as exc:
            run_hooks("post-update")
            run_hooks("post-update-fail")
            typer.echo(typer.style(f"Database update failed: {exc}", fg="red"), err=True)
            raise typer.Exit(code=1) from exc

    # Step 8: Restart service to apply changes
    typer.secho("\nApplying changes…", fg="green")
    try:
        executor.run(f"systemctl --user restart {instance_name}")
    except ExecutorError as exc:
        run_hooks("post-update")
        run_hooks("post-update-fail")
        typer.echo(typer.style(f"Restart failed: {exc}", fg="red"), err=True)
        raise typer.Exit(code=1) from exc

    # Step 8: post-update hooks
    run_hooks("post-update")
    run_hooks("post-update-success")

    typer.secho(f"\nInstance {instance_name!r} updated successfully.", fg="green")

    if watch:
        executor.watch_logs(eff_type, instance_name)
