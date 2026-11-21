# Chat-to-Anki workflow

## Current design

The workflow has two parts with a Drive-synchronized local folder as the handoff:

1. Claude reads `anki_config/collection_config.md` and
   `anki_config/generation_instructions.md`. After the user explicitly approves
   the cards, it creates one JSON request file per save request in `cards/`.
2. A local Python script reads those JSON files from the Drive for desktop
   folder, validates the collection destination and duplicates, then adds cards
   through AnkiConnect. It updates status in the JSON and records stable card
   IDs in a local SQLite receipt file.

The project should itself live inside the Google Drive for desktop synchronized
location. No Google API access token is used by the worker.

## Implemented in this branch

- `anki_config/` contains card-generation guidance and the collection schema
  exporter output path.
- `scripts/export_anki_config.py` refreshes exact live deck, note type, field,
  and template names when Anki is available.
- `scripts/import_cards.py` imports approved JSON requests from `cards/`.
- `scripts/cleanup_imported_cards.py` explicitly removes fully imported JSON
  files only; it never deletes notes from Anki.
- The worker records receipts before writes and pauses uncertain outcomes rather
  than retrying blindly. Potential duplicates are left for review.

## Still required for a complete chat experience

Claude needs access to the project folder and permission to create files under
`cards/`. The Markdown instructions explain the format, but do not grant Drive
access by themselves. Claude's built-in Drive integration is documented for
Google Docs and paid Claude plans; a custom remote MCP connector also requires
an eligible paid plan. If direct connector access is unavailable, Claude can
produce the JSON and the user can save it into the synchronized `cards/` folder
manually.

## Local setup

1. Install Google Drive for desktop and choose a synchronized local folder.
2. Move or clone this project into that folder.
3. Run `uv sync --locked`.
4. Start Anki Desktop with AnkiConnect installed.
5. Run `uv run python scripts/export_anki_config.py` to generate the current
   collection schema for the LLM.
6. Put approved request JSON files in `cards/` and run
   `uv run python scripts/import_cards.py`.
7. Run `uv run python scripts/cleanup_imported_cards.py` only when you want to
   remove completed JSON requests from Drive.
