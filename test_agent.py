from __future__ import annotations

import unittest
import io
import json
from unittest.mock import patch

from anki_agent import docs_gen
from anki_agent.ankiconnect import AnkiConnect, AnkiConnectError
from anki_agent.docs_gen import (
    build_note_type_auto,
    merge_with_manual,
    refresh_collection_guides,
    refresh_deck_docs,
)
from anki_agent.reader import NoteReader, build_search_query
from anki_agent.preview import PreviewService
from anki_agent.mutations import (
    AddNoteRequest,
    ApprovalRejectedError,
    BatchProposal,
    DuplicateReviewRequired,
    MutationError,
    MutationOutcomeUnknown,
    NoteMutationService,
    StaleProposalError,
    UpdateNoteRequest,
)
from anki_agent.duplicates import DuplicateChecker
from anki_agent.history import MutationHistory
from anki_agent.remote import RemoteGateway, RemoteUserContext
from anki_agent.config import AgentConfig


class FakeAnki:
    def __init__(
        self,
        *,
        fields: list[str],
        templates: dict[str, dict[str, str]],
        note_ids: list[int] | None = None,
        notes: dict[int, dict] | None = None,
        css: str = ".card { color: black; }",
        decks: list[str] | None = None,
    ):
        self.fields = fields
        self.templates = templates
        self.note_ids = note_ids or []
        self.notes = notes or {}
        self.css = css
        self.decks = decks or []
        self.notes_info_calls: list[list[int]] = []

    def model_field_names(self, model: str) -> list[str]:
        return self.fields

    def model_templates(self, model: str) -> dict[str, dict[str, str]]:
        return self.templates

    def model_styling(self, model: str) -> str:
        return self.css

    def find_notes(self, query: str) -> list[int]:
        return self.note_ids

    def deck_names(self) -> list[str]:
        return self.decks

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        self.notes_info_calls.append(note_ids)
        return [self.notes[note_id] for note_id in note_ids]


class FakeStorage:
    def __init__(self, files: dict[str, str] | None = None):
        self.files = files or {}

    def read(self, path: str) -> str | None:
        return self.files.get(path)

    def write(self, path: str, text: str) -> None:
        self.files[path] = text

    def append(self, path: str, text: str) -> None:
        self.files[path] = self.files.get(path, "") + text

    def list(self, prefix: str = "") -> list[str]:
        return sorted(path for path in self.files if path.startswith(prefix))


class NoteTypeDocumentationTests(unittest.TestCase):
    def test_documents_field_usage_templates_and_css(self) -> None:
        anki = FakeAnki(
            fields=["Front", "Back", "Hint"],
            templates={
                "Forward": {
                    "Front": "<div>{{text:Front}}</div>",
                    "Back": "{{FrontSide}}<hr>{{Back}}<small>{{Hint}}</small>",
                },
                "Reverse": {"Front": "{{Back}}", "Back": "{{Front}}"},
            },
            note_ids=[11],
            notes={
                11: {
                    "noteId": 11,
                    "tags": ["sample"],
                    "fields": {
                        "Front": {"value": "question"},
                        "Back": {"value": "answer"},
                        "Hint": {"value": "clue"},
                    },
                }
            },
        )

        markdown = build_note_type_auto(anki, "Test model")

        self.assertIn("| 1 | Front | Forward/Front, Reverse/Back |", markdown)
        self.assertIn("| 2 | Back | Forward/Back, Reverse/Front |", markdown)
        self.assertIn("| 3 | Hint | Forward/Back |", markdown)
        self.assertIn("**Forward:** the front template uses fields: Front.", markdown)
        self.assertIn("<div>{{text:Front}}</div>", markdown)
        self.assertIn(".card { color: black; }", markdown)
        self.assertIn("**Front**: `question`", markdown)

    def test_documents_cloze_deletion_variants_and_batches_notes(self) -> None:
        anki = FakeAnki(
            fields=["Text", "Extra"],
            templates={"Cloze": {"Front": "{{cloze:Text}}", "Back": "{{Extra}}"}},
            note_ids=[1, 2, 3],
            notes={
                1: {
                    "noteId": 1,
                    "fields": {"Text": {"value": "{{c1::one}} / {{c2::two}}"}},
                    "cards": [101, 102],
                },
                2: {
                    "noteId": 2,
                    "fields": {"Text": {"value": "{{c1::three}}"}},
                    "cards": [103],
                },
                3: {
                    "noteId": 3,
                    "fields": {"Text": {"value": "No deletions"}},
                    "cards": [],
                },
            },
        )

        with patch.object(docs_gen, "NOTE_INFO_BATCH_SIZE", 2):
            markdown = build_note_type_auto(anki, "Cloze model")

        self.assertIn("- **Cloze fields:** Text", markdown)
        self.assertIn("- **Cloze deletion numbers found:** c1 (2 notes), c2 (1 note)", markdown)
        self.assertIn("- **Generated cards in collection:** 3", markdown)
        self.assertIn("- **Notes with generated cards:** 2", markdown)
        self.assertEqual(anki.notes_info_calls, [[1, 2], [3]])

    def test_preserves_manual_notes_and_migrates_legacy_labels(self) -> None:
        existing = (
            "# Note type: Example\n\n"
            "<!-- AUTO:END -->\n\n"
            "## Note manuali (convenzioni, significato dei campi, eccezioni)\n\n"
            "Use this note type for short prompts.\n"
        )

        merged = merge_with_manual(existing, "# Note type: Example\n\n<!-- AUTO:START -->\n")

        self.assertIn("## Manual notes (conventions, field meanings, exceptions)", merged)
        self.assertIn("Use this note type for short prompts.", merged)
        self.assertNotIn("Note manuali", merged)

    def test_replaces_empty_note_placeholder_with_field_convention_format(self) -> None:
        existing = (
            "<!-- AUTO:END -->\n\n"
            "## Note manuali (convenzioni, significato dei campi, eccezioni)\n\n"
            "_Da compilare._\n"
        )

        merged = merge_with_manual(existing, "# Note type: Example\n\n<!-- AUTO:START -->\n")

        self.assertIn("### Field conventions", merged)
        self.assertIn("### Note-type conventions", merged)
        self.assertNotIn("_Da compilare._", merged)

    def test_refreshes_deck_auto_count_and_preserves_manual_content(self) -> None:
        storage = FakeStorage(
            {
                "decks/Japanese.md": (
                    "# Deck: Japanese\n\n- **Notes (including subdecks):** 99\n\n"
                    "## Conventions, note types used, and preferences\n\n"
                    "Use this deck for daily vocabulary.\n"
                )
            }
        )
        anki = FakeAnki(fields=[], templates={}, note_ids=[1, 2, 3], decks=["Japanese"])

        written = refresh_deck_docs(anki, storage)
        markdown = storage.read("decks/Japanese.md")

        self.assertIn("decks/Japanese.md", written)
        self.assertIn("<!-- AUTO:START (automatically generated, do not edit) -->", markdown)
        self.assertIn("**Notes (including subdecks):** 3", markdown)
        self.assertIn("Use this deck for daily vocabulary.", markdown)
        self.assertNotIn("**Notes (including subdecks):** 99", markdown)

    def test_creates_guides_once_and_preserves_user_edits(self) -> None:
        storage = FakeStorage()

        created = refresh_collection_guides(storage)
        preferences = storage.read("preferences/agent.md")
        storage.write("preferences/agent.md", preferences + "\nUser-confirmed: concise responses.\n")
        created_again = refresh_collection_guides(storage)

        self.assertEqual(set(created), {"conventions/README.md", "preferences/agent.md"})
        self.assertEqual(created_again, [])
        self.assertIn("**Application and documentation language:** English.", preferences)
        self.assertIn("User-confirmed: concise responses.", storage.read("preferences/agent.md"))


class FakeReaderAnki:
    def __init__(self, note_ids: list[int], records: list[dict] | None = None, error=None):
        self.note_ids = note_ids
        self.records = records or []
        self.error = error
        self.query = None
        self.requested_note_ids: list[int] = []

    def find_notes(self, query: str) -> list[int]:
        self.query = query
        if self.error:
            raise self.error
        return self.note_ids

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        self.requested_note_ids = note_ids
        if self.error:
            raise self.error
        return self.records


class NoteReaderTests(unittest.TestCase):
    def test_builds_quoted_search_for_text_deck_note_type_and_tags(self) -> None:
        query = build_search_query(
            text='a "dog"_2:3 & <>',
            deck="Japanese::Words and More",
            note_type="Basic (and reversed card)",
            tags=["jlpt::n2", "daily review"],
        )

        self.assertEqual(
            query,
            '"a \\"dog\\"\\_2\\:3 &amp; &lt;&gt;" '
            'deck:"Japanese::Words and More" '
            'note:"Basic (and reversed card)" '
            'tag:"jlpt::n2" tag:"daily review"',
        )

    def test_search_limits_results_and_normalizes_note_fields(self) -> None:
        anki = FakeReaderAnki(
            [2, 1, 3],
            records=[
                {
                    "noteId": 1,
                    "modelName": "Basic",
                    "fields": {"Front": {"value": "one", "order": 0}},
                    "tags": ["known"],
                    "cards": [101],
                },
                {
                    "noteId": 2,
                    "modelName": "Cloze",
                    "fields": {"Text": {"value": "two", "order": 0}},
                    "tags": [],
                    "cards": [202, 203],
                },
            ],
        )

        results = NoteReader(anki).search(text="word", limit=2)

        self.assertEqual(anki.query, '"word"')
        self.assertEqual(anki.requested_note_ids, [2, 1])
        self.assertEqual([note.note_id for note in results], [2, 1])
        self.assertEqual(results[0].fields, {"Text": "two"})
        self.assertEqual(results[0].card_ids, (202, 203))
        self.assertEqual(results[1].tags, ("known",))

    def test_empty_results_do_not_fetch_note_details(self) -> None:
        anki = FakeReaderAnki([])

        results = NoteReader(anki).search(deck="Japanese")

        self.assertEqual(results, [])
        self.assertEqual(anki.requested_note_ids, [])

    def test_rejects_unbounded_or_invalid_searches_and_propagates_api_errors(self) -> None:
        reader = NoteReader(FakeReaderAnki([]))
        with self.assertRaises(ValueError):
            reader.search()
        with self.assertRaises(ValueError):
            reader.search(text="word", limit=201)

        failing = NoteReader(FakeReaderAnki([], error=AnkiConnectError("offline")))
        with self.assertRaisesRegex(AnkiConnectError, "offline"):
            failing.search(text="word")


class FakePreviewAnki:
    def __init__(self, fields, templates, *, notes=None, css=".card { color: black; }"):
        self.fields = fields
        self.templates = templates
        self.notes = notes or []
        self.css = css

    def model_field_names(self, note_type):
        return self.fields

    def model_templates(self, note_type):
        return self.templates

    def model_styling(self, note_type):
        return self.css

    def notes_info(self, note_ids):
        return [note for note in self.notes if note["noteId"] in note_ids]


class NotePreviewTests(unittest.TestCase):
    def test_renders_fields_frontside_and_css(self) -> None:
        anki = FakePreviewAnki(
            ["Front", "Back"],
            {"Forward": {"Front": "<b>{{Front}}</b>", "Back": "{{FrontSide}}<hr>{{Back}}"}},
        )

        preview = PreviewService(anki).preview_new(
            "Basic", {"Front": "Question", "Back": "Answer"}, deck="Japanese", tags=["daily"]
        )

        self.assertEqual(len(preview.cards), 1)
        self.assertEqual(preview.cards[0].front_html, "<b>Question</b>")
        self.assertEqual(preview.cards[0].back_html, "<b>Question</b><hr>Answer")
        self.assertEqual(preview.css, ".card { color: black; }")

    def test_renders_nested_conditionals_and_text_filter(self) -> None:
        anki = FakePreviewAnki(
            ["Hint", "Back"],
            {
                "Forward": {
                    "Front": "{{#Hint}}<i>{{text:Hint}}{{#Back}}<b>{{Back}}</b>{{/Back}}</i>{{/Hint}}{{^Back}}<b>Missing</b>{{/Back}}",
                    "Back": "{{Back}}",
                }
            },
        )

        preview = PreviewService(anki).preview_new(
            "Basic", {"Hint": "<b>clue</b>", "Back": "answer"}
        )

        self.assertEqual(preview.cards[0].front_html, "<i>clue<b>answer</b></i>")

    def test_renders_each_cloze_variant_with_front_hint_and_answer(self) -> None:
        anki = FakePreviewAnki(
            ["Text"],
            {"Cloze": {"Front": "{{cloze:Text}}", "Back": "{{FrontSide}}<hr>{{cloze:Text}}"}},
        )

        preview = PreviewService(anki).preview_new(
            "Cloze model", {"Text": "Capital {{c1::Paris::city}} of {{c2::France}}"}
        )

        self.assertEqual([card.deletion_index for card in preview.cards], [1, 2])
        self.assertIn("[city]", preview.cards[0].front_html)
        self.assertIn("France", preview.cards[0].front_html)
        self.assertIn(">Paris</span>", preview.cards[0].back_html)
        self.assertIn("[…]", preview.cards[1].front_html)

    def test_edit_preview_shows_before_after_and_changed_fields(self) -> None:
        anki = FakePreviewAnki(
            ["Front", "Back"],
            {"Forward": {"Front": "{{Front}}", "Back": "{{Back}}"}},
            notes=[
                {
                    "noteId": 42,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Old question", "order": 0},
                        "Back": {"value": "Answer", "order": 1},
                    },
                    "tags": ["daily"],
                    "cards": [420],
                }
            ],
        )

        preview = PreviewService(anki).preview_edit(42, {"Front": "New question"})

        self.assertEqual(preview.changed_fields, ("Front",))
        self.assertEqual(preview.before.cards[0].front_html, "Old question")
        self.assertEqual(preview.after.cards[0].front_html, "New question")

    def test_warns_for_script_templates_and_validates_note_fields(self) -> None:
        anki = FakePreviewAnki(
            ["Front"],
            {"Card": {"Front": "{{Front}}<script>run()</script>", "Back": ""}},
        )
        service = PreviewService(anki)

        preview = service.preview_new("Basic", {"Front": "Question"})

        self.assertTrue(any("JavaScript" in warning for warning in preview.warnings))
        with self.assertRaisesRegex(ValueError, "Unknown fields"):
            service.preview_new("Basic", {"Unknown": "value"})


class FakeMutationAnki(FakePreviewAnki):
    def __init__(self, *, notes=None, fail_write=False):
        super().__init__(
            ["Front", "Back"],
            {"Forward": {"Front": "{{Front}}", "Back": "{{Back}}"}},
            notes=notes,
        )
        self.decks = ["Japanese"]
        self.available_models = ["Basic"]
        self.write_calls = []
        self.fail_write = fail_write

    def deck_names(self):
        return self.decks

    def model_names(self):
        return self.available_models

    def find_notes(self, query):
        return [note["noteId"] for note in self.notes]

    def _invoke_approved_write(self, action, **params):
        self.write_calls.append((action, params))
        if self.fail_write:
            raise AnkiConnectError("connection dropped")
        if action == "addNote":
            return 77
        return None


class NoteMutationTests(unittest.TestCase):
    def test_propose_add_does_not_write_and_explicit_approval_applies_it(self) -> None:
        anki = FakeMutationAnki()
        service = NoteMutationService(anki)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}, tags=["daily"]
        )

        self.assertEqual(anki.write_calls, [])
        self.assertEqual(proposal.preview.cards[0].front_html, "Question")
        result = service.confirm(proposal.proposal_id, user_response="approve")

        self.assertEqual(result.note_id, 77)
        action, params = anki.write_calls[0]
        self.assertEqual(action, "addNote")
        self.assertEqual(params["note"]["deckName"], "Japanese")
        self.assertEqual(params["note"]["fields"], {"Front": "Question", "Back": ""})
        self.assertEqual(params["note"]["tags"], ["daily"])

    def test_rejects_ambiguous_response_and_cancel_without_writing(self) -> None:
        anki = FakeMutationAnki()
        service = NoteMutationService(anki)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )

        with self.assertRaises(ApprovalRejectedError):
            service.confirm(proposal.proposal_id, user_response="maybe")
        with self.assertRaises(MutationError):
            service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual(anki.write_calls, [])

        another = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Another"}
        )
        service.cancel(another.proposal_id)
        self.assertEqual(anki.write_calls, [])

    def test_stale_template_or_note_changes_require_a_new_preview(self) -> None:
        anki = FakeMutationAnki()
        service = NoteMutationService(anki)
        add_proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )
        anki.css = ".card { color: blue; }"
        with self.assertRaises(StaleProposalError):
            service.confirm(add_proposal.proposal_id, user_response="approve")

        anki.notes = [
            {
                "noteId": 9,
                "modelName": "Basic",
                "fields": {
                    "Front": {"value": "Before", "order": 0},
                    "Back": {"value": "Answer", "order": 1},
                },
                "tags": [],
                "cards": [90],
            }
        ]
        update_proposal = service.propose_update(9, {"Back": "New answer"})
        anki.notes[0]["fields"]["Front"]["value"] = "Changed elsewhere"
        with self.assertRaises(StaleProposalError):
            service.confirm(update_proposal.proposal_id, user_response="approve")
        self.assertEqual(anki.write_calls, [])

    def test_modified_proposal_preview_is_rejected(self) -> None:
        anki = FakeMutationAnki()
        service = NoteMutationService(anki)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )
        proposal.preview.fields["Front"] = "Different preview"

        with self.assertRaisesRegex(StaleProposalError, "preview was modified"):
            service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual(anki.write_calls, [])

    def test_propose_update_previews_before_after_and_writes_only_after_approval(self) -> None:
        anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 9,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Question", "order": 0},
                        "Back": {"value": "Old answer", "order": 1},
                    },
                    "tags": [],
                    "cards": [90],
                }
            ]
        )
        service = NoteMutationService(anki)
        proposal = service.propose_update(9, {"Back": "New answer"})

        self.assertEqual(proposal.preview.changed_fields, ("Back",))
        self.assertEqual(anki.write_calls, [])
        result = service.confirm(proposal.proposal_id, user_response="approve")

        self.assertEqual(result.note_id, 9)
        self.assertEqual(
            anki.write_calls[0],
            ("updateNoteFields", {"note": {"id": 9, "fields": {"Back": "New answer"}}}),
        )

    def test_uncertain_write_cannot_be_retried_automatically(self) -> None:
        anki = FakeMutationAnki(fail_write=True)
        service = NoteMutationService(anki)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )

        with self.assertRaises(MutationOutcomeUnknown):
            service.confirm(proposal.proposal_id, user_response="approve")
        with self.assertRaises(MutationError):
            service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual(len(anki.write_calls), 1)

    def test_low_level_invoke_blocks_note_writes(self) -> None:
        with self.assertRaisesRegex(AnkiConnectError, "explicit approval flow"):
            AnkiConnect().invoke("addNote", note={})

    def test_add_requires_duplicate_review_and_explicit_keep_both_choice(self) -> None:
        anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 5,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Question", "order": 0},
                        "Back": {"value": "Answer", "order": 1},
                    },
                    "tags": [],
                    "cards": [50],
                }
            ]
        )
        service = NoteMutationService(anki)

        with self.assertRaises(DuplicateReviewRequired) as raised:
            service.propose_add(
                deck="Japanese", note_type="Basic", fields={"Front": "Question", "Back": "Answer"}
            )
        self.assertEqual(raised.exception.matches[0].match_type, "exact")
        self.assertEqual(anki.write_calls, [])

        proposal = service.propose_add(
            deck="Japanese",
            note_type="Basic",
            fields={"Front": "Question", "Back": "Answer"},
            allow_possible_duplicates=True,
        )
        service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual(anki.write_calls[0][0], "addNote")

    def test_batch_proposals_are_combined_and_approved_individually(self) -> None:
        anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 9,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Existing question", "order": 0},
                        "Back": {"value": "Existing answer", "order": 1},
                    },
                    "tags": [],
                    "cards": [90],
                }
            ]
        )
        service = NoteMutationService(anki)
        batch = service.propose_batch(
            [
                AddNoteRequest("Japanese", "Basic", {"Front": "Different question", "Back": "Answer"}),
                UpdateNoteRequest(9, {"Back": "Updated answer"}),
            ]
        )

        self.assertIsInstance(batch, BatchProposal)
        self.assertEqual(len(batch.proposals), 2)
        results = service.confirm_batch(
            batch.batch_id,
            {batch.proposals[0].proposal_id: "approve", batch.proposals[1].proposal_id: "reject"},
        )

        self.assertEqual([item.status for item in results.operations], ["applied", "rejected"])
        self.assertEqual(len(anki.write_calls), 1)
        self.assertEqual(anki.write_calls[0][0], "addNote")


class DuplicateCheckerTests(unittest.TestCase):
    def test_finds_exact_and_similar_candidates(self) -> None:
        anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 1,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "A yellow fox jumps", "order": 0},
                        "Back": {"value": "quickly", "order": 1},
                    },
                    "tags": [],
                    "cards": [10],
                },
                {
                    "noteId": 2,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "A yellow fox jumped", "order": 0},
                        "Back": {"value": "quickly", "order": 1},
                    },
                    "tags": [],
                    "cards": [20],
                },
            ]
        )

        matches = DuplicateChecker(anki).find(
            "Basic", {"Front": "A yellow fox jumps", "Back": "quickly"}
        )

        self.assertEqual([match.match_type for match in matches], ["exact", "similar"])
        self.assertGreater(matches[1].score, 0.82)

    def test_semantic_matcher_can_flag_candidate_for_user_review(self) -> None:
        anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 3,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Unrelated wording", "order": 0},
                        "Back": {"value": "Different explanation", "order": 1},
                    },
                    "tags": [],
                    "cards": [30],
                }
            ]
        )

        matches = DuplicateChecker(
            anki,
            semantic_matcher=lambda proposed, existing: 0.91,
        ).find("Basic", {"Front": "Another phrase", "Back": "Other wording"})

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].match_type, "semantic")
        self.assertEqual(matches[0].score, 0.91)


class CollectionOperationTests(unittest.TestCase):
    def setUp(self):
        self.anki = FakeMutationAnki(
            notes=[
                {
                    "noteId": 12,
                    "modelName": "Basic",
                    "fields": {
                        "Front": {"value": "Question", "order": 0},
                        "Back": {"value": "Answer", "order": 1},
                    },
                    "tags": ["old"],
                    "cards": [120, 121],
                }
            ]
        )
        self.anki.decks.append("Archive")
        self.service = NoteMutationService(self.anki)

    def test_tag_and_deck_changes_require_approval_and_have_precise_payloads(self):
        add = self.service.propose_add_tags(12, ["new"])
        move = self.service.propose_move_to_deck(12, "Archive")
        remove = self.service.propose_remove_tags(12, ["old"])
        self.assertEqual(self.anki.write_calls, [])

        for proposal in (add, move, remove):
            self.service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual([call[0] for call in self.anki.write_calls], ["addTags", "changeDeck", "removeTags"])
        self.assertEqual(self.anki.write_calls[0][1], {"notes": [12], "tags": "new"})
        self.assertEqual(self.anki.write_calls[1][1], {"cards": [120, 121], "deck": "Archive"})
        self.assertEqual(self.anki.write_calls[2][1], {"notes": [12], "tags": "old"})

    def test_delete_requires_preview_approval_and_second_exact_confirmation(self):
        proposal = self.service.propose_delete(12)
        self.assertEqual(proposal.preview.note.note_id, 12)
        with self.assertRaisesRegex(ApprovalRejectedError, "second confirmation"):
            self.service.confirm(proposal.proposal_id, user_response="approve")
        self.assertEqual(self.anki.write_calls, [])
        self.service.confirm(
            proposal.proposal_id, user_response="approve", delete_confirmation="DELETE 12"
        )
        self.assertEqual(self.anki.write_calls, [("deleteNotes", {"notes": [12]})])

    def test_collection_change_is_stale_if_note_disappears(self):
        proposal = self.service.propose_delete(12)
        self.anki.notes.clear()
        with self.assertRaises(StaleProposalError):
            self.service.confirm(
                proposal.proposal_id, user_response="approve", delete_confirmation="DELETE 12"
            )
        self.assertEqual(self.anki.write_calls, [])


class MutationHistoryTests(unittest.TestCase):
    def test_records_request_preview_approval_and_result_for_inspection(self):
        storage = FakeStorage()
        history = MutationHistory(storage)
        anki = FakeMutationAnki()
        service = NoteMutationService(anki, history=history)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )

        self.assertIn('"event": "proposed"', history.read())
        self.assertIn('"preview"', history.read())
        self.assertEqual(history.recovery_status()["incomplete"], [proposal.proposal_id])
        service.confirm(proposal.proposal_id, user_response="approve")
        document = history.read()
        self.assertIn("write_started", document)
        self.assertIn('"event": "applied"', document)
        self.assertIn('"note_id": 77', document)
        self.assertEqual(history.recovery_status(), {"incomplete": [], "outcome_unknown": []})

    def test_records_uncertain_interrupted_write_without_retry(self):
        storage = FakeStorage()
        history = MutationHistory(storage)
        anki = FakeMutationAnki(fail_write=True)
        service = NoteMutationService(anki, history=history)
        proposal = service.propose_add(
            deck="Japanese", note_type="Basic", fields={"Front": "Question"}
        )

        with self.assertRaises(MutationOutcomeUnknown):
            service.confirm(proposal.proposal_id, user_response="approve")
        self.assertIn('"event": "outcome_unknown"', history.read())
        self.assertEqual(history.recovery_status()["outcome_unknown"], [proposal.proposal_id])
        with self.assertRaises(MutationError):
            service.confirm(proposal.proposal_id, user_response="approve")


class RemoteGatewayTests(unittest.TestCase):
    def test_requires_bearer_authentication_and_isolates_collection_contexts(self):
        gateway = RemoteGateway()
        first_anki = FakeMutationAnki()
        second_anki = FakeMutationAnki()
        second_anki.decks = ["Private"]
        gateway.register("a" * 40, RemoteUserContext("first", NoteReader(first_anki), NoteMutationService(first_anki)))
        gateway.register("b" * 40, RemoteUserContext("second", NoteReader(second_anki), NoteMutationService(second_anki)))

        self.assertEqual(gateway.dispatch(None, "GET", "/v1/collection")[0], 401)
        first = gateway.dispatch("Bearer " + "a" * 40, "GET", "/v1/collection")
        second = gateway.dispatch("Bearer " + "b" * 40, "GET", "/v1/collection")
        self.assertEqual(first[1]["decks"], ["Japanese"])
        self.assertEqual(second[1]["decks"], ["Private"])

    def test_remote_proposal_requires_a_separate_approval_call(self):
        gateway = RemoteGateway()
        anki = FakeMutationAnki()
        gateway.register("c" * 40, RemoteUserContext("user", NoteReader(anki), NoteMutationService(anki)))
        token = "Bearer " + "c" * 40
        status, proposal = gateway.dispatch(token, "POST", "/v1/proposals/add", {
            "deck": "Japanese", "note_type": "Basic", "fields": {"Front": "Remote question"}
        })
        self.assertEqual(status, 201)
        self.assertEqual(anki.write_calls, [])

        confirmed = gateway.dispatch(token, "POST", f"/v1/proposals/{proposal['proposal_id']}/confirm", {
            "user_response": "approve"
        })
        self.assertEqual(confirmed[0], 200)
        self.assertEqual(anki.write_calls[0][0], "addNote")

    def test_wsgi_transport_rejects_plain_http_and_serves_json_over_https(self):
        gateway = RemoteGateway()
        anki = FakeMutationAnki()
        gateway.register("d" * 40, RemoteUserContext("user", NoteReader(anki), NoteMutationService(anki)))
        responses = []

        def call_app(scheme):
            environ = {
                "REQUEST_METHOD": "GET", "PATH_INFO": "/v1/collection",
                "wsgi.url_scheme": scheme, "wsgi.input": io.BytesIO(),
                "HTTP_AUTHORIZATION": "Bearer " + "d" * 40,
            }
            body = b"".join(gateway(environ, lambda status, headers: responses.append((status, headers))))
            return responses[-1][0], json.loads(body)

        self.assertEqual(call_app("http")[0], "400 Bad Request")
        status, payload = call_app("https")
        self.assertEqual(status, "200 OK")
        self.assertEqual(payload["decks"], ["Japanese"])


class ConfigurationTests(unittest.TestCase):
    def test_reads_connection_settings_and_separates_user_storage(self):
        first = AgentConfig.from_env({
            "ANKI_CONNECT_URL": "http://127.0.0.1:8766",
            "ANKI_CONNECT_API_KEY": "secret-value",
            "ANKI_CONNECT_TIMEOUT": "22",
            "ANKI_AGENT_DATA_DIR": "C:/anki-data",
            "ANKI_AGENT_USER_ID": "alice",
        })
        second = AgentConfig.from_env({
            "ANKI_AGENT_DATA_DIR": "C:/anki-data",
            "ANKI_AGENT_USER_ID": "bob",
        })

        self.assertEqual(first.create_anki().url, "http://127.0.0.1:8766")
        self.assertEqual(first.create_anki().api_key, "secret-value")
        self.assertEqual(first.create_anki().timeout, 22)
        self.assertNotEqual(first.storage_root, second.storage_root)
        self.assertEqual(second.anki_url, "http://127.0.0.1:8765")

    def test_rejects_invalid_configuration_and_unsafe_user_path(self):
        for settings in (
            {"ANKI_CONNECT_URL": "ftp://localhost"},
            {"ANKI_CONNECT_TIMEOUT": "zero"},
            {"ANKI_CONNECT_TIMEOUT": "0"},
            {"ANKI_AGENT_USER_ID": "../private"},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                AgentConfig.from_env(settings)


if __name__ == "__main__":
    unittest.main()
