# ContaFlow · Alpha 0.2 — budget sottovoci, build intermedia

## Budget per categorie e sottovoci

### Avvio e registro dopo l'aggiornamento — schema 8

Base dell'intervento: `ee76f4a7f3439ff08a55e2550e33ece101fda477`.
Segnalazione Windows: movimenti e conti assenti. Riprodotto il registro vuoto
su un archivio sintetico v7 con cinque movimenti sul secondo conto. Il servizio
li restituiva, ma la GUI selezionava il primo conto all'avvio. Le liste dei conti
erano popolate, quindi la segnalazione completa resta da verificare sul PC
dell'utente tramite rapporto diagnostico. Le date iniziali non filtravano,
i filtri non erano persistiti e i riferimenti facoltativi usavano LEFT JOIN.

Avvio con tutti i conti, contatori visualizzati/totali, filtri attivi e azzeramento.
Impostazioni → Diagnostica mostra in anteprima un rapporto esportabile in TXT
con percorso effettivo, metadati, conteggi e risultati SQLite. Gli eventi recenti
provengono da un log dedicato che registra categorie di errore, senza messaggi
o traceback contenenti dati. Il file legacy di log non viene esportato.

Apertura esplicita del percorso esistente senza creazione implicita, validazione
di schema e integrità prima delle modifiche, arresto con percorso e causa per
archivio inatteso. Una cartella alternativa mancante non crea un archivio
se il database predefinito esiste. Migrazione verificata anche con WAL attivo.

Test Windows con Python 3.12: `python -m unittest discover -s tests -q`,
86 superati. I test della selezione iniziale e del database corrotto fallivano
sulla base precedente. Verificati anche due avvii, saldo di 393,10 EUR, filtri
invalidi, export dopo anteprima, backup e migrazione fallita su dati sintetici.
Build EXE e riscontro della segnalazione originale tramite rapporto da fare.

Branch codex/contaflow-sviluppo, commit precedente 39afeca9f09c3cebea9f7b860daa07f2db4c93bd.
Il commit che contiene questa sezione è la versione corrente. Schema 8.

### Architettura

Gerarchia categoria → sottovoce → movimento. Codice contabile importato opzionale
sulla sottovoce, conto già assegnato al movimento preservato. Migrazione additiva
e versionata con backup verificato e confronto dei dati precedenti.
Budget nuovi soltanto per sottovoce, anno, mese e valuta in centesimi interi con
segno contabile. Budget categorie legacy restano conservati e non modificabili
nei servizi dell'app. I budget precedenti per conto contabile restano leggibili
in un prospetto storico distinto e non sono ripartiti automaticamente.

I budget legacy di categoria sono memorizzati come importi positivi. Il servizio
li converte in lettura in uscite negative o entrate positive secondo la categoria,
senza cambiare i valori originali. Per ogni categoria, mese e valuta, le sottovoci
hanno priorità. Se assenti si usa il legacy. Se entrambi esistono si visualizza
un avviso e il legacy informativo. Gli importi zero restano distinti da non impostato.
Le sottovoci parziali generano un avviso. La ripartizione legacy richiede anteprima,
conferma, somma esatta e audit, mantenendo intatto il valore storico.

Il periodo include gli estremi. Le quote giornaliere sono calcolate come frazioni
esatte dei centesimi, con arrotondamento HALF_UP una sola volta nei risultati.
Questa rappresentazione razionale evita gli arrotondamenti intermedi inevitabili
con una divisione Decimal periodica, come 1/3. Gli importi effettivi usano Decimal.
Il subtotale evidenzia le differenze di arrotondamento per budget, consuntivo e
scostamento. EUR e CHF restano separati, trasferimenti esclusi dal consuntivo.

### Funzionalità operative GUI

Scheda Sottovoci con creazione, modifica, archiviazione, associazione a conto
contabile importato, budget mensile, fornitori/alias e scelta dell'abituale.
Assegnazione singola/multipla dal registro con conferma e audit. Eventuale regola
per le descrizioni future, senza riclassificazione automatica dello storico.
Se un fornitore ha più candidati e nessuno è abituale, il movimento nuovo è
proposto e le alternative appaiono nei dettagli. Il registro mostra la sottovoce.

Il cambio categoria su un movimento con sottovoce è bloccato finché l'utente
non rimuove esplicitamente la sottovoce con conferma. La categoria ha tipo
non modificabile quando possiede movimenti o budget. Il confronto dal/al mostra
righe dettaglio, Non ripartito e subtotali, avvisi legacy/parziale, significato
di scostamento e differenze da arrotondamento. CSV UTF-8 BOM e separatore ;
con campi testuali iniziali pericolosi neutralizzati e nota sui subtotali.

### Workbook, prove e limiti

Il file Budget 2025_Marco.xlsx è stato successivamente copiato e letto in sola
lettura. È un esempio del metodo dell'utente, non una fonte obbligatoria di codici.
Il foglio Budget 2024-2025 contiene CdC, Descrizione, Voce, Categoria, Tipologia.
Fornitori collega descrizione estratto, nome fornitore e conto. Movimenti contiene
lo storico. Sono presenti codici duplicati tra righe e gruppi, righe senza conto,
formule e riferimenti #REF!. Nessun dato personale del file è stato importato.

Test sintetici Windows: migrazione 7→8 e due riaperture, backup integro, errore
simulato con rollback, cinque movimenti e saldo 393,10 EUR preservati, coerenza
categoria/sottovoce, storico/audit, riconoscimento ambiguo e regola confermata,
legacy/conflict/parziale/zero, giorni 28/29/30/31 e intervallo fra anni, quote
non arrotondate additive, differenza 0,01, segni, valute, CSV e widget Tk.
La suite completa è stata eseguita al termine dell'incremento.
Esito finale su Windows con Python 3.12.14: 81 superati, 0 falliti, 0 saltati,
comando python -m unittest discover -s tests -q. Alcuni test precedenti dei
budget sono stati aggiornati per verificare la lettura legacy e il blocco dei
nuovi inserimenti a livello di categoria o conto.
Sono disponibili periodi predefiniti mese, bimestre, trimestre e anno, oltre al
dal/al personalizzato. GUI ed export riportano le date effettive del confronto.
Collaudo manuale GUI, CSV ed EXE versione 8 non eseguiti. Il confronto e i
budget legacy per conto contabile rimangono consultabili separatamente, non
trasferiti sulle sottovoci senza una ripartizione esplicita futura.
La verifica post-migrazione confronta interamente i dati in memoria: valutare
prestazioni su archivi molto grandi. Gli importi REAL storici restano invariati.

Prima di aprire il nuovo EXE conservare a parte, a programma chiuso, la cartella
%LOCALAPPDATA%\ContaFlow. Il database migrato non è garantito apribile da un EXE
precedente. Per tornare indietro conservare separatamente i dati aggiornati, poi
ripristinare dalla copia pre-migrazione v7 il file contaflow.sqlite3 con tutte le
versioni chiuse. La copia è in %LOCALAPPDATA%\ContaFlow\backups.

### Avanzamento delle 12 fasi

Stime architettura / operatività GUI, con collaudo automatico parziale dove indicato.
01 App Windows 90% / 90% — test Tk.
02 Import bancario 85% / 80% — Revolut sintetico.
03 Conti e saldi iniziali 40% / 20% — parziale.
04 Contabilità e trasferimenti 75% / 70% — test automatici.
05 Esportazioni 55% / 45% — CSV automatico, collaudo manuale pendente.
06 Fornitori/categorie/piano dei conti 90% / 85% — associazioni testate.
07 Ricorrenze 0% / 0% — pendente.
08 Budget 90% / 85% — confronto, legacy, quote e CSV testati.
09 Dashboard 65% / 65% — saldi testati.
10 AI locale 0% / 0% — non valutata.
11 Google Sheets 5% / 0% — pendente.
12 Distribuzione 40% / 10% — nuovo EXE da compilare.

## Stato precedente C-bis, conservato come riferimento

## Confronto budget per intervallo

L'utente ha chiarito che il workbook è un esempio del suo metodo e non una fonte
vincolante per i codici o le classificazioni. Un fornitore può essere collegato
a più voci e la descrizione bancaria può richiedere una scelta manuale.

Il confronto per conto contabile accetta date iniziali e finali incluse, somma
i movimenti effettivi nel periodo e ripartisce ogni budget mensile per i giorni
effettivamente compresi, usando il numero reale di giorni del mese. Valute
separate, commissioni distinte, movimenti non assegnati visibili. Segnala il
numero di mesi privi di budget e permette esportazione CSV. Arrotondamento
alla fine del calcolo per voce e valuta. La visualizzazione usa il segno
contabile, uscite negative e differenza = consuntivo meno budget.
Resta distinto il budget per categoria già presente. La nuova funzione
interroga i budget per conto contabile e non trasferisce automaticamente valori
dal budget per categoria. Collaudo manuale dell'interfaccia e dell'export pendente.

Test sintetici dedicati superati per giorni inclusi, mesi parziali, febbraio
bisestile, valute separate e mesi senza budget.

## Incremento C-bis

Ultimo commit remoto di partenza verificato fb460f6ef5d2c905fdcaac41c83bd49c7f2a73ba.
Il commit che contiene questo aggiornamento identifica la revisione corrente.
Schema 7. Fase attiva C-bis. Stato parziale, importatore pronto, dati originali da caricare.

### Ispezione workbook

Budget 2025_Marco.xlsx è presente tra i file caricati, ma non nel checkout.
La lettura disponibile non espone celle. Il trasferimento dei byte per ispezione
è fallito. NON verificati fogli, intestazioni, colonne, gerarchie e relazioni originali.
Nessun conto, fornitore o associazione del workbook personale è stato caricato.
Nessun workbook personale è incluso nel repository.
Il modello è pertanto flessibile e provvisorio rispetto alla struttura reale.
Per completare l'ispezione, rendere disponibile il file nella cartella di lavoro
oppure allegarlo nuovamente. Mantenerlo escluso dai commit.

### Architettura implementata

Archivio ledger_accounts con codici TEXT esatti, descrizioni e origine importato/manuale.
Relazioni molti-a-molti conto contabile/categoria, fornitore/conto e alias/conto,
conto abituale opzionale. transactions.ledger_account_id nullable.
Regole contabili future separate dalle categorie e dalle classificazioni bancarie.
Creazione manuale protetta nel servizio da importazione precedente e richiesta esplicita.
La GUI non espone la creazione arbitraria di codici.

Migrazione additiva con backup verificato preesistente. Confronto automatico di
TUTTI i valori delle tabelle preesistenti, prima del commit e dopo il commit.
Questo comprende importi/commissioni da cui derivano i saldi, categorie, alias,
classificazioni e audit. Ogni difformità interrompe l'avvio e indica la copia di sicurezza.
Il confronto usa una fotografia in memoria, da valutare su archivi molto grandi.
I servizi restano utilizzabili senza importare Tkinter.

### Funzionalità operative nella GUI

- Scheda Piano dei conti vuota prima dell'importazione. Ricerca, origine,
  categorie esplicitamente collegate, modifica descrizioni e archiviazione.
- Import CSV ; / XLSX con nome foglio, prima riga e colonne configurabili.
  Anteprima differenze, conferma, transazione unica e rifiuto delle anteprime
  obsolete se le anagrafiche cambiano nel frattempo. Reimport senza conti duplicati.
  Codici e descrizioni non normalizzati. Codici numerici con formato 0000
  preservano gli zeri. Formule/formati ambigui nei campi mappati sono bloccati.
- Le categorie mappate devono già esistere. Nessuna relazione viene dedotta dai nomi.
  I fornitori vengono importati con nome esatto. Un nome già presente viene
  riutilizzato senza sovrascrivere la sua anagrafica.
- Gestione molti-a-molti per fornitori e alias, conto abituale opzionale.
- Assegnazione automatica soltanto nei nuovi import bancari. Una scelta
  memorizzata esplicitamente prevale, poi associazione alias esatta e associazioni
  fornitore. In caso di più candidati senza abituale non viene scelto un conto.
  Il nuovo movimento resta Proposto con candidati consultabili nei dettagli.
- Registro con conto bancario distinto dal conto contabile, colonna, ordinamento
  e filtro contabile, incluso Non assegnato. Assegnazione manuale singola/multipla
  con conferma, audit e opzione di regola futura. Nessuna assegnazione allo storico
  causata dall'importazione del piano dei conti.
- Budget mensile netto con segno per codice, consuntivi e commissioni separati
  per valuta, riga Non assegnato e categorie esplicite del workbook come riferimenti.
  Esportazione CSV per codice dal dialogo consuntivo. I budget per categoria
  precedenti rimangono un prospetto distinto, senza ripartizioni automatiche per codice.

### Collaudo C-bis

11 nuovi test sintetici Windows. Migrazione schema 6→7 e riaperture ripetute,
confronto esplicito di tutti i dati precedenti, cinque movimenti con commissione
e saldo esatto 393,10 EUR prima/dopo, alterazione simulata rilevata con rollback.
Backup pre-migrazione verificato, blocco importazione con anteprima obsoleta,
CSV/XLSX sintetici con zeri iniziali, import idempotente, gate creazione manuale,
relazioni molti-a-molti, ambiguità, assegnazione automatica nuova, audit manuale,
regola futura, storico invariato, Non assegnato e budget per codice.
GUI Tk reale verificata automaticamente per archivio, assegnazione e filtro.
La suite finale e le verifiche della baseline sono registrate nella chiusura sotto.

Chiusura automatica C-bis eseguita su Windows con Python 3.12.14 e SQLite 3.53.1.
Comando python -m unittest discover -s tests -v.
Esito 64 superati, 0 falliti, 0 saltati in 9,594 secondi, inclusi tutti i 53 test
precedenti e 11 nuovi. Ripristino e compatibilità WAL superati.
Collaudo manuale dell'EXE C-bis non eseguito.

### Limiti e prossimo incremento

Ispezione e collaudo del workbook originale pendenti. Non viene dichiarata
completata la mappatura dei suoi dati, delle gerarchie o dei fornitori.
L'importatore generale non tenta di indovinare formule o gerarchie.
Nessuna funzione di creazione manuale in GUI finché non richiesta esplicitamente.
Export CSV implementato ma collaudo manuale del file esportato pendente.
Le funzioni parziali A–F elencate più sotto restano successive a C-bis.
EXE C-bis non prodotto. Collaudo manuale Windows della nuova interfaccia pendente.
I collaudi manuali 0.2 di migrazione/persistenza/filtri/modifica multipla/audit
sono dichiarati dall'utente, distinti dai test automatici di questa sessione.

### Compatibilità e ritorno alla versione precedente

Prima dell'avvio, conservare a parte il database da %LOCALAPPDATA%\ContaFlow,
a programma chiuso. Il database aggiornato non è garantito compatibile con
il precedente EXE. Per tornare indietro, chiudere tutte le versioni, conservare
separatamente la cartella dati aggiornata e recuperare la copia pre-migrazione
%LOCALAPPDATA%\ContaFlow\backups\ContaFlow_pre_migrazione_v6_*.sqlite3.
Copiare quella copia con il nome originale contaflow.sqlite3 nella cartella dati
prima di avviare l'EXE precedente. Conservare anche la copia sorgente.
La funzione di ripristino dell'EXE nuovo aggiorna il backup allo schema nuovo,
quindi non rappresenta una procedura di downgrade.
Importi REAL legacy preservati. Nuovi calcoli Decimal e budget contabili in unità
minori. La migrazione massiva degli importi resta un'attività futura con strategia approvata.

### Avanzamento aggiornato delle 12 fasi

Stime di copertura prodotto, architettura / operatività GUI.
01 App Windows 90% / 90%, test automatici registro e dialoghi.
02 Import bancario 85% / 80%, test automatici Revolut/lotti.
03 Conti e saldi iniziali 40% / 20%, copertura parziale.
04 Contabilità/trasferimenti 75% / 70%, test automatici collegamenti.
05 Esportazioni 20% / 20%, CSV contabile operativo, collaudo manuale pendente.
06 Fornitori/categorie/piano dei conti 90% / 85%, test sintetici C-bis, workbook reale pendente.
07 Ricorrenze 0% / 0%, pendente.
08 Budget 80% / 80%, test automatici per categorie e codici.
09 Dashboard 65% / 65%, test automatici saldi.
10 AI locale 0% / 0%, non valutata.
11 Google Sheets 5% / 0%, pendente.
12 Distribuzione 40% / 10%, compilazione nuovo EXE pendente.

## Stato precedente Alpha 0.2, conservato come riferimento

- Branch codex/contaflow-sviluppo.
- Ultimo commit precedente al presente incremento: 331e12ba24f75fc2ef8c8e5f036483d19380e2e2.
  Il commit che contiene questo documento identifica l'incremento corrente.
- Fase attiva F operativa. Sprint A–F pubblicati in sequenza.
- Schema 6, Python 3.12, Tkinter/ttk, SQLite. Calcoli nuovi Decimal.
- Stato della consegna: sorgenti pronti alla compilazione e al collaudo manuale.
  EXE Alpha 0.2 NON prodotto. Versione intermedia, requisiti secondari aperti sotto.

## Architettura implementata e funzionalità operative

A. Registro via FinanceService con query parametrizzate, tutti i movimenti senza limite
di 100, conto/tutti i conti, testo, periodo, categoria, fornitore, stato e Da classificare.
Ordinamento su tutte le colonne, scroll orizzontale/verticale, selezione multipla,
dettagli e dati originali, legenda testuale/colori, importi italiani e commissioni separate.

B. Modifica singola/multipla con conferma del numero di movimenti e dei campi.
Fornitore, categoria, stato, note e natura contabile. Audit consultabile dal dialogo.
Scelta esplicita tra movimento selezionato e regola futura. Nessuna riclassificazione
dello storico non selezionato. Importi, dati sorgente e fingerprint non modificabili dal servizio.

C. Fornitori con note, categoria abituale, alternative, alias, archiviazione/riattivazione,
avvisi duplicati e collisioni alias. Salvataggio atomico delle anagrafiche.
Categorie con ID stabili, tipo, creazione/modifica/archiviazione, fornitori e movimenti collegati.
Importatore strutturato con validazione e conferma CSV ; / XLSX, foglio Anagrafiche,
intestazioni fornitore,categoria,tipo,alias,note. Il workbook personale non è nel checkout.
La mappatura del layout originale Budget 2025_Marco.xlsx resta da eseguire.

D. Revolut EUR/CHF con anteprima obbligatoria, snapshot immutabile del file confermato,
provider/valuta, conteggi, anomalie, conferma esplicita e transazione unica.
Lotti consultabili e annullabili. Dipendenze verificate sotto BEGIN IMMEDIATE.
Conferma specifica per modifiche manuali/trasferimenti/rimborsi. Audit conserva snapshot
integrali dei movimenti e dei collegamenti rimossi. I nuovi ID superano anche il massimo
dell'audit per evitare riuso dell'identità dopo annullamento. Le altre gambe di trasferimento
recuperano lo stato e la natura precedenti, preservando categorie e altre classificazioni.
BPER EUR, PDF e XLSX bancari hanno soltanto interfaccia comune predisposta read(payload).

E. Collegamento/scollegamento dal registro di due movimenti esistenti, con validazione
di segni, conti, importi e dipendenze. Trasferimento, giroconto, prelievo verso cassa,
rimborso e storno. Nessuna nuova gamba artificiale. Importi/valute originali conservati,
nessun tasso CHF/EUR inventato. Saldi aggiornati sui rispettivi conti, trasferimenti ed
esclusi separati dal consuntivo, rimborsi riducono la spesa, commissioni esposte separatamente.
Stato e natura dei trasferimenti coerenti. Scollegamento ripristina i valori precedenti.

F. Budget operativo in una scheda GUI. Anno/mese, categoria stabile, valuta,
inserimento/modifica, consuntivo, scostamento, totali entrate/uscite, commissioni e
movimenti senza categoria segnalati. EUR/CHF separati. Nuovi budget persistiti anche
come unità minori INTEGER, senza conversione massiva dei budget REAL legacy.

## Migrazioni e conservazione dati

Store effettua un backup PRIMA di qualsiasi scrittura sullo schema di un database
esistente da aggiornare. Ogni migrazione successiva ha una copia verificata con
integrity_check prima di partire. Chiusura esplicita delle connessioni. Nessun backup
superfluo per database appena creati senza dati utente. Migrazioni additive, versionate,
idempotenti, transazionali. Eliminato executescript dal corpo transazionale delle migrazioni.

Fallimento interrompe l'avvio. Verifica integrità/versione dopo rollback e mostra il
percorso della copia precedente. Copie conservate in backups accanto al database.
La funzione di backup/ripristino di 46a797e non è stata modificata.

I fingerprint Alpha 0.1 mantengono la stessa formula, inclusa la formattazione float
storica per l'identità. Non vengono ricalcolati fingerprint già salvati.
Gli importi bancari legacy restano REAL. Verifiche, consuntivi e budget nuovi usano Decimal
o unità minori. Futura migrazione di tutti gli importi verso rappresentazione esatta
richiederà strategia approvata e test di preservazione, senza conversione massiva in questo rilascio.

## Funzionalità collaudate

Eseguito su Windows, Python 3.12.14, SQLite 3.53.1, solo database sintetici sotto
cartelle temporanee del checkout, dati applicazione rediretti con CONTAFLOW_DATA_DIR.

Comando finale eseguito con l'interprete del runtime disponibile
    python -m unittest discover -s tests -v

Esito finale 53 superati, 0 falliti, 0 saltati, 7,416 secondi.
Include tutti i 25 test della baseline e 28 nuovi test.
Inclusi widget Tk reali controllati automaticamente, non collaudo manuale.

- A query combinate, 150 righe, ordinamento, formato italiano e GUI.
- B migrazione sintetica schema Alpha 0.1 v3→v6, riapertura due volte senza nuova
  migrazione, copia verificata PRIMA delle nuove colonne, rollback di migrazione fallita,
  copia non valida che blocca aggiornamento, audit/persistenza, modifica multipla GUI,
  regola futura che non modifica lo storico.
- C CSV e XLSX sintetici nel formato esplicito, duplicati, alias, note, categorie alternative,
  archiviazione, editor GUI e navigazione ai movimenti collegati.
- D EUR/CHF, preview senza scritture, snapshot, deduplica con identità legacy,
  errore a metà inserimento senza righe o lotto residuo, conferma GUI,
  annullamento con/senza dipendenze, reimport senza riuso degli ID audit,
  rifiuto di importi NaN, infiniti o fuori dal range REAL.
- E link/unlink, saldo/commissioni, valute distinte, limiti rimborso,
  annullamento lotto collegato e preservazione classificazione precedente.
- F budget esatto, valute distinte, esclusione trasferimenti/esclusi, GUI e riapertura.
- Baseline ripristino Windows, chiusura connessioni, WAL, sicurezza e distinzione errori/avvisi.

## Roadmap delle 12 fasi

Percentuali stimate di copertura funzionale del prodotto complessivo.
Architettura e operatività non equivalgono al collaudo manuale.
La numerazione segue i nomi e le priorità del master prompt Alpha 0.2;
le fasi non dettagliate nel master mantengono gli ambiti del progetto.

| Fase | Architettura | Operativa GUI | Collaudo automatico |
|---|---:|---:|---|
| 01 App Windows | 90% | 90% | Registro e dialoghi Tk |
| 02 Import bancario | 85% | 80% | Revolut e lotti |
| 03 Conti e saldi iniziali | 40% | 20% | Baseline parziale |
| 04 Contabilità e trasferimenti | 75% | 70% | Trasferimenti/rimborsi |
| 05 Esportazioni | 0% | 0% | Pendente |
| 06 Fornitori e categorie | 85% | 85% | Anagrafiche e import strutturato |
| 07 Ricorrenze | 0% | 0% | Pendente |
| 08 Budget | 75% | 75% | Budget mensile multivaluta |
| 09 Dashboard | 65% | 65% | Saldi e consuntivi Decimal |
| 10 AI locale | 0% | 0% | Non valutata |
| 11 Google Sheets | 5% | 0% | Pendente |
| 12 Distribuzione | 40% | 10% | Script presente, EXE 0.2 pendente |

## Limiti e prossimo incremento

- Collaudo manuale Windows e compilazione portable Alpha 0.2 pendenti.
- BPER/PDF/XLSX bancari non operativi. Occorrono esempi di formato.
- Workbook storico personale non mappato. Solo importatore strutturato collaudato.
- Inserimento manuale di una nuova gamba cassa non disponibile. I movimenti da collegare
  devono già esistere. Rimborso in valuta diversa non automatizzato.
- Saldi iniziali ancora privi di editor GUI, come nella baseline.
- Gli importi REAL storici conservano i limiti della loro rappresentazione.
- Il registro legge tutte le righe. Paginazione da valutare su archivi grandi.

Pubblicazione tramite connessione GitHub con verifica HEAD e avanzamento fast-forward.
Git CLI ha fallito per DNS. Nessuna attività su billing/Actions per sbloccarlo.

Prima di aprire la nuova versione sul PC di casa, copiare a parte il database Alpha 0.1
da %LOCALAPPDATA%\ContaFlow a programma chiuso. La nuova versione creerà comunque
una copia automatica verificata prima della migrazione. Compilare con build_windows.bat
e collaudare prima il portable con dati sintetici.
