# deploy update

Pull the latest code, update dependencies, and restart the service on the
target host.

## Signature

```bash
deploy [--config FILE] update <instance_name> [<ssh_host>] \
  [--type odoo|python|service] [-p PORT] [--db DATABASE] [--ignore-hooks]
```

## Arguments

| Argument | Required without config | Description |
|----------|------------------------|-------------|
| `instance_name` | Always | Name of the previously configured instance |
| `ssh_host` | If not in config | SSH target, or `localhost` / omit for local execution |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | auto | Deployment type: `odoo`, `python`, or `service` |
| `-p`, `--port` | — | SSH port on the remote host |
| `--db` | `<instance_name>` | Override target database name (Odoo only) |
| `--ignore-hooks` | `False` | Skip all hook execution |

## Steps

1. **Connect** — open SSH connection if `ssh_host` is not `localhost`.
2. **`pre-update` hooks** — non-blocking.
3. **`pre-update-required` hooks** — abort with exit 1 on failure; runs `pre-update-fail` first.
4. **`pre-update-success` or `pre-update-fail`** — based on steps 2–3 outcome.
5. **Pull latest code** — `git pull` inside `~/<instance_name>`.
6. **Update dependencies / rebuild**

    === "odoo"
        ```bash
        odoo-venv update .venv --backup --yes
        ```

    === "python"
        ```bash
        uv pip install -r requirements.txt   # if requirements.txt exists
        uv sync                              # if pyproject.toml exists
        ```

    === "service"
        Runs the `build` command from `deploy.yml`.

7. **Apply changes**

    === "odoo"
        ```bash
        ~/<instance_name>/.venv/bin/click-odoo-upgrade -d <database_name>
        systemctl --user restart <instance_name>
        ```

    === "python / service"
        ```bash
        systemctl --user restart <instance_name>
        ```

8. **`post-update` hooks**, then `post-update-success` or `post-update-fail`.

## Exit codes

| Condition | Exit code |
|-----------|-----------|
| All steps succeeded | 0 |
| SSH connection failed | 1 |
| Instance directory not found | 1 |
| `pre-update-required` hook failed | 1 |
| `git pull` failed | 1 |
| Dependency update failed | 1 |
| Upgrade / restart command failed | 1 |

## Examples

```bash
# Standard update — reads all values from deploy.yml
deploy update odoo-myproject-production

# Override database name
deploy update odoo-myproject-production --db myproject_alt

# Custom SSH port
deploy update odoo-myproject-staging -p 2222

# Skip hooks for emergency deploys
deploy update odoo-myproject-production --ignore-hooks

# Verbose output to see every remote command
deploy --verbose update odoo-myproject-production
```
