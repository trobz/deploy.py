from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app
from trobz_deploy.utils.executor import ExecutorError


@pytest.fixture
def runner():
    return CliRunner()


def _executor_mock(*, conf_exists: bool):
    """Executor mock where config/odoo.conf may or may not already exist."""
    mock = MagicMock()
    mock.capture.side_effect = lambda cmd, cwd=None, dry_run=False: "/home/deploy" if cmd == "echo $HOME" else ""

    def run_side_effect(cmd, cwd=None, check=True, dry_run=False):
        if not conf_exists and cmd.startswith("test -f") and cmd.endswith("odoo.conf"):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.run.side_effect = run_side_effect
    return mock


def _invoke(runner, extra_args, cfg, *, conf_exists):
    with (
        patch("trobz_deploy.command.configure.Executor") as MockExecutor,
        patch("trobz_deploy.command.configure.load_config", return_value=cfg),
    ):
        mock_exec = _executor_mock(conf_exists=conf_exists)
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "config", *extra_args],
        )
        return result, mock_exec


def _commands(mock_exec) -> list[str]:
    return [call.args[0] for call in mock_exec.run.call_args_list]


def test_config_generates_with_defaults_and_user_overrides(runner):
    cfg = {"version": "17.0", "config": {"db_password": "secret"}}
    result, mock_exec = _invoke(runner, [], cfg, conf_exists=False)

    assert result.exit_code == 0
    create = next(c for c in _commands(mock_exec) if c.startswith("odoo-config create"))
    assert "--version 17.0" in create
    assert "config/odoo.conf" in create
    assert "--db_user=odoo-myapp-staging" in create
    assert "--report.url=http://odoo-myapp-staging:8069" in create
    assert "--http_interface=odoo-myapp-staging" in create
    assert "--db_password=secret" in create
    assert "--preset staging" in create  # derived from the instance name
    assert "--admin_passwd=" in create and "--admin_passwd=admin" not in create  # never the default
    assert not any("mv " in c for c in _commands(mock_exec))  # nothing to back up


def test_config_warns_when_exists_without_recreate(runner):
    result, mock_exec = _invoke(runner, [], {"version": "17.0"}, conf_exists=True)

    assert result.exit_code == 0
    assert "already exists" in result.output
    assert not any(c.startswith("odoo-config create") for c in _commands(mock_exec))


def test_config_recreate_backs_up_then_regenerates(runner):
    result, mock_exec = _invoke(runner, ["--recreate"], {"version": "17.0"}, conf_exists=True)

    assert result.exit_code == 0
    cmds = _commands(mock_exec)
    assert any(
        c == "mv /home/deploy/odoo-myapp-staging/config/odoo.conf /home/deploy/odoo-myapp-staging/config/odoo.conf.bak"
        for c in cmds
    )
    assert any(c.startswith("odoo-config create") for c in cmds)


def test_config_defaults_version_when_undetectable(runner):
    """No configured version + a missing codebase dir (local executor raises
    FileNotFoundError on cwd) falls back to the prompt default instead of crashing."""

    def capture(cmd, cwd=None, dry_run=False):
        if cmd == "echo $HOME":
            return "/home/deploy"
        if "odoo-addons-path" in cmd:
            raise FileNotFoundError(2, "No such file or directory")
        return ""

    mock = _executor_mock(conf_exists=False)
    mock.capture.side_effect = capture
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value={}),
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "config"])

    assert result.exit_code == 0
    create = next(c for c in _commands(mock) if c.startswith("odoo-config create"))
    assert "--version 19.0" in create


def test_config_detects_version_from_addons_path(runner):
    """When no version is configured, read it from `odoo-addons-path --format=json`."""

    def capture(cmd, cwd=None, dry_run=False):
        if cmd == "echo $HOME":
            return "/home/deploy"
        if "odoo-addons-path" in cmd:
            return '{"layout": "Trobz", "version": "18.0"}'
        return ""

    mock = _executor_mock(conf_exists=False)
    mock.capture.side_effect = capture
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value={}),
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "config"])

    assert result.exit_code == 0
    create = next(c for c in _commands(mock) if c.startswith("odoo-config create"))
    assert "--version 18.0" in create


def test_config_no_preset_for_untyped_instance(runner):
    """An instance name without a known type (demo/test/...) gets no --preset."""
    with (
        patch("trobz_deploy.command.configure.Executor") as MockExecutor,
        patch("trobz_deploy.command.configure.load_config", return_value={"version": "17.0"}),
    ):
        MockExecutor.return_value = _executor_mock(conf_exists=False)
        result = runner.invoke(app, ["configure", "odoo-myapp-demo", "--type", "odoo", "--steps", "config"])
        mock_exec = MockExecutor.return_value

    assert result.exit_code == 0
    create = next(c for c in _commands(mock_exec) if c.startswith("odoo-config create"))
    assert "--preset" not in create
