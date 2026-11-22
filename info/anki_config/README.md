# Anki card configuration

This folder holds the collection schema and the instructions the card-writing
model should follow. Keep the whole project folder in the Google Drive for
desktop synchronized location so Claude can read these files and place card
requests in `cards/`.

Run `uv run python scripts/export_anki_config.py` while Anki Desktop and
AnkiConnect are available to create `collection_config.md` from the live
collection. The export lists deck names, note types, fields, and card template
names; it does not copy existing note contents.

Edit `collection_config.md` after export to explain the meaning of fields,
preferred mappings, and any exceptions. The generated section is refreshed by
the command, while the manual section is preserved.
