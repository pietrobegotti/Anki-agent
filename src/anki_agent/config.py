"""Environment-based application configuration and per-user storage paths."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .ankiconnect import AnkiConnect
from .storage import LocalStorage


@dataclass(frozen=True)
class AgentConfig:
    anki_url: str
    anki_api_key: str | None
    anki_timeout: int
    data_dir: Path
    user_id: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "AgentConfig":
        env = os.environ if environ is None else environ
        url = env.get("ANKI_CONNECT_URL", "http://127.0.0.1:8765").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("ANKI_CONNECT_URL must be an HTTP or HTTPS URL")
        try:
            timeout = int(env.get("ANKI_CONNECT_TIMEOUT", "15"))
        except ValueError as exc:
            raise ValueError("ANKI_CONNECT_TIMEOUT must be a positive integer") from exc
        if timeout < 1:
            raise ValueError("ANKI_CONNECT_TIMEOUT must be a positive integer")
        user_id = env.get("ANKI_AGENT_USER_ID", "default").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", user_id):
            raise ValueError("ANKI_AGENT_USER_ID may contain only letters, numbers, _ and -")
        data_dir = Path(env.get("ANKI_AGENT_DATA_DIR", "./collection_docs")).expanduser().resolve()
        api_key = env.get("ANKI_CONNECT_API_KEY", "").strip() or None
        return cls(url, api_key, timeout, data_dir, user_id)

    @property
    def storage_root(self) -> Path:
        return self.data_dir / self.user_id

    def create_anki(self) -> AnkiConnect:
        return AnkiConnect(self.anki_url, api_key=self.anki_api_key, timeout=self.anki_timeout)

    def create_storage(self) -> LocalStorage:
        return LocalStorage(self.storage_root)
