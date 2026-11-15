"""Backward-compatible local connection and documentation smoke test."""
from anki_agent.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["smoke"]))
