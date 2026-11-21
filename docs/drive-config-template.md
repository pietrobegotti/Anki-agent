# Anki Agent Configuration

Keep this file in `Anki Agent/config.md` on Google Drive. The chat assistant
reads it before creating queue files. The local worker validates every card
against the live Anki collection before import.

## Defaults

- Default deck: `Japanese::Vocabulary`
- Default note type: `Basic`
- Default tags: `chatgpt`

## Deck and note type mappings

| Use | Deck name (exact) | Note type (exact) | Required fields |
| --- | --- | --- | --- |
| Vocabulary | `Japanese::Vocabulary` | `Basic` | `Front`, `Back` |

Add one row for each permitted card type. Names must exactly match Anki.
Do not invent a deck, note type, or field when it is not listed here.

## Field guidance

- `Front`: Japanese word, expression, or prompt.
- `Back`: concise meaning and useful context.

## Queue layout

This file, `instructions.md`, and the `queue/` folder must all be children of
the Drive folder named `Anki Agent`. That folder itself is a child of the
user-selected Drive parent folder. Each save request is one immutable JSON
file in `queue/`; it can contain multiple cards. The worker adds processing
status to that file after import.

## Cleanup

Completed queue JSON files may be removed only when the user explicitly asks
to clean up completed queue files. Cleanup removes files from Drive only; it
does not delete or alter notes in Anki.
