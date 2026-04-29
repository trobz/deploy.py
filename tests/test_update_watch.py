from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from deploy.command.update import update


@pytest.fixture
def runner():
    return CliRunner()


def _executor_mock():
    mock = MagicMock()
    mock.capture.return_value = "/home/deploy"
    return mock


def _invoke(runner, extra_args: list[str]):
    with (
        patch("deploy.command.update.Executor") as MockExecutor,
        patch("deploy.command.update.load_config", return_value={}),
    ):
        mock_exec = _executor_mock()
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            update,
            ["service-myapp-production", "--type", "service", *extra_args],
            obj={"config": "", "verbose": False},
        )
        return result, mock_exec


def test_watch_streams_journalctl_after_success(runner):
    result, mock_exec = _invoke(runner, ["--watch"])

    assert result.exit_code == 0
    mock_exec.stream.assert_called_once_with("journalctl --user -u service-myapp-production -f")


def test_no_watch_does_not_stream(runner):
    result, mock_exec = _invoke(runner, [])

    assert result.exit_code == 0
    mock_exec.stream.assert_not_called()


def test_watch_handles_keyboard_interrupt(runner):
    with (
        patch("deploy.command.update.Executor") as MockExecutor,
        patch("deploy.command.update.load_config", return_value={}),
    ):
        mock_exec = _executor_mock()
        mock_exec.stream.side_effect = KeyboardInterrupt
        MockExecutor.return_value = mock_exec

        result = runner.invoke(
            update,
            ["service-myapp-production", "--type", "service", "--watch"],
            obj={"config": "", "verbose": False},
        )

        assert result.exit_code == 0
        mock_exec.stream.assert_called_once()
