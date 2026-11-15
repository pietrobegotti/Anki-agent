from __future__ import annotations

import unittest
from unittest.mock import patch

from anki_agent import docs_gen
from anki_agent.docs_gen import build_note_type_auto, merge_with_manual


class FakeAnki:
    def __init__(
        self,
        *,
        fields: list[str],
        templates: dict[str, dict[str, str]],
        note_ids: list[int] | None = None,
        notes: dict[int, dict] | None = None,
        css: str = ".card { color: black; }",
    ):
        self.fields = fields
        self.templates = templates
        self.note_ids = note_ids or []
        self.notes = notes or {}
        self.css = css
        self.notes_info_calls: list[list[int]] = []

    def model_field_names(self, model: str) -> list[str]:
        return self.fields

    def model_templates(self, model: str) -> dict[str, dict[str, str]]:
        return self.templates

    def model_styling(self, model: str) -> str:
        return self.css

    def find_notes(self, query: str) -> list[int]:
        return self.note_ids

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        self.notes_info_calls.append(note_ids)
        return [self.notes[note_id] for note_id in note_ids]


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


if __name__ == "__main__":
    unittest.main()
