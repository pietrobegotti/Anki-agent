# Istruzioni per l'LLM

- Crea una carta per ogni parola richiesta e salva un file JSON direttamente in `cards/`.
- Usa il template qui sotto senza aggiungere, rimuovere o rinominare campi. Scrivi solo JSON valido nel file, senza blocchi Markdown o testo aggiuntivo.
- Nomina il file `<id>_<word>.json`. Usa la parola giapponese in `<word>` e un ID progressivo a sei cifre: parti dal numero successivo a quello già presente in `cards/`; se non ci sono carte, inizia da `000001`. Non riutilizzare ID e non sovrascrivere file.
- Non chiedere all'utente di eseguire script.

## Template JSON

```json
{
  "id": "000001",
  "word": "[parola]",
  "furigana": "[lettura della parola]",
  "translation": "[traduzione italiana, o nella lingua richiesta]",
  "meaning": "[nota molto breve sulla nuance, l'uso o la connotazione; non una definizione]",
  "compound": "[sottoparola：traduzione italiana\nsottoparola：traduzione italiana; vuoto se la parola non è un composto lungo]",
  "synonyms": "[da zero a tre sinonimi; vuoto per i composti]",
  "antonyms": "[da zero a tre contrari; vuoto per i composti]",
  "kanji": "[kanji]\t[letture Takoboto]\t[traduzioni Takoboto]\n[kanji]\t[letture Takoboto]\t[traduzioni Takoboto]",
  "example": "[frase giapponese] — [traduzione italiana]\n[frase giapponese] — [traduzione italiana]\n[frase giapponese] — [traduzione italiana]"
}
```

## Regole dei campi

- `meaning`: descrivi in modo super conciso la sfumatura o il contesto d'uso. Non ripetere la traduzione e non dare una definizione. Esempio per `処置`: `Si usa quando si prende una misura concreta per affrontare un problema o una situazione, spesso in ambito medico o pratico.`
- `compound`: compilalo per le parole composte lunghe, scomponendole in sottoparole significative e traducendo ciascuna in italiano, una per riga nel formato `sottoparola：traduzione`. Per esempio: `伝統：tradizione\n工芸：arti e mestieri artigianali`. Lascialo vuoto se la parola non è un composto lungo.
- `synonyms` e `antonyms`: inserisci da zero a tre parole, separate da virgole; lasciali sempre vuoti per i composti, anche quando `compound` è vuoto. Per le parole non composte, lasciali vuoti se non trovi sinonimi o contrari adatti.
- `kanji`: leggi `info/Takoboto.enriched.json`. Per ogni kanji distinto presente in `word`, cerca l'elemento che ha quel kanji come chiave e copia `reading` e `translation` esattamente dal Takoboto. Elenca i kanji nell'ordine in cui appaiono nella parola, uno per riga. Separa kanji, lettura e traduzione con tabulazioni (`\t`) e le righe con newline (`\n`). Non aggiungere altri campi kanji. Se un carattere non è presente nel file, chiedi chiarimento prima di creare la carta; non inventare i dati.
- `example`: inserisci esattamente tre frasi o espressioni giapponesi che usano la parola; aggiungi la traduzione italiana sulla stessa riga dopo ` — `.
- `id`: stringa numerica di sei cifre, coerente con il nome del file e con la progressione esistente.
