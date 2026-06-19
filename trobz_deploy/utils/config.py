from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any

import yaml

KNOWN_ENVS: frozenset[str] = frozenset({"integration", "staging", "production", "hotfix", "debug", "demo"})


class DeployType(str, Enum):
    odoo = "odoo"
    python = "python"
    service = "service"


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


def _apply_ssh_user(host: str, ssh_user: str | None) -> str:
    """Prefix a bare hostname with ``ssh_user`` unless it already embeds a user or is localhost."""
    if ssh_user and host != "localhost" and "@" not in host:
        return f"{ssh_user}@{host}"
    return host


def normalize_hosts(ssh_host: Any, ssh_user: str | None = None) -> list[dict[str, Any]]:
    """Normalize the resolved ``ssh_host`` value into a list of per-host dicts.

    ``ssh_host`` may be a single string/``None`` (the common case) or a list of hosts
    for rolling a command out across several machines. Each list entry is either a
    bare hostname or a single-key mapping ``{hostname: {watch: bool, steps: {...}}}``.

    Returns a list of dicts with keys ``host``, ``watch`` (bool | None override), and
    ``steps`` (dict mapping command name -> comma-separated slug string).
    """
    if not isinstance(ssh_host, list):
        return [{"host": ssh_host, "watch": None, "steps": {}}]

    hosts: list[dict[str, Any]] = []
    for entry in ssh_host:
        if isinstance(entry, str):
            host, overrides = entry, {}
        elif isinstance(entry, dict) and len(entry) == 1:
            ((host, overrides),) = entry.items()
            overrides = overrides or {}
        else:
            msg = f"Invalid ssh_host list entry: {entry!r}. Expected a hostname string or a single-key mapping."
            raise ValueError(msg)
        if not isinstance(overrides, dict):
            msg = f"Invalid ssh_host overrides for {host!r}: {overrides!r}. Expected a mapping."
            raise ValueError(msg)  # noqa: TRY004 (kept as ValueError: callers catch ValueError, not TypeError)
        hosts.append({
            "host": _apply_ssh_user(host, ssh_user),
            "watch": overrides.get("watch"),
            "steps": overrides.get("steps") or {},
        })
    return hosts


def parse_step_option(value: str | None) -> list[str]:
    """Split a comma-separated option value into a list of trimmed, non-empty slugs."""
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def validate_step_slugs(option_name: str, slugs: list[str], valid_steps: dict[str, str], *, allow_all: bool) -> None:
    """Raise ValueError if any of *slugs* is not in *valid_steps* (or 'all' when allowed)."""
    valid = {*valid_steps, "all"} if allow_all else set(valid_steps)
    invalid = sorted(set(slugs) - valid)
    if invalid:
        choices = ", ".join((*valid_steps, "all") if allow_all else valid_steps)
        msg = f"Invalid {option_name} value(s): {', '.join(invalid)}. Available steps: {choices}"
        raise ValueError(msg)


def resolve_host_steps(
    host_steps: dict[str, str],
    action: str,
    eff_steps: list[str],
    eff_skip_steps: list[str],
    valid_steps: dict[str, str],
) -> tuple[list[str], list[str]]:
    """Resolve a single host's effective --steps/--except for *action*.

    *host_steps* is a host's ``steps`` override mapping (command name -> comma-separated
    slugs), as produced by ``normalize_hosts``. If the CLI explicitly constrained
    --steps/--except (i.e. *eff_steps*/*eff_skip_steps* are not the untouched defaults),
    or the host has no override for *action*, the CLI-resolved values win unchanged.
    Otherwise the host's value becomes its --steps, with no --except.
    """
    cli_overrides = eff_steps != ["all"] or bool(eff_skip_steps)
    host_steps_value = host_steps.get(action)
    if cli_overrides or not host_steps_value:
        return eff_steps, eff_skip_steps

    parsed = parse_step_option(host_steps_value)
    validate_step_slugs(f"ssh_host steps.{action}", parsed, valid_steps, allow_all=True)
    return parsed, []
