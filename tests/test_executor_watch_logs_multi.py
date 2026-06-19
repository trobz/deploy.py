from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from trobz_deploy.utils.executor import Executor, watch_logs_multi


def _executor() -> Any:
    executor = Executor(None)
    executor.capture = MagicMock()  # type: ignore[method-assign]
    executor.run = MagicMock()  # type: ignore[method-assign]
    executor.stream = MagicMock()  # type: ignore[method-assign]
    return executor


def test_no_targets_is_a_no_op():
    watch_logs_multi([])


def test_single_target_behaves_like_watch_logs():
    executor = _executor()

    watch_logs_multi([(executor, "python", "service-myapp-production")])

    executor.stream.assert_called_once()
    cmd = executor.stream.call_args[0][0]
    assert "journalctl --user -u service-myapp-production -f -o short-iso" in cmd


def test_multiple_targets_interleave_with_host_labels(capsys):
    executor1 = Executor("host1.example.com")
    executor1.stream_lines = MagicMock(return_value=iter(["line-a"]))  # type: ignore[method-assign]
    executor2 = Executor("host2.example.com")
    executor2.stream_lines = MagicMock(return_value=iter(["line-b"]))  # type: ignore[method-assign]

    watch_logs_multi([
        (executor1, "python", "service-a"),
        (executor2, "python", "service-b"),
    ])

    out = capsys.readouterr().out
    assert "[host1.example.com] line-a" in out
    assert "[host2.example.com] line-b" in out
