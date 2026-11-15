# Anki Agent

An AI agent for managing an Anki collection (notes, decks, tags, and duplicates)
through [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Status:** Step 7 — duplicate review and batched note operations are supported.
Creation and field updates require a preview and explicit approval before Anki
is changed.

## Requirements

- Python 3.9+
- Anki Desktop running with the AnkiConnect add-on (code `2055492159`)

## Installation

```powershell
uv sync
```

## First run

```powershell
uv run python test_run.py
```

The script prints the AnkiConnect version, decks, and note types, then generates
documentation in `collection_docs/`. Note type documents include field usage,
front/back templates, CSS, and generated Cloze cards. This folder is ignored by
Git because it contains data from your personal collection. The script also
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

Before creating a note, `DuplicateChecker` searches for exact and similar notes.
Possible matches require review; callers can pass an explicit keep-both choice
after that review. Batch proposals combine add and update previews while each
operation still requires its own approval or rejection.

The `AUTO` sections in generated files are refreshed on every run. The
"Manual notes" section is preserved.

Run the local documentation tests with:

```powershell
uv run python test_agent.py
```

## Project structure

```
src/anki_agent/
  ankiconnect.py   minimal AnkiConnect client (standard library only)
  reader.py        bounded read-only note search and retrieval
  duplicates.py    exact, similar, and semantic candidate duplicate checks
  preview.py       read-only note and card previews
  mutations.py     preview-gated note creation and field updates
  storage.py       Storage interface and LocalStorage implementation
  docs_gen.py      note type and deck documentation generation
test_run.py        smoke test
test_agent.py      automated tests using simulated Anki responses
ROADMAP.md         project roadmap
manifest.md        project requirements
```

## Roadmap

- [x] Write approved note additions and field updates
- [x] Preview and approval before every note operation
- [x] Duplicate review and individually approved batches
- [ ] `GoogleDriveStorage` with the same interface as `Storage`
- [ ] ChatGPT integration
