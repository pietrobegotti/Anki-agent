# Roadmap di implementazione: caricare in Anki le carte discusse in chat

## Obiettivo

Consentire all'utente di discutere e preparare carte Anki durante una normale
conversazione con ChatGPT e, quando dice «carica queste carte in Anki», rivedere
una proposta aggregata e approvarne il caricamento. La conversazione fornisce il
contenuto; il plugin lo trasforma in note Anki usando tipo di nota, campi,
mazzo, tag e convenzioni della collezione.

Il plugin non deve interpretare una semplice menzione di una carta come
autorizzazione a scrivere. La scrittura avviene solo dopo una richiesta esplicita
di caricamento e l'approvazione della proposta visualizzata.

## Esperienza finale desiderata

1. L'utente discute uno o più concetti con ChatGPT e chiede di trasformarli in
   carte, oppure l'assistente propone carte e l'utente le corregge.
2. L'assistente conserva nel contesto della conversazione una raccolta di bozze
   non ancora inviate ad Anki.
3. Alla richiesta «carica le carte», l'assistente raccoglie le bozze, completa i
   campi in base alle regole note e chiede chiarimenti per i dati mancanti o
   ambigui.
4. Il plugin controlla i duplicati e prepara un'anteprima di tutte le note e di
   tutte le carte generate dai rispettivi modelli.
5. L'utente può correggere, approvare o rifiutare le singole note. Nessuna
   scrittura avviene prima dell'approvazione.
6. Il plugin invia le note approvate ad Anki, restituisce gli esiti per ciascuna
   e registra le operazioni nella cronologia.

## Stato di partenza

Il repository contiene già componenti riutilizzabili:

- `src/anki_agent/remote.py`: API JSON remota con autenticazione bearer,
  contesti utente isolati, ricerca, proposte e conferme.
- `openapi.yaml`: contratto remoto iniziale per un connettore ChatGPT basato su
  OpenAPI / Actions.
- `src/anki_agent/mutations.py`: proposte di modifica con anteprima, approvazione
  esplicita, controllo di obsolescenza, cronologia e supporto a batch a livello
  di servizio.
- `src/anki_agent/duplicates.py`, `reader.py` e `preview.py`: ricerca note,
  controllo duplicati e anteprime delle carte.
- `src/anki_agent/docs_gen.py` e `storage.py`: documentazione della collezione
  su storage locale.

### Già implementato

La sequenza di branch `codex/chat-upload-*` ha aggiunto l'API batch, il server
MCP Streamable HTTP, le istruzioni per raccogliere le bozze dalla conversazione,
gli strumenti per consultare tipi di nota e guide, il generatore dell'archivio
plugin e la sincronizzazione AnkiWeb dopo una batch approvata.

### Architettura scelta e limiti

AnkiWeb sincronizza i client Anki ma non fornisce un'API pubblica supportata per
aggiungere note direttamente da un plugin esterno. La direzione preferita diventa
quindi una coda temporanea su Google Drive:

1. ChatGPT mostra l'anteprima e, dopo l'approvazione, scrive un file JSON per
   carta in una cartella privata di coda su Drive.
2. Un piccolo worker sul PC dell'utente controlla la coda quando il PC è acceso.
   Quando Anki Desktop e AnkiConnect sono disponibili, verifica di nuovo mazzo,
   tipo di nota e duplicati, poi importa le carte approvate.
3. Il worker chiede ad AnkiConnect di sincronizzare la collezione con AnkiWeb.
   Il telefono riceve le carte con la normale sincronizzazione AnkiDroid.

Il PC può restare spento mentre ChatGPT accoda le carte; l'importazione avviene
quando il PC torna disponibile. Se ChatGPT è usato dal PC mentre il worker e
Anki sono aperti, lo stesso flusso può importare le carte quasi subito. Non si
automatizzano endpoint privati di AnkiWeb.

I file devono avere un ID stabile, un ID batch, lo stato, il mazzo, il tipo di
nota e i campi. Il worker aggiorna lo stato in modo idempotente, mette in pausa
le carte con duplicati o errori e rimuove/archivia i file completati secondo una
scadenza configurata. L'accesso a Drive va limitato ai file dell'app tramite
OAuth `drive.file`; il worker locale e il plugin devono condividere una
configurazione OAuth valida per lo stesso utente.

### Lavoro rimanente

La coda Drive e il worker Windows non sono ancora implementati. Restano da
realizzare OAuth Drive, la gestione dei file temporanei, il worker locale,
l'installazione del plugin/worker e una verifica end-to-end su una collezione di
prova. Il precedente server MCP con host sempre acceso resta una strada
alternativa, ma non è necessario per il flusso a coda scelto.

## Progetti di implementazione

### 1. Definire il formato della bozza di carta

Stabilire il formato strutturato che l'assistente userà quando riconosce una
carta nella conversazione: mazzo, tipo di nota, campi, tag e, facoltativamente,
riferimento alla parte della conversazione da cui deriva. Definire come
rappresentare bozze incomplete e come modificarle o rimuoverle.

**Risultato:** un contratto semplice e stabile fra istruzioni del plugin e API;
non si dipende dal testo libero per ricostruire i campi al momento del
caricamento.

### 2. Progettare la raccolta per conversazione

Decidere dove risiedono le bozze e come sono associate alla chat. Per la prima
versione si può far mantenere la raccolta all'assistente nella conversazione e
inviare al backend il lotto completo solo quando l'utente chiede il caricamento.
Se le bozze devono sopravvivere a riavvii, cambi di dispositivo o chat diverse,
serve invece uno storage remoto con identificativi, scadenze e isolamento per
utente.

**Risultato:** comportamento chiaro per «aggiungi questa alla lista», «mostrami
le bozze», «rimuovi la seconda» e «carica le carte».

### 3. Preparare e convalidare il lotto

Aggiungere un'operazione API che accetti un insieme di bozze, verifichi mazzi,
tipi di nota, campi obbligatori e valori, e segnali i dati mancanti senza
indovinare. L'assistente deve poter consultare inventario e convenzioni prima
di comporre le note.

**Risultato:** le bozze vengono trasformate in operazioni Anki valide e
tracciabili; le domande di chiarimento avvengono prima dell'anteprima finale.

### 4. Esporre proposte batch nell'API remota

Collegare il supporto batch già presente in `NoteMutationService` al gateway e
al contratto OpenAPI. Il batch deve avere un identificativo, un esito e uno
stato espliciti; ogni nota deve restare approvabile o rifiutabile
individualmente. Rendere idempotenti le richieste o proteggere dai doppi invii,
così un timeout non crea duplicati se il client riprova.

**Risultato:** una sola proposta aggregata per le carte della conversazione,
con conferma controllata per ciascuna operazione e risposta recuperabile.

### 5. Definire il comportamento del plugin in chat

Creare le istruzioni e gli strumenti del plugin per:

- riconoscere quando il contenuto è una bozza e quando è una richiesta di
  caricamento;
- mantenere e aggiornare la raccolta durante la chat;
- chiedere il mazzo o il tipo di nota se non determinabili dalle preferenze;
- presentare anteprima e duplicati in modo leggibile;
- inviare conferme solo in risposta a un'approvazione chiara;
- riportare risultati parziali e non ritentare alla cieca gli esiti incerti.

**Risultato:** l'esperienza «discutiamo, poi carica» è naturale e non richiede
all'utente di costruire manualmente richieste JSON.

### 6. Scegliere e configurare la superficie del plugin

Usare inizialmente il contratto OpenAPI esistente se la priorità è arrivare
rapidamente a un'integrazione conversazionale. Se si vogliono strumenti MCP o
una vista interattiva dedicata per modificare e approvare il lotto, progettare
il relativo adattatore e l'interfaccia come lavoro aggiuntivo. In entrambi i
casi il servizio deve essere raggiungibile via HTTPS e configurato con
autenticazione; AnkiConnect resta locale alla macchina che ospita la collezione.

**Risultato:** plugin collegato a un endpoint reale, con credenziali gestite
come segreti e istruzioni coerenti con le operazioni supportate.

### 7. Deployment, configurazione utente e storage

Predisporre un deployment del gateway, TLS, gestione dei token, avvio e
monitoraggio del servizio. Documentare come collegare una collezione Anki e
separare configurazione, documenti e cronologia per utente. Decidere se la
prima versione usa storage locale sulla macchina del gateway o se implementa
Google Drive; quest'ultimo è un elemento previsto dal progetto ma non presente.

**Risultato:** installazione ripetibile e accesso remoto sicuro dalla chat.

### 8. Verifica end-to-end e distribuzione

Provare conversazioni complete con una collezione di test: una carta, lotto
misto, campi mancanti, duplicati, correzioni, rifiuto, approvazione parziale,
timeout, ripetizione della richiesta e risultato incerto. Verificare che nessuna
nota venga scritta senza approvazione e che l'esito in chat corrisponda allo
stato effettivo in Anki. Poi preparare configurazione, istruzioni d'uso e
modalità di distribuzione o condivisione del plugin.

**Risultato:** un'integrazione pronta all'uso, verificata nel percorso reale
dalla conversazione alla collezione.

## Sequenza consigliata per la prima versione

1. Definire il formato delle bozze e il comportamento della raccolta nella
   singola conversazione.
2. Aggiungere l'endpoint batch e aggiornare `openapi.yaml`.
3. Scrivere istruzioni e strumenti del plugin per raccolta, anteprima e
   approvazione.
4. Rendere disponibile il gateway su HTTPS e configurare credenziali e
   isolamento utente.
5. Eseguire la verifica end-to-end e collegare il plugin al client.

Google Drive e una vista MCP personalizzata possono seguire, salvo che siano
requisiti per la prima installazione. La prima versione può usare la chat
corrente come raccolta temporanea delle bozze, purché il plugin invii al backend
un lotto esplicito e ottenga una conferma prima di ogni scrittura.

## Decisioni aperte

- Il mazzo e il tipo di nota predefiniti: preferenze configurate o richiesta
  ogni volta?
- Le bozze devono sopravvivere alla chat o basta la conversazione corrente?
- Il caricamento deve essere tutto-o-niente oppure consentire approvazioni
  parziali per singola carta?
- Per la prima versione si usa l'Action OpenAPI oppure si investe subito in
  un'interfaccia MCP dedicata?
- Dove viene ospitato il gateway e dove sono conservati documentazione e
  cronologia per utente?

## Criterio di completamento

L'obiettivo è raggiunto quando, in una chat nuova con il plugin attivo, l'utente
può discutere più carte, chiedere di caricarle, vedere e correggere un'anteprima
completa con i duplicati segnalati, approvare o rifiutare le singole note e
ricevere un riepilogo affidabile dell'esito, senza scritture implicite.
