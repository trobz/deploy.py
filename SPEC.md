# deploy — Specification

## Overview

`deploy` is a CLI tool for deploying and managing applications on remote servers over SSH.
It supports multiple deployment types:

- **`odoo`** — Odoo projects, relying on [`odoo-venv`](https://github.com/trobz/odoo-venv.git) for
  virtual environment creation and `odoo-addons-path` for add-on discovery.
- **`python`** — Generic Python services (FastAPI, Flask, background workers, etc.).
- **`service`** — Any other application type (Node.js, Ruby, compiled binaries, etc.) where the
  operator controls the build and start commands via configuration.

The tool is distributed as a Python package with a single `deploy` console script entry point.

---

## Instance Name Convention

Instance names follow the pattern:

```
<type_prefix>-<project_slug>-<environment>[-<suffix>]
```

| Segment          | Values / Notes                                                                 |
|------------------|--------------------------------------------------------------------------------|
| `type_prefix`    | Always first. `odoo`, `openerp` → Odoo · `service` → Python                  |
| `project_slug`   | Everything between prefix and environment. May contain hyphens.               |
| `environment`    | `integration`, `staging`, `production`, `hotfix`, `debug`, `demo`             |
| `suffix`         | Optional. Short qualifier appended after the environment: `-02`, `-eu`, `-vn` |

**Examples**

```
odoo-myproject-production
odoo-myproject-staging-02
odoo-my-cool-project-production
openerp-legacy-integration
service-myapi-production-eu
service-worker-staging
```

**Parsing algorithm** — because the slug may contain hyphens, the name is parsed from both ends:

1. **Prefix** — everything before the first `-`.
2. **Suffix** — if the last segment does not match a known environment, treat it as a suffix and
   strip it.
3. **Environment** — the last remaining segment, which must be a known value
   (`integration`, `staging`, `production`, `hotfix`, `debug`, `demo`).
4. **Slug** — all segments between prefix and environment, joined with `-`.

**Type auto-detection** — when `--type` is not provided and no `type` key exists in `deploy.yml`,
the prefix is used to derive the type:

| Instance name prefix | Detected type |
|----------------------|---------------|
| `odoo-`, `openerp-`  | `odoo`        |
| `service-`           | `python`      |
| *(anything else)*    | error — `--type` is required |

The `service` deployment type (non-Python) is never auto-detected. It must be set explicitly via
`--type service` or `type: service` in `deploy.yml`.

**Database name** (Odoo only) — defaults to `instance_name` verbatim. Override with `--db` or the
`db` key in `deploy.yml`.

---

## Global Options

These options are accepted by all commands:

| Option        | Default        | Description                                                    |
|---------------|----------------|----------------------------------------------------------------|
| `--config`    | `deploy.yml`   | Path to the configuration file (resolved locally)             |
| `--verbose`   | `False`        | Print each remote command and its output as it runs           |

When `--config` is provided (or `deploy.yml` exists in the current directory), values are read
from the section matching `<instance_name>`. **CLI arguments always take precedence** over config
file values, which take precedence over built-in defaults.

---

## Commands

### 1. `deploy configure`

**Signature**

```bash
deploy [--config FILE] configure <instance_name> [<ssh_host>] [<repo_url>] [--type odoo|python|service] [-p <ssh_port>]
```

**Arguments**

| Argument        | Required without config | Description                                                                  |
|----------------|------------------------|------------------------------------------------------------------------------|
| `instance_name` | Always                 | Logical name for the instance (used for paths and service name)             |
| `ssh_host`      | If not in config       | SSH target, or `localhost` / omit to deploy locally without SSH             |
| `ssh_port`      | If not in config       | SSH port, default 22                                                        |
| `repo_url`      | If not in config       | Git repository URL (e.g. `git@github.com:org/repo.git`)                     |

**Options**

| Option         | Default  | Description                                                                                         |
|----------------|----------|-----------------------------------------------------------------------------------------------------|
| `--type`       | auto     | Deployment type: `odoo`, `python`, or `service`; auto-detected from instance name prefix if omitted |
| `--force`      | `False`  | Re-run steps 3–4 even if the instance directory already exists                                      |

**Steps (executed in order)**

1. **Connect** — if `ssh_host` is set and is not `localhost`, open an SSH connection.
   Otherwise all subsequent commands run as local subprocesses.

2. **Clone repository** — clone `repo_url` into `~/<instance_name>` on the target host.
   - If the directory already exists and is a valid Git repository:
     - Without `--force`: abort with an error and a hint to use `--force` or a different name.
     - With `--force`: skip the clone, proceed to steps 3–4.

3. **Set up the application environment**

   - **`odoo`**: create a virtual environment using `odoo-venv`:
     ```bash
     odoo-venv --project-dir ~/<instance_name>
     ```
     After creation, run `odoo-addons-path` to detect and record the add-on directories.
   - **`python`**: create a virtual environment and install dependencies using `uv`:
     ```bash
     uv venv .venv
     if [ -e requirements.txt ]; then uv pip install -r requirements.txt; fi
     if [ -e pyproject.toml ]; then uv sync; fi
     ```
   - **`service`**: run the `build` command defined in the local `deploy.yml`
     (e.g. `npm ci && npm run build`, `cargo build --release`), executed remotely on the target
     host. No Python venv is created.

4. **Install systemd user unit** — render the appropriate bundled template, write the unit file,
   and register it with the user-level systemd instance (no `sudo` required).

   - Unit file destination: `~/.config/systemd/user/<instance_name>.service`
   - Template variables per type:
     - **`odoo`**: `instance_name`, `instance_path`, `venv_path`, `odoo_addons_path`
     - **`python`**: `instance_name`, `instance_path`, `venv_path`, `exec_start`
     - **`service`**: `instance_name`, `instance_path`, `exec_start`
   - After writing the unit file, run:
     ```
     loginctl enable-linger
     systemctl --user daemon-reload
     systemctl --user enable --now <instance_name>
     ```
     `loginctl enable-linger` ensures the user's systemd instance (and all `--user` units) survive
     logout. It is idempotent and safe to re-run.

**Exit conditions**

| Condition                                    | Exit code |
|----------------------------------------------|-----------|
| All steps succeeded                          | 0         |
| SSH connection failed (remote targets only)  | 1         |
| Repository already exists (without `--force`)| 1         |
| Git clone failed                   | 1         |
| Virtual environment step failed    | 1         |
| Template rendering / write failed  | 1         |

---

### 2. `deploy update`

**Signature**

```bash
deploy [--config FILE] update <instance_name> [<ssh_host>] [-p <ssh_port>] [--type odoo|python|service] [--db DATABASE]
```

**Arguments**

| Argument        | Required without config | Description                                                                  |
|----------------|------------------------|------------------------------------------------------------------------------|
| `instance_name` | Always                 | Name of the previously configured instance                                  |
| `ssh_host`      | If not in config       | SSH target, or `localhost` / omit to deploy locally without SSH             |
| `ssh_port`      | If not in config       | SSH port, default 22                                                        |

**Options**

| Option             | Default           | Description                                              |
|--------------------|-------------------|----------------------------------------------------------|
| `--type`           | auto              | Deployment type: `odoo`, `python`, or `service`; auto-detected from instance name prefix if omitted |
| `--db`             | `<instance_name>` | (Odoo only) Override the target database name            |
| `--ignore-hooks`   | `False`           | Skip all hook execution                                  |

**Hooks**

Hooks are shell commands defined in `deploy.yml` under a `hooks` key, executed remotely on
`ssh_host` from the `~/<instance_name>` working directory.

```yaml
# deploy.yml
<instance_name>:
  hooks:
    pre-update:
      - ./scripts/check_disk_space.sh
      - ./scripts/notify_slack.sh "Update starting"
    pre-update-required:
      - ./scripts/run_tests.sh        # update is aborted if this fails
    pre-update-success:
      - ./scripts/notify_slack.sh "Pre-checks passed"
    pre-update-fail:
      - ./scripts/notify_slack.sh "Pre-checks failed"
    post-update:
      - ./scripts/smoke_test.sh
    post-update-success:
      - ./scripts/notify_slack.sh "Update succeeded"
    post-update-fail:
      - ./scripts/notify_slack.sh "Update failed"
```

This allows a single `deploy.yml` to carry configuration for multiple instances in the same
repository.

Hook semantics:

| Hook name              | When it runs                                           | Blocks update on failure? |
|------------------------|--------------------------------------------------------|---------------------------|
| `pre-update`           | Before any update step                                 | No                        |
| `pre-update-required`  | After `pre-update`; failure aborts the update          | **Yes**                   |
| `pre-update-success`   | After pre-update phase, only if all hooks succeeded    | No                        |
| `pre-update-fail`      | After pre-update phase, only if any hook failed        | No                        |
| `post-update`          | After update completes (success or failure)            | No                        |
| `post-update-success`  | After update, only if it succeeded                     | No                        |
| `post-update-fail`     | After update, only if it failed                        | No                        |

**Steps (executed in order)**

1. **Connect** — if `ssh_host` is set and is not `localhost`, open an SSH connection.
   Otherwise all subsequent commands run as local subprocesses.

2. **Run `pre-update` hooks** — execute all `pre-update` commands in order.

3. **Run `pre-update-required` hooks** — execute in order; if any fails, run `pre-update-fail`
   hooks and abort with exit code 1.

4. **Run `pre-update-success` or `pre-update-fail`** — based on the outcome of steps 2–3.

5. **Pull latest code** — inside `~/<instance_name>`, run `git pull`.
   Abort if the directory does not exist or is not a Git repository.

6. **Update dependencies / rebuild**

   - **`odoo`**: the script expects all changes in dependencies, even from odoo, are explicitly listed in requirements.txt, re-run `uv pip install -r requirements.txt` to sync the virtual environment.
   - **`python`**: run `uv pip install -r requirements.txt` (if the file exists) or `uv sync` if the file pyproject.toml exists.
   - **`service`**: re-run the `build` command from `deploy.yml`.

7. **Apply changes**

   - **`odoo`**: activate the virtual environment and run the upgrade, then restart the unit:
     ```bash
     ~/<instance_name>/.venv/bin/click-odoo-upgrade -d <database_name>
     systemctl --user restart <instance_name>
     ```
   - **`python`** / **`service`**: restart the user-level systemd unit:
     ```bash
     systemctl --user restart <instance_name>
     ```

8. **Run `post-update` hooks**, then `post-update-success` or `post-update-fail` depending on
   whether step 7 succeeded.

**Exit conditions**

| Condition                                    | Exit code |
|----------------------------------------------|-----------|
| All steps succeeded                          | 0         |
| SSH connection failed (remote targets only)  | 1         |
| Instance directory not found                 | 1         |
| `pre-update-required` hook failed            | 1         |
| `git pull` failed                            | 1         |
| Dependency update failed                     | 1         |
| Upgrade / restart command failed             | 1         |

---

### 3. `deploy status`

**Signature**

```bash
deploy [--config FILE] status <instance_name> [<ssh_host>] [-p <ssh_port>]
```

**Arguments**

| Argument        | Required without config | Description                                                                  |
|----------------|------------------------|------------------------------------------------------------------------------|
| `instance_name` | Always                 | Name of the previously configured instance                                  |
| `ssh_host`      | If not in config       | SSH target, or `localhost` / omit to deploy locally without SSH             |
| `ssh_port`      | If not in config       | SSH port, default 22                                                        |

**Output**

Prints a summary of the instance on the remote host:

```
Instance:  <instance_name>
Remote:    git@github.com:org/repo.git
Branch:    main (abc1234)
Unit:      active (running) since 2026-03-09 08:12:03
```

**Steps (executed in order)**

1. **Connect** — if `ssh_host` is set and is not `localhost`, open an SSH connection.
   Otherwise all subsequent commands run as local subprocesses.

2. **Git info** — inside `~/<instance_name>`, run:
   - `git remote get-url origin` → remote URL
   - `git rev-parse --abbrev-ref HEAD` → current branch
   - `git rev-parse --short HEAD` → current commit hash

3. **Unit status** — run `systemctl --user is-active <instance_name>` and
   `systemctl --user show <instance_name> --property=ActiveState,SubState,ActiveEnterTimestamp`
   to retrieve state and start time.

**Exit conditions**

| Condition                                   | Exit code |
|---------------------------------------------|-----------|
| All steps succeeded                         | 0         |
| SSH connection failed (remote targets only) | 1         |
| Instance directory not found                | 1         |

---

## Configuration File

`deploy.yml` is a YAML file where each top-level key is an `instance_name`. It centralises
per-instance defaults so commands can be invoked with only the instance name:

```bash
deploy update my-project          # reads ssh_host, type, db, hooks from deploy.yml
deploy update my-project --db alt # overrides only the db
```

**Full schema**

```yaml
# deploy.yml

odoo-myproject-production:
  # Arguments
  ssh_host: deploy@myserver.example.com   # omit or set to "localhost" for local deployment
  repo_url: git@github.com:org/repo.git   # used by configure
  # type: odoo                            # auto-detected from "odoo-" prefix; can be overridden
  db: myproject                           # Odoo only; defaults to instance_name if omitted

  # service / python only
  exec_start: python -m myapp.main:app    # `python -m module path` or `python file.py` or `fastapi entry` for python, can omit for server.py; verbatim for service
  build: npm ci && npm run build          # service only

  # Hooks (update command)
  hooks:
    pre-update:
      - ./scripts/check_disk_space.sh
    pre-update-required:
      - ./scripts/run_tests.sh
    pre-update-success:
      - ./scripts/notify_slack.sh "Pre-checks passed"
    pre-update-fail:
      - ./scripts/notify_slack.sh "Pre-checks failed"
    post-update:
      - ./scripts/smoke_test.sh
    post-update-success:
      - ./scripts/notify_slack.sh "Update succeeded"
    post-update-fail:
      - ./scripts/notify_slack.sh "Update failed"
```

**Precedence** (highest → lowest): CLI argument → `deploy.yml` value → built-in default.

The config file is resolved **locally** (on the machine running `deploy`), not on the remote host.
It is **not** committed to the project repository — it lives outside the deployment folder, typically
alongside the operator's other deployment scripts or in a private configuration repository.

---

## Bundled Templates

### `deploy/templates/odoo.service.j2`

```ini
[Unit]
Description=Odoo instance {{ instance_name }}
After=network.target postgresql.service

[Service]
Type=simple
WorkingDirectory={{ instance_path }}
ExecStart={{ venv_path }}/bin/python {{ venv_path }}/bin/odoo \
    --config {{ instance_path }}/config/odoo.conf \
    --addons-path $({{ odoo_addons_path }} {{ instance_path }})
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```

### `deploy/templates/python.service.j2`

```ini
[Unit]
Description=Python service {{ instance_name }}
After=network.target

[Service]
Type=simple
WorkingDirectory={{ instance_path }}
ExecStart={{ venv_path }}/bin/{{ exec_start }}
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```

### `deploy/templates/service.service.j2`

Generic template for non-Python services. `exec_start` is taken verbatim from `deploy.yml`.

```ini
[Unit]
Description={{ instance_name }}
After=network.target

[Service]
Type=simple
WorkingDirectory={{ instance_path }}
ExecStart={{ exec_start }}
Restart=on-failure
RestartSec=5s

[Install]
WantedBy=default.target
```

---

## Project Structure

```
deploy/
├── deploy/
│   ├── __init__.py
│   ├── cli.py               # Click entry point, registers commands
│   ├── command/
│   │   ├── configure.py     # `configure` command
│   │   ├── update.py        # `update` command
│   │   └── status.py        # `status` command
│   ├── utils/
│   │   ├── executor.py      # Executor abstraction: SSH (remote) or subprocess (local)
│   │   ├── venv.py          # Virtual environment helpers (odoo-venv / standard)
│   │   ├── addons.py        # odoo-addons-path integration
│   │   ├── config.py        # deploy.yml loader and CLI arg merging
│   │   └── render.py        # Jinja2 template rendering
│   └── templates/
│       ├── odoo.service.j2
│       ├── python.service.j2
│       └── service.service.j2
├── setup.py / pyproject.toml
└── README.md
```

---

## CLI Entry Point

```python
# setup.py / pyproject.toml
entry_points={
    "console_scripts": [
        "deploy=deploy.cli:cli",
    ]
}
```

---

## Dependencies

| Package    | Purpose                          |
|------------|----------------------------------|
| `click`    | CLI framework                    |
| `jinja2`   | Template rendering               |
| `pyyaml`   | `deploy.yml` parsing             |

All commands go through an **executor abstraction** (`executor.py`) that transparently runs
commands either via the system `ssh` binary (remote; respects `~/.ssh/config` and agent
forwarding) or as local subprocesses when `ssh_host` is absent or `localhost`.
The following tools must be pre-installed on the target host:

| Tool              | Required for         |
|-------------------|----------------------|
| `odoo-venv`       | `odoo` deployments   |
| `odoo-addons-path`| `odoo` deployments   |
| `uv`              | `python` deployments |
| `click-odoo-contrib` | `odoo` venv (not a local dep of `deploy`) |
| `git-aggregator`  | `odoo` deployments   |

For `service` deployments, any additional runtime or toolchain (Node.js, Ruby, Rust, etc.) must
also be pre-installed; `deploy` only orchestrates `git pull`, the `build` command, and systemd
service management.
