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

    def capture_side_effect(cmd, cwd=None):
        if cmd == "echo $HOME":
            return "/home/deploy"
        return ""

    mock.capture.side_effect = capture_side_effect
    return mock


def _invoke(runner, instance_name, deploy_type, extra_args, cfg, mocks):
    with (
        patch("trobz_deploy.command.update.Executor") as MockExecutor,
        patch("trobz_deploy.command.update.load_config", return_value=cfg),
    ):
        MockExecutor.side_effect = mocks
        result = runner.invoke(
            app,
            ["update", instance_name, "--type", deploy_type, *extra_args, "--ignore-hooks"],
        )
        return result, MockExecutor


def test_hosts_are_visited_in_order_with_per_host_steps(runner):
    cfg = {
        "ssh_host": [
            {"host2.example.com": {"steps": {"update": "pull, venv, db"}}},
            {"host1.example.com": {"steps": {"update": "pull, venv"}}},
        ],
    }
    mock1, mock2 = _executor_mock(), _executor_mock()

    result, MockExecutor = _invoke(runner, "odoo-myapp-staging", "odoo", [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    assert MockExecutor.call_args_list[0].args[0] == "host2.example.com"
    assert MockExecutor.call_args_list[1].args[0] == "host1.example.com"
    assert "=== Host 1/2: host2.example.com ===" in result.output
    assert "=== Host 2/2: host1.example.com ===" in result.output

    commands1 = [c.args[0] for c in mock1.run.call_args_list]
    commands2 = [c.args[0] for c in mock2.run.call_args_list]
    assert any("click-odoo-update" in c for c in commands1)
    assert not any("click-odoo-update" in c for c in commands2)


def test_cli_steps_override_wins_over_every_host_override(runner):
    cfg = {
        "ssh_host": [
            {"host2.example.com": {"steps": {"update": "pull, venv, db"}}},
            {"host1.example.com": {"steps": {"update": "pull, venv"}}},
        ],
    }
    mock1, mock2 = _executor_mock(), _executor_mock()

    result, _ = _invoke(runner, "odoo-myapp-staging", "odoo", ["--steps", "pull"], cfg, [mock1, mock2])

    assert result.exit_code == 0
    for mock_exec in (mock1, mock2):
        commands = [c.args[0] for c in mock_exec.run.call_args_list]
        assert any("git pull --recurse-submodules" in c for c in commands)
        assert not any("odoo-venv update" in c for c in commands)
        assert not any("click-odoo-update" in c for c in commands)


def test_single_host_list_does_not_print_host_header(runner):
    cfg = {"ssh_host": ["host1.example.com"]}
    mock1 = _executor_mock()

    result, _ = _invoke(runner, "odoo-myapp-staging", "odoo", [], cfg, [mock1])

    assert result.exit_code == 0
    assert "=== Host" not in result.output


def test_aborts_immediately_on_first_host_failure(runner):
    cfg = {"ssh_host": ["host1.example.com", "host2.example.com"]}
    mock1 = _executor_mock()

    def run_side_effect(cmd, cwd=None, check=True, dry_run=False):
        if cmd.startswith("test -d"):
            return ""
        if "git pull" in cmd:
            msg = "network unreachable"
            raise ExecutorError(msg)
        return ""

    mock1.run.side_effect = run_side_effect
    mock2 = _executor_mock()

    result, MockExecutor = _invoke(runner, "odoo-myapp-staging", "odoo", [], cfg, [mock1, mock2])

    assert result.exit_code == 1
    assert MockExecutor.call_count == 1


def test_per_host_watch_with_single_target_falls_back_to_watch_logs(runner):
    cfg = {
        "ssh_host": [
            {"host2.example.com": {"watch": True}},
            "host1.example.com",
        ],
    }
    mock1, mock2 = _executor_mock(), _executor_mock()

    result, _ = _invoke(runner, "service-myapp-production", "service", [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock1.watch_logs.assert_called_once_with("service", "service-myapp-production")
    mock2.watch_logs.assert_not_called()


def test_multiple_watched_hosts_dispatch_to_watch_logs_multi(runner):
    cfg = {
        "ssh_host": [
            {"host2.example.com": {"watch": True}},
            {"host1.example.com": {"watch": True}},
        ],
    }
    mock1, mock2 = _executor_mock(), _executor_mock()

    with patch("trobz_deploy.command.update.watch_logs_multi") as mock_watch_multi:
        result, _ = _invoke(runner, "service-myapp-production", "service", [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock_watch_multi.assert_called_once_with([
        (mock1, "service", "service-myapp-production"),
        (mock2, "service", "service-myapp-production"),
    ])


def test_cli_watch_flag_forces_watch_on_every_host(runner):
    cfg = {"ssh_host": ["host1.example.com", "host2.example.com"]}
    mock1, mock2 = _executor_mock(), _executor_mock()

    with patch("trobz_deploy.command.update.watch_logs_multi") as mock_watch_multi:
        result, _ = _invoke(runner, "service-myapp-production", "service", ["--watch"], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock_watch_multi.assert_called_once_with([
        (mock1, "service", "service-myapp-production"),
        (mock2, "service", "service-myapp-production"),
    ])
