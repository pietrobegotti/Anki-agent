# Roadmap — Anki Agent

Testing starts in the early iterations: use local automated tests for application logic and, when Anki is needed, integration tests with Anki Desktop and a test collection. Iteration 10 adds tests for the remote connection from ChatGPT.

## 01 - Connection and inventory *(completed)*

**Goal:** connect to Anki in read-only mode and generate initial collection documentation.

- Connect through AnkiConnect.
- Read the version, decks, and note types.
- Generate Markdown files for decks and note types.
- Verify the script with Anki Desktop running.

## 02 - Note type structure *(completed)*

**Goal:** document how notes are structured and which cards they generate.

- Read fields, templates, and CSS through AnkiConnect.
- Document field roles and front/back templates.
- Identify generated cards, including Cloze variants.
- Update documentation while preserving manual notes.
- Add automated tests with simulated Anki responses.

## 03 - Collection conventions and knowledge *(completed)*

**Goal:** add the rules needed to choose and fill notes alongside the technical data.

- Define a format for deck and field conventions.
- Record preferences and information confirmed by the user.
- Separate automatically detected data from manual content.
- Verify that regeneration preserves manual sections.

## 04 - Search and read notes

**Goal:** find existing notes and show their contents without changing them.

- Add search by text, deck, note type, and tag.
- Read all fields of selected notes.
- Return clear results limited to the request.
- Test queries, empty results, and connection errors.

## 05 - Operation previews

**Goal:** show the effect of creating or editing a note before applying it.

- Render notes and generated cards with the available templates.
- For edits, compare the current and proposed states.
- Highlight affected cards and fields.
- Verify previews with simple and complex note types.

## 06 - Approved creation and editing

**Goal:** apply note operations only after explicit approval.

- Implement note creation and editing through AnkiConnect.
- Request approval after showing the preview.
- Recheck the data immediately before writing.
- Test cancellation, errors, and operation results.

## 07 - Duplicates and multiple requests

**Goal:** handle ambiguity and requests that result in multiple changes.

- Find exact matches and possible duplicates.
- Ask how to proceed when a result is ambiguous.
- Present one combined preview for multiple operations.
- Allow each operation to be approved or rejected individually.

## 08 - Decks, tags, and deletions

**Goal:** extend operations to the collection structure.

- Add tag management and moving notes between decks.
- Define supported deck operations.
- Show the exact item before each deletion.
- Require an additional confirmation for deletions.

## 09 - History and recovery

**Goal:** track operations and make failures recoverable where possible.

- Record the request, preview, approval, operation, and result.
- Make the history accessible to the user.
- Assess which operations can be undone or restored.
- Test incomplete records and interruptions during operations.

## 10 - Remote connection and ChatGPT

**Goal:** use the agent from ChatGPT without requiring local access to the PC.

- Choose the remote bridge and connector architecture.
- Define authentication, data isolation, and credential handling.
- Connect the agent's features to the remote interface.
- Test the full flow from ChatGPT to Anki and back.

## 11 - Distribution and polish

**Goal:** prepare the project for different configurations and collections.

- Make the connection and documentation storage configurable.
- Isolate each user's data and settings.
- Complete installation, usage, and troubleshooting instructions.
- Run an end-to-end check on a clean installation.
