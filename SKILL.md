---
name: odoo-dev:deploy.py
description: Deploy and manage Odoo, Python, and generic service instances on remote servers via SSH using the deploy CLI tool. Use when setting up new instances (configure), deploying updates (update), or checking instance status (status).
version: 1.0.0
argument-hint: "[configure|update|status] [instance_name] [options]"
---

# deploy.py

Deploy and manage application instances on remote servers over SSH using the [`deploy`](https://github.com/trobz/deploy.py) CLI tool.

Supports three deployment types:
- **`odoo`** — Odoo projects (auto-detected from `odoo-` / `openerp-` prefix)
- **`python`** — Generic Python services (FastAPI, Flask, workers, etc.)
- **`service`** — Any non-Python application where build/start commands are operator-defined

**Scope:** deploy CLI only. Does NOT handle SSH key setup, PostgreSQL provisioning, or Odoo module development.

---

## Installation

### Local machine (operator)

```bash
uv tool install deploy
```

### Remote server (target host)

Install tools required by the deployment type:

```bash
# Odoo deployments
uv tool install odoo-venv
uv tool install odoo-addons-path
uv tool install git-aggregator

# Python deployments
uv tool install uv   # usually pre-installed
```

---

## Instance Name Convention

```
<type_prefix>-<project_slug>-<environment>[-<suffix>]
```

| Segment | Examples |
|---------|---------|
| `type_prefix` | `odoo`, `openerp`, `service` |
| `environment` | `integration`, `staging`, `production`, `hotfix`, `debug`, `demo` |
| `suffix` | Optional: `-02`, `-eu`, `-vn` |

**Examples:**
```
odoo-myproject-production
odoo-myproject-staging-02
service-myapi-production-eu
```

---

## Configuration File (`deploy.yml`)

Lives **locally** on the operator's machine (not committed to the project repo).

```yaml
# deploy.yml

odoo-myproject-production:
  ssh_host: deploy@myserver.example.com
  ssh_port: 22                              # optional, default 22
  repo_url: git@github.com:org/repo.git    # used by configure
  # type: odoo                             # auto-detected from "odoo-" prefix
  db: myproject                            # optional; defaults to instance_name

  hooks:
    pre-update:
      - ./scripts/check_disk_space.sh
    pre-update-required:
      - ./scripts/run_tests.sh             # failure aborts the update
    pre-update-success:
      - ./scripts/notify.sh "Pre-checks passed"
    pre-update-fail:
      - ./scripts/notify.sh "Pre-checks failed"
    post-update:
      - ./scripts/smoke_test.sh
    post-update-success:
      - ./scripts/notify.sh "Update succeeded"
    post-update-fail:
      - ./scripts/notify.sh "Update failed"

service-myapi-production:
  ssh_host: deploy@apiserver.example.com
  repo_url: git@github.com:org/myapi.git
  type: python
  exec_start: python -m myapi.main

service-myui-production:
  ssh_host: deploy@uiserver.example.com
  repo_url: git@github.com:org/myui.git
  type: service
  build: npm ci && npm run build
  exec_start: node dist/server.js
```

CLI arguments always override config file values.

---

## Commands

### `deploy configure` — Set up a new instance

Clones the repo, sets up the application environment, and registers a systemd user unit.

```bash
deploy configure <instance_name> [ssh_host] [repo_url] [--type odoo|python|service] [-p PORT] [--force]
```

**Options:**
- `--type` — Override auto-detected type
- `--force` — Re-run setup even if the instance directory already exists
- `-p` — SSH port (default: 22)

**Examples:**
```bash
# Odoo instance (type auto-detected from "odoo-" prefix)
deploy configure odoo-myproject-staging deploy@server.example.com git@github.com:org/repo.git

# With config file (only instance name needed)
deploy configure odoo-myproject-staging

# Python service
deploy configure service-myapi-production deploy@server.example.com git@github.com:org/api.git --type python

# Force re-setup
deploy configure odoo-myproject-staging --force
```

**What it does:**
1. Connects via SSH (or runs locally if no `ssh_host`)
2. Clones the repo into `~/<instance_name>` on the remote host
3. Sets up the environment:
   - **odoo**: runs `odoo-venv` + `odoo-addons-path`
   - **python**: creates `.venv`, installs from `requirements.txt` or `pyproject.toml`
   - **service**: runs the `build` command from `deploy.yml`
4. Writes and enables a systemd user unit at `~/.config/systemd/user/<instance_name>.service`

---

### `deploy update` — Deploy / update an existing instance

Pulls latest code, updates dependencies, applies changes, and restarts the service.

```bash
deploy [--config FILE] update <instance_name> [ssh_host] [-p PORT] [--type odoo|python|service] [--db DATABASE] [--ignore-hooks]
```

**Options:**
- `--db` — (Odoo only) Override the target database name
- `--ignore-hooks` — Skip all hook execution

**Examples:**
```bash
# With config file
deploy update odoo-myproject-staging

# Override database
deploy update odoo-myproject-staging --db myproject_alt

# Skip hooks
deploy update odoo-myproject-staging --ignore-hooks

# Specify config file location
deploy --config /path/to/deploy.yml update odoo-myproject-staging
```

**Hook execution order:**

| Hook | When | Blocks on failure? |
|------|------|--------------------|
| `pre-update` | Before update | No |
| `pre-update-required` | After pre-update | **Yes** |
| `pre-update-success` / `pre-update-fail` | After pre-update phase | No |
| `post-update` | After update | No |
| `post-update-success` / `post-update-fail` | After update | No |

**What it does (Odoo):**
1. Runs pre-update hooks
2. `git pull` in `~/<instance_name>`
3. `odoo-venv update .venv --backup --yes`
4. `click-odoo-upgrade -d <database_name>`
5. `systemctl --user restart <instance_name>`
6. Runs post-update hooks

---

### `deploy status` — Check instance state

```bash
deploy [--config FILE] status <instance_name> [ssh_host] [-p PORT]
```

**Output:**
```
Instance:  odoo-myproject-staging
Remote:    git@github.com:org/repo.git
Branch:    main (abc1234)
Unit:      active (running) since 2026-03-09 08:12:03
```

---

## Workflow Guide

### New instance setup

1. Ensure the remote server has the required tools installed
2. Create or update `deploy.yml` with the instance configuration
3. Run `deploy configure <instance_name>`
4. Verify with `deploy status <instance_name>`

### Regular deployment

1. Run `deploy update <instance_name>`
2. Monitor output for hook results and update status
3. Verify with `deploy status <instance_name>`

### Always ask for confirmation before production deployments

Before running any `deploy update` or `deploy configure` on a **production** instance, present the full command to the user and wait for explicit approval.

---

## Global Options

| Option | Default | Description |
|--------|---------|-------------|
| `--config FILE` | `deploy.yml` | Path to config file (local machine) |
| `--verbose` | `False` | Print each remote command and its output |
