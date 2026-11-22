# Local scripts

Run these commands from the project root after `uv sync --locked`:

- `uv run python scripts/export_anki_config.py` refreshes the actual Anki deck,
  note type, field, and template inventory. Anki Desktop must be open.
- `uv run python scripts/import_cards.py` imports approved requests from
  `cards/`. Anki Desktop and AnkiConnect must be available.
- `uv run python scripts/cleanup_imported_cards.py` explicitly removes only
  JSON requests whose cards all have successful local import receipts.

The receipt database is stored outside the Drive-synchronized project under
the current user's local state directory.
