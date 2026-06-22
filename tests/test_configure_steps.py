from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app
from trobz_deploy.utils.executor import ExecutorError


@pytest.fixture
def runner():
    return CliRunner()


def _executor_mock():
    mock = MagicMock()

    def capture_side_effect(cmd, cwd=None, dry_run=False):
        if cmd == "echo $HOME":
            return "/home/deploy"
        return ""

    mock.capture.side_effect = capture_side_effect
    return mock


def _executor_mock_fresh_dir():
    """Executor mock where the instance directory/repo does not exist yet."""
    mock = _executor_mock()

    def run_side_effect(cmd, cwd=None, check=True, dry_run=False):
        if cmd.startswith("test -d") or cmd.startswith("test -f"):
            msg = "not found"
            raise ExecutorError(msg)
        return ""

    mock.run.side_effect = run_side_effect
    return mock


def _invoke(
    runner,
    instance_name: str,
    deploy_type: str,
    extra_args: list[str],
    cfg=None,
    executor_factory=_executor_mock,
):
    cfg = cfg if cfg is not None else {"exec_start": "/usr/bin/myapp", "build": "make build"}
    with (
        patch("trobz_deploy.command.configure.Executor") as MockExecutor,
        patch("trobz_deploy.command.configure.load_config", return_value=cfg),
        patch("trobz_deploy.command.configure.render_unit", return_value="[Unit]\n"),
    ):
        mock_exec = executor_factory()
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["configure", instance_name, "--type", deploy_type, *extra_args],
        )
        return result, mock_exec


def _run_commands(mock_exec) -> list[str]:
    return [call.args[0] for call in mock_exec.run.call_args_list]


def _run_calls(mock_exec) -> list[tuple[str, dict]]:
    return [(call.args[0], call.kwargs) for call in mock_exec.run.call_args_list]


def test_invalid_step_value_exits_with_error(runner):
    result, _ = _invoke(runner, "service-myapp-production", "service", ["--steps", "bogus"])

    assert result.exit_code == 1
    assert "Invalid --steps value(s): bogus" in result.output


def test_invalid_except_value_exits_with_error(runner):
    result, _ = _invoke(runner, "service-myapp-production", "service", ["--except", "bogus"])

    assert result.exit_code == 1
    assert "Invalid --except value(s): bogus" in result.output


def test_step_set_up_instance_dir_only_runs_that_step(runner):
    result, mock_exec = _invoke(
        runner,
        "service-myapp-production",
        "service",
        ["--steps", "dir"],
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("mkdir -p" in cmd for cmd in commands)
    assert not any("make build" in cmd for cmd in commands)
    mock_exec.write_file.assert_not_called()


def test_except_skips_install_systemd_unit(runner):
    result, mock_exec = _invoke(
        runner,
        "service-myapp-production",
        "service",
        ["--except", "unit"],
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("mkdir -p" in cmd for cmd in commands)
    assert any("make build" in cmd for cmd in commands)
    mock_exec.write_file.assert_not_called()
    assert not any("systemctl --user enable --now" in cmd for cmd in commands)


def test_step_run_gitaggregate_only(runner):
    result, mock_exec = _invoke(
        runner,
        "odoo-myapp-staging",
        "odoo",
        ["--steps", "gitaggregate"],
        cfg={},
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("gitaggregate" in cmd for cmd in commands)
    assert not any(cmd.startswith("createuser") for cmd in commands)
    assert not any("odoo-venv create" in cmd for cmd in commands)
    mock_exec.write_file.assert_not_called()


def test_step_ensure_postgres_role_only(runner):
    result, mock_exec = _invoke(
        runner,
        "odoo-myapp-staging",
        "odoo",
        ["--steps", "pg"],
        cfg={},
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert not any("gitaggregate" in cmd for cmd in commands)
    assert any(cmd.startswith("createuser") for cmd in commands)
    assert not any("odoo-venv create" in cmd for cmd in commands)
    mock_exec.write_file.assert_not_called()


def test_step_all_runs_every_step_for_odoo(runner):
    cfg = {"repo_url": "git@example.com:org/myapp.git", "version": "17.0"}

    result, mock_exec = _invoke(
        runner,
        "odoo-myapp-staging",
        "odoo",
        ["--steps", "all"],
        cfg=cfg,
        executor_factory=_executor_mock_fresh_dir,
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("git clone" in cmd for cmd in commands)
    assert any(cmd.startswith("createuser") for cmd in commands)
    assert any("gitaggregate" in cmd for cmd in commands)
    assert any("odoo-venv create" in cmd for cmd in commands)
    assert any("odoo-config create --version 17.0" in cmd for cmd in commands)
    mock_exec.write_file.assert_called_once()
    assert any("systemctl --user enable --now" in cmd for cmd in commands)


def test_step_all_runs_every_step_for_python_package(runner):
    cfg = {"requirements": ["mypackage"], "exec_start": "/usr/bin/myapp"}

    result, mock_exec = _invoke(
        runner,
        "service-myapp-production",
        "python",
        ["--steps", "all"],
        cfg=cfg,
        executor_factory=_executor_mock_fresh_dir,
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("mkdir -p" in cmd for cmd in commands)
    assert any("uv venv .venv" in cmd for cmd in commands)
    assert any("uv pip install mypackage" in cmd for cmd in commands)
    mock_exec.write_file.assert_called_once()
    assert any("systemctl --user enable --now" in cmd for cmd in commands)


def test_step_all_runs_every_step_for_service(runner):
    result, mock_exec = _invoke(
        runner,
        "service-myapp-production",
        "service",
        [],
        executor_factory=_executor_mock_fresh_dir,
    )

    assert result.exit_code == 0
    commands = _run_commands(mock_exec)
    assert any("mkdir -p" in cmd for cmd in commands)
    assert any("make build" in cmd for cmd in commands)
    mock_exec.write_file.assert_called_once()
    assert any("systemctl --user enable --now" in cmd for cmd in commands)


def test_dry_run_marks_writing_commands_and_skips_postgres_creation(runner):
    cfg = {"repo_url": "git@example.com:org/myapp.git"}

    result, mock_exec = _invoke(
        runner,
        "odoo-myapp-staging",
        "odoo",
        ["--steps", "all", "--dry-run"],
        cfg=cfg,
        executor_factory=_executor_mock_fresh_dir,
    )

    assert result.exit_code == 0
    assert "Dry run complete" in result.output
    assert "[dry-run] Would create Postgres user" in result.output

    calls = _run_calls(mock_exec)
    clone_call = next(c for c in calls if "git clone" in c[0])
    assert clone_call[1].get("dry_run") is True

    # The Postgres role doesn't exist (mock capture returns ""), but in
    # dry-run mode no createuser/ALTER ROLE command should be issued.
    assert not any(cmd.startswith("createuser") for cmd, _ in calls)

    # Read-only existence checks are not marked as dry-run skips.
    check_calls = [c for c in calls if c[0].startswith("test -d")]
    assert check_calls
    assert all(not kwargs.get("dry_run") for _, kwargs in check_calls)

    _, write_kwargs = mock_exec.write_file.call_args
    assert write_kwargs.get("dry_run") is True


def test_dry_run_step_set_up_instance_dir_marks_mkdir(runner):
    result, mock_exec = _invoke(
        runner,
        "service-myapp-production",
        "service",
        ["--steps", "dir", "--dry-run"],
    )

    assert result.exit_code == 0
    calls = _run_calls(mock_exec)
    mkdir_call = next(c for c in calls if "mkdir -p" in c[0])
    assert mkdir_call[1].get("dry_run") is True
