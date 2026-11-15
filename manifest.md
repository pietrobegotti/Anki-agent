# Anki Agent — Documento dei requisiti

**Versione:** 0.6  
**Stato:** raccolta e definizione dei requisiti  
**Ultimo aggiornamento:** 14 novembre 2026

---

## 1. Visione del progetto

Realizzare un agente AI che possa gestire direttamente la collezione Anki dell'utente attraverso ChatGPT.

L'esperienza desiderata è quella di parlare con un assistente che abbia accesso alla propria collezione Anki, senza dover gestire manualmente sincronizzazioni, dispositivi o connessioni tecniche.

Esempio:

> «Aggiungimi una nota per questa parola, con lettura, significato ed esempi».

L'agente analizza la richiesta, prepara una proposta, mostra un'anteprima e, dopo l'approvazione dell'utente, esegue l'operazione su Anki.

Il sistema dovrà essere:
- utilizzabile da ChatGPT su PC e smartphone;
- indipendente dal dispositivo utilizzato;
- personalizzabile per ogni utente;
- riutilizzabile e potenzialmente distribuibile pubblicamente;
- modulare, così da poter integrare in futuro funzionalità di studio e apprendimento.

## 2. Ambito della prima versione

La prima versione si concentra esclusivamente sulla **gestione della collezione Anki**.

Sono inclusi:
- creazione, modifica ed eliminazione di Note;
- gestione dei campi delle Note;
- comprensione dei diversi tipi di nota e dei relativi template;
- gestione dei Deck;
- gestione dei tag;
- individuazione dei duplicati;
- modifica della formattazione;
- anteprima delle operazioni;
- documentazione interna della collezione.

Sono rimandati a una fase successiva:
- gestione di immagini, audio e video;
- funzionalità di tutoraggio;
- pianificazione dello studio;
- analisi delle prestazioni e dei progressi;
- generazione di percorsi di apprendimento.

L'architettura dovrà comunque consentire di aggiungere queste funzionalità senza riscrivere il nucleo del sistema.

## 3. Modello di ragionamento: Note e Card

L'agente dovrà ragionare principalmente in termini di **Note**.

Una Nota contiene informazioni organizzate in campi. Il tipo di nota determina quali campi sono disponibili e come vengono utilizzati dai template per generare una o più Card.

L'agente dovrà comprendere:
- la differenza tra Note e Card;
- la struttura dei campi di ogni tipo di nota;
- il significato e la funzione di ciascun campo;
- il rapporto tra campi e template;
- quante Card vengono generate da una Nota;
- quali Card vengono influenzate dalla modifica di un campo.

Esempio: una Nota di tipo Basic and reversed può generare due Card. Una modifica alla Nota potrebbe quindi influenzarle entrambe.

L'agente dovrà sempre considerare tutte le conseguenze di una modifica alla Nota, non soltanto la Card che l'utente sta visualizzando.

## 4. Comprensione dei tipi di nota

L'agente dovrà essere in grado di analizzare e utilizzare diversi tipi di nota:

- Basic
- Basic (and reversed)
- Cloze
- Tipi di nota personalizzati

Dovrà poter esaminare:
- nomi e struttura dei campi;
- HTML dei template;
- CSS;
- condizioni di generazione delle Card;
- eventuali relazioni tra campi e template.

Dovrà comprendere anche le Cloze con più cancellazioni, ad esempio `{{c1::...}}` e `{{c2::...}}`, sapendo che possono generare Card differenti.

La modifica dei template non dovrà essere una pratica ordinaria. L'agente dovrà preservare il comportamento originale e potrà proporre modifiche soltanto in casi eccezionali, spiegando il problema e discutendo le alternative con l'utente.

## 5. Sistema di documentazione Markdown

L'agente dovrà disporre di una documentazione persistente, organizzata in file Markdown, che descriva la collezione e le sue convenzioni.

Questa documentazione sarà una sorta di **base di conoscenza operativa dell'agente**.

Dovrà essere consultata prima delle operazioni pertinenti e aggiornata quando l'agente acquisisce nuove informazioni.

### 5.1 Documentazione dei tipi di nota

Dovrà esistere un documento Markdown per ogni **tipo di nota**, non per ogni singola Nota presente nella collezione.

Per ogni tipo di nota utilizzato dovrà essere documentato:
- nome e funzione del tipo;
- campi disponibili;
- significato di ogni campo;
- formato e convenzioni da rispettare;
- ruolo di ciascun campo nei template;
- Card generate;
- conseguenze delle modifiche ai singoli campi;
- eventuali particolarità o eccezioni.

### 5.2 Documentazione dei Deck

Per ogni Deck dovrà essere documentato:
- nome e struttura;
- tipi di nota utilizzati;
- convenzioni specifiche;
- eventuali regole di compilazione;
- preferenze dell'utente;
- relazioni con altri Deck.

### 5.3 Preferenze e comportamento dell'agente

Oltre alla documentazione tecnica della collezione, dovranno esistere documenti dedicati al comportamento dell'agente e alle preferenze dell'utente.

Questi documenti definiranno, per esempio:
- livello di sintesi desiderato;
- quantità di dettagli da mostrare;
- lingua delle spiegazioni e dei contenuti;
- formato delle risposte e delle anteprime;
- stile di generazione del testo;
- convenzioni da rispettare;
- livello di autonomia;
- quando chiedere chiarimenti.

Esempio: l'utente può preferire risposte molto sintetiche, che mostrino soltanto le informazioni essenziali, senza spiegazioni aggiuntive non richieste.

Le preferenze potranno evolversi nel tempo anche in base alle correzioni e alle indicazioni dell'utente.

### 5.4 Storico

L'agente dovrà mantenere uno storico delle operazioni e delle modifiche rilevanti alla struttura della collezione.

### 5.5 Autonomia nella documentazione

I file Markdown sono principalmente strumenti interni dell'agente.

L'agente può crearli e aggiornarli autonomamente, senza chiedere conferma per ogni modifica. Dovrà però chiedere chiarimenti quando non comprende una struttura o una convenzione.

La documentazione dovrà essere conservata in uno spazio cloud sempre accessibile all'agente. L'ipotesi preferita è il Google Drive personale dell'utente.

## 6. Gestione dei Deck

L'utente normalmente indica il Deck di destinazione.

Se non lo specifica, l'agente dovrà:
1. consultare la documentazione;
2. individuare il Deck più appropriato;
3. proporre la scelta;
4. attendere conferma prima di procedere.

L'agente dovrà poter:
- creare Deck;
- rinominare Deck;
- spostare Note tra Deck;
- unire Deck;
- eliminare Deck.

La creazione di nuovi Deck richiede conferma.

Le operazioni di unione dovranno tenere conto del fatto che Anki non dispone necessariamente di un'operazione nativa di fusione: potrebbe essere necessario spostare le Card e successivamente eliminare il Deck sorgente.

L'agente dovrà documentare le modifiche alla struttura dei Deck.

## 7. Gestione dei duplicati

Prima di creare una nuova Nota, l'agente dovrà verificare la presenza di possibili duplicati.

La verifica dovrà considerare:
- corrispondenza esatta dei contenuti;
- somiglianza dei campi;
- equivalenza semantica.

Se individua un duplicato o un possibile duplicato, dovrà chiedere all'utente come procedere.

Le alternative potranno includere:
- aggiornare la Nota esistente;
- mantenere entrambe;
- rinunciare alla creazione.

L'agente non dovrà prendere autonomamente decisioni ambigue.

## 8. Formattazione e contenuti multimediali

Nella prima versione sarà possibile modificare la formattazione delle Note.

Quando modifica soltanto il testo, l'agente dovrà preservare per quanto possibile la formattazione esistente.

Il supporto a immagini, audio e video è desiderato, ma viene rimandato a una fase successiva.

Le modifiche ai template dovranno essere eccezionali e sottoposte a discussione e approvazione.

## 9. Anteprima e approvazione delle operazioni

**Nessuna modifica alla collezione dovrà essere eseguita senza approvazione esplicita dell'utente.**

Questo vale per tutte le operazioni che modificano la collezione, non soltanto per la creazione delle Note.

### 9.1 Anteprima delle Note

Per una nuova Nota l'agente dovrà mostrare:
- i valori di tutti i campi;
- tutte le Card che verranno generate;
- il fronte e il retro di ciascuna Card.

### 9.2 Modifica di una Nota

Quando una Nota viene modificata, l'anteprima dovrà mostrare:
- tutte le Card interessate;
- il fronte e il retro prima della modifica;
- il fronte e il retro dopo la modifica;
- le differenze introdotte.

Se una Nota genera più Card, dovranno essere mostrate tutte quelle interessate.

### 9.3 Modifiche multiple

Se una richiesta comporta più operazioni, l'agente dovrà presentare un'unica anteprima aggregata.

L'utente dovrà poter approvare o rifiutare le singole operazioni, senza essere obbligato ad accettarle tutte.

### 9.4 Modifica dell'anteprima

L'utente dovrà poter correggere i contenuti proposti prima di approvarli.

L'anteprima dovrà avere una rappresentazione visiva simile a quella delle Card Anki. Non è necessario riprodurre perfettamente il rendering originale, ma deve essere sufficientemente fedele da consentire di verificare il risultato.

### 9.5 Eliminazioni

Per le eliminazioni dovrà essere mostrato esattamente l'elemento che verrà eliminato.

Le eliminazioni richiederanno una conferma aggiuntiva rispetto alle normali operazioni.

## 10. Sicurezza, storico e recupero

Il sistema dovrà mantenere un registro persistente delle operazioni.

Il registro dovrà essere:
- consultabile dall'agente;
- accessibile anche all'utente;
- sufficientemente dettagliato da ricostruire le operazioni eseguite.

L'agente dovrà comunicare normalmente l'esito delle operazioni. L'utente potrà disattivare queste notifiche.

Il sistema dovrebbe prevedere funzionalità di annullamento o recupero quando tecnicamente possibile.

Non è invece un requisito obbligatorio che le Note eliminate siano sempre recuperabili tramite cestino o backup.

## 11. Sincronizzazione

L'utente desidera che l'agente possa richiedere una sincronizzazione di Anki quando necessario.

La sincronizzazione dovrà essere gestita attraverso i meccanismi supportati da Anki, senza introdurre procedure manuali inutilmente complesse.

L'agente dovrà comunicare se una sincronizzazione è necessaria o se un'operazione non è ancora disponibile sugli altri dispositivi.

## 12. Infrastruttura e accesso remoto

L'obiettivo è utilizzare l'agente da qualsiasi dispositivo e rete, compreso lo smartphone, senza dover gestire manualmente il PC.

L'utente dispone di:
- Anki Desktop;
- AnkiConnect;
- AnkiDroid;
- sincronizzazione tramite AnkiWeb.

AnkiConnect fornisce un'interfaccia locale alla collezione. Per renderla accessibile all'agente da remoto sarà necessario progettare un'infrastruttura di collegamento sicura.

L'architettura dovrà separare chiaramente:
- agente AI;
- regole e istruzioni operative;
- connettore o interfaccia MCP;
- eventuale bridge remoto;
- AnkiConnect;
- sincronizzazione AnkiWeb;
- documentazione Markdown.

La soluzione tecnica dovrà garantire autenticazione, isolamento dei dati e protezione dell'accesso alla collezione.

## 13. Comportamento dell'agente

L'agente dovrà:
- interpretare le richieste in linguaggio naturale;
- ragionare sulle Note e sui loro campi;
- consultare la documentazione prima delle operazioni;
- chiedere chiarimenti quando una richiesta è ambigua;
- supportare richieste che comportano più operazioni;
- preparare anteprime;
- attendere l'approvazione;
- comunicare l'esito;
- aggiornare la propria documentazione.

L'agente non dovrà dare per scontato il significato di un campo o una convenzione che non conosce.

## 14. Configurazione e distribuzione

Il progetto dovrà essere progettato per essere utilizzabile anche da altri utenti.

Ogni utente dovrà poter collegare la propria collezione Anki e il proprio spazio di documentazione.

Configurazioni, credenziali, documentazione, preferenze e storico dovranno essere completamente separati tra utenti.

L'obiettivo è realizzare una soluzione riutilizzabile, potenzialmente distribuibile pubblicamente, senza che gli utenti debbano condividere dati o configurazioni.

## 15. Architettura modulare futura

Il sistema dovrà avere un nucleo indipendente dalle funzionalità specifiche.

In futuro si potranno aggiungere moduli come:
- assistente allo studio;
- analisi dei progressi;
- suggerimenti sui contenuti da studiare;
- generazione di esercizi;
- tutoraggio linguistico;
- analisi della qualità delle Note.

Questi moduli dovranno poter riutilizzare la conoscenza della collezione senza compromettere la gestione operativa di Anki.

---

## 16. Questioni ancora da definire

Le seguenti decisioni sono ancora aperte e dovranno essere affrontate durante la progettazione.

1. Come organizzare concretamente i file Markdown su Google Drive e come autorizzare l'agente ad accedervi.
2. Come rilevare modifiche apportate da AnkiDroid o da altri dispositivi mentre l'agente sta preparando un'operazione.
3. Come gestire i conflitti tra modifiche concorrenti.
4. Come implementare un sistema affidabile di anteprima visiva delle Card.
5. Come gestire le operazioni di annullamento e recupero.
6. Quale infrastruttura remota utilizzare per collegare ChatGPT ad AnkiConnect.
7. Come gestire l'autenticazione e l'isolamento dei dati per più utenti.
8. Come implementare in modo affidabile la sincronizzazione AnkiWeb.
9. Come distinguere e documentare le convenzioni specifiche di un Deck da quelle generali di un tipo di nota.
10. Quali operazioni dovranno essere supportate dal primo rilascio e quali potranno essere aggiunte successivamente.
