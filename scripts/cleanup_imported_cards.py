"""Remove completed legacy import requests; does not clean LLM card files."""
from __future__ import annotations

import sys

from anki_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["cleanup-cards", *sys.argv[1:]]))
