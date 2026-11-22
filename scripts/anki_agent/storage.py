"""Documentation storage: abstract interface and local implementation.

The next step will be a GoogleDriveStorage implementation with the same interface.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def read(self, path: str) -> str | None: ...

    @abstractmethod
    def write(self, path: str, text: str) -> None: ...

    @abstractmethod
    def append(self, path: str, text: str) -> None: ...

    @abstractmethod
    def list(self, prefix: str = "") -> list[str]: ...


class LocalStorage(Storage):
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, path: str) -> Path:
        p = (self.root / path).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError(f"Invalid path: {path}")
        if p.suffix != ".md":
            raise ValueError("Only .md files are allowed")
        return p

    def read(self, path: str) -> str | None:
        p = self._resolve(path)
        return p.read_text(encoding="utf-8") if p.exists() else None

    def write(self, path: str, text: str) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")

    def append(self, path: str, text: str) -> None:
        p = self._resolve(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(text)

    def list(self, prefix: str = "") -> list[str]:
        return sorted(
            str(p.relative_to(self.root)).replace("\\", "/")
            for p in self.root.rglob("*.md")
            if str(p.relative_to(self.root)).replace("\\", "/").startswith(prefix)
        )


def log_line(storage: Storage, message: str) -> None:
    """Append a line to the monthly log at log/YYYY-MM.md."""
    now = datetime.now(timezone.utc)
    storage.append(f"log/{now:%Y-%m}.md", f"- {now:%Y-%m-%d %H:%M}Z — {message}\n")
