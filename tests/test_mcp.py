import pytest
from mcp import Client

from backend.mcp.server import mcp


@pytest.mark.anyio
async def test_mcp_discovers_required_tools():
    async with Client(mcp, raise_exceptions=True) as client:
        result = await client.list_tools()
        names = {tool.name for tool in result.tools}
        assert {"ingest_content", "retrieve_context", "inspect_repository", "propose_patch", "execute_sandbox"}.issubset(names)


@pytest.mark.anyio
async def test_mcp_resource_and_prompt_exist():
    async with Client(mcp, raise_exceptions=True) as client:
        resources = await client.list_resources()
        prompts = await client.list_prompts()
        assert any(str(r.uri) == "sentinelforge://system/status" for r in resources.resources)
        assert any(p.name == "coding_task_analysis" for p in prompts.prompts)
