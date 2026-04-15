# deploy status

Show the current state of a deployment instance: git info and systemd unit status.

## Signature

```bash
deploy [--config FILE] status <instance_name> [<ssh_host>] [-p PORT]
```

## Arguments

| Argument | Required without config | Description |
|----------|------------------------|-------------|
| `instance_name` | Always | Name of the previously configured instance |
| `ssh_host` | If not in config | SSH target, or `localhost` / omit for local execution |

## Options

| Option | Default | Description |
|--------|---------|-------------|
| `-p`, `--port` | — | SSH port on the remote host |

## Output

```
Instance:  odoo-myproject-production
Remote:    git@github.com:org/repo.git
Branch:    main (abc1234)
Unit:      active (running) since 2026-03-09 08:12:03
```

## Steps

1. **Connect** — open SSH connection if `ssh_host` is not `localhost`.
2. **Git info** — inside `~/<instance_name>`:
   - `git remote get-url origin` → remote URL
   - `git rev-parse --abbrev-ref HEAD` → branch
   - `git rev-parse --short HEAD` → commit hash
3. **Unit status** — via `systemctl --user show`.

## Exit codes

| Condition | Exit code |
|-----------|-----------|
| All steps succeeded | 0 |
| SSH connection failed | 1 |
| Instance directory not found | 1 |

## Examples

```bash
# Read ssh_host from deploy.yml
deploy status odoo-myproject-production

# Explicit host
deploy status odoo-myproject-production deploy@myserver.example.com

# Custom SSH port
deploy status odoo-myproject-production -p 2222
```
