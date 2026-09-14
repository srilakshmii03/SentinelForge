from __future__ import annotations

import json

import httpx

from backend.core.config import settings


class OllamaError(RuntimeError):
    pass


async def _demo_generate(prompt: str, system: str = "") -> str:
    """Deterministic offline responses for the public zero-cost demo."""
    prompt_lower = prompt.lower()

    # Planning response
    if "return json with keys plan, search_queries, target_files, test_command" in prompt_lower:
        return """{
  "plan": "Add a small factorial function to the existing demo module and cover it with a unit test.",
  "search_queries": ["factorial demo.py test_demo.py"],
  "target_files": ["demo.py", "test_demo.py"],
  "test_command": "pytest -q"
}"""

    # Patch response for the public demo.
    if '"diff" and "rationale"' in prompt_lower:
        diff = '''--- a/demo.py
+++ b/demo.py
@@ -1,6 +1,15 @@
 """Synthetic sample project for SentinelForge evaluation."""
 
 
+def factorial(n: int) -> int:
+    """Return the factorial of a non-negative integer."""
+    if n < 0:
+        raise ValueError("factorial is undefined for negative numbers")
+    result = 1
+    for value in range(2, n + 1):
+        result *= value
+    return result
+
+
 def register_user(email: str, password: str) -> dict:
     """Create a synthetic user record."""
     return {"email": email, "password": password}
--- a/test_demo.py
+++ b/test_demo.py
@@ -1,6 +1,12 @@
 from demo import register_user
+from demo import factorial
 
 
 def test_register_user():
     user = register_user("user@example.com", "secret")
     assert user["email"] == "user@example.com"
+
+
+def test_factorial():
+    assert factorial(0) == 1
+    assert factorial(1) == 1
+    assert factorial(5) == 120
'''

        return json.dumps(
            {
                "diff": diff,
                "rationale": (
                    "Adds a small deterministic factorial helper to the existing "
                    "demo module and tests it without changing the existing "
                    "registration behavior."
                ),
            }
        )

    # Critique response
    if "critique the proposed coding change" in prompt_lower:
        return (
            "The proposed change is small and limited to the existing demo files. "
            "The factorial implementation handles zero and positive integers and "
            "rejects negative input. The sandbox test result provides evidence "
            "about whether the test suite passes. A production implementation "
            "could add an explicit negative-input test."
        )

    return "Demo provider response."


async def generate(prompt: str, system: str = "") -> str:
    """Generate using the configured provider."""
    if settings.model_provider.lower() == "demo":
        return await _demo_generate(prompt, system)

    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1},
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.ollama_base_url.rstrip('/')}/api/generate",
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", "")).strip()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError(
            f"Local Ollama inference unavailable: {exc}"
        ) from exc