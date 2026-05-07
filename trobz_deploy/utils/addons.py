from __future__ import annotations

from trobz_deploy.utils.executor import Executor


def get_addons_path(executor: Executor, instance_path: str) -> str:
    """Run ``odoo-addons-path`` in *instance_path* and return the result."""
    return executor.capture("odoo-addons-path", cwd=instance_path)
