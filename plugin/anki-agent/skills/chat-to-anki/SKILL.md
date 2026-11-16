---
name: chat-to-anki
description: Use when the user wants to collect, prepare, review, or upload Anki cards discussed in the current conversation.
---

# Turn this conversation into Anki cards

## Keep drafts separate from Anki

- Treat discussion as source material, not permission to write to the collection.
- Add a draft only when the user asks to make, collect, or save a concept as an Anki card, or directly asks to upload cards already discussed.
- Keep the draft cards in the current conversation. Do not claim they are stored in Anki or in a durable remote draft list.
- When the user asks to upload cards discussed earlier, inspect the current conversation and collect only the card drafts the user requested or accepted. Do not turn every fact mentioned in the chat into a card.
- If it is unclear which discussed items should become cards, show the candidates and ask which to include.
- Support requests to show, edit, or remove drafts before upload. Keep user corrections in the draft.

## Resolve the collection format

1. Call `get_collection` to learn available decks and note types.
2. Reuse a deck and note type explicitly chosen by the user earlier in the conversation when they still exist.
3. If the user has not selected them, use a clearly established choice from the conversation. Otherwise ask for the destination deck and note type before preparing the upload.
4. Never invent field names or silently map content into unknown note types. If required field structure is not available from tools or prior confirmed context, ask the user for the missing mapping.
5. Preserve the user's language and corrections. Make concise, atomic cards; do not add facts that were not discussed or reliably implied.

## Prepare and review a batch

1. Before upload, summarize the selected drafts and their intended deck and note type.
2. Call `propose_add_batch` with one object per note. Each object must contain `deck`, `note_type`, `fields`, and optional `tags`. Send only fields whose names and values have been confirmed from the collection or user context.
3. The tool prepares previews and checks for exact and similar duplicates. It does not write to Anki.
4. If the response is a duplicate conflict, use its `request_index` to identify the affected draft. Show the returned match and preview to the user. Do not retry that card with `allow_possible_duplicates: true` unless the user explicitly chooses to keep both. For the other cards, prepare a revised batch that leaves the unresolved draft out, if the user wants to proceed.
5. Show the user the preview for each proposal, including all generated cards and their front and back. Ask for any corrections before confirmation.
6. Map the user's explicit decision for each shown proposal ID to `approve` or `reject` and call `confirm_add_batch` once. Do not infer approval from the request to prepare a preview. Treat omitted decisions as rejection.
7. Report the per-card outcome returned by the tool. If an outcome is failed or uncertain, do not automatically retry it; explain which note needs inspection first.

## Safety rules

- Only `confirm_add_batch` can write new notes. Do not call it until the user has seen the current previews and explicitly approved the applicable cards.
- If the user changes a card after the preview, prepare a fresh proposal and show its updated preview before asking for approval.
- If the user cancels, call `cancel_add_batch` for a pending batch and confirm that no write was requested.
- Never claim a card was added unless the tool result says it was applied.
- Do not include unrelated notes, edits, tags, or deck changes in this card-upload workflow.
