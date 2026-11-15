"""Read-only previews of Anki notes and the cards generated from them."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Mapping

from .ankiconnect import AnkiConnect
from .reader import NoteReader

CLOZE_FIELD_PATTERN = re.compile(r"\{\{\s*cloze\s*:\s*([^{}]+?)\s*\}\}", re.IGNORECASE)
CLOZE_VALUE_PATTERN = re.compile(r"\{\{c(\d+)::(.*?)(?:::(.*?))?\}\}", re.DOTALL)
CONDITIONAL_PATTERN = re.compile(
    r"\{\{\s*([#^])\s*([^{}]+?)\s*\}\}|\{\{\s*/\s*([^{}]+?)\s*\}\}"
)
FIELD_PATTERN = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


@dataclass(frozen=True)
class CardPreview:
    card_name: str
    front_html: str
    back_html: str
    deletion_index: int | None = None


@dataclass(frozen=True)
class NotePreview:
    note_type: str
    fields: dict[str, str]
    css: str
    cards: tuple[CardPreview, ...]
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class NoteChangePreview:
    note_id: int
    before: NotePreview
    after: NotePreview
    changed_fields: tuple[str, ...]


def _cloze_fields(templates: dict[str, dict[str, str]]) -> list[str]:
    return sorted(
        {
            match.strip()
            for sides in templates.values()
            for template in sides.values()
            for match in CLOZE_FIELD_PATTERN.findall(template)
        }
    )


def _cloze_indices(fields: Mapping[str, str], cloze_fields: list[str]) -> list[int]:
    return sorted(
        {
            int(index)
            for field in cloze_fields
            for index in re.findall(r"\{\{c(\d+)::", fields.get(field, ""))
        }
    )


def _render_conditionals(template: str, fields: Mapping[str, str]) -> str:
    def parse(position: int, closing_field: str | None = None) -> tuple[str, int, bool]:
        output: list[str] = []
        while match := CONDITIONAL_PATTERN.search(template, position):
            output.append(template[position : match.start()])
            marker, field, closing = match.groups()
            if closing is not None:
                if closing_field == closing.strip():
                    return "".join(output), match.end(), True
                output.append(match.group(0))
                position = match.end()
                continue

            field = field.strip()
            body, end, closed = parse(match.end(), field)
            if not closed:
                output.append(match.group(0) + body)
                return "".join(output), end, False
            has_value = bool(fields.get(field, "").strip())
            if has_value == (marker == "#"):
                output.append(body)
            position = end

        output.append(template[position:])
        return "".join(output), len(template), False

    rendered, _, _ = parse(0)
    return rendered


def _render_furigana(value: str) -> str:
    return re.sub(
        r"([^\[\]]+)\[([^\[\]]+)\]",
        r"<ruby>\1<rt>\2</rt></ruby>",
        value,
    )


def _render_clozes(value: str, deletion_index: int | None, side: str) -> str:
    def replace(match: re.Match[str]) -> str:
        index, answer, hint = match.groups()
        if side == "Front" and deletion_index == int(index):
            answer = f"[{hint or '…'}]"
        return f'<span class="cloze">{answer}</span>'

    return CLOZE_VALUE_PATTERN.sub(replace, value)


def _render_template(
    template: str,
    fields: Mapping[str, str],
    *,
    context: Mapping[str, str],
    front_side: str,
    deletion_index: int | None,
    side: str,
    warnings: set[str],
) -> str:
    template = _render_conditionals(template, {**fields, **context})

    def replace(match: re.Match[str]) -> str:
        expression = match.group(1).strip()
        if expression == "FrontSide":
            return front_side
        parts = [part.strip() for part in expression.split(":")]
        field = parts[-1]
        filters = parts[:-1]
        if field in context:
            value = context[field]
        elif field in fields:
            value = fields[field]
        else:
            warnings.add(f"Template references an unavailable field or special value: {field}.")
            return ""

        for filter_name in filters:
            normalized = filter_name.lower()
            if normalized == "text":
                value = html.unescape(re.sub(r"<[^>]*>", "", value))
            elif normalized == "furigana":
                value = _render_furigana(value)
            elif normalized == "cloze":
                value = _render_clozes(value, deletion_index, side)
            elif normalized == "hint":
                if side == "Front":
                    value = '<span class="hint">[show hint]</span>'
            elif normalized == "type":
                if side == "Front":
                    value = '<span class="type-answer">[type answer]</span>'
            elif normalized.startswith("tts "):
                warnings.add("Text-to-speech playback is represented by a placeholder in previews.")
                value = '<span class="tts-placeholder">[audio]</span>'
            else:
                warnings.add(f"Template filter is not rendered: {filter_name}.")
        return value

    return FIELD_PATTERN.sub(replace, template)


class PreviewService:
    """Build card previews without writing to Anki."""

    def __init__(self, anki: AnkiConnect):
        self.anki = anki

    def preview_new(
        self,
        note_type: str,
        fields: Mapping[str, str],
        *,
        deck: str = "",
        tags: tuple[str, ...] | list[str] = (),
    ) -> NotePreview:
        return self._build_preview(note_type, fields, deck=deck, tags=tags)

    def preview_edit(self, note_id: int, updates: Mapping[str, str]) -> NoteChangePreview:
        notes = NoteReader(self.anki).read([note_id])
        if not notes:
            raise LookupError(f"Note {note_id} was not found")
        note = notes[0]
        unknown_fields = set(updates) - set(note.fields)
        if unknown_fields:
            raise ValueError(f"Unknown fields for {note.note_type}: {', '.join(sorted(unknown_fields))}")
        after_fields = dict(note.fields)
        after_fields.update(updates)
        changed_fields = tuple(name for name, value in after_fields.items() if note.fields.get(name) != value)
        before = self._build_preview(note.note_type, note.fields, tags=note.tags)
        after = self._build_preview(note.note_type, after_fields, tags=note.tags)
        return NoteChangePreview(note.note_id, before, after, changed_fields)

    def _build_preview(
        self,
        note_type: str,
        field_values: Mapping[str, str],
        *,
        deck: str = "",
        tags: tuple[str, ...] | list[str] = (),
    ) -> NotePreview:
        field_names = self.anki.model_field_names(note_type)
        unknown_fields = set(field_values) - set(field_names)
        if unknown_fields:
            raise ValueError(f"Unknown fields for {note_type}: {', '.join(sorted(unknown_fields))}")
        fields = {name: field_values.get(name, "") for name in field_names}
        templates = self.anki.model_templates(note_type)
        css = self.anki.model_styling(note_type)
        tag_list = tuple(tags)
        cloze_fields = _cloze_fields(templates)
        deletion_indices = _cloze_indices(fields, cloze_fields)
        warnings: set[str] = set()
        cards: list[CardPreview] = []

        context_base = {
            "Tags": " ".join(tag_list),
            "Type": note_type,
            "Deck": deck,
            "Subdeck": deck.split("::")[-1] if deck else "",
        }
        for card_name, sides in templates.items():
            front_template = sides.get("Front", sides.get("front", ""))
            back_template = sides.get("Back", sides.get("back", ""))
            is_cloze_card = any(CLOZE_FIELD_PATTERN.search(part) for part in (front_template, back_template))
            card_deletions: list[int | None] = deletion_indices if is_cloze_card else [None]
            for deletion_index in card_deletions:
                context = {**context_base, "Card": card_name}
                front = _render_template(
                    front_template,
                    fields,
                    context=context,
                    front_side="",
                    deletion_index=deletion_index,
                    side="Front",
                    warnings=warnings,
                )
                if not front.strip():
                    continue
                back = _render_template(
                    back_template,
                    fields,
                    context=context,
                    front_side=front,
                    deletion_index=deletion_index,
                    side="Back",
                    warnings=warnings,
                )
                if "<script" in (front + back).lower():
                    warnings.add("Preview HTML includes JavaScript markup; script behavior is not reproduced.")
                cards.append(
                    CardPreview(
                        card_name=card_name if deletion_index is None else f"{card_name} (c{deletion_index})",
                        front_html=front,
                        back_html=back,
                        deletion_index=deletion_index,
                    )
                )
        if cloze_fields and not deletion_indices:
            warnings.add("No Cloze deletion numbers were found in the fields referenced by the template.")
        return NotePreview(note_type, fields, css, tuple(cards), tuple(sorted(warnings)))
