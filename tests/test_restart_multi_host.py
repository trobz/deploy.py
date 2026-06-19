from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from trobz_deploy.cli import app


@pytest.fixture
def runner():
    return CliRunner()


def _invoke(runner, extra_args, cfg, mocks):
    with (
        patch("trobz_deploy.command.restart.Executor") as MockExecutor,
        patch("trobz_deploy.command.restart.load_config", return_value=cfg),
    ):
        MockExecutor.side_effect = mocks
        result = runner.invoke(app, ["restart", "service-myapp-production", *extra_args])
        return result, MockExecutor


def test_restarts_each_host_in_order(runner):
    cfg = {"ssh_host": ["host1.example.com", "host2.example.com"]}
    mock1, mock2 = MagicMock(), MagicMock()

    result, MockExecutor = _invoke(runner, [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    assert MockExecutor.call_args_list[0].args[0] == "host1.example.com"
    assert MockExecutor.call_args_list[1].args[0] == "host2.example.com"
    mock1.run.assert_called_once_with("systemctl --user restart service-myapp-production")
    mock2.run.assert_called_once_with("systemctl --user restart service-myapp-production")
    assert "=== Host 1/2: host1.example.com ===" in result.output
    assert "=== Host 2/2: host2.example.com ===" in result.output


def test_multiple_watched_hosts_dispatch_to_watch_logs_multi(runner):
    cfg = {
        "ssh_host": [
            {"host1.example.com": {"watch": True}},
            {"host2.example.com": {"watch": True}},
        ],
    }
    mock1, mock2 = MagicMock(), MagicMock()

    with patch("trobz_deploy.command.restart.watch_logs_multi") as mock_watch_multi:
        result, _ = _invoke(runner, [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock_watch_multi.assert_called_once_with([
        (mock1, "python", "service-myapp-production"),
        (mock2, "python", "service-myapp-production"),
    ])
