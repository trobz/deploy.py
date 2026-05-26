"""Regenerate site-docs/docs/cli-reference.md from the Typer app.

Invoked by `make cli-docs` (and transitively `make docs`). Keeps the public
docs site in sync with whatever flags/commands exist in trobz_deploy.main
without manual edits — add a flag, run `make docs`, commit the diff.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "site-docs" / "docs" / "cli-reference.md"

HEADER = """---
icon: lucide/book
description: Complete reference for every trobz-deploy command, auto-generated from --help.
tags:
  - reference
  - cli
---

!!! info "Auto-generated"
    This page is regenerated from `deploy --help` by `make cli-docs`.
    Do not edit by hand — your changes will be overwritten on the next build.

"""


def main() -> None:
    # `uv` is on PATH in the dev (`make`) and CI (`setup-uv`) environments.
    body = subprocess.check_output(
        ["uv", "run", "typer", "trobz_deploy.cli", "utils", "docs", "--name", "deploy"],  # noqa: S607
        text=True,
    )
    # Typer emits `[default: X]`, `[required]`, etc. which Zensical/Markdown
    # parses as link references. Escape the brackets so they render literally.
    body = re.sub(
        r"\[(default|env var|required)([^\]]*)\]",
        lambda m: rf"\[{m.group(1)}{m.group(2)}\]",
        body,
    )
    OUT.write_text(HEADER + body)
    try:
        rel = OUT.relative_to(Path.cwd())
    except ValueError:
        rel = OUT
    print(f"Wrote {rel} ({len(body.splitlines())} lines from typer)")


if __name__ == "__main__":
    main()
