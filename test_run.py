"""Primo test: solo letture da Anki, scrive la documentazione in ./collection_docs."""
from anki_agent.ankiconnect import AnkiConnect
from anki_agent.storage import LocalStorage
from anki_agent.docs_gen import refresh_note_type_docs, refresh_deck_docs

ac = AnkiConnect()
print("AnkiConnect versione:", ac.version())
print("Deck:", ac.deck_names())
print("Tipi di nota:", ac.model_names())

st = LocalStorage("./collection_docs")
print("Scritti:", refresh_note_type_docs(ac, st))
print("Scritti:", refresh_deck_docs(ac, st))
