# Roadmap — Anki Agent

I test iniziano fin dalle prime iterazioni: test automatici locali per la logica e, quando serve Anki, prove d'integrazione con Anki Desktop e una collezione di test. L'iterazione 10 aggiungerà i test del collegamento remoto da ChatGPT.

## 01 - Collegamento e inventario *(completata)*

**Obiettivo:** collegarsi ad Anki in sola lettura e generare una prima documentazione della collezione.

- Collegarsi tramite AnkiConnect.
- Leggere versione, deck e tipi di nota.
- Generare i file Markdown per deck e tipi di nota.
- Verificare lo script con Anki Desktop aperto.

## 02 - Struttura dei tipi di nota

**Obiettivo:** documentare come sono fatte le note e quali card producono.

- Leggere campi, template e CSS da AnkiConnect.
- Documentare il ruolo dei campi e i template fronte/retro.
- Rilevare le card generate, incluse le varianti Cloze.
- Aggiornare i documenti senza sovrascrivere le note manuali.
- Aggiungere test automatici con risposte Anki simulate.

## 03 - Convenzioni e conoscenza della collezione

**Obiettivo:** affiancare ai dati tecnici le regole utili a scegliere e compilare le note.

- Definire un formato per convenzioni di deck e campi.
- Registrare preferenze e informazioni confermate dall'utente.
- Separare dati rilevati automaticamente da contenuti manuali.
- Verificare che la rigenerazione preservi le sezioni manuali.

## 04 - Ricerca e lettura delle note

**Obiettivo:** trovare note esistenti e mostrarne i contenuti senza modificarle.

- Aggiungere ricerca per testo, deck, tipo di nota e tag.
- Leggere tutti i campi delle note selezionate.
- Restituire risultati chiari e limitati alla richiesta.
- Testare query, risultati vuoti ed errori di connessione.

## 05 - Anteprima delle operazioni

**Obiettivo:** mostrare in anticipo l'effetto di una creazione o modifica.

- Rappresentare note e card generate con i template disponibili.
- Per le modifiche, confrontare stato attuale e proposto.
- Evidenziare le card e i campi coinvolti.
- Verificare anteprime con tipi di nota semplici e complessi.

## 06 - Creazione e modifica approvate

**Obiettivo:** applicare operazioni sulle note solo dopo l'approvazione esplicita.

- Implementare creazione e modifica tramite AnkiConnect.
- Richiedere approvazione dopo aver mostrato l'anteprima.
- Ricontrollare i dati subito prima della scrittura.
- Testare annullamento, errori e conferma dell'esito.

## 07 - Duplicati e richieste multiple

**Obiettivo:** gestire ambiguità e richieste che producono più modifiche.

- Cercare corrispondenze esatte e possibili duplicati.
- Chiedere come procedere quando il risultato è ambiguo.
- Presentare un'unica anteprima per operazioni multiple.
- Consentire approvazione o rifiuto delle singole operazioni.

## 08 - Deck, tag ed eliminazioni

**Obiettivo:** estendere le operazioni alla struttura della collezione.

- Aggiungere gestione dei tag e spostamento delle note tra deck.
- Definire le operazioni supportate sui deck.
- Mostrare l'elemento esatto prima di ogni eliminazione.
- Richiedere una conferma aggiuntiva per le eliminazioni.

## 09 - Storico e recupero

**Obiettivo:** rendere tracciabili le operazioni e gestire gli errori in modo recuperabile.

- Registrare richiesta, anteprima, approvazione, operazione ed esito.
- Rendere lo storico consultabile dall'utente.
- Valutare quali operazioni possono essere annullate o ripristinate.
- Testare registrazioni incomplete e interruzioni durante le operazioni.

## 10 - Collegamento remoto e ChatGPT

**Obiettivo:** usare l'agente da ChatGPT senza richiedere accesso locale al PC.

- Scegliere l'architettura di bridge remoto e connettore.
- Definire autenticazione, isolamento dei dati e gestione delle credenziali.
- Collegare le funzioni dell'agente all'interfaccia remota.
- Testare il flusso completo da ChatGPT ad Anki e ritorno.

## 11 - Distribuzione e rifinitura

**Obiettivo:** preparare il progetto per configurazioni e collezioni diverse.

- Rendere configurabili connessione e spazio di documentazione.
- Separare i dati e le impostazioni per ogni utente.
- Completare istruzioni di installazione, uso e recupero dagli errori.
- Eseguire una verifica end-to-end su un'installazione pulita.
