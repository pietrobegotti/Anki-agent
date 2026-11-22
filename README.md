# Anki Agent

An AI agent for managing an Anki collection (notes, decks, tags, and duplicates)
through [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Status:** Step 11 — connection settings, per-user documentation storage,
installation, troubleshooting, and a remote API contract are provided.

## Requirements

- Python 3.10+
- Anki Desktop running with the AnkiConnect add-on (code `2055492159`)

## Installation

```powershell
uv sync
```

Python 3.10 or newer is required. Set optional configuration in the process
environment; the program does not load `.env` files:

```powershell
$env:ANKI_CONNECT_URL = "http://127.0.0.1:8765"
$env:ANKI_CONNECT_API_KEY = "your-local-anki-connect-key"
$env:ANKI_CONNECT_TIMEOUT = "15"
$env:ANKI_AGENT_DATA_DIR = "$env:USERPROFILE\.anki-agent\collection_docs"
$env:ANKI_AGENT_USER_ID = "default"
```

The URL, timeout, and data directory have defaults. Keep API keys in a secret
manager or process environment, not in committed files. Each user gets a
separate `<data directory>/<user ID>/` for documentation and history.

## First run

```powershell
uv run anki-agent smoke
```

The command prints the AnkiConnect version, decks, and note types, then generates
documentation in `~/.anki-agent/collection_docs/<user ID>/`. Note type documents include field usage,
front/back templates, CSS, and generated Cloze cards. This folder is ignored by
Git and kept outside the project because it contains data from your personal collection. The script also
creates convention and preference guides if they do not exist; it preserves
manual content and refreshes generated deck counts.

## Read notes from Python

`NoteReader` supports bounded searches by text, deck, note type, and tags, and
returns normalized fields, tags, and card IDs:

```python
from anki_agent.ankiconnect import AnkiConnect
from anki_agent.reader import NoteReader

reader = NoteReader(AnkiConnect())
notes = reader.search(text="趣味", deck="Japanese", limit=20)
```

`PreviewService.preview_new(...)` builds proposed cards, while
`PreviewService.preview_edit(note_id, updates)` returns before/after cards and
the changed fields. Both are read-only and include CSS and rendering warnings.

`NoteMutationService` creates a proposal containing that preview. Display it
and get explicit user approval before calling `confirm(..., user_response="approve")`.
The service rejects stale previews and blocks automatic retries when Anki's
write outcome is uncertain. Direct write actions through `AnkiConnect.invoke`
are blocked.

Before creating a note, `DuplicateChecker` searches bounded candidates for exact
and similar matches. Semantic matching is available only when a semantic
matcher or candidate IDs are supplied by the caller. Possible matches require
review; callers can pass an explicit keep-both choice after that review. Batch
proposals combine add and update previews while each operation still requires
its own approval or rejection.

Tag changes and moving a note to another deck use the same preview-and-approval
flow. Deletion previews the exact note and requires `DELETE <note ID>` as a
second confirmation. Deck creation and deck deletion are not supported.

`NoteMutationService` writes operation history by default under
`<data directory>/<user ID>/history/`. A custom `MutationHistory` can be passed
when constructing the service. History includes the request and preview,
approval decision, write status, and result; it may contain note content.
`history.recovery_status()` reports proposals interrupted before a known result
and operations whose write outcome is uncertain. It does not replay or undo
operations; inspect Anki before resolving an uncertain write.

## Remote ChatGPT connector

`RemoteGateway` is a WSGI JSON API for collection inventory and note search,
preview proposals, and separately approved writes. Register one
`RemoteUserContext` per user with a unique random bearer token of at least 32
characters. Each context must use its own `AnkiConnect`, `NoteReader`,
`NoteMutationService`, and storage root. The gateway rejects duplicate user IDs,
shared mutation services, and non-HTTPS WSGI requests.

Use [openapi.yaml](info/openapi.yaml) as the starting contract for a ChatGPT Action.
Replace its server URL with the deployed HTTPS endpoint, configure bearer-token
authentication, and keep the token in the connector's secret settings. Host the
WSGI application behind a production WSGI server and HTTPS reverse proxy; keep
AnkiConnect bound to loopback on the machine that owns the collection. The
repository provides the secured API and contract, but does not deploy a public
endpoint or configure a ChatGPT account.

### MCP server for a plugin

The project also provides an MCP Streamable HTTP adapter with tools for
collection lookup, note search, batch-add previews, individual batch decisions,
and batch cancellation. Install dependencies with `uv sync --locked`, set the
usual `ANKI_CONNECT_*` and `ANKI_AGENT_*` configuration, and provide a bearer
token of at least 32 characters in `ANKI_AGENT_BEARER_TOKEN`. Start it with:

```powershell
uv run anki-agent-mcp --host 127.0.0.1 --port 8000
```

Put the MCP server behind an HTTPS reverse proxy before connecting a remote
plugin. Keep the MCP endpoint private to authenticated requests and keep
AnkiConnect bound to loopback on the machine that owns the collection. The
default launcher registers one user context; deployments with multiple users
can construct a `RemoteGateway` and register one isolated context per token.
The project does not provision a host, TLS certificate, identity provider, or
plugin account configuration.

After a batch confirmation applies at least one note, the MCP workflow asks
AnkiConnect to run its `sync` action so the local collection is synchronized
with AnkiWeb. The response reports whether that sync completed. Anki Desktop
must be running, and the phone still needs to sync with AnkiWeb to receive the
cards. AnkiWeb is reached through the supported Anki Desktop sync flow; the
plugin does not call private AnkiWeb endpoints. To use the plugin while your
everyday PC is off, run Anki Desktop, AnkiConnect, and the MCP service together
on a separate always-on host connected to the same AnkiWeb account. See
[remote setup](info/REMOTE.md).

The local card-file workflow uses `cards/` and `info/`. When the user asks for
the meaning of one or more words, the LLM prepares readable card previews from
`info/CARDS.md` and `info/Takoboto.enriched.json`, then asks for confirmation.
If the user has not specified a deck, the LLM asks whether to use `ダイワ` or
`なでもかんでも`. Only after confirmation does it save one JSON card per word
directly in `cards/`, using `cards/next_id.txt` to track progressive IDs. This
flow requires no script to prepare or save card files.

The separate local queue importer still expects its legacy approved-request
schema, including a request wrapper, deck, and note type. It does not consume
the card files described by `info/CARDS.md`; those files are not automatically
imported into Anki by this workflow.

The `AUTO` sections in generated files are refreshed on every run. The
"Manual notes" section is preserved.

Run the local documentation tests with:

```powershell
uv run python scripts/tests/test_agent.py
```

## Troubleshooting

- **Connection refused:** start Anki Desktop, confirm AnkiConnect is installed,
  and check `ANKI_CONNECT_URL` and the configured port.
- **Unauthorized AnkiConnect response:** check the local API key in
  `ANKI_CONNECT_API_KEY`.
- **No generated files:** check write access to `ANKI_AGENT_DATA_DIR` and the
  selected `ANKI_AGENT_USER_ID` subfolder.
- **Remote API rejects a request:** use HTTPS, send `Authorization: Bearer …`,
  and verify that the token maps to the intended user's isolated services.

A clean-install check is `uv sync --locked` followed by the offline test
command. The smoke command requires Anki Desktop and AnkiConnect. Remote
deployment additionally requires a production WSGI server, HTTPS ingress, and
a ChatGPT Action configured from `info/openapi.yaml`. See [remote setup](info/REMOTE.md).

## Project structure

```
scripts/anki_agent/
  config.py        environment-based connection and per-user storage settings
  cli.py           local smoke-test command line
  ankiconnect.py   minimal AnkiConnect client (standard library only)
  reader.py        bounded read-only note search and retrieval
  duplicates.py    exact, similar, and semantic candidate duplicate checks
  preview.py       read-only note and card previews
  mutations.py     preview-gated note creation and field updates
  history.py       append-only mutation audit and recovery status
  remote.py        authenticated tenant-isolated WSGI API
  mcp_server.py    MCP Streamable HTTP adapter for remote chat tools
  local_cards.py   JSON request schema, local queue reader, and Anki importer
  collection_config.py exports deck and note-type fields for the LLM
  storage.py       Storage interface and LocalStorage implementation
  docs_gen.py      note type and deck documentation generation
info/              card workflow, remote setup, and API contract
scripts/           application setup and separate legacy queue utilities
cards/             Drive-synchronized LLM-created JSON cards
scripts/tests/test_run.py  smoke test
scripts/tests/test_agent.py automated tests using simulated Anki responses
info/openapi.yaml  ChatGPT Action / remote connector API contract
```

## Roadmap

- [x] Write approved note additions and field updates
- [x] Preview and approval before every note operation
- [x] Duplicate review and individually approved batches
- [x] Approved tag changes, deck moves, and confirmed note deletions
- [x] Local Drive-for-desktop synchronized JSON queue and import worker
- [x] Secured remote API and ChatGPT Action contract
