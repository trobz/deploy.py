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
    mock.capture.side_effect = [
        "/home/deploy",  # echo $HOME
        "ActiveState=active\nSubState=running\nActiveEnterTimestamp=",  # systemd props
    ]
    return mock


def _invoke(runner, extra_args, cfg, mocks):
    with (
        patch("trobz_deploy.command.status.Executor") as MockExecutor,
        patch("trobz_deploy.command.status.load_config", return_value=cfg),
    ):
        MockExecutor.side_effect = mocks
        result = runner.invoke(app, ["status", "service-myapp-production", *extra_args])
        return result, MockExecutor


def test_each_host_prints_its_own_labeled_block(runner):
    cfg = {"ssh_host": ["host1.example.com", "host2.example.com"]}
    mock1, mock2 = _executor_mock(), _executor_mock()

    result, MockExecutor = _invoke(runner, [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    assert MockExecutor.call_args_list[0].args[0] == "host1.example.com"
    assert MockExecutor.call_args_list[1].args[0] == "host2.example.com"
    assert "Host:      host1.example.com" in result.output
    assert "Host:      host2.example.com" in result.output
    # host1's block must be fully printed before host2's
    assert result.output.index("host1.example.com") < result.output.index("host2.example.com")


def test_single_host_list_has_no_host_label(runner):
    cfg = {"ssh_host": ["host1.example.com"]}
    mock1 = _executor_mock()

    result, _ = _invoke(runner, [], cfg, [mock1])

    assert result.exit_code == 0
    assert "Host:" not in result.output


def test_per_host_watch_with_single_target_falls_back_to_watch_logs(runner):
    cfg = {"ssh_host": [{"host1.example.com": {"watch": True}}, "host2.example.com"]}
    mock1, mock2 = _executor_mock(), _executor_mock()

    result, _ = _invoke(runner, [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock1.watch_logs.assert_called_once_with("python", "service-myapp-production")
    mock2.watch_logs.assert_not_called()


def test_multiple_watched_hosts_dispatch_to_watch_logs_multi(runner):
    cfg = {
        "ssh_host": [
            {"host1.example.com": {"watch": True}},
            {"host2.example.com": {"watch": True}},
        ],
    }
    mock1, mock2 = _executor_mock(), _executor_mock()

    with patch("trobz_deploy.command.status.watch_logs_multi") as mock_watch_multi:
        result, _ = _invoke(runner, [], cfg, [mock1, mock2])

    assert result.exit_code == 0
    mock_watch_multi.assert_called_once_with([
        (mock1, "python", "service-myapp-production"),
        (mock2, "python", "service-myapp-production"),
    ])
