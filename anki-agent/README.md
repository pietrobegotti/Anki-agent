# Anki Agent

Agente AI per gestire la propria collezione Anki (note, deck, tag, duplicati)
tramite [AnkiConnect](https://ankiweb.net/shared/info/2055492159).

**Stato:** step 1 — sola lettura + generazione della documentazione Markdown
della collezione (tipi di nota e deck). Nessuna scrittura su Anki.

## Requisiti

- Python 3.9+
- Anki Desktop aperto, con il plugin AnkiConnect (codice `2055492159`)

## Installazione

```bash
git clone <URL-del-repo>
cd anki-agent
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e .
```

## Primo test

```bash
python test_run.py
```

Stampa versione di AnkiConnect, deck e tipi di nota, poi genera la
documentazione in `collection_docs/` (ignorata da git: contiene dati personali).

Le sezioni `AUTO` dei file vengono rigenerate a ogni esecuzione; la sezione
"Note manuali" non viene mai sovrascritta.

## Struttura

```
src/anki_agent/
  ankiconnect.py   client minimale per AnkiConnect (solo libreria standard)
  storage.py       interfaccia Storage + LocalStorage
  docs_gen.py      generazione documentazione tipi di nota e deck
docs/              requisiti e documentazione di progetto
tests/
test_run.py        script di prova
```

## Roadmap

- [ ] Scritture su Anki (aggiungi/modifica/elimina note)
- [ ] Anteprima e approvazione prima di ogni operazione
- [ ] `GoogleDriveStorage` con la stessa interfaccia di `Storage`
- [ ] Integrazione con ChatGPT
