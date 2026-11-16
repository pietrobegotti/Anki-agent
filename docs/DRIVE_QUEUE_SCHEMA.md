# Drive queue for chat-created Anki notes

## Purpose

Keep approved card requests while the user's PC is offline. ChatGPT writes one
small JSON file per approved note to a private Drive folder. A local worker
processes the files when Anki Desktop and AnkiConnect are available.

The JSON files are queue instructions, not Anki database files. The worker uses
AnkiConnect to add notes to the selected collection and then asks Anki Desktop
to sync with AnkiWeb.

## Card file

Suggested path: `Anki Agent/queue/<card_id>.json`.

```json
{
  "schema_version": 1,
  "card_id": "opaque-random-id",
  "batch_id": "opaque-random-batch-id",
  "created_at": "2026-11-17T08:30:00Z",
  "expires_at": "2026-12-17T08:30:00Z",
  "status": "pending",
  "approved": true,
  "deck": "Japanese::Vocabulary",
  "note_type": "Basic",
  "fields": {
    "Front": "食べる",
    "Back": "to eat"
  },
  "tags": ["chatgpt"]
}
```

Files are created only after the user has reviewed and approved the chat
preview. Store the card content and minimum processing metadata only; never
store the full conversation, AnkiWeb password, or OAuth refresh token in the
queue file.

## State lifecycle

- `pending`: waiting for the local worker.
- `processing`: claimed by one worker instance with a lease expiry.
- `applied`: added to Anki; includes the note ID and sync result.
- `needs_review`: duplicate found, the destination changed, or the saved schema
  no longer matches; do not add automatically.
- `failed`: invalid data or a non-retryable Anki error; include a safe error
  summary and leave the file available for review.
- expired pending files are not imported; mark them `expired` and leave a short
  status for the next chat to report.

The worker keeps a local SQLite receipt keyed by `card_id` before acknowledging
`applied` in Drive. If Drive acknowledgment fails after Anki accepted a write,
the receipt prevents a later poll from creating the same note again. Worker
leases and receipts also prevent two PCs from processing the same queue item.

## PC worker behavior

1. Poll only the dedicated queue folder while the PC is on. Use the Drive
   Changes API rather than scanning all Drive files on every interval.
2. Claim a `pending` file using its Drive revision / ETag to avoid overwriting a
   concurrent worker's state.
3. Verify the approval marker, expiry, destination deck, note type, known
   fields, and current collection schema.
4. Recheck duplicates against the current Anki collection. Pause ambiguous
   matches as `needs_review` rather than deciding on the user's behalf.
5. Add the note through `NoteMutationService`; after a successful write, record
   the local receipt and ask AnkiConnect to sync with AnkiWeb.
6. Update the file with the note ID and sync result. Retain completed files for
   a configurable short period, then delete or archive them.

The worker publishes a compact snapshot of decks, note types, templates, and
collection guides to a separate Drive folder whenever it is online. ChatGPT
uses that snapshot to build accurate cards and previews while Anki is
unreachable. The worker always revalidates against the live collection before
writing.

## Authentication and privacy

Use separate OAuth sessions for the ChatGPT plugin and the PC worker, both
authorized for the same user's Drive and the same dedicated folder. Request the
least access supported by the chosen Google integration; the target is
`drive.file`, which is restricted to files the app creates or the user
explicitly opens/shares with it. Keep refresh tokens in each host's secret
storage and never in the queue JSON or repository.

The Drive integration, OAuth configuration, queue service, Windows worker, and
downloadable status reporting are implementation work; the current repository
does not yet process these files.
