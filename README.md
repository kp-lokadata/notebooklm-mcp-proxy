# NotebookLM MCP Proxy

MCP translation proxy between **Hermes MCP client** and **NotebookLM FastMCP v2 server**.

## Problem

Hermes MCP client cannot discover tools from FastMCP v2 servers. When you connect
NotebookLM MCP server (FastMCP v2) to Hermes via `manage_connections enable`, it
reports `connected` but `tools: []` — no tools are registered.

This proxy sits between Hermes and the NotebookLM server:

```
Hermes MCP Client ←→ Proxy (stdio, Hermes-compatible) ←→ NotebookLM MCP Server (FastMCP v2)
```

The proxy discovers tools from NotebookLM, translates them to a format Hermes
understands, and forwards all tool calls.

## Setup

### 1. Clone and install

```bash
git clone https://github.com/<your-org>/notebooklm-mcp-proxy.git
cd notebooklm-mcp-proxy

# Create venv and install
uv venv .venv --python 3.14
.venv/bin/pip install -e .
```

### 2. Configure environment

Copy `.env.example` to `.env` and adjust:

```bash
cp .env.example .env
```

Edit `.env` to point to your NotebookLM MCP server installation:

```ini
NOTEBOOKLM_SERVER_COMMAND=/home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp/.venv/bin/python
NOTEBOOKLM_SERVER_ARGS=["-m", "notebooklm_mcp.cli", "-c", "notebooklm-config.json", "server"]
NOTEBOOKLM_SERVER_CWD=/home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp
NOTEPOOKLM_BACKEND=web
NOTEPOOKLM_HEADLESS=true
NOTEPOOKLM_PROFILE_DIR=./chrome_profile_notebooklm
```

### 3. Register with Hermes

Copy `config.example.yaml` entry into your Hermes profile `config.yaml`
(`~/.hermes/profiles/lokadata/config.yaml`) under `mcp_servers`:

```yaml
notebooklm_proxy:
  command: /home/ubuntuvivo/notebooklm-mcp-proxy/.venv/bin/python
  args: ["-m", "notebooklm_mcp_proxy.server"]
  cwd: /home/ubuntuvivo/notebooklm-mcp-proxy
  env:
    NOTEBOOKLM_SERVER_COMMAND: /home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp/.venv/bin/python
    NOTEBOOKLM_SERVER_ARGS: '["-m", "notebooklm_mcp.cli", "-c", "notebooklm-config.json", "server"]'
    NOTEBOOKLM_SERVER_CWD: /home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp
    NOTEBOOKLM_BACKEND: web
    NOTEBOOKLM_HEADLESS: "true"
    NOTEBOOKLM_PROFILE_DIR: ./chrome_profile_notebooklm
  connect_timeout: 120.0
  enabled: true
```

Then enable:

```python
manage_connections(action='enable', connectors=[{"mcp": true, "name": "notebooklm_proxy"}])
```

Or via Hermes CLI:

```bash
hermes mcp enable notebooklm_proxy
```

### 4. Verify

Tools should now appear as `mcp__notebooklm_proxy__list_notebooks`,
`mcp__notebooklm_proxy__send_chat_message`, etc.

Test via terminal:

```bash
cd /home/ubuntuvivo/notebooklm-mcp-proxy
.venv/bin/python -c "
import asyncio, json
from notebooklm_mcp_proxy.client import NotebookLMClient

async def main():
    client = NotebookLMClient(
        command='/home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp/.venv/bin/python',
        args=['-m', 'notebooklm_mcp.cli', '-c', 'notebooklm-config.json', 'server'],
        cwd='/home/ubuntuvivo/.hermes/profiles/lokadata/notebooklm_mcp',
    )
    await client.start()
    tools = await client.list_tools()
    print(f'{len(tools)} tools available')
    for t in tools[:5]:
        print(' -', t['name'])
    await client.stop()

asyncio.run(main())
"
```

## Available Tools (28)

All NotebookLM MCP tools are forwarded:
- `list_notebooks`, `create_notebook`, `rename_notebook`, `delete_notebook`
- `navigate_to_notebook`, `get_default_notebook`, `set_default_notebook`
- `list_sources`, `add_source_url`, `add_source_text`, `delete_source`, `copy_source`
- `create_notebook_from_sources`
- `get_notebook_summary`, `get_share_status`, `set_notebook_public`, `share_notebook_with_user`
- `send_chat_message`, `get_chat_response`, `chat_with_notebook`
- `generate_audio_overview`, `list_audio_overviews`
- `generate_video_overview`, `list_video_overviews`
- `generate_mind_map`, `list_mind_maps`, `get_mind_map`
- `healthcheck`

## License

MIT
