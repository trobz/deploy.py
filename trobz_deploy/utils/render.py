from __future__ import annotations

from importlib.resources import files
from typing import Any

from jinja2 import Environment, select_autoescape


def render_unit(template_name: str, **variables: Any) -> str:
    """Render the bundled systemd unit template for *template_name*.

    Args:
        template_name: One of ``odoo``, ``python``, or ``service``.
        **variables: Template context variables.

    Returns:
        Rendered unit file content as a string.
    """
    pkg = files("trobz_deploy.templates")
    source = (pkg / f"{template_name}.service.j2").read_text(encoding="utf-8")
    env = Environment(autoescape=select_autoescape(["html", "htm", "xml"]))
    template = env.from_string(source)
    return template.render(**variables)
