# Anki Agent

An AI agent for managing an Anki collection (notes, decks, tags, and duplicates)
through [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Status:** Step 1 — read-only access and Markdown documentation generation
for the collection (note types and decks). No changes are made to Anki.

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
documentation in `collection_docs/`. This folder is ignored by Git because it
contains data from your personal collection.

The `AUTO` sections in generated files are refreshed on every run. The
"Manual notes" section is preserved.

## Project structure

```
src/anki_agent/
  ankiconnect.py   minimal AnkiConnect client (standard library only)
  storage.py       Storage interface and LocalStorage implementation
  docs_gen.py      note type and deck documentation generation
test_run.py        smoke test
ROADMAP.md         project roadmap
manifest.md        project requirements
```

## Roadmap

- [ ] Write to Anki (add, edit, and delete notes)
- [ ] Preview and approval before every operation
- [ ] `GoogleDriveStorage` with the same interface as `Storage`
- [ ] ChatGPT integration
