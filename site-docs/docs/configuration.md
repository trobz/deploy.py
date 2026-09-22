# Configuration

`deploy.yml` is a YAML file where each top-level key is an `instance_name`.
It centralises per-instance defaults so commands can be invoked with only the
instance name.

```bash
deploy update my-project           # reads all values from deploy.yml
deploy update my-project --db alt  # overrides only the db
```

## Precedence

Highest → lowest:

1. **CLI argument**
2. **`deploy.yml` value**
3. **Built-in default**

## Full schema

```yaml
# deploy.yml

odoo-myproject-production:
  # SSH connection
  ssh_host: deploy@myserver.example.com   # omit or set "localhost" for local deployment
  ssh_port: 22                            # optional; defaults to SSH default (22)

  # Repository
  repo_url: git@github.com:org/repo.git   # used by `configure`

  # Deployment type
  # type: odoo                            # auto-detected from "odoo-" prefix; can be overridden

  # Odoo only
  db: myproject                           # defaults to instance_name if omitted

  # Multiple databases
  db:
    - myproject_staging
    - myproject_integration

  # Odoo config overrides — written to config/odoo.conf by `configure`
  config:
    workers: 4
    limit_time_cpu: 600

  # Command-line options for the tools `configure` runs. Each key under a tool is
  # rendered as `--key value` and merged over the options deploy passes by default,
  # so every option is passed exactly once. A matching key overrides the default,
  # `true` renders a bare flag, `false` / null drops the option, and a list repeats it.
  # Note the difference from `config:` above: that sets values *inside* odoo.conf,
  # while `tools.odoo-config` controls *how odoo-config is invoked*.
  tools:
    odoo-venv:                          # → odoo-venv create
      odoo-dir: /opt/odoo/code/odoo/odoo/20.0/
      addons-path: /opt/odoo/code/odoo/odoo/20.0/addons,/opt/odoo/code/odoo/enterprise/20.0
    odoo-config:                        # → odoo-config create
      enterprise: true
      output-format: all
      from:
        - /opt/odoo/shared/base.conf


  # Environment variables — written to config/server.env by `configure`.
  # Merged over the built-in thread-limit defaults (the value here wins).
  env:
    ODOO_SESSION_REDIS: 1
    ODOO_SESSION_REDIS_HOST: localhost

  # python / service only
  exec_start: myapp.main:app              # module path for python; verbatim for service
  build: npm ci && npm run build          # service only

  # Hooks (used by `update`)
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

## Options reference

| Key | Type | Commands | Description |
|-----|------|----------|-------------|
| `ssh_host` | string | all | SSH target. Omit or `localhost` for local execution. |
| `ssh_port` | integer | all | SSH port on the remote host. |
| `repo_url` | string | `configure` | Git repository URL. |
| `type` | string | all | Deployment type: `odoo`, `python`, or `service`. |
| `db` | string or list of string | `update` | Target database name (Odoo only). Can be a list for multiple names. |
| `exec_start` | string | `configure` | Entry point for python/service systemd unit. |
| `build` | string | `configure`, `update` | Build command for `service` type. |
| `config` | mapping | `configure` | Odoo config overrides written to `config/odoo.conf` (Odoo only). |
| `tools` | mapping | `configure` | Command-line options for the tools the steps run, keyed by tool (Odoo only) — see [Tool options](#tool-options). |
| `env` | mapping | `configure` | Environment variables written to `config/server.env`, merged over the built-in thread-limit defaults (Odoo only). |
| `hooks` | mapping | `update` | Lifecycle hooks — see [Hooks](hooks.md). |

## Tool options

The `configure` steps shell out to `odoo-venv` and `odoo-config`. The `tools` section sets
command-line options for them, keyed by tool:

| Tool key | Command | Options deploy passes by default |
|----------|---------|----------------------------------|
| `odoo-venv` | `odoo-venv create` | `--project-dir`, `--preset project` |
| `odoo-config` | `odoo-config create` | `--version`, `--preset`, `--instance-dir`, `--config` |

Your keys are merged over those defaults, so each option is passed exactly once:

- a key matching a default **overrides** it, keeping its position
- `true` renders a bare flag — `enterprise: true` → `--enterprise`
- `false` or null **drops** the option, including a default
- a list **repeats** the option — `from: [a, b]` → `--from a --from b`
- values are shell-quoted

```yaml
odoo-myproject-staging:
  tools:
    odoo-venv:
      odoo-dir: /opt/odoo/code/odoo/odoo/20.0/
      addons-path: /opt/odoo/code/odoo/odoo/20.0/addons,/opt/odoo/code/odoo/enterprise/20.0
    odoo-config:
      enterprise: true
      version: 20.0
```

`tools.odoo-config.version` also short-circuits version detection, so `configure` will not
probe the codebase or prompt for it. It takes precedence over the top-level `version` and
`preset` keys, which keep working.

Do not confuse `tools.odoo-config` with `config`: the former controls **how odoo-config is
invoked**, the latter sets **values written into odoo.conf**. `odoo-config` treats any option
it does not recognise as an odoo.conf value, so a CLI flag placed under `config` will not work.

## Multiple instances

A single `deploy.yml` can hold configuration for any number of instances:

```yaml
odoo-myproject-staging:
  ssh_host: deploy@staging.example.com
  repo_url: git@github.com:org/repo.git

odoo-myproject-production:
  ssh_host: deploy@prod.example.com
  repo_url: git@github.com:org/repo.git
  db: myproject_prod
```

!!! tip
    `deploy.yml` is resolved **locally** — on the machine running `deploy`, not on
    the remote host. Keep it outside your project repository in a private
    configuration directory.
