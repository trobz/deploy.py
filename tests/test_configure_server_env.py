from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app
from trobz_deploy.command.configure import _render_server_env
from trobz_deploy.utils.executor import ExecutorError


@pytest.fixture
def runner():
    return CliRunner()


def test_render_server_env_emits_key_value_lines():
    rendered = _render_server_env({"A": 1, "B": "x"})
    assert rendered == "A=1\nB=x\n"


def _executor_mock(*, env_exists: bool):
    """Executor mock where config/server.env may or may not already exist."""
    mock = MagicMock()
    mock.capture.side_effect = lambda cmd, cwd=None, dry_run=False: "/home/deploy" if cmd == "echo $HOME" else ""

    def run_side_effect(cmd, cwd=None, check=True, dry_run=False):
        if not env_exists and cmd.startswith("test -f") and cmd.endswith("server.env"):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.run.side_effect = run_side_effect
    return mock


def _invoke(runner, cfg, *, env_exists):
    with (
        patch("trobz_deploy.command.configure.Executor") as MockExecutor,
        patch("trobz_deploy.command.configure.load_config", return_value=cfg),
    ):
        mock_exec = _executor_mock(env_exists=env_exists)
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "env"],
        )
        return result, mock_exec


def test_server_env_writes_defaults_plus_overrides(runner):
    cfg = {"version": "17.0", "env": {"ODOO_SESSION_REDIS": 1, "OMP_NUM_THREADS": 4}}
    result, mock_exec = _invoke(runner, cfg, env_exists=False)

    assert result.exit_code == 0
    written = mock_exec.write_file.call_args.args[0]
    assert "OPENBLAS_NUM_THREADS=1\n" in written  # default kept
    assert "ODOO_SESSION_REDIS=1\n" in written  # extra env added
    assert "OMP_NUM_THREADS=4\n" in written  # user value wins over default
    assert "OMP_NUM_THREADS=1\n" not in written


def test_server_env_skips_when_exists_without_recreate(runner):
    result, mock_exec = _invoke(runner, {"version": "17.0"}, env_exists=True)

    assert result.exit_code == 0
    assert "server.env already exists" in result.output
    mock_exec.write_file.assert_not_called()
