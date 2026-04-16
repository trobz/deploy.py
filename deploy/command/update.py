from __future__ import annotations

import click

from deploy.utils.addons import get_addons_path
from deploy.utils.config import load_config, resolve_options
from deploy.utils.executor import Executor, ExecutorError
from deploy.utils.venv import setup_python_deps, upgrade_package


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
@click.option(
    "--repo-subdir",
    "repo_subdir",
    default=None,
    help="Subdirectory within the repo to use as the service root (for monorepos).",
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
    repo_subdir: str | None,
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
            repo_subdir=repo_subdir,
        )
    except ValueError as exc:
        raise click.ClickException(click.style(str(exc), fg="red")) from exc

    eff_ssh_host: str | None = opts.get("ssh_host")
    eff_ssh_port: int | None = opts.get("ssh_port")
    eff_type: str = opts["type"]
    eff_db: str = opts.get("db", instance_name)
    eff_requirement: str | None = opts.get("requirement")
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
                click.secho(
                    f"Hook {hook_name!r} failed: {exc}",
                    fg="red",
                    err=True,
                )
                return False
        return True

    # Step 2: pre-update hooks (non-blocking)
    click.secho("\nRunning pre-update hooks…", fg="green")
    run_hooks("pre-update")

    # Step 3: pre-update-required hooks (blocking on failure)
    click.secho("\nRunning pre-update-required hooks…", fg="green")
    if not run_hooks("pre-update-required"):
        run_hooks("pre-update-fail")
        msg = click.style(
            "pre-update-required hook failed. Update aborted.",
            fg="red",
        )
        raise click.ClickException(msg)

    # Step 4: pre-update-success
    run_hooks("pre-update-success")

    # Step 5+6: Pull/upgrade code and update dependencies
    if eff_type == "python" and eff_requirement:
        # Package mode: upgrade pip package directly, no git pull
        click.secho("\nUpgrading package…", fg="green")
        try:
            upgrade_package(executor, instance_path, eff_requirement)
        except ExecutorError as exc:
            run_hooks("post-update")
            run_hooks("post-update-fail")
            msg = click.style(f"Package upgrade failed: {exc}", fg="red")
            raise click.ClickException(msg) from exc
    else:
        # Repo mode: git pull then update deps
        try:
            executor.run(f"test -d {instance_path}/.git")
        except ExecutorError:
            msg = click.style(
                f"Instance directory not found or not a git repo: ~/{instance_name}",
                fg="red",
            )
            raise click.ClickException(msg) from None

        click.secho("\nPulling latest code…", fg="green")
        try:
            executor.run("git pull", cwd=instance_path)
        except ExecutorError as exc:
            run_hooks("post-update")
            run_hooks("post-update-fail")
            msg = click.style(f"git pull failed: {exc}", fg="red")
            raise click.ClickException(msg) from exc

        click.secho("\nUpdating dependencies…", fg="green")
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
            msg = click.style(f"Dependency update failed: {exc}", fg="red")
            raise click.ClickException(msg) from exc

    # Step 7: Apply changes
    click.secho("\nApplying changes…", fg="green")
    try:
        if eff_type == "odoo":
            addons_path = get_addons_path(executor, instance_path)
            executor.run(
                f".venv/bin/click-odoo-update -d {eff_db} --addons-path={addons_path}",
                cwd=instance_path,
            )
        executor.run(f"systemctl --user restart {instance_name}")
    except ExecutorError as exc:
        run_hooks("post-update")
        run_hooks("post-update-fail")
        msg = click.style(f"Restart/upgrade failed: {exc}", fg="red")
        raise click.ClickException(msg) from exc

    # Step 8: post-update hooks
    run_hooks("post-update")
    run_hooks("post-update-success")

    click.secho(f"\nInstance {instance_name!r} updated successfully.", fg="green")
