"""MCP proxy server that Hermes Agent connects to.

This server speaks MCP protocol to Hermes on stdio, discovers tools from the
NotebookLM FastMCP v2 server (via subprocess), translates them to a
Hermes-compatible format, and forwards tool calls back to NotebookLM.

Usage:
    python -m notebooklm_mcp_proxy.server

Environment variables (see .env.example):
    NOTEBOOKLM_SERVER_COMMAND   - command to start NotebookLM MCP server
    NOTEBOOKLM_SERVER_ARGS      - JSON array of args
    NOTEBOOKLM_SERVER_CWD       - working directory for NotebookLM server
    NOTEBOOKLM_PROFILE_DIR      - Chrome profile dir for cookie auth
    NOTEBOOKLM_BACKEND          - auth backend: web or android
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent

from .client import NotebookLMClient
from .translator import (
    translate_call_arguments,
    translate_call_result,
    translate_tools_for_hermes,
)

# Load .env file from the proxy directory
load_dotenv()

server = Server("notebooklm-mcp-proxy")

_notebooklm_client: Optional[NotebookLMClient] = None
_notebooklm_tools: List[Dict[str, Any]] = []


def _get_notebooklm_command() -> List[str]:
    """Build the command to start the NotebookLM MCP server from env vars."""
    command = os.environ.get("NOTEBOOKLM_SERVER_COMMAND", "python")
    args_raw = os.environ.get("NOTEBOOKLM_SERVER_ARGS", "[]")
    try:
        args = json.loads(args_raw)
        if not isinstance(args, list):
            args = []
    except json.JSONDecodeError:
        args = []
    return [command] + args


def _get_notebooklm_env() -> Dict[str, str]:
    """Build environment dict for the NotebookLM server subprocess."""
    env = {}
    for key in ("NOTEBOOKLM_BACKEND", "NOTEBOOKLM_HEADLESS", "NOTEBOOKLM_PROFILE_DIR", "NOTEBOOKLM_CONFIG_PATH"):
        val = os.environ.get(key)
        if val:
            env[key] = val
    return env


async def _ensure_notebooklm_client() -> NotebookLMClient:
    """Start (or reuse) the NotebookLM MCP client connection."""
    global _notebooklm_client
    if _notebooklm_client is None:
        cmd = _get_notebooklm_command()
        if not cmd or cmd == ["python"]:
            raise RuntimeError(
                "NOTEBOOKLM_SERVER_COMMAND not set. See .env.example"
            )
        cwd = os.environ.get("NOTEBOOKLM_SERVER_CWD") or os.getcwd()
        env = _get_notebooklm_env()
        _notebooklm_client = NotebookLMClient(
            command=cmd[0],
            args=cmd[1:],
            cwd=cwd,
            env=env,
        )
        await _notebooklm_client.start()
    return _notebooklm_client


async def _load_notebooklm_tools() -> List[Dict[str, Any]]:
    """Fetch tool list from NotebookLM server and cache it."""
    global _notebooklm_tools
    client = await _ensure_notebooklm_client()
    raw_tools = await client.list_tools()
    _notebooklm_tools = raw_tools
    return raw_tools


@server.list_tools()
async def handle_list_tools() -> List[Dict[str, Any]]:
    """Return tools discovered from NotebookLM, translated for Hermes."""
    raw_tools = await _load_notebooklm_tools()
    return translate_tools_for_hermes(raw_tools)


@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Forward a tool call to the NotebookLM server and return translated result."""
    client = await _ensure_notebooklm_client()
    translated_args = translate_call_arguments(name, arguments or {})
    raw_result = await client.call_tool(name, translated_args)
    return translate_call_result(raw_result)


async def _shutdown() -> None:
    """Close the NotebookLM client connection."""
    global _notebooklm_client
    if _notebooklm_client:
        await _notebooklm_client.stop()
        _notebooklm_client = None


def main() -> None:
    """Entry point for the proxy server."""
    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass
    finally:
        asyncio.run(_shutdown())


async def _run() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )
