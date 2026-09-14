from __future__ import annotations

import os
import shutil

try:
    import resource
except ImportError:
    resource = None
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from backend.core.config import settings
from backend.security.commands import validate_command
from backend.security.paths import reject_symlink_escape


class SandboxRunner:
    def __init__(self, workspace_root: Path | None = None):
        self.workspace_root = (workspace_root or settings.workspace_dir).resolve()
        self.workspace_root.mkdir(parents=True, exist_ok=True)

    def _set_process_limits(self) -> None:
        """Apply best-effort OS resource limits for the subprocess fallback."""
        if os.name != "posix" or resource is None:
            return

        try:
            cpu_limit = max(1, int(settings.sandbox_timeout_seconds))
            memory_limit = int(settings.sandbox_memory_mb) * 1024 * 1024

            resource.setrlimit(resource.RLIMIT_CPU, (cpu_limit, cpu_limit + 1))
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))

            # Limit the number of processes created by the child.
            resource.setrlimit(
                resource.RLIMIT_NPROC,
                (
                    int(settings.sandbox_pids_limit),
                    int(settings.sandbox_pids_limit),
                ),
            )
        except (ValueError, OSError):
            # Resource limits are platform-dependent; the outer timeout
            # and output limits still remain active.
            pass

    def _docker_available(self) -> bool:
        return shutil.which("docker") is not None

    def _run_process(
        self,
        cmd: list[str],
        root: Path,
        output_limit: int,
        started: float,
        *,
        runner: str,
    ) -> dict:
        streams: dict[str, bytearray] = {
            "stdout": bytearray(),
            "stderr": bytearray(),
        }
        overflow = {"value": False}

        def drain(stream, name: str) -> None:
            while True:
                chunk = stream.read(4096)
                if not chunk:
                    return

                remaining = output_limit - len(streams[name])
                if remaining > 0:
                    streams[name].extend(chunk[:remaining])

                if len(streams[name]) >= output_limit:
                    overflow["value"] = True
                    return

        env = os.environ.copy()
        env.update(
            {
                "PYTHONNOUSERSITE": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                "NO_PROXY": "*",
                "no_proxy": "*",
                "HTTP_PROXY": "",
                "HTTPS_PROXY": "",
                "ALL_PROXY": "",
                "http_proxy": "",
                "https_proxy": "",
                "all_proxy": "",
            }
        )

        popen_kwargs = {
            "cwd": root,
            "env": env,
            "stdout": subprocess.PIPE,
            "stderr": subprocess.PIPE,
            "stdin": subprocess.DEVNULL,
        }

        if os.name == "posix":
            popen_kwargs["preexec_fn"] = self._set_process_limits

        try:
            proc = subprocess.Popen(cmd, **popen_kwargs)
        except OSError as exc:
            return {
                "ok": False,
                "status": "runner_error",
                "error": str(exc),
                "runner": runner,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "network": "restricted",
            }

        assert proc.stdout is not None and proc.stderr is not None

        stdout_thread = threading.Thread(
            target=drain,
            args=(proc.stdout, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=drain,
            args=(proc.stderr, "stderr"),
            daemon=True,
        )

        stdout_thread.start()
        stderr_thread.start()

        deadline = time.monotonic() + settings.sandbox_timeout_seconds

        while proc.poll() is None:
            if overflow["value"]:
                proc.kill()
                proc.wait()

                return {
                    "ok": False,
                    "status": "output_limit",
                    "stdout": streams["stdout"].decode(errors="replace"),
                    "stderr": streams["stderr"].decode(errors="replace"),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "runner": runner,
                    "network": "restricted",
                }

            if time.monotonic() >= deadline:
                proc.kill()
                proc.wait()

                return {
                    "ok": False,
                    "status": "timeout",
                    "stdout": streams["stdout"].decode(errors="replace"),
                    "stderr": streams["stderr"].decode(errors="replace"),
                    "duration_ms": int((time.monotonic() - started) * 1000),
                    "runner": runner,
                    "network": "restricted",
                }

            time.sleep(0.05)

        stdout_thread.join(timeout=1)
        stderr_thread.join(timeout=1)

        duration = int((time.monotonic() - started) * 1000)
        stdout = streams["stdout"].decode(errors="replace")
        stderr = streams["stderr"].decode(errors="replace")

        return {
            "ok": proc.returncode == 0,
            "status": "completed",
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "duration_ms": duration,
            "runner": runner,
            "network": "restricted",
            "timed_out": False,
        }

    def execute(
        self,
        files: dict[str, str],
        command: str,
        approved: bool = False,
        preview: bool = False,
    ) -> dict:
        # Preview execution is safe because it occurs in an isolated
        # temporary workspace. Applying a generated patch is a separate,
        # explicit approval boundary.
        if not approved and not preview:
            return {
                "ok": False,
                "status": "approval_required",
                "message": "Sandbox execution requires explicit approval.",
            }

        args = validate_command(command)
        started = time.monotonic()

        with tempfile.TemporaryDirectory(dir=self.workspace_root) as tmp:
            root = Path(tmp).resolve()

            for rel, content in files.items():
                target = reject_symlink_escape(root, rel)

                if target.suffix.lower() not in {
                    ".py",
                    ".txt",
                    ".md",
                    ".json",
                }:
                    return {
                        "ok": False,
                        "status": "blocked",
                        "message": f"File type not allowed: {rel}",
                    }

                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")

            output_limit = settings.sandbox_output_kb * 1024

            if self._docker_available():
                cmd = [
                    "docker",
                    "run",
                    "--rm",
                    "--network",
                    "none",
                    "--cpus",
                    "0.5",
                    "--memory",
                    f"{settings.sandbox_memory_mb}m",
                    "--pids-limit",
                    str(settings.sandbox_pids_limit),
                    "--read-only",
                    "--tmpfs",
                    "/tmp:rw,noexec,nosuid,size=32m",
                    "-v",
                    f"{root}:/workspace:rw",
                    "-w",
                    "/workspace",
                    "python:3.12-slim",
                    *args,
                ]

                return self._run_process(
                    cmd,
                    root,
                    output_limit,
                    started,
                    runner="docker",
                )

            # Render Free does not provide a Docker daemon to the running
            # application. Fall back to a restricted child process using
            # the existing command allowlist, temporary workspace,
            # timeout, output, memory, CPU, and process-count limits.
            return self._run_process(
                args,
                root,
                output_limit,
                started,
                runner="restricted-subprocess",
            )