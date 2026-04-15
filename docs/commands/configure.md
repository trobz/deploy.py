# deploy configure

Clone a repository, set up the application environment, and install a
systemd user unit on the target host.

## Signature

```bash
deploy [--config FILE] configure <instance_name> [<ssh_host>] [<repo_url>] \
  [--type odoo|python|service] [-p PORT] [--force]
```

## Arguments

| Argument | Required without config | Description |
|----------|------------------------|-------------|
| `instance_name` | Always | Logical name for the instance |
| `ssh_host` | If not in config | SSH target, or `localhost` / omit for local execution |
| `repo_url` | If not in config | Git repository URL |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `--type` | auto | Deployment type: `odoo`, `python`, or `service` |
| `-p`, `--port` | — | SSH port on the remote host |
| `--force` | `False` | Re-run steps 3–4 even if the instance directory already exists |

## Steps

1. **Connect** — open SSH connection if `ssh_host` is set and is not `localhost`.
2. **Clone repository** — clone `repo_url` into `~/<instance_name>`.
   - If the directory already exists without `--force`: abort with exit 1.
   - With `--force`: skip clone, proceed to step 3.
3. **Set up environment**

    === "odoo"

        ```bash
        odoo-venv create --project-dir ~/<instance_name> --preset project
        odoo-addons-path ~/<instance_name>
        ```

    === "python"

        ```bash
        uv venv .venv
        uv pip install -r requirements.txt   # if requirements.txt exists
        uv sync                              # if pyproject.toml exists
        ```

    === "service"

        Runs the `build` command defined in `deploy.yml`.

4. **Install systemd unit** — render the bundled template and register it:

    ```bash
    mkdir -p ~/.config/systemd/user/
    # write ~/<instance_name>.service
    loginctl enable-linger
    systemctl --user daemon-reload
    systemctl --user enable --now <instance_name>
    ```

## Exit codes

| Condition | Exit code |
|-----------|-----------|
| All steps succeeded | 0 |
| SSH connection failed | 1 |
| Repository already exists (without `--force`) | 1 |
| Git clone failed | 1 |
| Virtual environment step failed | 1 |
| Template rendering / write failed | 1 |

## Examples

```bash
# Auto-detect type from prefix, read config from deploy.yml
deploy configure odoo-myproject-production

# Explicit SSH host and repo
deploy configure service-api-staging deploy@host.example.com git@github.com:org/api.git

# Custom SSH port
deploy configure odoo-myproject-staging -p 2222

# Re-run environment setup without re-cloning
deploy configure odoo-myproject-production --force
```
