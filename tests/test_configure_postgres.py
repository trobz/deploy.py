from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from trobz_deploy.command.configure import _ensure_postgres_user, _postgres_user_exists
from trobz_deploy.utils.executor import Executor


def _executor() -> Any:
    executor = Executor(None)
    executor.capture = MagicMock()  # type: ignore[method-assign]
    executor.run = MagicMock()  # type: ignore[method-assign]
    return executor


def test_postgres_user_exists_true_when_role_found():
    executor = _executor()
    executor.capture.return_value = "1"

    assert _postgres_user_exists(executor, "odoo-foo-staging") is True
    executor.capture.assert_called_once_with(
        "psql -tAc \"SELECT 1 FROM pg_roles WHERE rolname='odoo-foo-staging'\" -d postgres"
    )


def test_postgres_user_exists_false_when_role_missing():
    executor = _executor()
    executor.capture.return_value = ""

    assert _postgres_user_exists(executor, "odoo-foo-staging") is False


def test_ensure_postgres_user_skips_creation_when_role_exists():
    executor = _executor()
    executor.capture.return_value = "1"

    _ensure_postgres_user(executor, "odoo-foo-staging")

    executor.run.assert_not_called()


def test_ensure_postgres_user_creates_role_with_password_when_missing(capsys):
    executor = _executor()
    executor.capture.return_value = ""

    _ensure_postgres_user(executor, "odoo-foo-staging")

    assert executor.run.call_count == 2
    createuser_cmd, alter_role_cmd = (call.args[0] for call in executor.run.call_args_list)

    assert createuser_cmd == "createuser --no-createrole --superuser odoo-foo-staging"
    assert alter_role_cmd.startswith('psql -d postgres -c "ALTER ROLE \\"odoo-foo-staging\\" WITH PASSWORD \'')
    assert alter_role_cmd.endswith("'\"")

    out = capsys.readouterr().out
    assert "Created Postgres user 'odoo-foo-staging' with password:" in out
