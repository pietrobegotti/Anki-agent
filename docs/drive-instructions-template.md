# Anki Card Writing Instructions

Keep this file in `Anki Agent/instructions.md` on Google Drive. Read it together
with `config.md` whenever preparing cards for the Drive queue.

## Writing style

- Use clear, natural English explanations unless the card requires another
  language.
- Keep each card focused on one testable fact.
- Prefer concise answers; include context only when it helps recall or prevents
  ambiguity.
- Preserve source language and spelling for vocabulary cards.
- Do not fabricate facts. Ask the user when the source or intended meaning is
  unclear.

## Preparing a queue request

- Create a JSON file only after the user explicitly says to save the reviewed
  cards.
- Use the exact deck, note type, and field names from `config.md`.
- Include every required field and use strings for all field values.
- Assign every card a stable UUID `card_id`; assign the request a UUID
  `request_id`.
- Set `approved` to `true` only after explicit user approval.
- Save one file per request, named `<request_id>.json`, under `queue/`.
- Never overwrite another request file. A retry must reuse the same request
  and card IDs so it cannot create duplicates.
- Do not delete completed files automatically. Delete completed queue JSON files
  only when the user explicitly asks for Drive cleanup. This never means
  deleting notes from Anki.

## User workflow

1. “Save these cards” prepares and saves an approved JSON request in Drive.
2. “Import the cards” runs the local worker when the PC and Anki are available.
3. “Clean up imported queue files” explicitly removes completed JSON files from
   Drive. It does not remove Anki notes.
