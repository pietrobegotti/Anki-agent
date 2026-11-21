# Drive queue for chat-created Anki notes

## Layout

The whole queue lives beneath a Drive parent folder selected by the user:

```text
<selected parent>/Anki Agent/
  config.md
  instructions.md
  queue/
  completed/  (reserved)
```

`GoogleDriveProvider.ensure_layout(parent_id)` creates/finds this nested
structure and seeds the two English guide documents if they are missing. It
never overwrites existing guides.

## Request files

ChatGPT writes one immutable JSON file per save request. A request can contain
multiple cards; every card and request has a stable UUID. Retries must reuse the
same IDs.

```json
{
  "schema_version": 1,
  "request_id": "opaque-random-request-id",
  "created_at": "2026-11-17T08:30:00Z",
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

Files are created only after the user reviewed and approved the card content.
Never store conversation transcripts, AnkiWeb passwords, or OAuth refresh
tokens in the queue file.

## Import and idempotency

The `anki-agent drive-import` command reads JSON from `queue/`, validates the
approval marker, and proposes each card through `NoteMutationService` so current
decks, note types, fields, and duplicate checks are applied. It writes only
through that service's explicit approval path. A local SQLite receipt keyed by
`card_id` is saved before the write. Applied IDs are skipped on later runs;
`applying` and uncertain outcomes are paused for reconciliation, never retried
blindly. Duplicate matches are marked `needs_review`. After additions, the
worker asks Anki Desktop to sync with AnkiWeb.

Run one worker PC. Multi-PC revision claims are not implemented. A status
update in Drive can fail after a successful Anki write; the local receipt still
prevents the same card ID from being added again on this PC.

## Explicit cleanup

Completed JSON requests stay in Drive until the user explicitly runs
`anki-agent drive-cleanup`. Cleanup deletes fully imported JSON files from
Drive only. It does not delete or change notes in Anki. Requests with pending,
failed, or review-needed cards are retained.

## Guides and authentication

English starter documents are `docs/drive-config-template.md` and
`docs/drive-instructions-template.md`; `ensure_layout` seeds equivalent
defaults. The Google Drive v3 adapter accepts an access-token callback, keeping
OAuth secrets outside this package and the queue. The CLI currently expects a
valid token in `ANKI_AGENT_DRIVE_ACCESS_TOKEN` and the selected parent ID in
`ANKI_AGENT_DRIVE_PARENT_ID`. Token issuance/refresh management is not included.
