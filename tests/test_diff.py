import pytest
from backend.security.diff import apply_unified_diff
from backend.security.paths import SecurityError


def test_unified_diff_applies_only_existing_file():
    files = {"demo.py": "print('old')\n"}
    diff = "--- a/demo.py\n+++ b/demo.py\n@@ -1 +1 @@\n-print('old')\n+print('new')\n"
    assert apply_unified_diff(files, diff)["demo.py"] == "print('new')\n"


def test_unified_diff_rejects_new_file():
    files = {"demo.py": "print('old')\n"}
    diff = "--- a/new.py\n+++ b/new.py\n@@ -0,0 +1 @@\n+print('new')\n"
    with pytest.raises(SecurityError):
        apply_unified_diff(files, diff)


def test_unified_diff_rejects_context_mismatch():
    files = {"demo.py": "print('actual')\n"}
    diff = "--- a/demo.py\n+++ b/demo.py\n@@ -1 +1 @@\n-print('expected')\n+print('new')\n"
    with pytest.raises(SecurityError):
        apply_unified_diff(files, diff)
