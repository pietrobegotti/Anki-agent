"""Append-only, human-readable history for note mutation workflows."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from .storage import Storage


class MutationHistory:
    """Store mutation lifecycle events in monthly Markdown files."""

    def __init__(self, storage: Storage):
        self.storage = storage

    def record(self, proposal_id: str, event: str, **details: Any) -> None:
        now = datetime.now(timezone.utc)
        payload = {"proposal_id": proposal_id, "event": event, **details}
        rendered = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, indent=2)
        self.storage.append(
            f"history/{now:%Y-%m}.md",
            f"## {now:%Y-%m-%d %H:%M:%S}Z — {event} ({proposal_id})\n\n"
            f"```json\n{rendered}\n```\n\n",
        )

    def read(self) -> str:
        """Return the stored history as one readable Markdown document."""
        return "\n".join(
            self.storage.read(path) or ""
            for path in self.storage.list("history/")
        )

    def recovery_status(self) -> dict[str, list[str]]:
        """Summarize proposals interrupted before a known result.

        Unknown write outcomes are reported separately and must be inspected
        manually; they are never safe to retry automatically.
        """
        events: dict[str, str] = {}
        document = self.read()
        for block in re.findall(r"```json\s*(.*?)\s*```", document, flags=re.DOTALL):
            try:
                payload = json.loads(block)
                events[payload["proposal_id"]] = payload["event"]
            except (ValueError, KeyError, TypeError):
                continue
        uncertain = sorted(key for key, event in events.items() if event == "outcome_unknown")
        terminal = {"applied", "rejected", "cancelled", "outcome_unknown"}
        incomplete = sorted(key for key, event in events.items() if event not in terminal)
        return {"incomplete": incomplete, "outcome_unknown": uncertain}

