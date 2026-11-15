from __future__ import annotations

import unittest
from unittest.mock import patch

from anki_agent import docs_gen
from anki_agent.ankiconnect import AnkiConnectError
from anki_agent.docs_gen import (
    build_note_type_auto,
    merge_with_manual,
    refresh_collection_guides,
    refresh_deck_docs,
)
from anki_agent.reader import NoteReader, build_search_query


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


if __name__ == "__main__":
    unittest.main()
