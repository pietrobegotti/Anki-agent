"""Create and update notes through a preview-and-explicit-approval flow."""
from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from typing import Mapping

from .ankiconnect import AnkiConnect
from .duplicates import DuplicateChecker, DuplicateMatch
from .preview import NoteChangePreview, NotePreview, PreviewService


class MutationError(Exception):
    """Base class for note mutation workflow errors."""


class ApprovalRejectedError(MutationError):
    pass


class StaleProposalError(MutationError):
    pass


class MutationOutcomeUnknown(MutationError):
    pass


class DuplicateReviewRequired(MutationError):
    def __init__(self, preview: NotePreview, matches: list[DuplicateMatch]):
        super().__init__("Possible duplicates were found; review them before proposing a new note")
        self.preview = preview
        self.matches = tuple(matches)


@dataclass(frozen=True)
class OperationProposal:
    proposal_id: str
    operation: str
    preview: NotePreview | NoteChangePreview


@dataclass(frozen=True)
class MutationResult:
    operation: str
    note_id: int


@dataclass(frozen=True)
class AddNoteRequest:
    deck: str
    note_type: str
    fields: Mapping[str, str]
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class UpdateNoteRequest:
    note_id: int
    fields: Mapping[str, str]


@dataclass(frozen=True)
class BatchProposal:
    batch_id: str
    proposals: tuple[OperationProposal, ...]


@dataclass(frozen=True)
class BatchOperationResult:
    proposal_id: str
    status: str
    result: MutationResult | None = None
    error: str | None = None


@dataclass(frozen=True)
class BatchResult:
    batch_id: str
    operations: tuple[BatchOperationResult, ...]


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

    def __init__(
        self,
        anki: AnkiConnect,
        previews: PreviewService | None = None,
        duplicates: DuplicateChecker | None = None,
    ):
        self.anki = anki
        self.previews = previews or PreviewService(anki)
        self.duplicates = duplicates or DuplicateChecker(anki)
        self._pending: dict[str, _PendingOperation] = {}
        self._batches: dict[str, BatchProposal] = {}
        self._batch_status: dict[str, str] = {}

    def propose_add(
        self,
        *,
        deck: str,
        note_type: str,
        fields: Mapping[str, str],
        tags: tuple[str, ...] | list[str] = (),
        allow_possible_duplicates: bool = False,
        semantic_candidate_ids: tuple[int, ...] | list[int] = (),
    ) -> OperationProposal:
        if deck not in self.anki.deck_names():
            raise ValueError(f"Unknown deck: {deck}")
        if note_type not in self.anki.model_names():
            raise ValueError(f"Unknown note type: {note_type}")
        normalized_tags = tuple(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        preview = self.previews.preview_new(note_type, fields, deck=deck, tags=normalized_tags)
        duplicate_matches = self.duplicates.find(
            note_type,
            preview.fields,
            semantic_candidate_ids=semantic_candidate_ids,
        )
        if duplicate_matches and not allow_possible_duplicates:
            raise DuplicateReviewRequired(preview, duplicate_matches)
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

    def propose_batch(self, requests: list[AddNoteRequest | UpdateNoteRequest]) -> BatchProposal:
        if not requests:
            raise ValueError("A batch must contain at least one operation")
        proposals: list[OperationProposal] = []
        try:
            for request in requests:
                if isinstance(request, AddNoteRequest):
                    proposal = self.propose_add(
                        deck=request.deck,
                        note_type=request.note_type,
                        fields=request.fields,
                        tags=request.tags,
                    )
                elif isinstance(request, UpdateNoteRequest):
                    proposal = self.propose_update(request.note_id, request.fields)
                else:
                    raise TypeError(f"Unsupported batch request: {type(request).__name__}")
                proposals.append(proposal)
        except Exception:
            for proposal in proposals:
                self.cancel(proposal.proposal_id)
            raise
        batch = BatchProposal(secrets.token_urlsafe(12), tuple(proposals))
        self._batches[batch.batch_id] = batch
        self._batch_status[batch.batch_id] = "pending"
        return batch

    def confirm_batch(self, batch_id: str, decisions: Mapping[str, str]) -> BatchResult:
        batch = self._batches.get(batch_id)
        if batch is None:
            raise MutationError("Batch proposal was not found")
        if self._batch_status.get(batch_id) != "pending":
            raise MutationError(f"Batch cannot be applied in state: {self._batch_status[batch_id]}")
        self._batch_status[batch_id] = "applying"
        results = []
        for proposal in batch.proposals:
            try:
                result = self.confirm(
                    proposal.proposal_id,
                    user_response=decisions.get(proposal.proposal_id, ""),
                )
            except ApprovalRejectedError:
                results.append(BatchOperationResult(proposal.proposal_id, "rejected"))
            except Exception as exc:
                results.append(BatchOperationResult(proposal.proposal_id, "failed", error=str(exc)))
            else:
                results.append(BatchOperationResult(proposal.proposal_id, "applied", result=result))
        self._batch_status[batch_id] = "completed"
        return BatchResult(batch_id, tuple(results))

    def cancel_batch(self, batch_id: str) -> None:
        batch = self._batches.get(batch_id)
        if batch is None:
            raise MutationError("Batch proposal was not found")
        if self._batch_status.get(batch_id) != "pending":
            raise MutationError(f"Batch cannot be cancelled in state: {self._batch_status[batch_id]}")
        for proposal in batch.proposals:
            self.cancel(proposal.proposal_id)
        self._batch_status[batch_id] = "cancelled"

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
