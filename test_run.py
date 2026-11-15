"""First smoke test: read from Anki and write documentation to ./collection_docs."""
from anki_agent.ankiconnect import AnkiConnect
from anki_agent.storage import LocalStorage
from anki_agent.docs_gen import refresh_note_type_docs, refresh_deck_docs

ac = AnkiConnect()
print("AnkiConnect version:", ac.version())
print("Decks:", ac.deck_names())
print("Note types:", ac.model_names())

st = LocalStorage("./collection_docs")
print("Written:", refresh_note_type_docs(ac, st))
print("Written:", refresh_deck_docs(ac, st))
