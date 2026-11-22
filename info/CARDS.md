# Creating Anki card JSON files

This document is for the LLM creating card requests. When the user asks to save
approved cards, create a JSON file directly in `cards/`. Do not ask the user to
run a script as part of creating that file.

## Choose the Anki note format and fields

Before writing JSON, get the collection schema from the live Anki Agent tools
when available: call `get_collection`, then `inspect_note_type` for the chosen
type. Otherwise read `info/anki_config/collection_config.md` if it exists. The
schema lists available decks, note types, exact field names, and card
templates. Choose a note type whose fields and templates fit the requested
card. Use the field names exactly as written, including capitalization. Put the
card content in those note fields; Anki uses the note type's templates to
produce the displayed card or cards.

Do not assume that a note type called `Basic` has fields named `Front` and
`Back`, or that every note creates exactly one card. Do not invent a deck, note
type, field, field meaning, or template. If neither live tools nor the
collection configuration is available, or the schema does not fit the request,
ask the user for the needed collection format before creating a file. Include
only fields supported by the selected note type; each value must be a JSON
string.

## File format

Create one file per save request. A request can contain one or more cards. Use
this structure, replacing every example value and field name with the approved
content and the exact collection schema:

```json
{
  "schema_version": 1,
  "request_id": "unique-request-id",
  "created_at": "2026-11-21T08:30:00Z",
  "approved": true,
  "cards": [
    {
      "card_id": "unique-card-id",
      "deck": "Exact deck name from the collection",
      "note_type": "Exact note type from the collection",
      "fields": {
        "Exact field name from the selected note type": "Card content"
      },
      "tags": ["optional-tag"]
    }
  ]
}
```

- `schema_version`: integer `1`.
- `request_id`: unique ID for this save request; use a UUID.
- `created_at`: creation time in ISO 8601 format with a UTC offset, preferably
  UTC (`Z`).
- `approved`: boolean `true` only after the user explicitly approves the card
  content.
- `cards`: non-empty array of card objects.
- `card_id`: unique, stable ID for the card. Keep it unchanged if the same
  request is retried.
- `deck`: exact existing deck name, including `::` for subdecks.
- `note_type`: exact existing note type name.
- `fields`: non-empty object containing only supported field names and string
  values. Use the selected note type's actual fields, not generic `Front` and
  `Back` names unless those names appear in the collection configuration.
- `tags`: optional array of strings; use `[]` when there are no tags.

The filename should be `<request_id>.json`. Write valid UTF-8 JSON with double
quotes and no comments or trailing commas. Do not include processing fields
such as `card_status`, `errors`, or `note_ids`; those are added by the importer.

## Card writing rules

- Make each note test one clear fact or skill. Keep prompts focused and answers
  concise but sufficient.
- Follow the selected note type's templates and the user's requested direction
  (for example, recognition, recall, or cloze). A note may generate multiple
  cards through its templates.
- Preserve the source language and user-confirmed terminology. Do not add facts
  that were not supplied or reliably implied.
- Show the proposed deck, note type, fields, values, and tags to the user and
  wait for explicit approval before saving the JSON file.
- Do not store conversation transcripts, credentials, or tokens in the file.
- Do not edit a saved request. Create a new request with new IDs for later
  changes.
