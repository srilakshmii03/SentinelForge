from backend.sandbox.runner import SandboxRunner


def test_sandbox_requires_approval(tmp_path):
    result = SandboxRunner(tmp_path).execute({"test.py": "print('ok')"}, "python test.py", approved=False)
    assert result["status"] == "approval_required"
