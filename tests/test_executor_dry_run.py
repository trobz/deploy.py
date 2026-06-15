from __future__ import annotations

from unittest.mock import patch

from trobz_deploy.utils.executor import Executor


def test_run_with_dry_run_does_not_execute_and_prints_command(capsys):
    executor = Executor(None)

    with patch("trobz_deploy.utils.executor.subprocess.run") as mock_run:
        result = executor.run("rm -rf /tmp/foo", dry_run=True)

    mock_run.assert_not_called()
    assert result == ""
    assert "[dry-run] $ rm -rf /tmp/foo" in capsys.readouterr().out


def test_run_with_dry_run_includes_cwd(capsys):
    executor = Executor(None)

    with patch("trobz_deploy.utils.executor.subprocess.run") as mock_run:
        executor.run("uv venv .venv", cwd="/home/deploy/app", dry_run=True)

    mock_run.assert_not_called()
    assert "[dry-run] $ cd /home/deploy/app && uv venv .venv" in capsys.readouterr().out


def test_run_without_dry_run_executes_normally():
    executor = Executor(None)

    with patch("trobz_deploy.utils.executor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "ok"
        result = executor.run("echo hi")

    mock_run.assert_called_once()
    assert result == "ok"


def test_write_file_with_dry_run_does_not_write(capsys):
    executor = Executor(None)

    with patch("trobz_deploy.utils.executor.subprocess.run") as mock_run:
        executor.write_file("[Unit]\nDescription=test\n", "/home/deploy/.config/systemd/user/foo.service", dry_run=True)

    mock_run.assert_not_called()
    out = capsys.readouterr().out
    assert "[dry-run] would write /home/deploy/.config/systemd/user/foo.service:" in out
    assert "[Unit]" in out


def test_write_file_without_dry_run_writes():
    executor = Executor(None)

    with patch("trobz_deploy.utils.executor.subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        executor.write_file("[Unit]\n", "/home/deploy/.config/systemd/user/foo.service")

    mock_run.assert_called_once()
    assert "base64 -d > /home/deploy/.config/systemd/user/foo.service" in mock_run.call_args[0][0]
