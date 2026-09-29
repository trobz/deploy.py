from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app
from trobz_deploy.utils.addons import addons_path_command
from trobz_deploy.utils.executor import ExecutorError

CFG = {
    "tools": {
        "odoo-addons-path": {
            "odoo-dir": "/opt/odoo/odoo/17.0/",
            "addons-dir": "/opt/odoo/enterprise/17.0,/opt/odoo/proj",
        }
    }
}
ARGS = "--odoo-dir /opt/odoo/odoo/17.0/ --addons-dir /opt/odoo/enterprise/17.0,/opt/odoo/proj"


@pytest.fixture
def runner():
    return CliRunner()


def _mock():
    mock = MagicMock()
    mock.capture.side_effect = lambda cmd, cwd=None, dry_run=False: "/home/deploy" if cmd == "echo $HOME" else ""

    def run_side_effect(cmd, cwd=None, check=True, dry_run=False):
        if cmd.startswith(("test -d", "test -f")):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.run.side_effect = run_side_effect
    return mock


def test_addons_path_command_without_args():
    assert addons_path_command() == "odoo-addons-path"


def test_addons_path_command_with_args():
    assert addons_path_command("/bin/oap", {"odoo-dir": "/o"}) == "/bin/oap --odoo-dir /o"


def test_update_passes_tool_options_to_addons_path(runner):
    with (
        patch("trobz_deploy.command.update.Executor") as ex,
        patch("trobz_deploy.command.update.load_config", return_value=CFG),
    ):
        ex.return_value = mock = _mock()
        result = runner.invoke(
            app, ["update", "odoo-myapp-staging", "--type", "odoo", "--steps", "db", "--ignore-hooks"]
        )

    assert result.exit_code == 0
    assert f"odoo-addons-path {ARGS}" in [c.args[0] for c in mock.capture.call_args_list]


def test_configure_renders_tool_options_into_unit(runner):
    mock = _mock()
    mock.capture.side_effect = lambda cmd, cwd=None, dry_run=False: (
        "/home/deploy" if cmd == "echo $HOME" else "/usr/bin/odoo-addons-path" if cmd.startswith("which") else ""
    )
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value=CFG),
        patch("trobz_deploy.command.configure.render_unit", return_value="[Unit]\n") as render,
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "unit"])

    assert result.exit_code == 0
    assert render.call_args.kwargs["addons_path_command"] == f"/usr/bin/odoo-addons-path {ARGS}"


def test_configure_version_detection_uses_tool_options(runner):
    mock = _mock()
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value=CFG),
    ):
        runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "config"])

    assert f"odoo-addons-path {ARGS} -v --format=json" in [c.args[0] for c in mock.capture.call_args_list]


def test_configure_rejects_addons_path_in_config(runner):
    cfg = {"config": {"addons_path": "/x"}}
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=_mock()),
        patch("trobz_deploy.command.configure.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "config"])

    assert result.exit_code == 1
    assert "config.addons_path" in result.output
