"""Minimal AnkiConnect client (standard library only)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

WRITE_ACTIONS = frozenset(
    {
        "addNote",
        "addNotes",
        "updateNoteFields",
        "updateNote",
        "updateNoteModel",
        "updateNoteTags",
        "addTags",
        "removeTags",
        "deleteNotes",
        "createDeck",
        "deleteDecks",
        "changeDeck",
        "changeNoteDeck",
        "updateModelTemplates",
        "updateModelStyling",
    }
)
APPROVED_NOTE_WRITE_ACTIONS = frozenset(
    {"addNote", "updateNoteFields", "addTags", "removeTags", "changeDeck", "deleteNotes"}
)


class AnkiConnectError(Exception):
    pass


class AnkiConnect:
    def __init__(self, url: str = "http://127.0.0.1:8765", api_key: str | None = None, timeout: int = 15):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def invoke(self, action: str, **params: Any) -> Any:
        if action in WRITE_ACTIONS:
            raise AnkiConnectError(
                "Collection writes must go through the explicit approval flow in NoteMutationService"
            )
        return self._request(action, **params)

    def _invoke_approved_write(self, action: str, **params: Any) -> Any:
        """Internal write path used only after a mutation proposal is approved."""
        if action not in APPROVED_NOTE_WRITE_ACTIONS:
            raise AnkiConnectError(f"Unsupported write action: {action}")
        return self._request(action, **params)

    def _request(self, action: str, **params: Any) -> Any:
        payload: dict[str, Any] = {"action": action, "version": 6, "params": params}
        if self.api_key:
            payload["key"] = self.api_key
        req = urllib.request.Request(
            self.url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.load(resp)
        except (urllib.error.URLError, TimeoutError) as e:
            raise AnkiConnectError(
                f"Could not reach AnkiConnect at {self.url}: {e}. "
                "Is Anki Desktop running with the add-on installed?"
            ) from e
        if data.get("error"):
            raise AnkiConnectError(f"{action}: {data['error']}")
        return data.get("result")

    # --- read actions ---
    def version(self) -> int:
        return self.invoke("version")

    def deck_names(self) -> list[str]:
        return self.invoke("deckNames")

    def model_names(self) -> list[str]:
        return self.invoke("modelNames")

    def model_field_names(self, model: str) -> list[str]:
        return self.invoke("modelFieldNames", modelName=model)

    def model_templates(self, model: str) -> dict[str, dict[str, str]]:
        return self.invoke("modelTemplates", modelName=model)

    def model_styling(self, model: str) -> str:
        return self.invoke("modelStyling", modelName=model).get("css", "")

    def find_notes(self, query: str) -> list[int]:
        return self.invoke("findNotes", query=query)

    def find_cards(self, query: str) -> list[int]:
        return self.invoke("findCards", query=query)

    def notes_info(self, note_ids: list[int]) -> list[dict]:
        return self.invoke("notesInfo", notes=note_ids)

    def cards_info(self, card_ids: list[int]) -> list[dict]:
        return self.invoke("cardsInfo", cards=card_ids)

    def sync_with_ankiweb(self) -> None:
        """Ask the running Anki Desktop client to sync its local collection."""
        self.invoke("sync")
