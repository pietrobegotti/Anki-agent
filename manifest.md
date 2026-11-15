# Anki Agent — Requirements Document

**Version:** 0.6
**Status:** requirements gathering and definition
**Last updated:** 14 November 2026

---

## 1. Project vision

Build an AI agent that can manage the user's Anki collection directly through ChatGPT.

The intended experience is a conversation with an assistant that can access the user's Anki collection without requiring manual synchronization, device management, or technical setup.

Example:

> “Add a note for this word, including its reading, meaning, and examples.”

The agent analyzes the request, prepares a proposal, shows a preview, and performs the operation in Anki only after the user approves it.

The system should be:
- usable in ChatGPT on desktop and mobile;
- independent of the device being used;
- customizable for each user;
- reusable and potentially available to the public;
- modular, so study and learning features can be added later.

## 2. Scope of the first version

The first version focuses exclusively on **managing the Anki collection**.

Included:
- creating, editing, and deleting notes;
- managing note fields;
- understanding different note types and their templates;
- managing decks;
- managing tags;
- finding duplicates;
- editing formatting;
- previewing operations;
- maintaining internal collection documentation.

Deferred to a later phase:
- managing images, audio, and video;
- tutoring features;
- study planning;
- performance and progress analysis;
- generating learning paths.

The architecture should still allow these features to be added without rewriting the system's core.

## 3. Reasoning model: notes and cards

The agent should reason primarily in terms of **notes**.

A note contains information organized into fields. Its note type determines which fields are available and how templates use them to generate one or more cards.

The agent should understand:
- the difference between notes and cards;
- the field structure of each note type;
- the meaning and purpose of each field;
- the relationship between fields and templates;
- how many cards a note generates;
- which cards are affected when a field changes.

For example, a Basic and reversed note may generate two cards. Editing the note could therefore affect both cards.

The agent must consider every consequence of editing a note, not only the card currently shown to the user.

## 4. Understanding note types

The agent must be able to analyze and use different note types:

- Basic
- Basic (and reversed)
- Cloze
- Custom note types

It should be able to inspect:
- field names and structure;
- template HTML;
- CSS;
- card generation conditions;
- relationships between fields and templates.

It must also understand Cloze notes with multiple deletions, such as `{{c1::...}}` and `{{c2::...}}`, which can generate different cards.

Changing templates should not be routine. The agent must preserve their original behavior and may propose changes only in exceptional cases, explaining the problem and discussing alternatives with the user.

## 5. Markdown documentation system

The agent must have persistent Markdown documentation describing the collection and its conventions.

This documentation serves as the agent's **operational knowledge base**.

It should be consulted before relevant operations and updated when the agent learns new information.

### 5.1 Note type documentation

There must be one Markdown document for each **note type**, not for each individual note in the collection.

For each note type in use, document:
- its name and purpose;
- its available fields;
- the meaning of each field;
- required formats and conventions;
- the role of each field in the templates;
- the cards it generates;
- the consequences of changing each field;
- any special cases or exceptions.

### 5.2 Deck documentation

For each deck, document:
- its name and structure;
- the note types it uses;
- deck-specific conventions;
- any entry rules;
- user preferences;
- relationships with other decks.

### 5.3 Agent preferences and behavior

In addition to the collection's technical documentation, there should be documents describing the agent's behavior and the user's preferences.

For example, these documents may define:
- preferred level of concision;
- how much detail to show;
- the language for explanations and content;
- response and preview formats;
- text generation style;
- conventions to follow;
- level of autonomy;
- when to ask clarifying questions.

For example, the user may prefer concise responses that show only essential information, without unrequested explanations.

Preferences may evolve over time based on the user's corrections and instructions.

### 5.4 History

The agent must maintain a history of operations and significant changes to the collection structure.

### 5.5 Documentation autonomy

Markdown files are primarily internal tools for the agent.

The agent may create and update them autonomously, without asking for approval for every change. It should ask for clarification when it does not understand a structure or convention.

The documentation should be stored in cloud storage that is always accessible to the agent. The preferred option is the user's personal Google Drive.

## 6. Deck management

The user will usually specify the destination deck.

If they do not, the agent should:
1. consult the documentation;
2. identify the most appropriate deck;
3. propose that choice;
4. wait for confirmation before proceeding.

The agent should be able to:
- create decks;
- rename decks;
- move notes between decks;
- merge decks;
- delete decks.

Creating a new deck requires confirmation.

When merging decks, account for the fact that Anki may not provide a native merge operation. It may be necessary to move cards and then delete the source deck.

The agent must document changes to the deck structure.

## 7. Duplicate management

Before creating a note, the agent must check for possible duplicates.

The check should consider:
- exact content matches;
- similar field values;
- semantic equivalence.

If it finds a duplicate or a possible duplicate, it must ask the user how to proceed.

Options may include:
- updating the existing note;
- keeping both notes;
- cancelling the creation.

The agent must not make ambiguous decisions on its own.

## 8. Formatting and media

The first version may edit note formatting.

When editing text only, the agent should preserve existing formatting as much as possible.

Support for images, audio, and video is desired but deferred to a later phase.

Template changes should be exceptional and discussed with the user for approval.

## 9. Operation previews and approval

**No change to the collection may be made without the user's explicit approval.**

This applies to every operation that changes the collection, not only note creation.

### 9.1 Note preview

For a new note, the agent must show:
- the value of every field;
- every card that will be generated;
- the front and back of each card.

### 9.2 Editing a note

When editing a note, the preview must show:
- every affected card;
- the front and back before the edit;
- the front and back after the edit;
- the changes made.

If a note generates multiple cards, show every affected card.

### 9.3 Multiple edits

If a request involves multiple operations, the agent must present one combined preview.

The user must be able to approve or reject individual operations without having to accept them all.

### 9.4 Editing the preview

The user must be able to edit proposed content before approving it.

The preview should look similar to Anki cards. It does not need to reproduce the original rendering perfectly, but it must be faithful enough for the user to check the result.

### 9.5 Deletions

For a deletion, show the exact item that will be deleted.

Deletions require an additional confirmation beyond the usual operation approval.

## 10. Safety, history, and recovery

The system must keep a persistent operation log.

The log must be:
- available to the agent;
- accessible to the user;
- detailed enough to reconstruct the operations performed.

The agent should normally report operation results. The user may disable these notifications.

The system should support undo or recovery where technically possible.

It is not a mandatory requirement that deleted notes can always be recovered from a trash folder or backup.

## 11. Synchronization

The user wants the agent to be able to request an Anki sync when needed.

Synchronization must use mechanisms supported by Anki and avoid unnecessarily complex manual steps.

The agent must tell the user when synchronization is needed or when an operation is not yet available on other devices.

## 12. Remote infrastructure and access

The goal is to use the agent from any device and network, including a smartphone, without manually managing the PC.

The user has:
- Anki Desktop;
- AnkiConnect;
- AnkiDroid;
- AnkiWeb synchronization.

AnkiConnect provides a local interface to the collection. Secure infrastructure will be needed to make it accessible to the agent remotely.

The architecture must clearly separate:
- the AI agent;
- operational rules and instructions;
- the connector or MCP interface;
- any remote bridge;
- AnkiConnect;
- AnkiWeb synchronization;
- Markdown documentation.

The solution must provide authentication, data isolation, and protection for collection access.

## 13. Agent behavior

The agent must:
- interpret natural language requests;
- reason about notes and their fields;
- consult documentation before operations;
- ask for clarification when a request is ambiguous;
- support requests involving multiple operations;
- prepare previews;
- wait for approval;
- report results;
- update its documentation.

The agent must not assume the meaning of a field or convention it does not know.

## 14. Configuration and distribution

The project must be designed for use by other people.

Each user must be able to connect their own Anki collection and documentation storage.

Configuration, credentials, documentation, preferences, and history must be fully separated between users.

The goal is a reusable solution that could be made publicly available without users sharing data or configuration.

## 15. Future modular architecture

The system must have a core that is independent of specific features.

Future modules may include:
- study assistance;
- progress analysis;
- suggestions about what to study;
- exercise generation;
- language tutoring;
- note quality analysis.

These modules must be able to reuse collection knowledge without compromising Anki management.

## 16. Open questions

The following decisions remain open and must be addressed during design:

1. How to organize Markdown files in Google Drive and authorize the agent to access them.
2. How to detect changes made in AnkiDroid or other devices while the agent prepares an operation.
3. How to handle conflicting concurrent edits.
4. How to implement reliable visual card previews.
5. How to implement undo and recovery.
6. Which remote infrastructure to use to connect ChatGPT to AnkiConnect.
7. How to handle authentication and data isolation for multiple users.
8. How to implement reliable AnkiWeb synchronization.
9. How to distinguish and document deck-specific conventions from general note type conventions.
10. Which operations should be supported in the first release and which can be added later.
