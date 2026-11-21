"""Import approved request JSON files from the synchronized cards folder."""
from __future__ import annotations

import sys

from anki_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["import-cards", *sys.argv[1:]]))
