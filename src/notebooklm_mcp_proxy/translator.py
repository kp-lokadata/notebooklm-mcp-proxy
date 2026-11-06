"""Translation layer between Hermes MCP client and NotebookLM FastMCP v2 server.

The issue: Hermes MCP client cannot discover tools from FastMCP v2 servers
(tools/list returns empty or is not parsed correctly). This proxy sits between
Hermes and the NotebookLM server, exposing tools in a format Hermes understands
and forwarding calls to the NotebookLM server.
"""

from typing import Any, Dict, List, Optional

from mcp.types import Tool


def translate_tools_for_hermes(raw_tools: List[Dict[str, Any]]) -> List[Tool]:
    """Translate tool definitions from FastMCP v2 format to Hermes-compatible format.

    FastMCP v2 may include fields (e.g., outputSchema, strict inputSchema)
    that Hermes' MCP SDK does not expect. We strip unknown fields and keep
    only name, description, and inputSchema.
    """
    hermes_tools: List[Tool] = []
    for t in raw_tools:
        name = t.get("name", "")
        description = t.get("description", "") or ""
        input_schema = t.get("inputSchema", {"type": "object", "properties": {}, "additionalProperties": False})

        # Ensure inputSchema is a proper JSON Schema object
        if not isinstance(input_schema, dict):
            input_schema = {"type": "object", "properties": {}, "additionalProperties": False}

        hermes_tools.append(
            Tool(
                name=name,
                description=description,
                inputSchema=input_schema,
            )
        )
    return hermes_tools


def translate_call_arguments(tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Translate tool call arguments if needed before forwarding to NotebookLM.

    Currently a pass-through, but kept as a hook for future argument
    normalization (e.g., renaming parameters, adding defaults).
    """
    return dict(arguments)


def translate_call_result(raw_result: Any) -> List[Dict[str, Any]]:
    """Translate tool call result from NotebookLM server to Hermes-compatible format.

    MCP call_tool returns a list of content blocks (TextContent, etc.).
    We normalize to [{"type": "text", "text": "..."}] format.
    """
    if raw_result is None:
        return [{"type": "text", "text": ""}]

    # If already a list of content blocks
    if isinstance(raw_result, list):
        return raw_result

    # If a single object with 'content' key (some MCP servers wrap like this)
    if isinstance(raw_result, dict) and "content" in raw_result:
        return raw_result["content"]

    # If a dict, serialize as JSON text
    if isinstance(raw_result, dict):
        import json

        return [{"type": "text", "text": json.dumps(raw_result, ensure_ascii=False, indent=2)}]

    # Fallback: convert to string
    return [{"type": "text", "text": str(raw_result)}]


def extract_notebook_id_from_notebooks(notebooks: List[Dict[str, Any]]) -> Optional[str]:
    """Extract the first notebook ID from a list of notebooks, if available."""
    for nb in notebooks:
        nid = nb.get("id") or nb.get("notebook_id")
        if nid:
            return str(nid)
    return None
