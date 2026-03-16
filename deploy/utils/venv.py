from __future__ import annotations

from deploy.utils.executor import Executor


def setup_odoo_venv(executor: Executor, instance_path: str) -> None:
    """Create or update an Odoo virtual environment using ``odoo-venv``."""
    executor.run(
        f"odoo-venv create --project-dir {instance_path}",
        cwd=instance_path,
    )
    executor.run("uv pip install click-odoo-contrib", cwd=instance_path)


def setup_python_venv(executor: Executor, instance_path: str) -> None:
    """Create a venv with ``uv`` and install dependencies from requirements.txt."""
    executor.run("uv venv .venv", cwd=instance_path)
    setup_python_deps(executor, instance_path)


def setup_python_deps(executor: Executor, instance_path: str) -> None:
    executor.run("if [ -e requirements.txt ]; then uv pip install -r requirements.txt; fi", cwd=instance_path)
    executor.run("if [ -e pyproject.toml ]; then uv sync; fi", cwd=instance_path)
