"""Tenant-isolated WSGI gateway for a remote ChatGPT connector."""
from __future__ import annotations

import hmac
import json
import re
from dataclasses import asdict
from typing import Any, Callable

from .mutations import DuplicateReviewRequired, NoteMutationService
from .reader import NoteReader
from .config import AgentConfig
from .history import MutationHistory
from .storage import LocalStorage


class RemoteUserContext:
    """An authenticated user's isolated Anki and mutation services."""

    def __init__(self, user_id: str, reader: NoteReader, mutations: NoteMutationService):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):
            raise ValueError("User ID may contain only letters, numbers, _ and -")
        if reader.anki is not mutations.anki:
            raise ValueError("Reader and mutation service must target the same Anki user collection")
        self.user_id = user_id
        self.reader = reader
        self.mutations = mutations
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
            return 409, {
                "error": str(exc),
                "preview": asdict(exc.preview),
                "matches": [
                    {"note_id": match.note.note_id, "match_type": match.match_type,
                     "score": match.score, "matched_fields": match.matched_fields}
                    for match in exc.matches
                ],
            }
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
