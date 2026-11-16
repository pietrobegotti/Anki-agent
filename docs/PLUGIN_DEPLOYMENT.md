# Deploy and connect the Anki Agent plugin

This guide describes how to connect the plugin package to a running Anki Agent
MCP server. The repository supplies the server and package builder; it does not
create hosting, a public hostname, HTTPS, or an account-side plugin connection.

## Network layout

The computer running Anki Desktop must also run the Anki Agent MCP server. The
server talks to AnkiConnect over loopback. A public HTTPS reverse proxy or
secure tunnel forwards only the MCP route to the local server. Do not expose
AnkiConnect's port `8765` to the internet.

```text
ChatGPT plugin -- HTTPS + bearer token --> public tunnel / reverse proxy
                                          --> Anki Agent MCP :8000/mcp
                                          --> AnkiConnect 127.0.0.1:8765
                                          --> Anki Desktop collection
```

The Anki computer needs to remain on and connected while the plugin is in use.
If the user wants access while that computer is off, Anki must instead run on
an always-on host with the collection available there.

## Configure the Anki computer

1. Install the project with `uv sync --locked` and confirm that Anki Desktop and
   AnkiConnect work locally.
2. Set `ANKI_CONNECT_URL` to `http://127.0.0.1:8765` (the default) and set
   `ANKI_AGENT_USER_ID` and `ANKI_AGENT_DATA_DIR` if needed.
3. Generate a random bearer token of at least 32 characters and store it in a
   secret manager or process environment as `ANKI_AGENT_BEARER_TOKEN`. Do not
   commit it or put it in the plugin archive.
4. Start `uv run anki-agent-mcp --host 127.0.0.1 --port 8000`.
5. Configure a reverse proxy or tunnel with a stable hostname and a valid HTTPS
   certificate. Forward `/mcp` to `http://127.0.0.1:8000/mcp`, preserve the
   `Authorization` header, and do not publish port `8765`.

The launcher configures one user context and one bearer token. A multi-user
service needs a deployment entry point that registers a separate Anki
connection, storage root, and token for every user.

## Build the plugin archive

Once the HTTPS endpoint is ready, build the plugin archive from the repository
root:

```powershell
uv run python plugin/build_package.py `
  --mcp-url "https://YOUR_HOST/mcp" `
  --output "dist/anki-agent-plugin.zip"
```

The builder requires HTTPS, writes no credentials to the archive, configures
bearer API-key authentication for the MCP server, and checks that the archive
contains the manifest, skill, and MCP configuration. The actual endpoint is
required; do not install a package containing a placeholder URL.

## Save and connect the plugin

1. Upload the generated ZIP through the Plugin Creator workflow to save a
   private plugin in the account or active workspace.
2. Configure the bearer token in the plugin's secret/API-key settings when
   prompted. Keep the token out of chat messages and source files.
3. Confirm that the plugin reports these MCP tools as available: `get_collection`,
   `inspect_note_type`, `list_collection_docs`, `read_collection_doc`,
   `search_notes`, `propose_add_batch`, `confirm_add_batch`, and
   `cancel_add_batch`.
4. Open a new chat with the plugin enabled. Discuss or collect cards, request an
   upload, review the preview, and approve the intended notes.

The tool being visible is not enough to establish that Anki is reachable. Do a
real read-only collection lookup before using write proposals. The first real
write must be an explicitly approved proposal whose result is checked in Anki.

## Operational requirements

- Keep the Anki computer on while remote access is needed.
- Keep the bearer token secret and rotate it if it is exposed.
- Back up the Anki collection and the agent data directory.
- If the server restarts while a preview is awaiting approval, create a fresh
  proposal and review its new preview; pending proposal state is currently held
  in server memory.
- Public plugin distribution requires separate privacy, support, and listing
  preparation. The private plugin archive does not include those public listing
  steps.
