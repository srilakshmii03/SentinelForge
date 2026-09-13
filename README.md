# SentinelForge

SentinelForge is a privacy-first AI developer platform for asking questions about a local knowledge base and proposing safe code changes through Model Context Protocol (MCP).

## Architecture

- **FastAPI**: web/API layer and OpenAPI metadata.
- **MCP v2**: core tool workflow, resource, and reusable prompt.
- **Local RAG**: local sentence-transformer embeddings + SQLite vector storage, with source metadata and citations.
- **Agent**: task analysis → retrieval → patch proposal → sandbox execution → self-critique.
- **Sandbox**: Docker, network disabled, resource limits, command allowlist, isolated temporary workspace.
- **React**: browser interface (under construction in Phase 2).

## Local run

1. Create a Python 3.11+ virtual environment.
2. Install `pip install -e ".[dev]"`.
3. Copy `.env.example` to `.env`.
4. Install/start Ollama and pull the configured open model.
5. Run `uvicorn backend.main:app --reload`.

Open `/docs` for the API and `/mcp` for the MCP Streamable HTTP endpoint.

## Tests

```bash
pytest -q
```

## Security posture

Retrieved content is treated as untrusted data. Sandbox execution requires explicit approval, uses a network-disabled Docker container, resource limits, an allowlist, and an assigned workspace.

## Assessment scope

This repository is being built against the SentinelForge technical assessment requirements: integrated MCP, local RAG, sandboxed agent, web app/API, automated tests, reproducibility, and zero-cost deployment.
