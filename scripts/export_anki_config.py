"""Export current deck, note type, and field names to anki_config/."""
from __future__ import annotations

import sys

from anki_agent.cli import main

if __name__ == "__main__":
    raise SystemExit(main(["export-config", *sys.argv[1:]]))
