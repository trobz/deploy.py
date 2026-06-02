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
    return mock


def _invoke(runner, extra_args: list[str], side_effect=None):
    with (
        patch("trobz_deploy.command.restart.Executor") as MockExecutor,
        patch("trobz_deploy.command.restart.load_config", return_value={}),
    ):
        mock_exec = _executor_mock()
        if side_effect:
            mock_exec.stream.side_effect = side_effect
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["restart", "service-myapp-production", *extra_args],
        )
        return result, mock_exec


def test_restart_runs_systemctl(runner):
    result, mock_exec = _invoke(runner, [])

    assert result.exit_code == 0
    mock_exec.run.assert_called_once_with("systemctl --user restart service-myapp-production")


def test_watch_streams_journalctl_after_restart(runner):
    result, mock_exec = _invoke(runner, ["--watch"])

    assert result.exit_code == 0
    mock_exec.stream.assert_called_once_with("journalctl --user -u service-myapp-production -f")


def test_no_watch_does_not_stream(runner):
    result, mock_exec = _invoke(runner, [])

    assert result.exit_code == 0
    mock_exec.stream.assert_not_called()


def test_watch_handles_keyboard_interrupt(runner):
    result, mock_exec = _invoke(runner, ["--watch"], side_effect=KeyboardInterrupt)

    assert result.exit_code == 0
    mock_exec.stream.assert_called_once()
