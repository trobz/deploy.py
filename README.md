# deploy

CLI tool for deploying and managing applications on remote servers over SSH.
It supports multiple deployment types:

- **`odoo`** — Odoo projects, relying on [`odoo-venv`](https://github.com/trobz/odoo-venv.git) for
  virtual environment creation and `odoo-addons-path` for add-on discovery.
- **`python`** — Generic Python services (FastAPI, Flask, background workers, etc.).
- **`service`** — Any other application type (Node.js, Ruby, compiled binaries, etc.)
  where the operator controls the build and start commands via configuration.

## Installation

With [`uv`](https://docs.astral.sh/uv/):

```bash
uv tool install trobz-deploy
```

On remote server where applications will be deployed:

```bash
uv tool install odoo-venv
uv tool install odoo-addons-path
uv tool install git-aggregator
```

Sample configuration file:

```yaml
openerp-my-project-staging:
  ssh_host: user@server.domain.com
  ssh_port: 1234
  repo_url: git@github.com:org/my-project.git
  hooks:
    pre-update:
      - echo "Update starting"
    pre-update-required:
      - echo "Update required"
    pre-update-success:
      - echo "Pre-checks passed"
    pre-update-fail:
      - echo "Pre-checks failed"
    post-update:
      - echo "Post update"
    post-update-success:
      - echo "Update succeeded"
    post-update-fail:
      - echo "Update failed"
```

## Usage

Refer to [SPEC.md](SPEC.md) for details.
