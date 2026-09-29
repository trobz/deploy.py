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
        patch("trobz_deploy.command.configure._resolve_addons_path") as check,
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "unit"])

    assert result.exit_code == 0
    assert render.call_args.kwargs["addons_path_command"] == f"/usr/bin/odoo-addons-path {ARGS}"
    assert check.call_args.args[1:] == (f"/usr/bin/odoo-addons-path {ARGS}", "/home/deploy/odoo-myapp-staging")


def _unit_step(runner, addons_output: str, missing_dir: bool = False):
    mock = _mock()

    def capture(cmd, cwd=None, dry_run=False):
        if cmd == "echo $HOME":
            return "/home/deploy"
        if cmd.startswith("which"):
            return "/usr/bin/odoo-addons-path"
        if "odoo-addons-path" in cmd:
            return addons_output
        return ""

    def run(cmd, cwd=None, check=True, dry_run=False):
        if cmd.startswith("test -f") or (missing_dir and cmd.startswith("test -d /b")):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.capture.side_effect = capture
    mock.run.side_effect = run
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value={}),
        patch("trobz_deploy.command.configure.render_unit", return_value="[Unit]\n"),
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "unit"])
    return result, mock


def test_unit_step_accepts_valid_addons_path(runner):
    result, mock = _unit_step(runner, "/a,/b")

    assert result.exit_code == 0
    assert any("test -d /a" in c.args[0] for c in mock.run.call_args_list)
    mock.write_file.assert_called_once()


def test_unit_step_aborts_on_empty_addons_path(runner):
    result, mock = _unit_step(runner, "")

    assert result.exit_code == 1
    assert "returned no add-ons path" in result.output
    mock.write_file.assert_not_called()


def test_unit_step_aborts_when_addons_dir_missing(runner):
    result, mock = _unit_step(runner, "/a,/b", missing_dir=True)

    assert result.exit_code == 1
    assert "Invalid add-ons path" in result.output
    mock.write_file.assert_not_called()


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


def _venv_step(runner, cfg, addons_output: str = "/core/addons,/ee,/proj"):
    mock = _mock()

    def capture(cmd, cwd=None, dry_run=False):
        if cmd == "echo $HOME":
            return "/home/deploy"
        if "odoo-addons-path" in cmd:
            return addons_output
        return ""

    def run(cmd, cwd=None, check=True, dry_run=False):
        if cmd.endswith("/.venv"):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.capture.side_effect = capture
    mock.run.side_effect = run
    with (
        patch("trobz_deploy.command.configure.Executor", return_value=mock),
        patch("trobz_deploy.command.configure.load_config", return_value=cfg),
    ):
        result = runner.invoke(app, ["configure", "odoo-myapp-staging", "--type", "odoo", "--steps", "venv"])
    return result, [c.args[0] for c in mock.run.call_args_list]


def _venv_create(commands):
    return next(c for c in commands if c.startswith("odoo-venv create"))


def test_venv_gets_resolved_addons_path_and_odoo_dir(runner):
    result, commands = _venv_step(runner, CFG)

    assert result.exit_code == 0
    assert _venv_create(commands) == (
        "odoo-venv create --project-dir /home/deploy/odoo-myapp-staging --preset project "
        "--odoo-dir /opt/odoo/odoo/17.0/ --addons-path /core/addons,/ee,/proj"
    )


def test_explicit_odoo_venv_keys_win_over_derived(runner):
    cfg = {"tools": {**CFG["tools"], "odoo-venv": {"odoo-dir": "/custom", "addons-path": "/only"}}}

    result, commands = _venv_step(runner, cfg)

    assert result.exit_code == 0
    create = _venv_create(commands)
    assert "--odoo-dir /custom --addons-path /only" in create
    assert "/opt/odoo/odoo/17.0/" not in create


def test_venv_unchanged_without_addons_path_tool(runner):
    result, commands = _venv_step(runner, {})

    assert result.exit_code == 0
    assert _venv_create(commands) == "odoo-venv create --project-dir /home/deploy/odoo-myapp-staging --preset project"


def test_venv_aborts_when_addons_path_unresolvable(runner):
    result, commands = _venv_step(runner, CFG, addons_output="")

    assert result.exit_code == 1
    assert "Invalid add-ons path" in result.output
    assert not any(c.startswith("odoo-venv create") for c in commands)


def test_addons_path_options_from_instance_keys():
    from trobz_deploy.utils.addons import addons_path_options

    assert addons_path_options({"odoo_dir": "/o", "addons_dir": ["/a", "/b"]}) == {
        "odoo-dir": "/o",
        "addons-dir": "/a,/b",
    }
    assert addons_path_options({}) == {}


def test_tools_override_wins_over_instance_keys():
    from trobz_deploy.utils.addons import addons_path_options

    opts = {
        "odoo_dir": "/o",
        "addons_dir": "/a",
        "tools": {"odoo-addons-path": {"odoo-dir": "/custom", "check-versions": True}},
    }

    assert addons_path_options(opts) == {"odoo-dir": "/custom", "addons-dir": "/a", "check-versions": True}


def test_venv_and_unit_use_instance_level_keys(runner):
    cfg = {"odoo_dir": "/opt/odoo/odoo/17.0/", "addons_dir": "/opt/odoo/enterprise/17.0,/opt/odoo/proj"}

    result, commands = _venv_step(runner, cfg)

    assert result.exit_code == 0
    assert _venv_create(commands).endswith("--odoo-dir /opt/odoo/odoo/17.0/ --addons-path /core/addons,/ee,/proj")
