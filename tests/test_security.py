from pathlib import Path

import pytest

from backend.security.commands import validate_command
from backend.security.paths import SecurityError, safe_join


def test_path_traversal_blocked(tmp_path):
    with pytest.raises(SecurityError):
        safe_join(tmp_path, "../../etc/passwd")


def test_absolute_path_blocked(tmp_path):
    with pytest.raises(SecurityError):
        safe_join(tmp_path, "/etc/passwd")


def test_shell_blocked():
    with pytest.raises(SecurityError):
        validate_command("bash -c 'echo hacked'")


def test_network_tool_blocked():
    with pytest.raises(SecurityError):
        validate_command("curl https://example.com")
