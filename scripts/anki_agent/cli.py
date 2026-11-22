"""Command-line entry points for local setup checks."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import AgentConfig
from .collection_config import refresh_collection_config
from .docs_gen import refresh_collection_guides, refresh_deck_docs, refresh_note_type_docs
from .local_cards import ImportReceipts, LocalCardImporter, LocalFolderQueueProvider
from .mutations import NoteMutationService

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anki-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("smoke", help="check AnkiConnect and generate local collection docs")
    export = subparsers.add_parser("export-config", help="write the live Anki decks and fields to info/anki_config")
    export.add_argument("--output", type=Path, default=PROJECT_ROOT / "info" / "anki_config" / "collection_config.md")
    importer = subparsers.add_parser(
        "import-cards", help="import legacy approved-request JSON (not info/CARDS.md files)"
    )
    importer.add_argument("--cards-dir", type=Path, default=PROJECT_ROOT / "cards")
    cleanup = subparsers.add_parser(
        "cleanup-cards", help="delete completed legacy import requests from cards/"
    )
    cleanup.add_argument("--cards-dir", type=Path, default=PROJECT_ROOT / "cards")
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
    if args.command == "export-config":
        config = AgentConfig.from_env()
        target = refresh_collection_config(config.create_anki(), args.output)
        print("Updated:", target)
        return 0
    if args.command in {"import-cards", "cleanup-cards"}:
        config = AgentConfig.from_env()
        importer = LocalCardImporter(
            LocalFolderQueueProvider(args.cards_dir),
            NoteMutationService(config.create_anki()),
            ImportReceipts(config.local_state_root / "card-import-receipts.sqlite3"),
        )
        if args.command == "import-cards":
            for card_id, status in importer.process().items():
                print(f"{card_id}: {status}")
        else:
            deleted = importer.cleanup_completed()
            print(f"Deleted completed JSON files: {len(deleted)}")
        return 0
    return 2
