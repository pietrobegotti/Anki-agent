# Remote connection

The project includes an authenticated MCP server and an OpenAPI contract at
`info/openapi.yaml`. A remote deployment needs Anki Desktop and AnkiConnect on
the host, a bearer token, and an HTTPS reverse proxy. Keep AnkiConnect bound to
`127.0.0.1`; never expose port `8765` to the internet.

Set a random secret as `ANKI_AGENT_BEARER_TOKEN` in the host's secret store and
start the server locally:

```powershell
uv sync --locked
uv run anki-agent-mcp --host 127.0.0.1 --port 8000
```

Configure the proxy to forward HTTPS `/mcp` requests to the local MCP server
and preserve the `Authorization` header. To build the private plugin archive,
run from the project root with the deployed HTTPS endpoint:

```powershell
uv run python scripts/plugin/build_package.py `
  --mcp-url "https://YOUR_HOST/mcp" `
  --output "dist/anki-agent-plugin.zip"
```

Configure the plugin with the same bearer token using its secret settings. Do
not put tokens in source files, chat messages, or the archive. The project
provides the server and package builder; it does not provide hosting, TLS, or
account-side plugin setup.