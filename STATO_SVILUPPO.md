# ContaFlow · Alpha 0.2 — build intermedia

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
