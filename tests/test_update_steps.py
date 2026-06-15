from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def _executor_mock():
    mock = MagicMock()

    def capture_side_effect(cmd, cwd=None):
        if cmd == "echo $HOME":
            return "/home/deploy"
        return ""

    mock.capture.side_effect = capture_side_effect
    return mock


def _invoke(runner, instance_name: str, deploy_type: str, extra_args: list[str], cfg=None):
    cfg = cfg if cfg is not None else {}
    with (
        patch("trobz_deploy.command.update.Executor") as MockExecutor,
        patch("trobz_deploy.command.update.load_config", return_value=cfg),
    ):
        mock_exec = _executor_mock()
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["update", instance_name, "--type", deploy_type, *extra_args, "--ignore-hooks"],
        )
        return result, mock_exec


def _run_commands(mock_exec) -> list[str]:
    return [call.args[0] for call in mock_exec.run.call_args_list]


def _run_calls(mock_exec) -> list[tuple[str, dict]]:
    return [(call.args[0], call.kwargs) for call in mock_exec.run.call_args_list]


def test_invalid_step_value_exits_with_error(runner):
    result, _ = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "bogus"])

    assert result.exit_code == 1
    assert "Invalid --steps value(s): bogus" in result.output


def test_invalid_except_value_exits_with_error(runner):
    result, _ = _invoke(runner, "odoo-myapp-staging", "odoo", ["--except", "bogus"])

    assert result.exit_code == 1
    assert "Invalid --except value(s): bogus" in result.output


def test_step_pull_latest_code_only(runner):
    result, mock_exec = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "pull"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert any("systemctl --user restart odoo-myapp-staging" in cmd for cmd in commands)


def test_step_update_dependencies_only(runner):
    result, mock_exec = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "venv"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert any("systemctl --user restart odoo-myapp-staging" in cmd for cmd in commands)


def test_step_update_database_only(runner):
    result, mock_exec = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "db"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert any("click-odoo-update" in cmd for cmd in commands)
    assert any("systemctl --user restart odoo-myapp-staging" in cmd for cmd in commands)


def test_except_update_database_skips_db_update(runner):
    result, mock_exec = _invoke(runner, "odoo-myapp-staging", "odoo", ["--except", "db"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert any("systemctl --user restart odoo-myapp-staging" in cmd for cmd in commands)


def test_package_mode_upgrade_runs_for_dependencies_step(runner):
    cfg = {"requirements": ["mypackage"]}

    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "venv"], cfg=cfg)

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("uv pip install --upgrade mypackage" in cmd for cmd in commands)


def test_package_mode_upgrade_skipped_for_pull_step(runner):
    cfg = {"requirements": ["mypackage"]}

    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "pull"], cfg=cfg)

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("uv pip install --upgrade" in cmd for cmd in commands)
    assert any("systemctl --user restart" in cmd for cmd in commands)


def test_package_mode_upgrade_skipped_when_only_database_step(runner):
    cfg = {"requirements": ["mypackage"]}

    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "db"], cfg=cfg)

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("uv pip install --upgrade" in cmd for cmd in commands)
    assert any("systemctl --user restart" in cmd for cmd in commands)


def test_python_repo_mode_step_pull_latest_code_only(runner):
    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "pull"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert not any("uv sync" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_python_repo_mode_step_update_dependencies_only(runner):
    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "venv"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert any("uv sync" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_python_repo_mode_update_database_step_is_noop(runner):
    result, mock_exec = _invoke(runner, "service-myapp-production", "python", ["--steps", "db"])

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert not any("uv sync" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_service_repo_mode_step_pull_latest_code_only(runner):
    cfg = {"repo_url": "git@example.com:org/myapp.git", "build": "make build"}

    result, mock_exec = _invoke(runner, "service-myapp-production", "service", ["--steps", "pull"], cfg=cfg)

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert not any("make build" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_service_repo_mode_step_update_dependencies_only(runner):
    cfg = {"repo_url": "git@example.com:org/myapp.git", "build": "make build"}

    result, mock_exec = _invoke(runner, "service-myapp-production", "service", ["--steps", "venv"], cfg=cfg)

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert any("make build" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_service_no_repo_default_steps_prints_skip_message(runner):
    result, mock_exec = _invoke(runner, "service-myapp-production", "service", [])

    assert result.exit_code == 0
    assert "No repository to update, skipping pull" in result.output
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert not any("make build" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_service_no_repo_step_update_dependencies_skips_pull_message(runner):
    result, mock_exec = _invoke(runner, "service-myapp-production", "service", ["--steps", "venv"])

    assert result.exit_code == 0
    assert "No repository to update, skipping pull" not in result.output
    commands = _run_commands(mock_exec)
    assert not any("git pull --recurse-submodules" in cmd for cmd in commands)
    assert not any("odoo-venv update" in cmd for cmd in commands)
    assert not any("click-odoo-update" in cmd for cmd in commands)
    assert not any("uv pip install -r requirements.txt" in cmd for cmd in commands)
    assert not any("make build" in cmd for cmd in commands)
    assert any("systemctl --user restart service-myapp-production" in cmd for cmd in commands)


def test_dry_run_marks_writing_commands(runner):
    result, mock_exec = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "all", "--dry-run"])

    assert result.exit_code == 0
    assert "Dry run complete" in result.output

    calls = _run_calls(mock_exec)
    pull_call = next(c for c in calls if "git pull --recurse-submodules" in c[0])
    assert pull_call[1].get("dry_run") is True

    venv_call = next(c for c in calls if "odoo-venv update" in c[0])
    assert venv_call[1].get("dry_run") is True

    db_call = next(c for c in calls if "click-odoo-update" in c[0])
    assert db_call[1].get("dry_run") is True

    restart_call = next(c for c in calls if "systemctl --user restart" in c[0])
    assert restart_call[1].get("dry_run") is True

    # The read-only repo check is not marked as a dry-run skip.
    check_call = next(c for c in calls if c[0].startswith("test -d"))
    assert not check_call[1].get("dry_run")


def test_dry_run_marks_hook_commands(runner):
    cfg = {"hooks": {"pre-update": ["echo before"], "post-update": ["echo after"]}}

    with (
        patch("trobz_deploy.command.update.Executor") as MockExecutor,
        patch("trobz_deploy.command.update.load_config", return_value=cfg),
    ):
        mock_exec = _executor_mock()
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["update", "odoo-myapp-staging", "--type", "odoo", "--steps", "all", "--dry-run"],
        )

    assert result.exit_code == 0
    calls = _run_calls(mock_exec)
    pre_hook_call = next(c for c in calls if c[0] == "echo before")
    assert pre_hook_call[1].get("dry_run") is True
    post_hook_call = next(c for c in calls if c[0] == "echo after")
    assert post_hook_call[1].get("dry_run") is True
