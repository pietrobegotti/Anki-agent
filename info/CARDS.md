# Card workflow

This project uses `cards/` as a local JSON queue. Read the live schema at
`info/anki_config/collection_config.md` before preparing cards; refresh it with
`uv run python scripts/export_anki_config.py` while Anki Desktop is running.

## Prepare a request

Create one `<request_id>.json` file in `cards/` only after the user has reviewed
and approved the proposed cards. A request may contain several cards. Use only
deck, note type, and field names present in the live schema. Keep each note
focused on one fact, preserve the source language, and never invent field
meanings. Use stable unique IDs; retain each `card_id` if retrying the same
request. Do not edit a request after saving it.

```json
{
  "schema_version": 1,
  "request_id": "unique-request-id",
  "created_at": "2026-11-21T08:30:00Z",
  "approved": true,
  "cards": [
    {
      "card_id": "unique-card-id",
      "deck": "Exact deck name",
      "note_type": "Exact note type",
      "fields": {"Front": "Question", "Back": "Answer"},
      "tags": []
    }
  ]
}
```

All field values must be strings. `approved` must be `true` only after explicit
approval. Do not put credentials or conversation transcripts in queue files.

## Import and cleanup

On the PC, start Anki Desktop with AnkiConnect, then run:

```powershell
uv run python scripts/import_cards.py
```

The importer validates the request, checks duplicates, records card IDs in a
local receipt database, updates queue status, and syncs AnkiWeb after successful
adds. Possible duplicates or uncertain write outcomes are paused for review.
Completed JSON stays in `cards/` until you explicitly run:

```powershell
uv run python scripts/cleanup_imported_cards.py
```

Cleanup removes only fully imported JSON files; it never deletes Anki notes.