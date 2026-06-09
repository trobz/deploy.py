from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from trobz_deploy.utils.executor import Executor, ExecutorError


def _executor() -> Any:
    executor = Executor(None)
    executor.capture = MagicMock()  # type: ignore[method-assign]
    executor.run = MagicMock()  # type: ignore[method-assign]
    executor.stream = MagicMock()  # type: ignore[method-assign]
    return executor


def _streamed_command(executor: Any) -> str:
    return executor.stream.call_args[0][0]


def test_non_odoo_type_streams_journalctl_only_in_its_color():
    executor = _executor()

    executor.watch_logs("python", "service-myapp-production")

    cmd = _streamed_command(executor)
    assert cmd == (
        'journalctl --user -u service-myapp-production -f -o short-iso | stdbuf -oL sed "s/.*/\x1b[36m&\x1b[0m/"'
    )
    executor.capture.assert_not_called()
    executor.run.assert_not_called()


def test_odoo_type_merges_each_log_in_its_own_color():
    executor = _executor()
    executor.capture.side_effect = [
        "/home/deploy",  # echo $HOME
        "/home/deploy/odoo-foo-staging/log/odoo.log",  # grep logfile from odoo.conf
    ]
    executor.run.side_effect = None  # `test -f log/upgrade.log` succeeds

    executor.watch_logs("odoo", "odoo-foo-staging")

    cmd = _streamed_command(executor)
    assert cmd == (
        "( journalctl --user -u odoo-foo-staging -f -o short-iso"
        ' | stdbuf -oL sed "s/.*/\x1b[36m&\x1b[0m/"'
        " & tail -f /home/deploy/odoo-foo-staging/log/odoo.log"
        ' | stdbuf -oL sed "s/.*/\x1b[32m&\x1b[0m/"'
        " & tail -f /home/deploy/odoo-foo-staging/log/upgrade.log"
        ' | stdbuf -oL sed "s/.*/\x1b[33m&\x1b[0m/"'
        " & wait )"
    )


def test_odoo_type_without_log_files_streams_journalctl_only():
    executor = _executor()
    executor.capture.side_effect = [
        "/home/deploy",  # echo $HOME
        "",  # no logfile configured
    ]
    executor.run.side_effect = ExecutorError("not found")  # `test -f log/upgrade.log` fails

    executor.watch_logs("odoo", "odoo-foo-staging")

    cmd = _streamed_command(executor)
    assert cmd == ('journalctl --user -u odoo-foo-staging -f -o short-iso | stdbuf -oL sed "s/.*/\x1b[36m&\x1b[0m/"')


def test_keyboard_interrupt_is_swallowed():
    executor = _executor()
    executor.capture.side_effect = ExecutorError("unreachable")
    executor.stream.side_effect = KeyboardInterrupt

    with patch("trobz_deploy.utils.executor.typer.echo") as mock_echo:
        executor.watch_logs("python", "service-myapp-production")

    mock_echo.assert_called_once_with()
