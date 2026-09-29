from __future__ import annotations

from typing import Any

from trobz_deploy.utils.config import render_cli_args
from trobz_deploy.utils.executor import Executor


def addons_path_command(binary: str = "odoo-addons-path", args: dict[str, Any] | None = None) -> str:
    """Build the ``odoo-addons-path`` command line from the ``tools.odoo-addons-path`` options.

    Every caller (systemd unit, ``update``, version detection) goes through here, so the
    add-ons path is resolved with the same options everywhere.
    """
    rendered = render_cli_args(args)
    return f"{binary} {rendered}" if rendered else binary


def get_addons_path(executor: Executor, instance_path: str, args: dict[str, Any] | None = None) -> str:
    """Run ``odoo-addons-path`` in *instance_path* and return the result."""
    return executor.capture(addons_path_command(args=args), cwd=instance_path)
