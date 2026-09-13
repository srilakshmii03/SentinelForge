from __future__ import annotations

import httpx

from backend.core.config import settings


class OllamaError(RuntimeError):
    pass


async def generate(prompt: str, system: str = "") -> str:
    payload = {
        "model": settings.ollama_model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": 0.1},
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/generate", json=payload)
            response.raise_for_status()
            data = response.json()
            return str(data.get("response", "")).strip()
    except (httpx.HTTPError, ValueError) as exc:
        raise OllamaError(f"Local Ollama inference unavailable: {exc}") from exc
