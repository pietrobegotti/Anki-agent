# Anki Card Generation Instructions

Read the generated `collection_config.md` before creating card JSON. Use only exact deck,
note type, and field names listed there. Ask the user when a destination or
field meaning is unclear; never invent collection schema.

## Card quality

- Make each note test one clear fact or skill.
- Keep the front focused and the back concise but sufficient.
- Preserve the source language and the user's confirmed terminology.
- Do not add facts that were not supplied or reliably implied.
- Use strings for all field values and include only fields supported by the
  selected note type.

## Saving cards

- Create a JSON request only when the user explicitly asks to save the reviewed
  cards.
- Put one file per save request directly in the `cards/` folder. One request
  can contain several cards.
- Use unique stable IDs for `request_id` and every `card_id`; retries must keep
  the original IDs.
- Set `approved` to `true` only after the user has approved the proposed card
  content.
- Do not edit an existing request after saving it. Create a new request for
  later changes.
- Never delete completed request files automatically. Cleanup is a separate
  explicit operation and removes JSON files only, not Anki notes.

## JSON shape

```json
{
  "schema_version": 1,
  "request_id": "unique-request-id",
  "created_at": "2026-11-21T00:00:00Z",
  "approved": true,
  "cards": [
    {
      "card_id": "unique-card-id",
      "deck": "Exact deck name",
      "note_type": "Exact note type",
      "fields": {"Front": "Question", "Back": "Answer"},
      "tags": ["chatgpt"]
    }
  ]
}
```
