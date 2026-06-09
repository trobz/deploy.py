from __future__ import annotations

import base64
import subprocess

import typer


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
            typer.echo(f"$ {display}", err=True)

        result = subprocess.run(  # noqa: S603
            argv,
            shell=not is_remote,
            cwd=cwd if not is_remote else None,
            capture_output=not self.verbose,
            text=True,
        )

        if self.verbose and result.stdout:
            typer.echo(result.stdout, nl=False)

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
            typer.echo(f"$ {display}", err=True)

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

    @staticmethod
    def _colorize(command: str, ansi_code: str) -> str:
        """Pipe *command*'s output through ``sed``, wrapping each line in an ANSI color."""
        return f'{command} | stdbuf -oL sed "s/.*/\x1b[{ansi_code}m&\x1b[0m/"'

    def watch_logs(self, eff_type: str, instance_name: str) -> None:
        """Stream journalctl logs for *instance_name*, merged with Odoo log files if found.

        For ``eff_type == "odoo"``, reads ``config/odoo.conf`` under the instance
        home directory to locate ``logfile``, and checks for a ``log/upgrade.log``
        written by ``click-odoo-update``.  Any streams found are tailed concurrently.
        """
        typer.secho("\nWatching service logs (Ctrl+C to stop)…", fg="cyan")

        log_file: str | None = None
        upgrade_log_file: str | None = None
        if eff_type == "odoo":
            try:
                home_dir = self.capture("echo $HOME")
                instance_path = f"{home_dir}/{instance_name}"
            except ExecutorError:
                instance_path = None

            if instance_path:
                try:
                    conf = f"{instance_path}/config/odoo.conf"
                    raw = self.capture(f"grep -E '^logfile' {conf} | cut -d= -f2 | tr -d ' ' || true")
                    candidate = (raw or "").strip()
                    if candidate and candidate.lower() not in ("false", "none"):
                        log_file = candidate
                except ExecutorError:
                    pass

                candidate_upgrade_log = f"{instance_path}/log/upgrade.log"
                try:
                    self.run(f"test -f {candidate_upgrade_log}")
                    upgrade_log_file = candidate_upgrade_log
                except ExecutorError:
                    pass

        streams: list[str] = [
            self._colorize(f"journalctl --user -u {instance_name} -f -o short-iso", "36")  # cyan
        ]
        if log_file:
            typer.secho(f"Merging with Odoo log: {log_file}", fg="cyan")
            streams.append(self._colorize(f"tail -f {log_file}", "32"))  # green
        if upgrade_log_file:
            typer.secho(f"Merging with upgrade log: {upgrade_log_file}", fg="cyan")
            streams.append(self._colorize(f"tail -f {upgrade_log_file}", "33"))  # yellow

        try:
            cmd = f"( {' & '.join(streams)} & wait )" if len(streams) > 1 else streams[0]
            self.stream(cmd)
        except KeyboardInterrupt:
            typer.echo()

    def stream(self, command: str, cwd: str | None = None) -> None:
        """Run a long-lived streaming command (e.g. journalctl -f).

        Output goes directly to the terminal. Returns when the process exits
        or is interrupted (Ctrl+C).
        """
        argv = self._build_argv(command, cwd)
        is_remote = isinstance(argv, list)
        if self.verbose:
            display = argv[-1] if is_remote else command
            typer.echo(f"$ {display}", err=True)
        subprocess.run(argv, shell=not is_remote, cwd=cwd if not is_remote else None)  # noqa: S603

    def write_file(self, content: str, remote_path: str) -> None:
        """Write *content* to *remote_path* on the target host.

        Base64-encodes the content so that any special characters are safe
        to pass through the SSH command line.
        """
        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        if self.verbose:
            typer.echo(f"Writing to {remote_path}\n{content}")
        verbose = self.verbose
        self.verbose = False
        self.run(f"echo '{b64}' | base64 -d > {remote_path}")
        self.verbose = verbose
