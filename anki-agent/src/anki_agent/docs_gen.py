"""Genera/aggiorna la documentazione Markdown dei tipi di nota e l'indice dei deck.

Ogni file ha una sezione AUTO (rigenerata dai dati reali di Anki) e una sezione
MANUALE che non viene mai sovrascritta: lì l'agente e l'utente annotano
convenzioni, significato dei campi, eccezioni.
"""
from __future__ import annotations

import re

from .ankiconnect import AnkiConnect
from .storage import Storage, log_line

AUTO_START = "<!-- AUTO:START (rigenerata automaticamente, non modificare) -->"
AUTO_END = "<!-- AUTO:END -->"
MANUAL_HEADER = "## Note manuali (convenzioni, significato dei campi, eccezioni)"
MANUAL_PLACEHOLDER = "_Da compilare._"


def _field_used(field: str, template: str) -> bool:
    pattern = r"\{\{[#^/]?(?:[^{}:]+:)*" + re.escape(field) + r"\}\}"
    return re.search(pattern, template) is not None


def _is_cloze(templates: dict[str, dict[str, str]]) -> bool:
    return any("{{cloze:" in t for tpl in templates.values() for t in tpl.values())


def _fence(lang: str, text: str) -> str:
    return f"```{lang}\n{text.strip()}\n```"


def build_note_type_auto(ac: AnkiConnect, model: str) -> str:
    fields = ac.model_field_names(model)
    templates = ac.model_templates(model)
    css = ac.model_styling(model)
    note_ids = ac.find_notes(f'"note:{model}"')
    cloze = _is_cloze(templates)

    out = [f"# Tipo di nota: {model}", "", AUTO_START, ""]
    out.append(f"- **Note nella collezione:** {len(note_ids)}")
    out.append(f"- **Cloze:** {'sì' if cloze else 'no'}")
    if cloze:
        out.append("- **Card generate:** una per ogni numero di cancellazione distinto (`c1`, `c2`, …) presente nel campo.")
    else:
        out.append(f"- **Card generate per nota:** fino a {len(templates)} (una per template; un template può non generare card se il campo del fronte è vuoto).")
    out += ["", "## Campi", "", "| # | Campo | Usato in |", "|---|-------|----------|"]
    for i, f in enumerate(fields, 1):
        used = [
            f"{card}/{side}"
            for card, sides in templates.items()
            for side, html in sides.items()
            if _field_used(f, html)
        ]
        out.append(f"| {i} | {f} | {', '.join(used) or '—'} |")

    out += ["", "## Template"]
    for card, sides in templates.items():
        out += ["", f"### {card}"]
        for side, html in sides.items():
            out += ["", f"**{side}**", "", _fence("html", html)]
    out += ["", "## CSS", "", _fence("css", css or "/* vuoto */")]

    if note_ids:
        sample = ac.notes_info(note_ids[:1])[0]
        out += ["", "## Esempio reale (prima nota trovata)", ""]
        out.append(f"- note id: `{sample['noteId']}`, tag: {sample.get('tags') or '—'}")
        for name, data in sample["fields"].items():
            out.append(f"- **{name}**: `{data['value']}`")
    out += ["", AUTO_END]
    return "\n".join(out)


def merge_with_manual(existing: str | None, auto_block: str) -> str:
    """Sostituisce solo la parte AUTO; conserva la parte manuale esistente."""
    manual = f"{MANUAL_HEADER}\n\n{MANUAL_PLACEHOLDER}\n"
    if existing and AUTO_END in existing:
        manual = existing.split(AUTO_END, 1)[1].lstrip("\n")
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
    log_line(storage, f"refresh documentazione tipi di nota: {len(written)} file")
    return written


def refresh_deck_docs(ac: AnkiConnect, storage: Storage) -> list[str]:
    """Crea uno scheletro per ogni deck (se non esiste) e un indice dei deck."""
    decks = sorted(ac.deck_names())
    written = []
    for deck in decks:
        path = f"decks/{_safe_name(deck)}.md"
        if storage.read(path) is None:
            n = len(ac.find_notes(f'"deck:{deck}"'))
            storage.write(
                path,
                f"# Deck: {deck}\n\n- **Note (inclusi sotto-deck):** {n}\n\n"
                "## Convenzioni, tipi di nota usati, preferenze\n\n_Da compilare._\n",
            )
            written.append(path)
    index = "# Indice dei deck\n\n" + "\n".join(f"- {d}" for d in decks) + "\n"
    storage.write("decks/_index.md", index)
    log_line(storage, f"refresh deck: {len(decks)} deck, {len(written)} nuovi file")
    return written
