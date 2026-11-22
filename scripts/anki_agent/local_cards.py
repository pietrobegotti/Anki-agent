"""Legacy approved-request queue schema and local importer.

This importer uses the old request wrapper with deck and note_type fields. It
does not consume the LLM card-file format documented in info/CARDS.md.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Protocol
from uuid import uuid4

from .mutations import DuplicateReviewRequired, MutationOutcomeUnknown, NoteMutationService

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class QueuedCard:
    card_id: str
    deck: str
    note_type: str
    fields: Mapping[str, str]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueueRequest:
    request_id: str
    created_at: str
    approved: bool
    cards: tuple[QueuedCard, ...]

    @classmethod
    def create(cls, cards: list[QueuedCard] | tuple[QueuedCard, ...]) -> "QueueRequest":
        if not cards:
            raise ValueError("A queue request must contain at least one card")
        if len({card.card_id for card in cards}) != len(cards):
            raise ValueError("Card IDs must be unique within a queue request")
        for card in cards:
            if not card.deck.strip() or not card.note_type.strip() or not card.fields:
                raise ValueError("Each card needs a deck, note type, and fields")
            if any(not isinstance(key, str) or not isinstance(value, str) for key, value in card.fields.items()):
                raise ValueError("Card field names and values must be strings")
        return cls(
            request_id=uuid4().hex,
            created_at=datetime.now(timezone.utc).isoformat(),
            approved=True,
            cards=tuple(cards),
        )

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "request_id": self.request_id,
                "created_at": self.created_at,
                "approved": self.approved,
                "cards": [
                    {"card_id": c.card_id, "deck": c.deck, "note_type": c.note_type,
                     "fields": dict(c.fields), "tags": list(c.tags)}
                    for c in self.cards
                ],
            },
            ensure_ascii=False,
            indent=2,
        )

    @classmethod
    def from_json(cls, raw: str) -> "QueueRequest":
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise ValueError("Queue request must be a JSON object")
        if data.get("schema_version") != SCHEMA_VERSION or data.get("approved") is not True:
            raise ValueError("Unsupported queue file or missing explicit approval")
        if not isinstance(data.get("request_id"), str) or not data["request_id"].strip():
            raise ValueError("Queue request needs a request_id")
        if not isinstance(data.get("created_at"), str):
            raise ValueError("Queue request needs a created_at timestamp")
        if not isinstance(data.get("cards"), list) or not data["cards"]:
            raise ValueError("Queue request needs a non-empty cards list")
        cards_list: list[QueuedCard] = []
        for card in data["cards"]:
            if not isinstance(card, dict):
                raise ValueError("Each card must be a JSON object")
            card_id, deck, note_type = card.get("card_id"), card.get("deck"), card.get("note_type")
            fields, tags = card.get("fields"), card.get("tags", [])
            if not all(isinstance(value, str) and value.strip() for value in (card_id, deck, note_type)):
                raise ValueError("Each card needs non-empty card_id, deck, and note_type strings")
            if not isinstance(fields, dict) or not fields or any(
                not isinstance(key, str) or not isinstance(value, str) for key, value in fields.items()
            ):
                raise ValueError("Each card needs a fields object with string names and values")
            if not isinstance(tags, list) or any(not isinstance(tag, str) for tag in tags):
                raise ValueError("Card tags must be a list of strings")
            cards_list.append(QueuedCard(card_id, deck, note_type, dict(fields), tuple(tags)))
        cards = tuple(cards_list)
        request = cls(data["request_id"], data["created_at"], True, cards)
        if not cards or len({card.card_id for card in cards}) != len(cards):
            raise ValueError("Queue request must contain cards with unique IDs")
        return request


class QueueProvider(Protocol):
    def list_json(self, folder_id: str = "") -> list[tuple[str, str]]: ...
    def update_json(self, file_id: str, content: str) -> None: ...
    def delete_file(self, file_id: str) -> None: ...


class LocalFolderQueueProvider:
    """Read and update JSON requests in a local folder synchronized by Drive for desktop."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder).expanduser().resolve()
        self.folder.mkdir(parents=True, exist_ok=True)

    def list_json(self, _folder_id: str = "") -> list[tuple[str, str]]:
        return [
            (path.name, path.read_text(encoding="utf-8"))
            for path in sorted(self.folder.glob("*.json"))
            if path.is_file()
        ]

    def update_json(self, file_id: str, content: str) -> None:
        path = self._resolve(file_id)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(path)

    def delete_file(self, file_id: str) -> None:
        self._resolve(file_id).unlink(missing_ok=True)

    def _resolve(self, file_id: str) -> Path:
        path = (self.folder / file_id).resolve()
        if path.parent != self.folder or path.suffix.lower() != ".json":
            raise ValueError(f"Invalid queue file name: {file_id}")
        return path

class ImportReceipts:
    """Durable local idempotency ledger. `applying` entries are never retried blindly."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute(
            "CREATE TABLE IF NOT EXISTS receipts (card_id TEXT PRIMARY KEY, status TEXT NOT NULL, "
            "note_id INTEGER, error TEXT, updated_at TEXT NOT NULL)"
        )
        self.db.commit()

    def get(self, card_id: str) -> tuple[str, int | None, str | None] | None:
        row = self.db.execute(
            "SELECT status,note_id,error FROM receipts WHERE card_id=?", (card_id,)
        ).fetchone()
        return row

    def set(self, card_id: str, status: str, note_id: int | None = None, error: str | None = None) -> None:
        self.db.execute(
            "INSERT INTO receipts VALUES(?,?,?,?,?) ON CONFLICT(card_id) DO UPDATE SET "
            "status=excluded.status,note_id=excluded.note_id,error=excluded.error,updated_at=excluded.updated_at",
            (card_id, status, note_id, error, datetime.now(timezone.utc).isoformat()),
        )
        self.db.commit()


class LocalCardImporter:
    """Import approved pending cards; never removes or edits Anki notes."""

    def __init__(self, provider: QueueProvider, mutations: NoteMutationService, receipts: ImportReceipts):
        self.provider = provider
        self.mutations = mutations
        self.receipts = receipts

    def process(self) -> dict[str, str]:
        outcomes: dict[str, str] = {}
        added_any = False
        for file_id, raw in self.provider.list_json():
            try:
                request = QueueRequest.from_json(raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                outcomes[file_id] = f"invalid: {exc}"
                continue
            state = json.loads(raw)
            card_states = state.setdefault("card_status", {})
            for card in request.cards:
                receipt = self.receipts.get(card.card_id)
                if receipt and receipt[0] in {"applied", "applying", "uncertain"}:
                    card_states[card.card_id] = receipt[0]
                    outcomes[card.card_id] = receipt[0]
                    continue
                if card_states.get(card.card_id) == "applied":
                    outcomes[card.card_id] = "applied"
                    continue
                try:
                    proposal = self.mutations.propose_add(
                        deck=card.deck, note_type=card.note_type,
                        fields=card.fields, tags=card.tags,
                    )
                except DuplicateReviewRequired as exc:
                    card_states[card.card_id] = "needs_review"
                    card_states.setdefault("errors", {})[card.card_id] = str(exc)
                    self.receipts.set(card.card_id, "needs_review", error=str(exc))
                    outcomes[card.card_id] = "needs_review"
                    continue
                except Exception as exc:
                    card_states[card.card_id] = "failed"
                    card_states.setdefault("errors", {})[card.card_id] = str(exc)
                    self.receipts.set(card.card_id, "failed", error=str(exc))
                    outcomes[card.card_id] = "failed"
                    continue

                # Persist before the write. If the process dies mid-write, a later
                # run pauses for reconciliation instead of creating a duplicate.
                self.receipts.set(card.card_id, "applying")
                card_states[card.card_id] = "applying"
                try:
                    result = self.mutations.confirm(proposal.proposal_id, user_response="approve")
                except MutationOutcomeUnknown as exc:
                    self.receipts.set(card.card_id, "uncertain", error=str(exc))
                    card_states[card.card_id] = "uncertain"
                    outcomes[card.card_id] = "uncertain"
                except Exception as exc:
                    self.receipts.set(card.card_id, "failed", error=str(exc))
                    card_states[card.card_id] = "failed"
                    card_states.setdefault("errors", {})[card.card_id] = str(exc)
                    outcomes[card.card_id] = "failed"
                else:
                    self.receipts.set(card.card_id, "applied", note_id=result.note_id)
                    added_any = True
                    card_states[card.card_id] = "applied"
                    card_states.setdefault("note_ids", {})[card.card_id] = result.note_id
                    outcomes[card.card_id] = "applied"
            self.provider.update_json(file_id, json.dumps(state, ensure_ascii=False, indent=2))
        if added_any:
            try:
                self.mutations.anki.sync_with_ankiweb()
                outcomes["sync"] = "completed"
            except Exception as exc:
                outcomes["sync"] = f"failed: {exc}"
        return outcomes

    def cleanup_completed(self) -> list[str]:
        """Explicitly delete fully imported JSON files; never touches Anki notes."""
        deleted: list[str] = []
        for file_id, raw in self.provider.list_json():
            try:
                request = QueueRequest.from_json(raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
            if all((self.receipts.get(card.card_id) or (None,))[0] == "applied" for card in request.cards):
                self.provider.delete_file(file_id)
                deleted.append(file_id)
        return deleted


