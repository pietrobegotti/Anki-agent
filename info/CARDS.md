# Card queue

Place approved JSON request files directly in `cards/`. Google Drive for
desktop synchronizes this folder; the local importer reads each `*.json` file
and writes processing status back to that file.

Run `uv run python scripts/import_cards.py` on the PC to import. The script
requires Anki Desktop and AnkiConnect to be running. Completed JSON files stay
here until you explicitly run `uv run python scripts/cleanup_imported_cards.py`.
That cleanup only removes fully imported JSON files; it never deletes Anki notes.
