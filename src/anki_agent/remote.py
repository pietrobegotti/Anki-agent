"""Tenant-isolated WSGI gateway for a remote ChatGPT connector."""
from __future__ import annotations

import hmac
import json
import re
from dataclasses import asdict
from typing import Any, Callable

from .mutations import AddNoteRequest, DuplicateReviewRequired, NoteMutationService
from .reader import NoteReader
from .config import AgentConfig
from .history import MutationHistory
from .storage import LocalStorage, Storage


class RemoteUserContext:
    """An authenticated user's isolated Anki and mutation services."""

    def __init__(
        self,
        user_id: str,
        reader: NoteReader,
        mutations: NoteMutationService,
        documentation_storage: Storage | None = None,
    ):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):
            raise ValueError("User ID may contain only letters, numbers, _ and -")
        if reader.anki is not mutations.anki:
            raise ValueError("Reader and mutation service must target the same Anki user collection")
        self.user_id = user_id
        self.reader = reader
        self.mutations = mutations
        self.documentation_storage = documentation_storage or mutations.history.storage
        if mutations._uses_default_history:
            config = AgentConfig.from_env()
            mutations.history = MutationHistory(LocalStorage(config.data_dir / user_id))
            mutations._uses_default_history = False


class RemoteGateway:
    """Small connector-neutral JSON API, suitable for deployment behind HTTPS."""

    def __init__(self):
        self._users: list[tuple[str, RemoteUserContext]] = []

    def register(self, bearer_token: str, context: RemoteUserContext) -> None:
        if len(bearer_token) < 32:
            raise ValueError("Bearer tokens must contain at least 32 characters")
        if any(hmac.compare_digest(existing, bearer_token) for existing, _ in self._users):
            raise ValueError("Bearer token is already registered")
        if any(existing.user_id == context.user_id for _, existing in self._users):
            raise ValueError("User ID is already registered")
        if any(existing.mutations is context.mutations for _, existing in self._users):
            raise ValueError("Each user must have an isolated mutation service")
        if any(existing.mutations.anki is context.mutations.anki for _, existing in self._users):
            raise ValueError("Each user must have an isolated Anki connection")
        for _, existing in self._users:
            old_docs = existing.documentation_storage
            new_docs = context.documentation_storage
            if old_docs is new_docs:
                raise ValueError("Each user must have isolated collection documentation")
            old_docs_root = getattr(old_docs, "root", None)
            new_docs_root = getattr(new_docs, "root", None)
            if old_docs_root is not None and old_docs_root == new_docs_root:
                raise ValueError("Each user must have isolated collection documentation")
            old_history = existing.mutations.history
            new_history = context.mutations.history
            if old_history is not None and new_history is not None:
                if old_history.storage is new_history.storage:
                    raise ValueError("Each user must have an isolated history store")
                old_root = getattr(old_history.storage, "root", None)
                new_root = getattr(new_history.storage, "root", None)
                if old_root is not None and old_root == new_root:
                    raise ValueError("Each user must have an isolated history store")
        self._users.append((bearer_token, context))

    def dispatch(
        self, authorization: str | None, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> tuple[int, dict[str, Any]]:
        token = authorization.removeprefix("Bearer ") if authorization and authorization.startswith("Bearer ") else ""
        user = next(
            (context for known, context in self._users if hmac.compare_digest(known, token)), None
        )
        if user is None:
            return 401, {"error": "Unauthorized"}
        body = payload or {}
        try:
            if method == "GET" and path == "/v1/collection":
                anki = user.mutations.anki
                return 200, {"decks": anki.deck_names(), "note_types": anki.model_names()}
            if method == "GET" and path == "/v1/collection/docs":
                storage = user.documentation_storage
                paths = sorted({
                    path
                    for prefix in ("note_types/", "decks/", "preferences/")
                    for path in storage.list(prefix)
                })
                return 200, {"documents": paths}
            if method == "POST" and path == "/v1/collection/docs/read":
                document_path = body["path"]
                prefixes = ("note_types/", "decks/", "preferences/")
                parts = document_path.split("/") if isinstance(document_path, str) else []
                if (
                    not isinstance(document_path, str)
                    or "\\" in document_path
                    or not document_path.endswith(".md")
                    or len(parts) < 2
                    or any(part in {"", ".", ".."} for part in parts)
                    or not document_path.startswith(prefixes)
                ):
                    raise ValueError("path must identify a collection Markdown guide")
                content = user.documentation_storage.read(document_path)
                if content is None:
                    return 404, {"error": "Collection document not found"}
                if len(content) > 100_000:
                    raise ValueError("Collection document exceeds the 100000-character read limit")
                return 200, {"path": document_path, "content": content}
            if method == "POST" and path == "/v1/note-types/inspect":
                note_type = body["note_type"]
                anki = user.mutations.anki
                if note_type not in anki.model_names():
                    raise ValueError(f"Unknown note type: {note_type}")
                return 200, {
                    "note_type": note_type,
                    "fields": anki.model_field_names(note_type),
                    "templates": anki.model_templates(note_type),
                }
            if method == "POST" and path == "/v1/notes/search":
                notes = user.reader.search(
                    text=body.get("text"), deck=body.get("deck"),
                    note_type=body.get("note_type"), tags=body.get("tags", []),
                    limit=body.get("limit", 50),
                )
                return 200, {"notes": [asdict(note) for note in notes]}
            if method == "POST" and path == "/v1/proposals/add":
                proposal = user.mutations.propose_add(
                    deck=body["deck"], note_type=body["note_type"],
                    fields=body["fields"], tags=body.get("tags", []),
                    allow_possible_duplicates=body.get("allow_possible_duplicates", False),
                )
                return 201, {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                             "preview": asdict(proposal.preview)}
            if method == "POST" and path == "/v1/proposals/add-batch":
                notes = body["notes"]
                if not isinstance(notes, list):
                    raise ValueError("notes must be an array")
                if not 1 <= len(notes) <= 50:
                    raise ValueError("A batch must contain between 1 and 50 notes")
                requests = [
                    AddNoteRequest(
                        deck=item["deck"],
                        note_type=item["note_type"],
                        fields=item["fields"],
                        tags=item.get("tags", []),
                        allow_possible_duplicates=item.get("allow_possible_duplicates", False),
                    )
                    for item in notes
                ]
                batch = user.mutations.propose_batch(requests)
                return 201, {
                    "batch_id": batch.batch_id,
                    "proposals": [
                        {"proposal_id": proposal.proposal_id,
                         "operation": proposal.operation,
                         "preview": asdict(proposal.preview)}
                        for proposal in batch.proposals
                    ],
                }
            if method == "POST" and path == "/v1/proposals/update":
                proposal = user.mutations.propose_update(body["note_id"], body["fields"])
                return 201, {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                             "preview": asdict(proposal.preview)}
            if method == "POST" and path == "/v1/proposals/delete":
                proposal = user.mutations.propose_delete(body["note_id"])
                return 201, {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                             "preview": asdict(proposal.preview),
                             "delete_confirmation": f"DELETE {body['note_id']}"}
            if method == "POST" and path == "/v1/proposals/move-deck":
                proposal = user.mutations.propose_move_to_deck(body["note_id"], body["deck"])
                return 201, {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                             "preview": asdict(proposal.preview)}
            if method == "POST" and path in {"/v1/proposals/add-tags", "/v1/proposals/remove-tags"}:
                method_name = "propose_add_tags" if path.endswith("add-tags") else "propose_remove_tags"
                proposal = getattr(user.mutations, method_name)(body["note_id"], body["tags"])
                return 201, {"proposal_id": proposal.proposal_id, "operation": proposal.operation,
                             "preview": asdict(proposal.preview)}
            if method == "POST" and path.startswith("/v1/batches/") and path.endswith("/confirm"):
                batch_id = path.removeprefix("/v1/batches/").removesuffix("/confirm").strip("/")
                decisions = body.get("decisions", {})
                if not isinstance(decisions, dict):
                    raise ValueError("decisions must be an object keyed by proposal ID")
                result = user.mutations.confirm_batch(batch_id, decisions)
                response = asdict(result)
                if any(operation.status == "applied" for operation in result.operations):
                    try:
                        user.mutations.anki.sync_with_ankiweb()
                    except Exception as exc:
                        response["ankiweb_sync"] = {"status": "failed", "error": str(exc)}
                    else:
                        response["ankiweb_sync"] = {"status": "completed"}
                else:
                    response["ankiweb_sync"] = {"status": "not_needed"}
                return 200, response
            if method == "POST" and path.startswith("/v1/batches/") and path.endswith("/cancel"):
                batch_id = path.removeprefix("/v1/batches/").removesuffix("/cancel").strip("/")
                user.mutations.cancel_batch(batch_id)
                return 200, {"batch_id": batch_id, "status": "cancelled"}
            if method == "POST" and path.startswith("/v1/proposals/") and path.endswith("/confirm"):
                proposal_id = path.removeprefix("/v1/proposals/").removesuffix("/confirm").strip("/")
                result = user.mutations.confirm(
                    proposal_id,
                    user_response=body.get("user_response", ""),
                    delete_confirmation=body.get("delete_confirmation", ""),
                )
                return 200, asdict(result)
            return 404, {"error": "Not found"}
        except DuplicateReviewRequired as exc:
            response = {
                "error": str(exc),
                "preview": asdict(exc.preview),
                "matches": [
                    {"note_id": match.note.note_id, "match_type": match.match_type,
                     "score": match.score, "matched_fields": match.matched_fields}
                    for match in exc.matches
                ],
            }
            if exc.request_index is not None:
                response["request_index"] = exc.request_index
            return 409, response
        except (KeyError, TypeError, ValueError) as exc:
            return 400, {"error": str(exc)}
        except Exception as exc:
            return 409, {"error": str(exc)}

    def __call__(self, environ: dict, start_response: Callable):
        if environ.get("wsgi.url_scheme") != "https" and environ.get("HTTP_X_FORWARDED_PROTO") != "https":
            body = b'{"error":"HTTPS is required"}'
            start_response("400 Bad Request", [("Content-Type", "application/json"),
                                                ("Content-Length", str(len(body))),
                                                ("Cache-Control", "no-store")])
            return [body]
        method = environ.get("REQUEST_METHOD", "GET")
        path = environ.get("PATH_INFO", "/")
        authorization = environ.get("HTTP_AUTHORIZATION")
        payload = None
        if method == "POST":
            try:
                length = min(int(environ.get("CONTENT_LENGTH") or 0), 1_000_000)
                payload = json.loads(environ["wsgi.input"].read(length) or b"{}")
                if not isinstance(payload, dict):
                    raise ValueError("JSON request body must be an object")
            except (ValueError, json.JSONDecodeError) as exc:
                status, response = 400, {"error": f"Invalid JSON request: {exc}"}
            else:
                status, response = self.dispatch(authorization, method, path, payload)
        else:
            status, response = self.dispatch(authorization, method, path)
        body = json.dumps(response, ensure_ascii=False).encode("utf-8")
        labels = {200: "200 OK", 201: "201 Created", 400: "400 Bad Request",
                  401: "401 Unauthorized", 404: "404 Not Found", 409: "409 Conflict"}
        start_response(labels[status], [("Content-Type", "application/json; charset=utf-8"),
                                        ("Content-Length", str(len(body))),
                                        ("Cache-Control", "no-store")])
        return [body]
