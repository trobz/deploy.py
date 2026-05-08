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
| `db` | string | `update` | Target database name (Odoo only). |
| `exec_start` | string | `configure` | Entry point for python/service systemd unit. |
| `build` | string | `configure`, `update` | Build command for `service` type. |
| `hooks` | mapping | `update` | Lifecycle hooks — see [Hooks](hooks.md). |

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
