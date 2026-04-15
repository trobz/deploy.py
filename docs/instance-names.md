# Instance Names

Instance names follow a structured convention that encodes the deployment type,
project, environment, and an optional qualifier.

## Format

```
<type_prefix>-<project_slug>-<environment>[-<suffix>]
```

| Segment | Values / Notes |
|---------|----------------|
| `type_prefix` | Always first. `odoo`, `openerp` → Odoo · `service` → Python |
| `project_slug` | Everything between prefix and environment. May contain hyphens. |
| `environment` | `integration`, `staging`, `production`, `hotfix`, `debug`, `demo` |
| `suffix` | Optional. Short qualifier after the environment: `-02`, `-eu`, `-vn` |

## Examples

```
odoo-myproject-production
odoo-myproject-staging-02
odoo-my-cool-project-production
openerp-legacy-integration
service-myapi-production-eu
service-worker-staging
```

## Parsing algorithm

Because the slug may contain hyphens, the name is parsed from both ends:

1. **Prefix** — everything before the first `-`.
2. **Suffix** — if the last segment does not match a known environment, treat it as a suffix and strip it.
3. **Environment** — the last remaining segment, which must be a known value.
4. **Slug** — all segments between prefix and environment, joined with `-`.

## Type auto-detection

When `--type` is not provided and no `type` key exists in `deploy.yml`,
the prefix determines the deployment type automatically:

| Prefix | Detected type |
|--------|---------------|
| `odoo-`, `openerp-` | `odoo` |
| `service-` | `python` |
| *(anything else)* | error — `--type` is required |

!!! note
    The `service` deployment type (non-Python) is never auto-detected.
    It must be set explicitly via `--type service` or `type: service` in `deploy.yml`.

## Database name (Odoo)

For `odoo` deployments the database name defaults to the full `instance_name`.
Override it with `--db` or the `db` key in `deploy.yml`.
