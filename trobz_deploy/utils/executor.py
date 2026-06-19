from __future__ import annotations

import base64
import subprocess
import threading
from collections.abc import Iterator

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

    def run(self, command: str, cwd: str | None = None, check: bool = True, dry_run: bool = False) -> str:
        """Run a command, streaming output in verbose mode.

        Args:
            command: Shell command to execute.
            cwd: Working directory (embedded in remote command; passed to local subprocess).
            check: Raise ExecutorError if the command exits non-zero.
            dry_run: If True, print what would run instead of executing it.

        Returns:
            Combined stdout (empty string when verbose or dry-run, since output is streamed).
        """
        if dry_run:
            display = f"cd {cwd} && {command}" if cwd else command
            typer.secho(f"[dry-run] $ {display}", fg="cyan")
            return ""

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

    def capture(self, command: str, cwd: str | None = None, dry_run: bool = False) -> str:
        """Run a command and always return its stdout (never streams).

        Use this when the output is needed programmatically.
        """
        if dry_run:
            display = f"cd {cwd} && {command}" if cwd else command
            typer.secho(f"[dry-run] $ {display}", fg="cyan")
            return ""

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
        cmd = self.build_watch_command(eff_type, instance_name)
        try:
            self.stream(cmd)
        except KeyboardInterrupt:
            typer.echo()

    def build_watch_command(self, eff_type: str, instance_name: str) -> str:
        """Build the merged journalctl/log-tail shell command used by ``watch_logs``.

        Exposed separately so multiple hosts can be watched concurrently via
        ``merge_stream_lines`` instead of each blocking the terminal in turn.
        """
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

        cmd = f"( {' & '.join(streams)} & wait )" if len(streams) > 1 else streams[0]
        return cmd

    def stream_lines(self, command: str, cwd: str | None = None) -> Iterator[str]:
        """Run a long-lived command and yield its stdout one line at a time.

        Useful for commands like ``tail -f`` where output must be processed
        incrementally rather than printed wholesale to the terminal.
        """
        argv = self._build_argv(command, cwd)
        is_remote = isinstance(argv, list)
        if self.verbose:
            display = argv[-1] if is_remote else command
            typer.echo(f"$ {display}", err=True)
        with subprocess.Popen(  # noqa: S603
            argv,
            shell=not is_remote,
            cwd=cwd if not is_remote else None,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        ) as proc:
            assert proc.stdout is not None  # noqa: S101
            for line in proc.stdout:
                yield line.rstrip("\n")

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

    def write_file(self, content: str, remote_path: str, dry_run: bool = False) -> None:
        """Write *content* to *remote_path* on the target host.

        Base64-encodes the content so that any special characters are safe
        to pass through the SSH command line.
        """
        if dry_run:
            typer.secho(f"[dry-run] would write {remote_path}:", fg="cyan")
            typer.echo(content)
            return

        b64 = base64.b64encode(content.encode("utf-8")).decode("ascii")
        if self.verbose:
            typer.echo(f"Writing to {remote_path}\n{content}")
        verbose = self.verbose
        self.verbose = False
        self.run(f"echo '{b64}' | base64 -d > {remote_path}")
        self.verbose = verbose


# ANSI color cycle for merge_stream_lines labels (cyan, green, yellow, magenta, blue)
_LABEL_COLORS = ["36", "32", "33", "35", "34"]


def merge_stream_lines(streams: list[tuple[Executor, str]], prefix: bool = True) -> None:
    """Stream output from multiple (executor, command) pairs concurrently.

    Each stream runs in its own thread. Lines are printed as they arrive,
    optionally prefixed with a colored ``[host]`` label so you can tell them apart.
    Blocks until all streams end or until a KeyboardInterrupt.
    """
    lock = threading.Lock()

    def _pump(executor: Executor, command: str, label: str, color: str) -> None:
        colored_label = f"\x1b[{color}m[{label}]\x1b[0m"
        try:
            for line in executor.stream_lines(command):
                with lock:
                    typer.echo(f"{colored_label} {line}" if prefix else line)
        except Exception as e:
            typer.secho(f"{colored_label} Exception in _pump {e}", fg="red")

    threads: list[threading.Thread] = []
    for i, (executor, command) in enumerate(streams):
        label = executor.ssh_host or "localhost"
        color = _LABEL_COLORS[i % len(_LABEL_COLORS)]
        t = threading.Thread(target=_pump, args=(executor, command, label, color), daemon=True)
        t.start()
        threads.append(t)

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        typer.echo()


def watch_logs_multi(targets: list[tuple[Executor, str, str]]) -> None:
    """Watch logs for one or more ``(executor, eff_type, instance_name)`` targets.

    A single target behaves exactly like ``Executor.watch_logs``. With more than one,
    each host's merged journalctl/log stream is tailed concurrently and interleaved
    with a colored ``[host]`` label via ``merge_stream_lines``.
    """
    if not targets:
        return
    if len(targets) == 1:
        executor, eff_type, instance_name = targets[0]
        executor.watch_logs(eff_type, instance_name)
        return

    typer.secho("\nWatching service logs for multiple hosts (Ctrl+C to stop)…", fg="cyan")
    streams = [
        (executor, executor.build_watch_command(eff_type, instance_name))
        for executor, eff_type, instance_name in targets
    ]
    merge_stream_lines(streams)
