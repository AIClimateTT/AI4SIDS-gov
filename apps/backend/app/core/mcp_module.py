import asyncio
import json
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy.orm import Session

from app.core.contracts import Fact, IngestResult, MetricSpec


class McpDataModule:
    """A DataModule that proxies to a metrics server over the MCP stdio transport.

    Conforms to the same DataModule protocol (app/core/registry.py) as the in-process
    Survey123Module, but instead of importing metric functions and querying the DB
    directly, it spawns the given command as a subprocess per call and speaks MCP to it.
    No transport/session detail (ClientSession, stdio_client, CallToolResult, etc.)
    leaks past list_metrics()/run_metric() — callers only ever see MetricSpec/Fact.
    """

    def __init__(self, name: str, command: str, args: list[str], env: dict[str, str] | None = None):
        self.name = name
        self._server_params = StdioServerParameters(command=command, args=args, env=env)

    def ingest(self, file_path: Path) -> IngestResult:
        raise NotImplementedError(f"{self.name} runs externally over MCP; ingest via that system directly")

    def list_metrics(self) -> list[MetricSpec]:
        tools = asyncio.run(self._list_tools())
        return [
            MetricSpec(
                name=tool.name,
                description=tool.description or "",
                params_schema=tool.inputSchema,
                module=self.name,
            )
            for tool in tools
        ]

    def run_metric(self, name: str, params: dict, session: Session) -> list[Fact]:
        raw = asyncio.run(self._call_tool(name, params))
        return [Fact.model_validate(item) for item in json.loads(raw)]

    async def _list_tools(self):
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                await client_session.initialize()
                result = await client_session.list_tools()
                return result.tools

    async def _call_tool(self, name: str, params: dict) -> str:
        async with stdio_client(self._server_params) as (read, write):
            async with ClientSession(read, write) as client_session:
                await client_session.initialize()
                result = await client_session.call_tool(name, arguments={"params": params})

        # Raise (or return) only after the stdio transport and session have fully
        # torn down. Raising while those nested `async with` blocks are still
        # unwinding causes anyio's TaskGroup to wrap the ValueError in a
        # BaseExceptionGroup instead of letting it propagate as a plain
        # exception -- a transport-layer detail we don't want callers of
        # run_metric to ever see.
        if result.isError:
            detail = result.content[0].text if result.content else "unknown MCP error"
            raise ValueError(f"MCP tool {name!r} on module {self.name!r} failed: {detail}")
        return result.content[0].text
