from __future__ import annotations

import typer

from trobz_deploy.utils.executor import Executor, ExecutorError


def _venv_exists(executor: Executor, instance_path: str, suffix: str = "") -> bool:
    try:
        executor.run(f"test -d {instance_path}/.venv{suffix}")
    except ExecutorError:
        return False
    return True


def _backup_venv(executor: Executor, instance_path: str, dry_run: bool = False) -> None:
    if _venv_exists(executor, instance_path, suffix=".bak"):
        executor.run(f"rm -r {instance_path}/.venv.bak", dry_run=dry_run)
    executor.run(f"mv {instance_path}/.venv {instance_path}/.venv.bak", dry_run=dry_run)


def _show_venv_exists() -> None:
    msg = (
        "Venv exists, skipping venv creation. Use --except venv to skip this step or --recreate to re-create the venv."
    )
    typer.secho(msg, fg="yellow")


def setup_odoo_venv(executor: Executor, instance_path: str, recreate: bool = False, dry_run: bool = False) -> None:
    """Create or update an Odoo virtual environment using ``odoo-venv``."""
    if _venv_exists(executor, instance_path):
        if recreate:
            _backup_venv(executor, instance_path, dry_run=dry_run)
        else:
            _show_venv_exists()
            return
    executor.run(
        f"odoo-venv create --project-dir {instance_path} --preset project",
        cwd=instance_path,
        dry_run=dry_run,
    )


def setup_python_venv(executor: Executor, instance_path: str, recreate: bool = False, dry_run: bool = False) -> None:
    """Create a venv with ``uv`` and install dependencies from requirements.txt."""
    need_create = False
    if _venv_exists(executor, instance_path):
        if recreate:
            _backup_venv(executor, instance_path, dry_run=dry_run)
            need_create = True
        else:
            _show_venv_exists()
    else:
        need_create = True
    if need_create:
        executor.run("uv venv .venv", cwd=instance_path, dry_run=dry_run)
    setup_python_deps(executor, instance_path, dry_run=dry_run)


def setup_python_deps(executor: Executor, instance_path: str, dry_run: bool = False) -> None:
    executor.run(
        "if [ -e requirements.txt ]; then uv pip install -r requirements.txt; fi", cwd=instance_path, dry_run=dry_run
    )
    executor.run("if [ -e pyproject.toml ]; then uv sync; fi", cwd=instance_path, dry_run=dry_run)


def setup_package_venv(executor: Executor, instance_path: str, requirements: list[str], dry_run: bool = False) -> None:
    """Create a venv with ``uv`` and install pip packages directly."""
    if _venv_exists(executor, instance_path):
        typer.secho("Venv exists, skipping venv creation. Use --except venv to skip this step.", fg="yellow")
    else:
        executor.run("uv venv .venv", cwd=instance_path, dry_run=dry_run)
    executor.run(f"uv pip install {' '.join(requirements)}", cwd=instance_path, dry_run=dry_run)


def upgrade_package(executor: Executor, instance_path: str, requirements: list[str], dry_run: bool = False) -> None:
    """Upgrade pip packages in an existing venv."""
    executor.run(f"uv pip install --upgrade {' '.join(requirements)}", cwd=instance_path, dry_run=dry_run)


def get_odoo_version(executor: Executor, instance_path: str) -> str:
    """Read the ``odoo_version`` from ``.venv/.odoo-venv.toml`` (written by odoo-venv)."""
    return executor.capture(
        "grep -m1 '^odoo_version' .venv/.odoo-venv.toml | cut -d'\"' -f2",
        cwd=instance_path,
    )
