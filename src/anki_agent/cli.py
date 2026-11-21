"""Command-line entry points for local setup checks."""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from .config import AgentConfig
from .docs_gen import refresh_collection_guides, refresh_deck_docs, refresh_note_type_docs
from .drive_queue import DriveQueueWorker, GoogleDriveProvider, GoogleOAuthTokenProvider, ImportReceipts
from .mutations import NoteMutationService


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="anki-agent")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("smoke", help="check AnkiConnect and generate local collection docs")
    drive_import = subparsers.add_parser("drive-import", help="import approved cards from the nested Drive queue")
    drive_import.add_argument("--parent-id", default=os.environ.get("ANKI_AGENT_DRIVE_PARENT_ID", "root"))
    drive_cleanup = subparsers.add_parser("drive-cleanup", help="delete fully imported queue JSON files from Drive")
    drive_cleanup.add_argument("--parent-id", default=os.environ.get("ANKI_AGENT_DRIVE_PARENT_ID", "root"))
    subparsers.add_parser("drive-auth", help="authorize this PC for the Anki Agent Drive queue")
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
    if args.command in {"drive-auth", "drive-import", "drive-cleanup"}:
        config = AgentConfig.from_env()
        client_file = Path(os.environ.get(
            "ANKI_AGENT_GOOGLE_OAUTH_CLIENT_FILE", str(config.storage_root / "google-oauth-client.json")
        ))
        try:
            oauth = GoogleOAuthTokenProvider(client_file)
        except (OSError, ValueError, RuntimeError) as exc:
            parser.error(str(exc))
        if args.command == "drive-auth":
            oauth.authorize()
            print("Google Drive authorization saved to the operating system credential store.")
            return 0
        if not args.parent_id:
            parser.error("Set ANKI_AGENT_DRIVE_PARENT_ID or pass --parent-id")
        drive = GoogleDriveProvider(oauth.access_token)
        layout = drive.ensure_layout(args.parent_id)
        worker = DriveQueueWorker(
            drive, NoteMutationService(config.create_anki()),
            ImportReceipts(config.storage_root / "drive-queue-receipts.sqlite3"),
        )
        if args.command == "drive-import":
            for card_id, status in worker.process(queue_folder_id=layout["queue"]).items():
                print(f"{card_id}: {status}")
        else:
            deleted = worker.cleanup_completed(queue_folder_id=layout["queue"])
            print(f"Deleted completed Drive JSON files: {len(deleted)}")
        return 0
    return 2
