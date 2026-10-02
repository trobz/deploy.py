from __future__ import annotations

import shlex

from trobz_deploy.utils.executor import Executor


def get_addons_path(executor: Executor, instance_path: str) -> str:
    """Run ``odoo-addons-path`` on *instance_path* and return the result.

    The codebase is passed explicitly: odoo-addons-path does not detect the
    layout of the current directory implicitly.
    """
    return executor.capture(f"odoo-addons-path {shlex.quote(instance_path)}", cwd=instance_path)
