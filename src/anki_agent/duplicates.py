"""Find exact, similar, and externally identified semantic note duplicates."""
from __future__ import annotations

import html
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Callable, Mapping

from .ankiconnect import AnkiConnect
from .reader import NoteReader, NoteRecord

SemanticMatcher = Callable[[Mapping[str, str], NoteRecord], bool | float]


class DuplicateMatch:
    def __init__(
        self,
        note: NoteRecord,
        match_type: str,
        score: float,
        matched_fields: tuple[str, ...],
    ):
        self.note = note
        self.match_type = match_type
        self.score = score
        self.matched_fields = matched_fields


def _normalize(value: str) -> str:
    plain_text = re.sub(r"<[^>]*>", " ", html.unescape(value))
    return " ".join(unicodedata.normalize("NFKC", plain_text).casefold().split())


def _anchor(value: str) -> str:
    terms = re.findall(r"\w+", value)
    return max(terms, key=len) if terms else value.strip()


class DuplicateChecker:
    """Search a note type for exact or near matches before creating a note.

    A semantic matcher may score retrieved candidates. Callers may also supply
    note IDs selected by an external semantic review, such as a ChatGPT layer.
    """

    def __init__(
        self,
        anki: AnkiConnect,
        *,
        limit_per_query: int = 25,
        similarity_threshold: float = 0.82,
        semantic_matcher: SemanticMatcher | None = None,
    ):
        if limit_per_query < 1:
            raise ValueError("limit_per_query must be positive")
        if not 0 <= similarity_threshold <= 1:
            raise ValueError("similarity_threshold must be between 0 and 1")
        self.anki = anki
        self.reader = NoteReader(anki)
        self.limit_per_query = limit_per_query
        self.similarity_threshold = similarity_threshold
        self.semantic_matcher = semantic_matcher

    def find(
        self,
        note_type: str,
        fields: Mapping[str, str],
        *,
        semantic_candidate_ids: tuple[int, ...] | list[int] = (),
    ) -> list[DuplicateMatch]:
        normalized_fields = {name: _normalize(value) for name, value in fields.items()}
        if not any(normalized_fields.values()):
            return []

        candidates: dict[int, NoteRecord] = {}
        queried_anchors: set[str] = set()
        for value in normalized_fields.values():
            if not value:
                continue
            anchor = _anchor(value)
            if not anchor or anchor in queried_anchors:
                continue
            queried_anchors.add(anchor)
            for note in self.reader.search(
                text=anchor,
                note_type=note_type,
                limit=self.limit_per_query,
            ):
                candidates[note.note_id] = note

        for note in self.reader.read(list(semantic_candidate_ids)):
            if note.note_type == note_type:
                candidates[note.note_id] = note

        matches: list[DuplicateMatch] = []
        for note in candidates.values():
            if note.note_type != note_type:
                continue
            candidate_fields = {name: _normalize(value) for name, value in note.fields.items()}
            if normalized_fields == candidate_fields:
                matches.append(DuplicateMatch(note, "exact", 1.0, tuple(sorted(normalized_fields))))
                continue

            field_scores = {
                name: SequenceMatcher(None, value, candidate_fields.get(name, "")).ratio()
                for name, value in normalized_fields.items()
                if value
            }
            if not field_scores:
                continue
            average_score = sum(field_scores.values()) / len(field_scores)
            matched_fields = tuple(sorted(name for name, score in field_scores.items() if score >= 0.8))
            if average_score >= self.similarity_threshold and matched_fields:
                matches.append(DuplicateMatch(note, "similar", average_score, matched_fields))
                continue

            if self.semantic_matcher is not None:
                semantic_result = self.semantic_matcher(fields, note)
                if semantic_result is True:
                    semantic_score = 1.0
                elif semantic_result is False:
                    continue
                else:
                    semantic_score = float(semantic_result)
                if semantic_score >= self.similarity_threshold:
                    matches.append(
                        DuplicateMatch(note, "semantic", semantic_score, matched_fields)
                    )

        rank = {"exact": 0, "similar": 1, "semantic": 2}
        return sorted(matches, key=lambda match: (rank[match.match_type], -match.score, match.note.note_id))
