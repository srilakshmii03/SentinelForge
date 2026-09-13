from __future__ import annotations

from mcp import Client

from .server import mcp


async def call_mcp(name: str, arguments: dict) -> dict:
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.call_tool(name, arguments)
        if result.structured_content is not None:
            return dict(result.structured_content)
        return {"ok": not result.is_error, "content": [getattr(c, "text", str(c)) for c in result.content]}
