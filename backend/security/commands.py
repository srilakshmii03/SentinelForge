from __future__ import annotations

import shlex

from .paths import SecurityError

ALLOWED_COMMANDS = {
    "python",
    "python3",
    "pytest",
}

BLOCKED_TOKENS = {
    "bash", "sh", "zsh", "fish", "cmd", "powershell", "pwsh",
    "curl", "wget", "nc", "netcat", "ssh", "scp", "socat",
    "sudo", "su", "mount", "umount", "docker", "podman",
}


def validate_command(command: str) -> list[str]:
    if not command or len(command) > 512:
        raise SecurityError("Command is empty or too long")
    args = shlex.split(command)
    if not args:
        raise SecurityError("Command is empty")
    executable = args[0].split("/")[-1]
    if executable not in ALLOWED_COMMANDS:
        raise SecurityError(f"Command '{executable}' is not allowed")
    lowered = {a.lower() for a in args}
    if lowered & BLOCKED_TOKENS:
        raise SecurityError("Command contains a blocked executable/token")
    if any(".." in a.replace("\\", "/").split("/") for a in args):
        raise SecurityError("Path traversal is not allowed in command arguments")
    return args
