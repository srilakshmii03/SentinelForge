from __future__ import annotations

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
  "plan": "Improve the existing demo user-registration code with a small, testable validation helper.",
  "search_queries": ["register_user email validation"],
  "target_files": ["demo.py", "test_demo.py"],
  "test_command": "pytest -q"
}"""

    # Patch response
    if '"diff" and "rationale"' in prompt_lower:
        return """{
  "diff": "--- a/demo.py\\n+++ b/demo.py\\n@@ -1,6 +1,10 @@\\n \\\\\\\"\\\\\\\"\\\\\\\"Synthetic sample project for SentinelForge evaluation.\\\\\\\"\\\\\\\"\\\\\\\"\\n \\n+def is_valid_email(email: str) -> bool:\\n+    \\\\\\\"\\\\\\\"\\\\\\\"Return whether an email contains the basic required separator.\\\\\\\"\\\\\\\"\\\\\\\"\\n+    return \\\\\\\"@\\\\\\\" in email and \\\\\\\".\\\\\\\" in email.split(\\\\\\\"@\\\\\\\", 1)[-1]\\n+\\n \\n def register_user(email: str, password: str) -> dict:\\n     \\\\\\\"\\\\\\\"\\\\\\\"Create a synthetic user record.\\\\\\\"\\\\\\\"\\\\\\\"\\n     return {\\\\\\\"email\\\\\\\": email, \\\\\\\"password\\\\\\\": password}\\n",
  "rationale": "Adds a small deterministic validation helper to the existing demo file without changing the existing registration behavior."
}"""

    # Critique response
    if "critique the proposed coding change" in prompt_lower:
        return (
            "The proposed change is small and limited to the existing demo module. "
            "The sandbox test result provides evidence about whether the existing test suite "
            "still passes. A production implementation should use stronger email validation "
            "and should never store plaintext passwords."
        )

    return "Demo provider response."


async def generate(prompt: str, system: str = "") -> str:
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