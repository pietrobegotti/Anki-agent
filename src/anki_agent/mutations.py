"""Create and update notes through a preview-and-explicit-approval flow."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from typing import Mapping

from .ankiconnect import AnkiConnect
from .preview import NoteChangePreview, NotePreview, PreviewService


class MutationError(Exception):
    """Base class for note mutation workflow errors."""


class ApprovalRejectedError(MutationError):
    pass


class StaleProposalError(MutationError):
    pass


class MutationOutcomeUnknown(MutationError):
    pass


@dataclass(frozen=True)
class OperationProposal:
    proposal_id: str
    operation: str
    preview: NotePreview | NoteChangePreview


@dataclass(frozen=True)
class MutationResult:
    operation: str
    note_id: int


@dataclass
class _PendingOperation:
    proposal: OperationProposal
    payload: dict
    fingerprint: str
    status: str = "pending"


def _fingerprint(operation: str, payload: dict, preview: NotePreview | NoteChangePreview) -> str:
    content = json.dumps(
        {"operation": operation, "payload": payload, "preview": asdict(preview)},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class NoteMutationService:
    """Propose note writes, then apply them only after explicit approval."""

    def __init__(self, anki: AnkiConnect, previews: PreviewService | None = None):
        self.anki = anki
        self.previews = previews or PreviewService(anki)
        self._pending: dict[str, _PendingOperation] = {}

    def propose_add(
        self,
        *,
        deck: str,
        note_type: str,
        fields: Mapping[str, str],
        tags: tuple[str, ...] | list[str] = (),
    ) -> OperationProposal:
        if deck not in self.anki.deck_names():
            raise ValueError(f"Unknown deck: {deck}")
        if note_type not in self.anki.model_names():
            raise ValueError(f"Unknown note type: {note_type}")
        normalized_tags = tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        preview = self.previews.preview_new(note_type, fields, deck=deck, tags=normalized_tags)
        payload = {
            "deckName": deck,
            "modelName": note_type,
            "fields": preview.fields,
            "tags": list(normalized_tags),
        }
        return self._register("add", payload, preview)

    def propose_update(self, note_id: int, updates: Mapping[str, str]) -> OperationProposal:
        if not updates:
            raise ValueError("Provide at least one field to update")
        preview = self.previews.preview_edit(note_id, updates)
        payload = {"note_id": note_id, "fields": dict(updates)}
        return self._register("update", payload, preview)

    def _register(
        self,
        operation: str,
        payload: dict,
        preview: NotePreview | NoteChangePreview,
    ) -> OperationProposal:
        proposal = OperationProposal(secrets.token_urlsafe(12), operation, preview)
        fingerprint = _fingerprint(operation, payload, preview)
        self._pending[proposal.proposal_id] = _PendingOperation(proposal, payload, fingerprint)
        return proposal

    def cancel(self, proposal_id: str) -> None:
        pending = self._get_pending(proposal_id)
        if pending.status != "pending":
            raise MutationError(f"Proposal cannot be cancelled in state: {pending.status}")
        pending.status = "cancelled"

    def confirm(self, proposal_id: str, *, user_response: str) -> MutationResult:
        """Apply a proposal only when the caller passes an explicit 'approve' response."""
        pending = self._get_pending(proposal_id)
        if pending.status != "pending":
            raise MutationError(f"Proposal cannot be applied in state: {pending.status}")
        if user_response.strip().casefold() != "approve":
            pending.status = "cancelled"
            raise ApprovalRejectedError("No write was made; the proposal was cancelled.")

        self._verify_current_state(pending)
        pending.status = "applying"
        try:
            if pending.proposal.operation == "add":
                note_id = self.anki._invoke_approved_write("addNote", note=pending.payload)
                if note_id is None:
                    raise MutationError("AnkiConnect did not return a note ID")
                result = MutationResult("add", int(note_id))
            else:
                self.anki._invoke_approved_write(
                    "updateNoteFields",
                    note={"id": pending.payload["note_id"], "fields": pending.payload["fields"]},
                )
                result = MutationResult("update", int(pending.payload["note_id"]))
        except Exception as exc:
            pending.status = "outcome_unknown"
            raise MutationOutcomeUnknown(
                "AnkiConnect did not confirm the write. Inspect the collection before retrying."
            ) from exc
        pending.status = "applied"
        return result

    def _verify_current_state(self, pending: _PendingOperation) -> None:
        payload = pending.payload
        proposal_fingerprint = _fingerprint(
            pending.proposal.operation,
            payload,
            pending.proposal.preview,
        )
        if proposal_fingerprint != pending.fingerprint:
            pending.status = "stale"
            raise StaleProposalError("The proposal preview was modified; create a new proposal.")
        if pending.proposal.operation == "add":
            if payload["deckName"] not in self.anki.deck_names():
                pending.status = "stale"
                raise StaleProposalError("The destination deck changed after the preview; create a new proposal.")
            if payload["modelName"] not in self.anki.model_names():
                pending.status = "stale"
                raise StaleProposalError("The note type changed after the preview; create a new proposal.")
            current_preview = self.previews.preview_new(
                payload["modelName"],
                payload["fields"],
                deck=payload["deckName"],
                tags=payload["tags"],
            )
        else:
            current_preview = self.previews.preview_edit(payload["note_id"], payload["fields"])
        current_fingerprint = _fingerprint(pending.proposal.operation, payload, current_preview)
        if current_fingerprint != pending.fingerprint:
            pending.status = "stale"
            raise StaleProposalError("The note or its templates changed after the preview; create a new proposal.")

    def _get_pending(self, proposal_id: str) -> _PendingOperation:
        try:
            return self._pending[proposal_id]
        except KeyError as exc:
            raise MutationError("Proposal was not found or is no longer available") from exc
