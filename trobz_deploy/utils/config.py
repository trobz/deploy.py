from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

KNOWN_ENVS: frozenset[str] = frozenset({"integration", "staging", "production", "hotfix", "debug", "demo"})

# Maps instance name prefix → deployment type
_PREFIX_TO_TYPE: dict[str, str] = {
    "odoo": "odoo",
    "openerp": "odoo",
    "service": "python",
}


def parse_instance_name(name: str) -> tuple[str, str, str, str | None]:
    """Parse instance name into (prefix, slug, environment, suffix).

    Format: <prefix>-<slug>-<environment>[-<suffix>]
    """
    parts = name.split("-")
    if len(parts) < 3:
        msg = f"Invalid instance name: {name!r}"
        raise ValueError(msg)

    prefix = parts[0]
    rest = parts[1:]

    # Optional suffix: last segment is not a known environment
    suffix: str | None = None
    if rest and rest[-1] not in KNOWN_ENVS:
        suffix = rest[-1]
        rest = rest[:-1]

    if not rest or rest[-1] not in KNOWN_ENVS:
        known = ", ".join(sorted(KNOWN_ENVS))
        msg = f"Cannot determine environment from instance name: {name!r}. Expected one of: {known}."
        raise ValueError(msg)

    environment = rest[-1]
    slug = "-".join(rest[:-1])

    return prefix, slug, environment, suffix


def detect_type(prefix: str) -> str:
    """Auto-detect deployment type from instance name prefix."""
    if prefix not in _PREFIX_TO_TYPE:
        msg = (
            f"Cannot auto-detect deployment type from prefix {prefix!r}. "
            "Use --type to specify: odoo, python, or service."
        )
        raise ValueError(msg)
    return _PREFIX_TO_TYPE[prefix]


def load_config(config_path: str, instance_name: str) -> dict[str, Any]:
    """Load and return the instance section from deploy.yml."""
    path = Path(config_path)
    if not path.exists():
        return {}
    with path.open() as f:
        data = yaml.safe_load(f) or {}
    return data.get(instance_name, {})


def resolve_options(
    config: dict[str, Any],
    instance_name: str,
    *,
    ssh_host: str | None = None,
    ssh_port: int | None = None,
    repo_url: str | None = None,
    repo_branch: str | None = None,
    deploy_type: str | None = None,
    db: str | None = None,
    repo_subdir: str | None = None,
    require_type: bool = True,
) -> dict[str, Any]:
    """Merge CLI args over config values over built-in defaults.

    CLI args take precedence over config, which takes precedence over defaults.
    """
    resolved: dict[str, Any] = dict(config)

    if ssh_host is not None:
        resolved["ssh_host"] = ssh_host
    if ssh_port is not None:
        resolved["ssh_port"] = ssh_port
    if repo_url is not None:
        resolved["repo_url"] = repo_url
    if repo_branch is not None:
        resolved["repo_branch"] = repo_branch
    if deploy_type is not None:
        resolved["type"] = deploy_type
    if db is not None:
        resolved["db"] = db
    if repo_subdir is not None:
        resolved["repo_subdir"] = repo_subdir

    # Auto-detect type from instance name prefix when not explicitly set
    if require_type and "type" not in resolved:
        prefix, _, _, _ = parse_instance_name(instance_name)
        resolved["type"] = detect_type(prefix)

    # Default db to instance_name for odoo
    if resolved.get("type") == "odoo" and "db" not in resolved:
        resolved["db"] = instance_name

    return resolved
