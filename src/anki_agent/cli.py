"""Command-line entry points for local setup checks."""
from __future__ import annotations

import argparse

from .config import AgentConfig
from .docs_gen import refresh_collection_guides, refresh_deck_docs, refresh_note_type_docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anki-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("smoke", help="check AnkiConnect and generate local collection docs")
    args = parser.parse_args(argv)
    if args.command == "smoke":
        config = AgentConfig.from_env()
        anki = config.create_anki()
        print("AnkiConnect version:", anki.version())
        print("Decks:", anki.deck_names())
        print("Note types:", anki.model_names())
        storage = config.create_storage()
        print("Written:", refresh_note_type_docs(anki, storage))
        print("Written:", refresh_deck_docs(anki, storage))
        print("Written:", refresh_collection_guides(storage))
        print("Documentation directory:", config.storage_root)
        return 0
    return 2
