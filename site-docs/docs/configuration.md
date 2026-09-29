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

  # Where Odoo lives when it is not inside the project (odoo deployments). Passed to
  # `odoo-addons-path` (systemd unit, `update`, version detection) as --odoo-dir / --addons-dir,
  # and used to build the venv. `addons_dir` may also be a list.
  odoo_dir: /opt/odoo/code/odoo/odoo/20.0/
  addons_dir: /opt/odoo/code/odoo/enterprise/20.0,/opt/odoo/myproject

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
      no-cache: true
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
| `odoo-addons-path` | `odoo-addons-path` | `--odoo-dir` / `--addons-dir` from `odoo_dir` / `addons_dir` |
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
    odoo-config:
      enterprise: true
      version: 20.0
```

`odoo_dir` and `addons_dir` (instance level) are rendered as `odoo-addons-path --odoo-dir … --addons-dir …`
wherever the add-ons path is resolved: the generated systemd unit (at every start), `update`, and
`configure`'s version detection. `tools.odoo-addons-path` is merged over them for any other option
or to override one. Don't set `addons_path` under `config:`; the unit computes it at start-up, so
`configure` rejects it.

When either is set, `configure` also resolves the add-ons path before creating the venv and passes
`--odoo-dir` and `--addons-path` to `odoo-venv create`. With both given, `odoo-venv` skips its own
layout detection, which would not find an Odoo source living outside the project. The add-ons
path is recorded in the venv's `.odoo-venv.toml`. With the `project` preset, requirements are
installed from the project's `requirements.txt`, not scanned from the add-ons dirs. Keys under `tools.odoo-venv` override the derived
values. With neither set, `odoo-venv` runs with its defaults.

`configure` reads `version` and `odoo_edition` from `odoo-addons-path --format=json` in the codebase:
the version feeds `--version`, and an `EE` edition (an `enterprise` dir in the add-ons path, so
`addons_dir` must include it) adds `--enterprise`. `tools.odoo-config.version` and
`tools.odoo-config.enterprise` take precedence (`enterprise: false` drops the flag). When both are set
the codebase is not probed at all, and `configure` will not prompt for the version. `tools.odoo-config.version`
also takes precedence over the top-level `version` and `preset` keys, which keep working.

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
