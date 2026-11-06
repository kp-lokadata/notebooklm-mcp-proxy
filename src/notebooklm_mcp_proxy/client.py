"""MCP client that connects to the NotebookLM MCP server (FastMCP v2).

Starts the NotebookLM server as a subprocess and speaks MCP protocol to it,
exposing list_tools and call_tool for the proxy server to use.
"""

import asyncio
import json
import os
from typing import Any, Dict, List, Optional

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


class NotebookLMClient:
    """Wrapper around NotebookLM MCP server via stdio."""

    def __init__(
        self,
        command: str,
        args: List[str],
        cwd: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        self.command = command
        self.args = args
        self.cwd = cwd or os.getcwd()
        self.env = env or {}
        self._session: Optional[ClientSession] = None
        self._read_stream = None
        self._write_stream = None
        self._context_manager = None

    async def start(self) -> None:
        """Start the NotebookLM server subprocess and initialize MCP session."""
        # Merge environment: current env + overrides
        full_env = dict(os.environ)
        full_env.update(self.env)

        params = StdioServerParameters(
            command=self.command,
            args=self.args,
            cwd=self.cwd,
            env=full_env,
        )

        self._context_manager = stdio_client(params)
        self._read_stream, self._write_stream = await self._context_manager.__aenter__()
        self._session = ClientSession(self._read_stream, self._write_stream)
        await self._session.__aenter__()
        await self._session.initialize()

    async def stop(self) -> None:
        """Close the MCP session and subprocess."""
        if self._session:
            await self._session.__aexit__(None, None, None)
            self._session = None
        if self._context_manager:
            await self._context_manager.__aexit__(None, None, None)
            self._context_manager = None

    async def list_tools(self) -> List[Dict[str, Any]]:
        """List tools from the NotebookLM server."""
        if not self._session:
            raise RuntimeError("NotebookLM client not started")
        result = await self._session.list_tools()
        # result.tools is a list of Tool objects; convert to dict
        return [
            {
                "name": t.name,
                "description": t.description or "",
                "inputSchema": t.inputSchema or {"type": "object", "properties": {}, "additionalProperties": False},
            }
            for t in result.tools
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        """Call a tool on the NotebookLM server."""
        if not self._session:
            raise RuntimeError("NotebookLM client not started")
        result = await self._session.call_tool(name, arguments)
        return result

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()
