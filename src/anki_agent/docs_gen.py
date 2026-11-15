"""Generate and update Markdown documentation for note types and the deck index.

Each file has an AUTO section (refreshed from Anki data) and a MANUAL section
that is never overwritten. The agent and user can record conventions, field
meanings, and exceptions there.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator
from typing import Any

from .ankiconnect import AnkiConnect
from .storage import Storage, log_line

AUTO_START = "<!-- AUTO:START (automatically generated, do not edit) -->"
AUTO_END = "<!-- AUTO:END -->"
MANUAL_HEADER = "## Manual notes (conventions, field meanings, exceptions)"
MANUAL_PLACEHOLDER = "_To be completed._"
NOTE_INFO_BATCH_SIZE = 250


def _field_used(field: str, template: str) -> bool:
    pattern = r"\{\{[#^/]?(?:[^{}:]+:)*" + re.escape(field) + r"\}\}"
    return re.search(pattern, template) is not None


def _cloze_fields(templates: dict[str, dict[str, str]]) -> list[str]:
    fields = {
        match.strip()
        for sides in templates.values()
        for template in sides.values()
        for match in re.findall(r"\{\{\s*cloze\s*:\s*([^{}]+?)\s*\}\}", template, re.IGNORECASE)
    }
    return sorted(fields)


def _notes_info_in_batches(ac: AnkiConnect, note_ids: list[int]) -> Iterator[dict[str, Any]]:
    for start in range(0, len(note_ids), NOTE_INFO_BATCH_SIZE):
        yield from ac.notes_info(note_ids[start : start + NOTE_INFO_BATCH_SIZE])


def _cloze_card_stats(
    ac: AnkiConnect,
    note_ids: list[int],
    cloze_fields: list[str],
) -> tuple[Counter[int], int, int, dict[str, Any] | None]:
    """Return deletion counts, generated-card totals, and the first note sample."""
    deletion_note_counts: Counter[int] = Counter()
    card_count = 0
    notes_with_cards = 0
    sample = None
    deletion_pattern = re.compile(r"\{\{c(\d+)::")

    for note in _notes_info_in_batches(ac, note_ids):
        if sample is None:
            sample = note
        note_deletions: set[int] = set()
        fields = note.get("fields", {})
        for field in cloze_fields:
            value = fields.get(field, {}).get("value", "")
            note_deletions.update(int(index) for index in deletion_pattern.findall(value))
        deletion_note_counts.update(note_deletions)
        cards = note.get("cards", [])
        card_count += len(cards)
        if cards:
            notes_with_cards += 1

    return deletion_note_counts, card_count, notes_with_cards, sample


def _fence(lang: str, text: str) -> str:
    return f"```{lang}\n{text.strip()}\n```"


def build_note_type_auto(ac: AnkiConnect, model: str) -> str:
    fields = ac.model_field_names(model)
    templates = ac.model_templates(model)
    css = ac.model_styling(model)
    note_ids = ac.find_notes(f'"note:{model}"')
    cloze_fields = _cloze_fields(templates)
    cloze = bool(cloze_fields)
    cloze_sample = None

    out = [f"# Note type: {model}", "", AUTO_START, ""]
    out.append(f"- **Notes in collection:** {len(note_ids)}")
    out.append(f"- **Cloze:** {'yes' if cloze else 'no'}")
    if cloze:
        out.append(f"- **Cloze fields:** {', '.join(cloze_fields)}")
        deletion_note_counts, card_count, notes_with_cards, cloze_sample = _cloze_card_stats(
            ac, note_ids, cloze_fields
        )
        if deletion_note_counts:
            deletion_summary = ", ".join(
                f"c{index} ({count} note{'s' if count != 1 else ''})"
                for index, count in sorted(deletion_note_counts.items())
            )
        else:
            deletion_summary = "none found"
        out.append(f"- **Cloze deletion numbers found:** {deletion_summary}")
        out.append(f"- **Generated cards in collection:** {card_count}")
        out.append(f"- **Notes with generated cards:** {notes_with_cards}")
    else:
        out.append(f"- **Cards generated per note:** up to {len(templates)} (one per template; a template may not generate a card if its front field is empty).")
    out += ["", "## Card templates", ""]
    for card, sides in templates.items():
        front_fields = [field for field in fields if _field_used(field, sides.get("Front", ""))]
        front_usage = f"uses fields: {', '.join(front_fields)}" if front_fields else "uses no detected fields"
        out.append(f"- **{card}:** the front template {front_usage}.")
    out += ["", "## Fields", "", "| # | Field | Used in |", "|---|-------|----------|"]
    for i, f in enumerate(fields, 1):
        used = [
            f"{card}/{side}"
            for card, sides in templates.items()
            for side, html in sides.items()
            if _field_used(f, html)
        ]
        out.append(f"| {i} | {f} | {', '.join(used) or '—'} |")

    out += ["", "## Templates"]
    for card, sides in templates.items():
        out += ["", f"### {card}"]
        for side, html in sides.items():
            out += ["", f"**{side}**", "", _fence("html", html)]
    out += ["", "## CSS", "", _fence("css", css or "/* empty */")]

    if note_ids:
        sample = cloze_sample if cloze else ac.notes_info(note_ids[:1])[0]
        assert sample is not None
        out += ["", "## Collection example (first note found)", ""]
        out.append(f"- note id: `{sample['noteId']}`, tag: {sample.get('tags') or '—'}")
        for name, data in sample["fields"].items():
            out.append(f"- **{name}**: `{data['value']}`")
    out += ["", AUTO_END]
    return "\n".join(out)


def merge_with_manual(existing: str | None, auto_block: str) -> str:
    """Replace only the AUTO section and preserve the existing manual section."""
    manual = f"{MANUAL_HEADER}\n\n{MANUAL_PLACEHOLDER}\n"
    if existing and AUTO_END in existing:
        manual = existing.split(AUTO_END, 1)[1].lstrip("\n")
        manual = manual.replace(
            "## Note manuali (convenzioni, significato dei campi, eccezioni)",
            MANUAL_HEADER,
        ).replace("_Da compilare._", MANUAL_PLACEHOLDER)
    return auto_block.rstrip() + "\n\n" + manual if manual.strip() else auto_block


def _safe_name(name: str) -> str:
    return re.sub(r"[^\w\-. ]", "_", name.replace("::", "__")).strip()


def refresh_note_type_docs(ac: AnkiConnect, storage: Storage, only: str | None = None) -> list[str]:
    models = [only] if only else ac.model_names()
    written = []
    for model in models:
        path = f"note_types/{_safe_name(model)}.md"
        auto = build_note_type_auto(ac, model)
        storage.write(path, merge_with_manual(storage.read(path), auto))
        written.append(path)
    log_line(storage, f"refreshed note type documentation: {len(written)} files")
    return written


def refresh_deck_docs(ac: AnkiConnect, storage: Storage) -> list[str]:
    """Create a skeleton for each deck (if missing) and a deck index."""
    decks = sorted(ac.deck_names())
    written = []
    for deck in decks:
        path = f"decks/{_safe_name(deck)}.md"
        if storage.read(path) is None:
            n = len(ac.find_notes(f'"deck:{deck}"'))
            storage.write(
                path,
                f"# Deck: {deck}\n\n- **Notes (including subdecks):** {n}\n\n"
                "## Conventions, note types used, and preferences\n\n_To be completed._\n",
            )
            written.append(path)
    index = "# Deck index\n\n" + "\n".join(f"- {d}" for d in decks) + "\n"
    storage.write("decks/_index.md", index)
    log_line(storage, f"refreshed decks: {len(decks)} decks, {len(written)} new files")
    return written
