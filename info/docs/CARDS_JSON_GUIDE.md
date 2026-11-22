# Guida: come inserire le carte nel JSON

Questa guida spiega come preparare una richiesta JSON per aggiungere carte ad Anki tramite la coda in `cards/`. Per il formato completo vedi `info/docs/DRIVE_QUEUE_SCHEMA.md`. Per le regole di contenuto vedi `info/anki_config/generation_instructions.md`.

## Prima di iniziare

1. Leggi `info/anki_config/collection_config.md`. Contiene i nomi esatti di deck, note type e campi della tua collezione. Usa solo quei nomi.
2. Se una destinazione o il significato di un campo non è chiaro, chiedi prima. Non inventare nomi di deck, note type o campi.
3. Mostra all'utente le carte proposte (deck, note type, campi, tag) e attendi la sua approvazione esplicita.

## Dove salvare

- Un file per ogni richiesta, direttamente nella cartella `cards/`.
- Il nome del file deve essere `<request_id>.json`, dove `<request_id>` è esattamente il valore di `request_id` contenuto nel file. Ad esempio, se `request_id` è `5f2c9a1e-3b7d-4e8a-9c01-2d6f4a8b7e13`, il file si chiama `5f2c9a1e-3b7d-4e8a-9c01-2d6f4a8b7e13.json`.
- Una richiesta può contenere più carte.
- Non modificare una richiesta già salvata. Per correzioni crea una nuova richiesta con nuovi ID.

## Struttura del file

```json
{
  "schema_version": 1,
  "request_id": "unique-request-id",
  "created_at": "2026-11-21T00:00:00Z",
  "approved": true,
  "cards": [
    {
      "card_id": "unique-card-id",
      "deck": "Exact deck name",
      "note_type": "Exact note type",
      "fields": {"Front": "Question", "Back": "Answer"},
      "tags": ["chatgpt"]
    }
  ]
}
```

### Campi della richiesta

- `schema_version`: sempre `1`.
- `request_id`: ID unico della richiesta. Non riutilizzarlo.
- `created_at`: data e ora in formato ISO 8601 UTC, ad esempio `2026-11-21T08:30:00Z`.
- `approved`: `true` solo dopo che l'utente ha approvato il contenuto delle carte. Altrimenti le carte non vengono importate.
- `cards`: lista di carte.

### Campi di ogni carta

- `card_id`: ID unico e stabile della carta. Deve restare lo stesso in caso di nuovo tentativo.
- `deck`: nome esatto del deck, come in `collection_config.md`. Per i sottodeck usa `::`, ad esempio `Japanese::Vocabulary`.
- `note_type`: nome esatto del note type, ad esempio `Basic`.
- `fields`: oggetto con i valori dei campi. Le chiavi sono i nomi esatti dei campi del note type. Includi solo i campi supportati da quel note type. Tutti i valori devono essere stringhe.
- `tags`: lista di tag come stringhe. Può essere vuota (`[]`).

## Regole importanti

- Gli ID (`request_id` e `card_id`) devono essere unici e stabili. Per generarli usa un UUID v4 oppure una stringa casuale simile.
- Ogni nota deve verificare un solo fatto o una sola abilità.
- Il fronte deve essere chiaro e focalizzato. Il retro deve essere conciso ma completo.
- Mantieni la lingua originale e la terminologia confermata dall'utente.
- Non aggiungere informazioni non fornite o non ragionevolmente implicite.
- Non inserire nel file trascrizioni della conversazione, credenziali o token.
- Non cancellare i file completati: la pulizia è un'operazione separata e manuale.

## Esempio completo

Il file di esempio va salvato come `5f2c9a1e-3b7d-4e8a-9c01-2d6f4a8b7e13.json`.

```json
{
  "schema_version": 1,
  "request_id": "5f2c9a1e-3b7d-4e8a-9c01-2d6f4a8b7e13",
  "created_at": "2026-11-21T08:30:00Z",
  "approved": true,
  "cards": [
    {
      "card_id": "a1b2c3d4-0001-4f5e-8a9b-111111111111",
      "deck": "Japanese::Vocabulary",
      "note_type": "Basic",
      "fields": {"Front": "食べる", "Back": "to eat"},
      "tags": ["chatgpt"]
    },
    {
      "card_id": "a1b2c3d4-0002-4f5e-8a9b-222222222222",
      "deck": "Japanese::Vocabulary",
      "note_type": "Basic",
      "fields": {"Front": "飲む", "Back": "to drink"},
      "tags": ["chatgpt"]
    }
  ]
}
```

Nell'esempio, il deck e il note type devono esistere nella tua collezione con quei nomi esatti. Verificalo in `collection_config.md` prima di usarlo.

## Dopo aver salvato il file

1. Attendi che Google Drive per desktop sincronizzi la cartella `cards/` sul PC.
2. Sul PC, con Anki Desktop e AnkiConnect attivi, esegui:

   ```powershell
   uv run python scripts/import_cards.py
   ```

3. Il worker valida la richiesta, controlla deck e note type, cerca duplicati e scrive le note approvate. Aggiorna lo stato di ogni carta direttamente nel file JSON.
4. Le carte già importate vengono registrate e non vengono reimportate.
5. Se un possibile duplicato viene trovato, la carta viene marcata `needs_review` e non importata automaticamente.
6. I file completati restano in `cards/` finché non esegui esplicitamente:

   ```powershell
   uv run python scripts/cleanup_imported_cards.py
   ```

   Questa operazione rimuove solo i file JSON le cui carte sono tutte importate. Non elimina né modifica le note in Anki.

## Errori comuni

- Nome di deck, note type o campo scritto diversamente da `collection_config.md`.
- Campo non presente nel note type selezionato.
- Valori non stringa, ad esempio numeri o `null`.
- `approved` impostato a `true` prima dell'approvazione dell'utente.
- `card_id` o `request_id` riutilizzati da una richiesta precedente.
- Nome del file diverso dal `request_id`.
- Virgole finali o virgolette non chiuse nel JSON.
- Anki Desktop o AnkiConnect non attivi durante l'import.
