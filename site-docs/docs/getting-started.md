# Getting Started

## Installation

Install `trobz-deploy` with [`uv`](https://docs.astral.sh/uv/) (recommended):

```bash
uv tool install trobz-deploy
```

Or with pip:

```bash
pip install trobz-deploy
```

## Remote host requirements

The following tools must be pre-installed on the **target host** before using `trobz-deploy`:

| Tool | Required for |
|------|-------------|
| `git` | All deployment types |
| `odoo-venv` | `odoo` deployments |
| `odoo-addons-path` | `odoo` deployments |
| `git-aggregator` | `odoo` deployments |
| `uv` | `python` deployments |
| `click-odoo-upgrade` | `odoo` upgrades |
| `systemd` (user) | All — service management |

Install Trobz tools on the remote host:

```bash
uv tool install odoo-venv
uv tool install odoo-addons-path
uv tool install git-aggregator
```

## Quickstart

**1. Create a `deploy.yml`** alongside your deployment scripts:

```yaml
odoo-myproject-production:
  ssh_host: deploy@myserver.example.com
  ssh_port: 22
  repo_url: git@github.com:myorg/myproject.git
```

**2. Configure the instance** (clone repo + set up venv + install systemd unit):

```bash
deploy configure odoo-myproject-production
```

**3. Update the instance** (pull + sync venv + upgrade + restart):

```bash
deploy update odoo-myproject-production
```

**4. Check status**:

```bash
deploy status odoo-myproject-production
```

## Next steps

- [Instance Names](instance-names.md) — understand the naming convention
- [Configuration](configuration.md) — full `deploy.yml` reference
- [Commands](commands/index.md) — detailed command documentation
- [Hooks](hooks.md) — automate pre/post update tasks
