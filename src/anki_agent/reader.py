"""Read-only note search and retrieval helpers."""
from __future__ import annotations

from dataclasses import dataclass

from .ankiconnect import AnkiConnect

DEFAULT_NOTE_RESULTS = 50
MAX_NOTE_RESULTS = 200


@dataclass(frozen=True)
class NoteRecord:
    """A normalized read-only view of an Anki note."""

    note_id: int
    note_type: str
    fields: dict[str, str]
    tags: tuple[str, ...]
    card_ids: tuple[int, ...]


def _escape_search_value(value: str, *, preserve_colons: bool = False) -> str:
    """Quote a value using Anki's search escaping rules."""
    escaped = value.replace("\\", "\\\\")
    characters = ('"', "*", "_") if preserve_colons else ('"', "*", "_", ":")
    for character in characters:
        escaped = escaped.replace(character, "\\" + character)
    escaped = escaped.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f'"{escaped}"'


def build_search_query(
    *,
    text: str | None = None,
    deck: str | None = None,
    note_type: str | None = None,
    tags: tuple[str, ...] | list[str] = (),
) -> str:
    """Build a safely quoted Anki search query from user-provided filters."""
    terms: list[str] = []
    if text is not None:
        normalized = text.strip()
        if normalized:
            terms.append(_escape_search_value(normalized))
    for key, value in (("deck", deck), ("note", note_type)):
        if value is not None:
            normalized = value.strip()
            if normalized:
                terms.append(
                    f"{key}:{_escape_search_value(normalized, preserve_colons=key == 'deck')}"
                )
    for tag in tags:
        normalized = tag.strip()
        if normalized:
            terms.append(f"tag:{_escape_search_value(normalized, preserve_colons=True)}")
    if not terms:
        raise ValueError("Provide at least one text, deck, note type, or tag filter")
    return " ".join(terms)


class NoteReader:
    """Search and read notes without modifying the collection."""

    def __init__(self, anki: AnkiConnect):
        self.anki = anki

    def search(
        self,
        *,
        text: str | None = None,
        deck: str | None = None,
        note_type: str | None = None,
        tags: tuple[str, ...] | list[str] = (),
        limit: int = DEFAULT_NOTE_RESULTS,
    ) -> list[NoteRecord]:
        if not 1 <= limit <= MAX_NOTE_RESULTS:
            raise ValueError(f"limit must be between 1 and {MAX_NOTE_RESULTS}")
        query = build_search_query(text=text, deck=deck, note_type=note_type, tags=tags)
        note_ids = self.anki.find_notes(query)[:limit]
        return self.read(note_ids)

    def read(self, note_ids: list[int] | tuple[int, ...]) -> list[NoteRecord]:
        """Return requested notes in the same order, omitting IDs no longer found."""
        unique_ids = list(dict.fromkeys(note_ids))[:MAX_NOTE_RESULTS]
        if not unique_ids:
            return []
        records = self.anki.notes_info(unique_ids)
        by_id = {int(item["noteId"]): self._normalize(item) for item in records}
        return [by_id[note_id] for note_id in unique_ids if note_id in by_id]

    @staticmethod
    def _normalize(item: dict) -> NoteRecord:
        fields = {
            name: value.get("value", "")
            for name, value in item.get("fields", {}).items()
        }
        return NoteRecord(
            note_id=int(item["noteId"]),
            note_type=item.get("modelName", ""),
            fields=fields,
            tags=tuple(item.get("tags", [])),
            card_ids=tuple(int(card_id) for card_id in item.get("cards", [])),
        )
