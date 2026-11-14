"""Client minimale per AnkiConnect (solo libreria standard)."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class AnkiConnectError(Exception):
    pass


class AnkiConnect:
    def __init__(self, url: str = "http://127.0.0.1:8765", api_key: str | None = None, timeout: int = 15):
        self.url = url
        self.api_key = api_key
        self.timeout = timeout

    def invoke(self, action: str, **params: Any) -> Any:
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
                f"AnkiConnect non raggiungibile su {self.url}: {e}. "
                "Anki Desktop è aperto e il plugin installato?"
            ) from e
        if data.get("error"):
            raise AnkiConnectError(f"{action}: {data['error']}")
        return data.get("result")

    # --- lettura ---
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
