# Commands

`deploy` provides three commands. All commands accept global options:

| Option | Default | Description |
|--------|---------|-------------|
| `--config FILE` | `deploy.yml` | Path to the configuration file (resolved locally) |
| `--verbose` | `False` | Print each remote command and its output as it runs |

## Overview

| Command | Purpose |
|---------|---------|
| [`configure`](configure.md) | Clone repo, set up environment, install systemd unit |
| [`update`](update.md) | Pull latest code, sync deps, restart service |
| [`status`](status.md) | Show git info and systemd unit state |

## Global usage

```bash
deploy [--config FILE] [--verbose] <command> [args...]
```

Example using a custom config path:

```bash
deploy --config /etc/deploy/myserver.yml update odoo-myproject-production
```
