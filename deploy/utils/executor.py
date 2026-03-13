from __future__ import annotations

import base64
import subprocess

import click


class ExecutorError(Exception):
    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


class Executor:
    """Runs shell commands either via SSH (remote) or as local subprocesses.

    Uses the system ``ssh`` binary so that ``~/.ssh/config`` and agent
    forwarding are respected automatically.
    """

    def __init__(
        self,
        ssh_host: str | None,
        verbose: bool = False,
        ssh_port: int | None = None,
    ) -> None:
        is_remote = bool(ssh_host) and ssh_host != "localhost"
        self.ssh_host: str | None = ssh_host if is_remote else None
        self.ssh_port = ssh_port
        self.verbose = verbose

    def _build_argv(self, command: str, cwd: str | None) -> list[str] | str:
        """Return argv for subprocess.run (list for SSH, str for local shell)."""
        if self.ssh_host and self.ssh_host != "localhost":
            shell_cmd = f"cd {cwd} && {command}" if cwd else command
            argv = ["ssh", "-A"]
            if self.ssh_port is not None:
                argv += ["-p", str(self.ssh_port)]
            argv += [self.ssh_host, shell_cmd]
            return argv
        return command

    def run(self, command: str, cwd: str | None = None, check: bool = True) -> str:
        """Run a command, streaming output in verbose mode.

        Args:
            command: Shell command to execute.
            cwd: Working directory (embedded in remote command; passed to local subprocess).
            check: Raise ExecutorError if the command exits non-zero.

        Returns:
            Combined stdout (empty string when verbose, since output is streamed).
        """
        argv = self._build_argv(command, cwd)
        is_remote = isinstance(argv, list)

        if self.verbose:
            display = argv[-1] if is_remote else command
            click.echo(f"$ {display}", err=True)

        result = subprocess.run(  # noqa: S603
            argv,
            shell=not is_remote,
            cwd=cwd if not is_remote else None,
            capture_output=not self.verbose,
            text=True,
        )

        if self.verbose and result.stdout:
            click.echo(result.stdout, nl=False)

        if check and result.returncode != 0:
            err = (result.stderr or "").strip()
            msg = f"Command failed (exit {result.returncode}): {command}"
            if err:
                msg = f"{msg}\n{err}"
            raise ExecutorError(msg, result.returncode)

        return result.stdout or ""

    def capture(self, command: str, cwd: str | None = None) -> str:
        """Run a command and always return its stdout (never streams).

        Use this when the output is needed programmatically.
        """
        argv = self._build_argv(command, cwd)
        is_remote = isinstance(argv, list)

        if self.verbose:
            display = argv[-1] if is_remote else command
            click.echo(f"$ {display}", err=True)

        result = subprocess.run(  # noqa: S603
            argv,
            shell=not is_remote,
            cwd=cwd if not is_remote else None,
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            err = (result.stderr or "").strip()
            msg = f"Command failed (exit {result.returncode}): {command}"
            if err:
                msg = f"{msg}\n{err}"
            raise ExecutorError(msg, result.returncode)

        return result.stdout.strip()

    def write_file(self, content: str, remote_path: str) -> None:
        """Write *content* to *remote_path* on the target host.

        Base64-encodes the content so that any special characters are safe
        to pass through the SSH command line.
        """
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        self.run(f"echo '{b64}' | base64 -d > {remote_path}")
