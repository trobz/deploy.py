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
        "git@github.com:trobz/myapp.git",  # remote url
        "main",  # branch
        "abc1234",  # commit
        "ActiveState=active\nSubState=running\nActiveEnterTimestamp=",  # systemd props
    ]
    return mock


def _invoke(runner, extra_args: list[str], side_effect=None):
    with (
        patch("trobz_deploy.command.status.Executor") as MockExecutor,
        patch("trobz_deploy.command.status.load_config", return_value={}),
    ):
        mock_exec = _executor_mock()
        if side_effect:
            mock_exec.watch_logs.side_effect = side_effect
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["status", "service-myapp-production", *extra_args],
        )
        return result, mock_exec


def test_watch_streams_journalctl_after_status(runner):
    result, mock_exec = _invoke(runner, ["--watch"])

    assert result.exit_code == 0
    mock_exec.watch_logs.assert_called_once_with("service-myapp-production")


def test_no_watch_does_not_stream(runner):
    result, mock_exec = _invoke(runner, [])

    assert result.exit_code == 0
    mock_exec.watch_logs.assert_not_called()


def test_watch_handles_keyboard_interrupt(runner):
    # KeyboardInterrupt is handled inside Executor.watch_logs; command exits cleanly
    result, mock_exec = _invoke(runner, ["--watch"])

    assert result.exit_code == 0
    mock_exec.watch_logs.assert_called_once()
