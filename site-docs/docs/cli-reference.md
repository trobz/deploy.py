---
icon: lucide/book
description: Complete reference for every trobz-deploy command, auto-generated from --help.
tags:
  - reference
  - cli
---

!!! info "Auto-generated"
    This page is regenerated from `deploy --help` by `make cli-docs`.
    Do not edit by hand — your changes will be overwritten on the next build.

# `deploy`

Deploy and manage applications on remote servers over SSH.

**Usage**:

```console
$ deploy [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `-V, --version`: Display the trobz-deploy version.
* `--config FILE`: Path to the configuration file.  \[default: deploy.yml\]
* `--verbose`: Print each remote command and its output as it runs.
* `--install-completion`: Install completion for the current shell.
* `--show-completion`: Show completion for the current shell, to copy it or customize the installation.
* `--help`: Show this message and exit.

**Commands**:

* `configure`: Configure a new deployment instance.
* `update`: Update an existing deployment instance.
* `restart`: Restart the systemd unit for a deployment...
* `status`: Show status of a deployment instance.

## `deploy configure`

Configure a new deployment instance.

**Usage**:

```console
$ deploy configure [OPTIONS] INSTANCE_NAME [SSH_HOST] [REPO_URL]
```

**Arguments**:

* `INSTANCE_NAME`: \[required\]
* `[SSH_HOST]`
* `[REPO_URL]`

**Options**:

* `--type [odoo|python|service]`: Deployment type (auto-detected from instance name prefix if omitted).
* `-p, --port INTEGER`: SSH port on the remote host.
* `--repo-subdir TEXT`: Subdirectory within the repo to use as the service root (for monorepos).
* `--repo-branch TEXT`: Git branch to clone and track (defaults to the repository&#x27;s default branch).
* `--watch`: Stream service logs with journalctl after a successful configure. Also merge with odoo and click-odoo-update logs if applicable.
* `--steps TEXT`: Comma-separated steps to run, or &#x27;all&#x27;. Available: dir, pg, gitaggregate, venv, unit.  \[default: all\]
* `--except TEXT`: Comma-separated steps to skip. Available: dir, pg, gitaggregate, venv, unit.
* `--dry-run`: Go through all steps without running any writing/destructive commands.
* `--help`: Show this message and exit.

## `deploy update`

Update an existing deployment instance.

**Usage**:

```console
$ deploy update [OPTIONS] INSTANCE_NAME [SSH_HOST]
```

**Arguments**:

* `INSTANCE_NAME`: \[required\]
* `[SSH_HOST]`

**Options**:

* `--type [odoo|python|service]`: Deployment type (auto-detected from instance name prefix if omitted).
* `--db TEXT`: Override the target database name (Odoo only). Can be comma-separated for multiple databases.
* `-p, --port INTEGER`: SSH port on the remote host.
* `--ignore-hooks`: Skip all hook execution.
* `--repo-subdir TEXT`: Subdirectory within the repo to use as the service root (for monorepos).
* `--repo-branch TEXT`: Git branch to pull (defaults to the currently checked-out branch).
* `--watch`: Stream service logs with journalctl after a successful update. Also merge with odoo and click-odoo-update logs if applicable.
* `--steps TEXT`: Comma-separated steps to run, or &#x27;all&#x27;. Available: pull, venv, db.  \[default: all\]
* `--except TEXT`: Comma-separated steps to skip. Available: pull, venv, db.
* `--ignore-addons TEXT`: Comma-separated list of addons to ignore. These will not be updated if their checksum has changed. Use with care. Passed to click-odoo-update --ignore-addons.
* `--ignore-core-addons`: Passed to click-odoo-update --ignore-core-addons. If this option is set, Odoo CE and EE addons are not updated. This is normally safe, due the Odoo stable policy.
* `--update-all`: Passed to click-odoo-update --update-all. Force a complete upgrade (-u base).
* `-m, --modules TEXT`: Comma-separated list of modules to update by running Odoo directly (-u MODULES --stop-after-init), skipping click-odoo-update.
* `--dry-run`: Go through all steps without running any writing/destructive commands.
* `--help`: Show this message and exit.

## `deploy restart`

Restart the systemd unit for a deployment instance.

**Usage**:

```console
$ deploy restart [OPTIONS] INSTANCE_NAME [SSH_HOST]
```

**Arguments**:

* `INSTANCE_NAME`: \[required\]
* `[SSH_HOST]`

**Options**:

* `--type [odoo|python|service]`: Deployment type (auto-detected from instance name prefix if omitted).
* `-p, --port INTEGER`: SSH port on the remote host.
* `--watch`: Stream service logs with journalctl after restarting. Also merge with odoo and click-odoo-update logs if applicable.
* `--help`: Show this message and exit.

## `deploy status`

Show status of a deployment instance.

**Usage**:

```console
$ deploy status [OPTIONS] INSTANCE_NAME [SSH_HOST]
```

**Arguments**:

* `INSTANCE_NAME`: \[required\]
* `[SSH_HOST]`

**Options**:

* `--type [odoo|python|service]`: Deployment type (auto-detected from instance name prefix if omitted).
* `-p, --port INTEGER`: SSH port on the remote host.
* `--watch`: Stream service logs with journalctl after showing status. Also merge with odoo and click-odoo-update logs if applicable.
* `--help`: Show this message and exit.
