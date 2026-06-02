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
        "",  # which odoo-addons-path (not reached for service type)
    ]
    # render_unit needs exec_start resolved; capture for server.py check returns ""
    mock.capture.return_value = ""
    return mock


def _invoke(runner, extra_args: list[str], side_effect=None):
    with (
        patch("trobz_deploy.command.configure.Executor") as MockExecutor,
        patch(
            "trobz_deploy.command.configure.load_config",
            return_value={"exec_start": "/usr/bin/myapp"},
        ),
        patch("trobz_deploy.command.configure.render_unit", return_value="[Unit]\n"),
    ):
        mock_exec = _executor_mock()
        if side_effect:
            mock_exec.stream.side_effect = side_effect
        MockExecutor.return_value = mock_exec
        result = runner.invoke(
            app,
            ["configure", "service-myapp-production", "--type", "service", *extra_args],
        )
        return result, mock_exec


def test_watch_streams_journalctl_after_configure(runner):
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
