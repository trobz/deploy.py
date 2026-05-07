from __future__ import annotations

from deploy.utils.executor import Executor


def setup_odoo_venv(executor: Executor, instance_path: str) -> None:
    """Create or update an Odoo virtual environment using ``odoo-venv``."""
    executor.run(
        f"odoo-venv create --project-dir {instance_path} --preset project",
        cwd=instance_path,
    )


def setup_python_venv(executor: Executor, instance_path: str, force: bool = False) -> None:
    """Create a venv with ``uv`` and install dependencies from requirements.txt."""
    clear_flag = " --clear" if force else ""
    executor.run(f"uv venv{clear_flag} .venv", cwd=instance_path)
    setup_python_deps(executor, instance_path)


def setup_python_deps(executor: Executor, instance_path: str) -> None:
    executor.run("if [ -e requirements.txt ]; then uv pip install -r requirements.txt; fi", cwd=instance_path)
    executor.run("if [ -e pyproject.toml ]; then uv sync; fi", cwd=instance_path)


def setup_package_venv(executor: Executor, instance_path: str, requirements: list[str], force: bool = False) -> None:
    """Create a venv with ``uv`` and install pip packages directly."""
    clear_flag = " --clear" if force else ""
    executor.run(f"uv venv{clear_flag} .venv", cwd=instance_path)
    executor.run(f"uv pip install {' '.join(requirements)}", cwd=instance_path)


def upgrade_package(executor: Executor, instance_path: str, requirements: list[str]) -> None:
    """Upgrade pip packages in an existing venv."""
    executor.run(f"uv pip install --upgrade {' '.join(requirements)}", cwd=instance_path)
