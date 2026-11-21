# Local Drive-synchronized card queue

## Project folders

```text
anki_config/
  collection_config.md           generated from the live Anki collection
  generation_instructions.md     instructions for Claude or another LLM
scripts/
  export_anki_config.py
  import_cards.py
  cleanup_imported_cards.py
cards/
  <request-id>.json               one approved request per file
```

Keep the project folder inside the Google Drive for desktop synchronized
location. Claude can read the two Markdown guides and save approved request
JSON files in `cards/`. The local worker uses normal filesystem access; it does
not need a Google API key or OAuth token.

## Request format

One request file may hold multiple cards. Request and card IDs must be stable
across retries.

```json
{
  "schema_version": 1,
  "request_id": "opaque-random-request-id",
  "created_at": "2026-11-21T08:30:00Z",
  "approved": true,
  "cards": [{
    "card_id": "opaque-random-card-id",
    "deck": "Japanese::Vocabulary",
    "note_type": "Basic",
    "fields": {"Front": "食べる", "Back": "to eat"},
    "tags": ["chatgpt"]
  }]
}
```

The LLM writes a file only after the user asks to save reviewed cards. Do not
store conversation transcripts, credentials, or refresh tokens in these files.
The worker adds per-card processing status to each JSON file; Drive for desktop
syncs those updates back to Drive.

## Import

Run `uv run python scripts/import_cards.py` on the PC. The worker validates the
request, checks current Anki decks and note types through the mutation preview,
checks possible duplicates, and writes approved notes through
`NoteMutationService`. Anki Desktop and AnkiConnect must be running. After
successful additions, the worker asks Anki Desktop to sync with AnkiWeb.

A local SQLite receipt keyed by `card_id` is kept outside the synchronized
project and prevents re-importing a card. A write interrupted at an uncertain
point is paused instead of retried blindly. A possible duplicate is marked
`needs_review` and not imported automatically.

## Cleanup

Completed request JSON files remain in `cards/` until the user runs
`uv run python scripts/cleanup_imported_cards.py`. Cleanup removes only files
whose cards all have `applied` receipts. It never deletes or changes Anki notes.
