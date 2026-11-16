# Deploy and connect the Anki Agent plugin

This guide describes how to connect the plugin package to a running Anki Agent
MCP server. The repository supplies the server and package builder; it does not
create hosting, a public hostname, HTTPS, or an account-side plugin connection.

## Preferred design for a powered-off PC: Drive queue

The project is moving toward a temporary Google Drive queue so the user's PC
does not need to be online during the ChatGPT conversation:

```text
ChatGPT plugin -- Google OAuth --> private Drive queue (one JSON file per card)
                                      |
                                      | local polling when PC is on
                                      v
                           Windows worker -> AnkiConnect -> Anki Desktop
                                                           | sync
                                                           v
                                                         AnkiWeb -> phone
```

ChatGPT will prepare and preview the cards, then write approved cards to a
private Drive folder. When the PC and Anki are available, a local worker will
read each pending card, recheck the deck, note type, and duplicates, import it,
and ask AnkiConnect to sync. The PC may be off while cards wait in Drive. If a
duplicate or stale schema is found when the worker wakes, that card is paused
for review rather than imported automatically.

The intended Drive access is OAuth with the `drive.file` scope, which is limited
to files created or explicitly opened/shared with the app ([Google scope guide](https://developers.google.com/workspace/drive/api/guides/api-specific-auth)).
The PC worker can poll Drive's change feed while running; push notifications
would require a public HTTPS webhook ([Drive change guide](https://developers.google.com/workspace/drive/api/guides/manage-changes)).
Neither the Drive OAuth integration nor the local queue worker is implemented
yet.

## Existing MCP prototype (requires an always-on Anki host)

The rest of this guide documents the earlier MCP deployment prototype. It
connects to a remote MCP endpoint and requires Anki Desktop to be open on that
host. It is not the planned no-always-on-host workflow above.

### Network layout

AnkiWeb does not provide a documented public API for third-party note writes.
The supported route is to use a second, always-on Anki client as the bridge:
Anki Desktop and AnkiConnect run on a dedicated host, and the MCP server runs
there too. AnkiConnect stays on loopback. A public HTTPS reverse proxy or secure
tunnel forwards only the MCP route to the local server. Do not expose
AnkiConnect's port `8765` to the internet.

```text
ChatGPT plugin -- HTTPS + bearer token --> public tunnel / reverse proxy
                                          --> always-on host: Anki Agent MCP
                                          --> AnkiConnect 127.0.0.1:8765
                                          --> Anki Desktop <--> AnkiWeb
                                                               ^
                                             phone -- sync -----+
```

The user's everyday PC can be off. The dedicated host, Anki Desktop, AnkiConnect,
and the MCP server must remain on and connected. The phone synchronizes with
AnkiWeb independently after the desktop host syncs the changes.

### Configure the always-on host

1. Choose a host that can keep Anki Desktop open in a logged-in desktop
   session. A dedicated always-on mini PC is the simplest setup; a remote VM
   needs a supported graphical session and must be evaluated before use.
2. Install Anki Desktop and AnkiConnect on that host. Back up the current
   collection before connecting the host to the same AnkiWeb account.
3. Treat this as a new Anki device. If its local collection is empty and the
   existing collection is on AnkiWeb, choose **Download from AnkiWeb** on the
   initial sync. Do not select Upload, which would make the host's empty
   collection replace the one in AnkiWeb. The [Anki sync manual](https://docs.ankiweb.net/syncing.html)
   describes the initial upload/download choice.
4. Install the project with `uv sync --locked` and confirm that AnkiConnect
   works on loopback at `http://127.0.0.1:8765`.
5. Set `ANKI_CONNECT_URL` to `http://127.0.0.1:8765` (the default) and set
   `ANKI_AGENT_USER_ID` and `ANKI_AGENT_DATA_DIR` if needed.
6. Generate a random bearer token of at least 32 characters and store it in a
   secret manager or process environment as `ANKI_AGENT_BEARER_TOKEN`. Do not
   commit it or put it in the plugin archive.
7. Start `uv run anki-agent-mcp --host 127.0.0.1 --port 8000`.
8. Configure a reverse proxy or tunnel with a stable hostname and a valid HTTPS
   certificate. Forward `/mcp` to `http://127.0.0.1:8000/mcp`, preserve the
   `Authorization` header, and do not publish port `8765`.

The launcher configures one user context and one bearer token. A multi-user
service needs a deployment entry point that registers a separate Anki
connection, storage root, and token for every user.

### Build the MCP plugin archive

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

### Save and connect the MCP plugin

1. Upload the generated ZIP through the Plugin Creator workflow to save a
   private plugin in the account or active workspace.
2. Configure the bearer token in the plugin's secret/API-key settings when
   prompted. Keep the token out of chat messages and source files.
3. Confirm that the plugin reports these MCP tools as available: `get_collection`,
   `inspect_note_type`, `list_collection_docs`, `read_collection_doc`,
   `search_notes`, `propose_add_batch`, `confirm_add_batch`, and
   `cancel_add_batch`.
4. Open a new chat with the plugin enabled. Discuss or collect cards, request an
   upload, review the preview, and approve the intended notes. After at least
   one note is added, the plugin asks AnkiConnect to sync the collection with
   AnkiWeb and reports the sync result.

The tool being visible is not enough to establish that Anki is reachable. Do a
real read-only collection lookup before using write proposals. The first real
write must be an explicitly approved proposal whose result is checked in Anki.
To see the new cards on a phone, sync the phone with the same AnkiWeb account
after the desktop sync completes.

### Operational requirements for the MCP prototype

- Keep the dedicated Anki host on while remote access is needed; the everyday
  PC may be off.
- Keep the bearer token secret and rotate it if it is exposed.
- Back up the Anki collection and the agent data directory.
- If the server restarts while a preview is awaiting approval, create a fresh
  proposal and review its new preview; pending proposal state is currently held
  in server memory.
- Public plugin distribution requires separate privacy, support, and listing
  preparation. The private plugin archive does not include those public listing
  steps.
