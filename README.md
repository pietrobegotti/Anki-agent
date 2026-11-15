# Anki Agent

An AI agent for managing an Anki collection (notes, decks, tags, and duplicates)
through [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Status:** Step 3 — collection conventions and confirmed agent preferences,
alongside read-only note type structure documentation. No changes are made to Anki.

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

The `AUTO` sections in generated files are refreshed on every run. The
"Manual notes" section is preserved.

Run the local documentation tests with:

```powershell
uv run python test_docs_gen.py
```

## Project structure

```
src/anki_agent/
  ankiconnect.py   minimal AnkiConnect client (standard library only)
  storage.py       Storage interface and LocalStorage implementation
  docs_gen.py      note type and deck documentation generation
test_run.py        smoke test
test_docs_gen.py   automated tests using simulated Anki responses
ROADMAP.md         project roadmap
manifest.md        project requirements
```

## Roadmap

- [ ] Write to Anki (add, edit, and delete notes)
- [ ] Preview and approval before every operation
- [ ] `GoogleDriveStorage` with the same interface as `Storage`
- [ ] ChatGPT integration
