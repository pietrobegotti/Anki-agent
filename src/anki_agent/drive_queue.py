"""Drive queue contracts and a local import worker for approved Anki notes.

Drive access is supplied by a small provider adapter. This keeps OAuth tokens
out of the queue and lets the worker be exercised against a fake provider.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping, Protocol
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
        if data.get("schema_version") != SCHEMA_VERSION or data.get("approved") is not True:
            raise ValueError("Unsupported queue file or missing explicit approval")
        cards = tuple(
            QueuedCard(
                card_id=str(card["card_id"]), deck=str(card["deck"]),
                note_type=str(card["note_type"]), fields=dict(card["fields"]),
                tags=tuple(str(tag) for tag in card.get("tags", [])),
            )
            for card in data["cards"]
        )
        request = cls(str(data["request_id"]), str(data["created_at"]), True, cards)
        if not cards or len({card.card_id for card in cards}) != len(cards):
            raise ValueError("Queue request must contain cards with unique IDs")
        return request


class DriveQueueProvider(Protocol):
    """Minimal provider contract; IDs are provider file IDs, not paths."""

    def list_json(self, folder_id: str) -> list[tuple[str, str]]: ...
    def create_json(self, folder_id: str, name: str, content: str) -> str: ...
    def update_json(self, file_id: str, content: str) -> None: ...
    def delete_file(self, file_id: str) -> None: ...


class GoogleDriveProvider:
    """Small Drive v3 adapter using an externally managed OAuth access token.

    The callback must return a current access token. OAuth login/refresh-token
    storage intentionally stays outside this module and the queue files.
    """

    API = "https://www.googleapis.com/drive/v3/files"
    UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"

    def __init__(self, access_token: Callable[[], str], *, timeout: int = 20):
        self.access_token = access_token
        self.timeout = timeout

    def _request(self, url: str, *, method: str = "GET", body: bytes | None = None,
                 content_type: str | None = None) -> bytes:
        headers = {"Authorization": f"Bearer {self.access_token()}"}
        if content_type:
            headers["Content-Type"] = content_type
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Google Drive API returned HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Could not reach Google Drive API: {exc}") from exc

    @staticmethod
    def _escape_query(value: str) -> str:
        return value.replace("\\", "\\\\").replace("'", "\\'")

    def _find_folder(self, name: str, parent_id: str) -> str | None:
        query = (f"name='{self._escape_query(name)}' and mimeType="
                 f"'application/vnd.google-apps.folder' and '{self._escape_query(parent_id)}' in parents and trashed=false")
        url = self.API + "?" + urllib.parse.urlencode({"q": query, "fields": "files(id,name)", "pageSize": 100})
        data = json.loads(self._request(url))
        matches = data.get("files", [])
        return str(matches[0]["id"]) if matches else None

    def ensure_folder(self, name: str, parent_id: str) -> str:
        existing = self._find_folder(name, parent_id)
        if existing:
            return existing
        body = json.dumps({"name": name, "mimeType": "application/vnd.google-apps.folder",
                           "parents": [parent_id]}).encode()
        result = json.loads(self._request(self.API, method="POST", body=body,
                                          content_type="application/json; charset=utf-8"))
        return str(result["id"])

    def ensure_layout(self, parent_id: str, *, config_text: str | None = None,
                      instructions_text: str | None = None) -> dict[str, str]:
        """Create/find the nested layout and seed its two guide documents once."""
        root = self.ensure_folder(DriveQueue.ROOT_NAME, parent_id)
        queue = self.ensure_folder(DriveQueue.QUEUE_NAME, root)
        completed = self.ensure_folder(DriveQueue.COMPLETED_NAME, root)
        config_id = self._find_file("config.md", root)
        instructions_id = self._find_file("instructions.md", root)
        if not config_id:
            config_id = self.create_text(root, "config.md", config_text or DEFAULT_CONFIG)
        if not instructions_id:
            instructions_id = self.create_text(root, "instructions.md", instructions_text or DEFAULT_INSTRUCTIONS)
        return {"root": root, "queue": queue, "completed": completed,
                "config": config_id, "instructions": instructions_id}

    def _find_file(self, name: str, parent_id: str) -> str | None:
        query = (f"name='{self._escape_query(name)}' and '{self._escape_query(parent_id)}' in parents "
                 "and trashed=false")
        url = self.API + "?" + urllib.parse.urlencode({"q": query, "fields": "files(id,name)", "pageSize": 100})
        files = json.loads(self._request(url)).get("files", [])
        return str(files[0]["id"]) if files else None

    def create_text(self, folder_id: str, name: str, content: str) -> str:
        # Drive supports plain text documents; keep Markdown as text/plain.
        boundary = "anki-agent-" + uuid4().hex
        metadata = json.dumps({"name": name, "mimeType": "text/markdown", "parents": [folder_id]}).encode()
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                + metadata + f"\r\n--{boundary}\r\nContent-Type: text/markdown; charset=UTF-8\r\n\r\n".encode()
                + content.encode("utf-8") + f"\r\n--{boundary}--".encode())
        result = json.loads(self._request(self.UPLOAD + "?uploadType=multipart&fields=id", method="POST",
                                          body=body, content_type=f"multipart/related; boundary={boundary}"))
        return str(result["id"])

    def list_json(self, folder_id: str) -> list[tuple[str, str]]:
        query = f"'{self._escape_query(folder_id)}' in parents and trashed=false and mimeType='application/json'"
        page_token: str | None = None
        files: list[tuple[str, str]] = []
        while True:
            params = {"q": query, "fields": "nextPageToken,files(id,name)", "pageSize": 1000}
            if page_token:
                params["pageToken"] = page_token
            result = json.loads(self._request(self.API + "?" + urllib.parse.urlencode(params)))
            for item in result.get("files", []):
                file_id = str(item["id"])
                content = self._request(self.API + "/" + urllib.parse.quote(file_id) + "?alt=media")
                files.append((file_id, content.decode("utf-8")))
            page_token = result.get("nextPageToken")
            if not page_token:
                return files

    def create_json(self, folder_id: str, name: str, content: str) -> str:
        boundary = "anki-agent-" + uuid4().hex
        metadata = json.dumps({"name": name, "mimeType": "application/json", "parents": [folder_id]}).encode()
        media = content.encode("utf-8")
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                + metadata + f"\r\n--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n".encode()
                + media + f"\r\n--{boundary}--".encode())
        url = self.UPLOAD + "?uploadType=multipart&fields=id"
        result = json.loads(self._request(url, method="POST", body=body,
                                          content_type=f"multipart/related; boundary={boundary}"))
        return str(result["id"])

    def update_json(self, file_id: str, content: str) -> None:
        url = self.UPLOAD + "/" + urllib.parse.quote(file_id) + "?uploadType=media"
        self._request(url, method="PATCH", body=content.encode("utf-8"),
                      content_type="application/json; charset=utf-8")

    def delete_file(self, file_id: str) -> None:
        self._request(self.API + "/" + urllib.parse.quote(file_id), method="DELETE")


class DriveQueue:
    """Queue layout rooted under a caller-selected Drive parent folder.

    The provider's ensure_folder implementation must create/find `Anki Agent`
    beneath parent_id, then its `queue` and `completed` children.
    """

    ROOT_NAME = "Anki Agent"
    QUEUE_NAME = "queue"
    COMPLETED_NAME = "completed"

    def __init__(self, provider: DriveQueueProvider, parent_id: str):
        self.provider = provider
        self.parent_id = parent_id

    def enqueue(self, request: QueueRequest, *, queue_folder_id: str) -> str:
        return self.provider.create_json(
            queue_folder_id, f"{request.request_id}.json", request.to_json()
        )


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


class DriveQueueWorker:
    """Import approved pending cards; never removes or edits Anki notes."""

    def __init__(self, provider: DriveQueueProvider, mutations: NoteMutationService, receipts: ImportReceipts):
        self.provider = provider
        self.mutations = mutations
        self.receipts = receipts

    def process(self, *, queue_folder_id: str) -> dict[str, str]:
        outcomes: dict[str, str] = {}
        added_any = False
        for file_id, raw in self.provider.list_json(queue_folder_id):
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

    def cleanup_completed(self, *, queue_folder_id: str) -> list[str]:
        """Explicitly delete fully imported JSON files from Drive; never touches Anki."""
        deleted: list[str] = []
        for file_id, raw in self.provider.list_json(queue_folder_id):
            try:
                request = QueueRequest.from_json(raw)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError):
                continue
            if all((self.receipts.get(card.card_id) or (None,))[0] == "applied" for card in request.cards):
                self.provider.delete_file(file_id)
                deleted.append(file_id)
        return deleted


DEFAULT_CONFIG = """# Anki Agent Configuration\n\n## Defaults\n\n- Default deck: `Japanese::Vocabulary`\n- Default note type: `Basic`\n- Default tags: `chatgpt`\n\n## Deck and note type mappings\n\n| Use | Deck name (exact) | Note type (exact) | Required fields |\n| --- | --- | --- | --- |\n| Vocabulary | `Japanese::Vocabulary` | `Basic` | `Front`, `Back` |\n\nNames must exactly match Anki. Add a row for each permitted card type. Do not invent missing decks, note types, or fields.\n\n## Queue layout\n\nThis file, `instructions.md`, and `queue/` are children of the Drive folder `Anki Agent`, itself nested under the selected Drive parent. Each save request is one JSON file and can contain multiple cards.\n\n## Cleanup\n\nCompleted JSON files are removed from Drive only when the user explicitly asks. Cleanup never deletes or changes Anki notes.\n"""

DEFAULT_INSTRUCTIONS = """# Anki Card Writing Instructions\n\nRead this with `config.md` before preparing cards.\n\n- Keep each card focused on one testable fact.\n- Use concise, natural explanations; do not fabricate missing facts. Ask when meaning or destination is unclear.\n- Use exact deck, note type, and field names from `config.md`; all field values must be strings.\n- Create a JSON request only after the user explicitly asks to save the reviewed cards.\n- Use stable UUIDs for request and card IDs. One immutable JSON file per request goes in `queue/`. Retries reuse IDs.\n- Never remove completed files automatically. Delete completed queue JSON from Drive only after an explicit cleanup request. This does not delete Anki notes.\n"""
