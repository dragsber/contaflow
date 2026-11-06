# Ricerca di riusi open source per ContaFlow

**Consultazione delle fonti: 6 novembre 2026**  
**Repository:** `dragsber/ContaFlow` — branch `codex/contaflow-sviluppo`  
**HEAD remoto esaminato:** `33109d75989aa012539155162cf98c7ee022f643`  
**Esito:** analisi documentale. Nessun pacchetto installato, codice di terzi eseguito, dato personale letto o codice applicativo modificato.

## Sintesi

I riusi con beneficio netto più chiaro sono `openpyxl`, che può sostituire parte del lettore XLSX fatto in casa, e `RapidFuzz`, che può generare candidati per la revisione umana senza alterare l'ordine o l'esito del classificatore. Entrambi sono **proposte ADOTTARE**, non integrazioni approvate o già eseguite. Il collaudo Windows/PyInstaller resta obbligatorio.

Per OFX, PDF e CAMT esistono parser di terzi, ma ContaFlow non ha ancora campioni bancari reali e autorizzati con cui verificare mapping e semantica. I parser non sostituiscono anteprima, deduplica, coerenza di valuta/conto, audit o transazione atomica. Per budget, saldi, trasferimenti e riconciliazione l'app dispone già di servizi specifici e testati; in questa fase conviene studiare modelli e casi limite, non sostituirli.

## 1. Inventario del codice ContaFlow

Stato rilevato da `STATO_SVILUPPO.md`, sorgenti e test sul commit remoto. “Operativo” significa collegato alla GUI secondo il repository; il collaudo manuale dell'EXE resta pendente ove dichiarato nello stato.

| Area | Presente e stato | Mancanze o fragilità | Ordine di grandezza del codice personalizzato |
|---|---|---|---:|
| Import bancario | Revolut CSV EUR/CHF: `adapters/revolut.py`, `adapters/statements.py`, `services/imports.py`; anteprima, deduplica, esclusioni e lotto. Operativo; test sintetici presenti. | BPER, PDF, XLSX bancari, OFX/QIF e CAMT sono adattatori predisposti o assenti; parser e mapping non collaudati su estratti reali. | Circa 210 LOC per adapter CSV, flusso e dipendenze di lotto; parser aggiuntivi non stimabili prima dei campioni. |
| XLSX | Importatori mappabili di piano/associazioni in `adapters/chart.py` e `services/catalog_import.py`; test sintetici. | Lettore OOXML scritto localmente e parziale: formule/formati ambigui vengono rifiutati; non è una libreria generale per modificare workbook. Export budget attuale è CSV. | 87 LOC nel lettore/mappatore XLSX; 201 LOC nel servizio catalogo. |
| Classificazione/fornitori | Normalizzazione, alias esatti, regole confermate, proposte ambigue e relazioni a sottovoci in `contaflow/store.py`, `services/editing.py`, `services/subcategories.py`; GUI e test. | Nessun motore di similarità: varianti non coperte da alias restano da confermare. L'eventuale similarità deve solo proporre candidati. | Circa 310 LOC nel servizio store, 369 LOC sottovoci e GUI fornitori in `contaflow/app.py`; non conviene sostituire il classificatore. |
| Budget | `services/budget.py`, `services/subcategories.py`, `services/period_report.py`, `contaflow/budget.py`; confronto periodo, ripartizione proporzionale, legacy, valute separate e CSV; test sintetici. | Nessuna previsione; i collaudi manuali GUI/CSV/EXE sono pendenti. | Oltre 500 LOC tra servizi di budget/sottovoci/report e relativa GUI; area già sostanzialmente operativa. |
| Saldi, trasferimenti, cassa, riconciliazione | `services/accounts.py`, `services/transfers.py`, `services/cash.py`, `services/reconciliation.py`, `contaflow/accounts.py`; operativi secondo stato, test sintetici. | Riconciliazione è manuale; l'app segnala possibili duplicati, non prova movimenti mancanti. Manca collaudo manuale Windows recente. | Circa 450 LOC nei servizi specifici, oltre alla GUI. Non sostituire senza regressione dimostrata. |
| Piano dei conti/partita doppia | Archivio conti contabili e relazioni opzionali; modello corrente a conto bancario, categoria/sottovoce e natura contabile. | Il piano contabile dipende da importazione esplicita; non esiste un giornale generale a partita doppia. | Modello e migrazioni in `db/migrations.py` (287 LOC) e servizi; non è necessario trasformarli per il budget approvato. |
| GUI e grafici | Tkinter/ttk; Treeview per registro e tabelle, filtri, ordinamento, dettagli e indicatori. | Nessuna libreria grafici aggiunta; alcuni controlli e tabelle sono implementati manualmente. | `contaflow/register.py` 354 LOC, `contaflow/accounts.py` 271 LOC; moduli GUI in totale diverse centinaia di LOC. |
| Backup, audit, migrazioni | SQLite, backup verificato pre-migrazione, migrazioni additive, audit, diagnostica; test dedicati. | La verifica su EXE Windows e sul database personale resta collaudo manuale; non è una lacuna da delegare a un ORM. | `db/migrations.py` 287 LOC, `contaflow/store.py` 310 LOC, più audit e diagnostica. Codice sensibile: mantenere proprietario e coperto da test. |

Le misure sono conteggi di file/moduli presenti o stime indicative, non una promessa di riduzione esatta del codice. La misura non include tutta la GUI, integrazione, test, aggiornamento build e manutenzione.

## 2. Strategia e fonti

Inventario eseguito prima della ricerca; query per funzioni: `Python OFX parser`, `CSV field mapping finance`, `bank statement PDF text/table parser`, `CAMT.053 parser Python`, `XLSX reader/writer Python`, `fuzzy string matching Python`, `personal finance SQLite schema`, `double-entry accounting model`, `Tkinter spreadsheet widget`. Sono stati consultati repository GitHub, documenti ufficiali e metadati PyPI collegati. I link nelle schede sono alle fonti primarie; data di consultazione 6 novembre 2026.

Non sono stati clonati, installati o eseguiti progetti esterni. Non sono state scaricate fixture finanziarie. Le compatibilità indicate come dichiarate provengono dai metadati o dalla documentazione; **nessuna prova di integrazione è stata eseguita**.

## 3. Classifica dei cinque riusi con maggior beneficio atteso

| Pos. | Progetto/componente | Lacuna e codice ContaFlow affiancato/sostituito | Lavoro personalizzato potenzialmente evitato (stima) | Licenza e modalità | Compatibilità | Costo d'integrazione / rischio | Decisione |
|---:|---|---|---|---|---|---|---|
| 1 | [openpyxl](https://github.com/ericgazoni/openpyxl) | Lettura delle cartelle XLSX in `adapters/chart.py`; non sostituisce mapping, validazione, anteprima o importazione. | Potrebbe rimuovere gran parte dei circa 60–80 LOC che interpretano manualmente XML, shared strings e stili; resta codice per mappatura e regole ContaFlow. | MIT verificata; dipendenza diretta `et-xmlfile` MIT verificata. Nessun'altra dipendenza runtime dichiarata nei metadati esaminati. Dipendenza proposta. | Python ≥3.8 e Windows dichiarati nei metadati; 3.12 ricade nel requisito minimo, ma il classificatore PyPI consultato non elenca 3.12. PyInstaller onedir non verificato. | Basso/medio; rischio di differenze nella gestione formule, celle vuote e numeri/codici con zeri iniziali. Wheel openpyxl indicata a 245 KB; incremento effettivo onedir non misurato. | **ADOTTARE**, solo dopo approvazione e prova Windows. |
| 2 | [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Suggerimenti di alias/fornitore in `contaflow/store.py` e GUI fornitori/registro; affianca la ricerca esatta, non la sostituisce. | Evita di scrivere e mantenere un algoritmo di similarità e metriche; ordine di grandezza circa 20–50 LOC più test per selezione/soglie, non una riduzione dell'attuale normalizzazione esatta. | MIT verificata. Nessuna dipendenza runtime obbligatoria nei metadati; NumPy è opzionale. Wheel contiene estensione nativa; conservare avviso MIT. | PyPI dichiara Python 3.12 e offre wheel Windows x86-64; progetto dichiara requisiti Windows e pubblica test hook per PyInstaller. Nessuna build onedir ContaFlow verificata. | Basso/medio; falso positivo se punteggio usato come classificazione. Regola vincolante: mostra solo candidati e motivazione; nessuna assegnazione/fusione automatica. Dimensione finale non misurata. | **ADOTTARE**, solo come suggeritore e dopo approvazione/collaudo. |
| 3 | [ofxparse](https://github.com/jseutter/ofxparse) | OFX/QFX in `adapters/statements.py`, oggi non implementati. Parser dati, non integrazione con il database. | Evita una prima implementazione del parser OFX e dei modelli di statement; stima LOC non affidabile senza mapping e campione. | MIT dichiarata dal repository; dipendenze runtime transitive e licenze complete **non verificate**. La README elenca BeautifulSoup4, six e lxml tra requisiti per sviluppo/test, non prova sufficiente della dipendenza installata. | La documentazione presenta parser OFX/QFX e test con esempi; compatibilità dichiarata Python 3.12, Windows e PyInstaller non verificata. | Medio/alto; salute/versione e compatibilità dei file OFX/QFX di banca italiana da controllare. `lxml` aggiunge estensione nativa. | **STUDIARE** dopo acquisizione di un file OFX/QFX d'esempio autorizzato. |
| 4 | [pdfplumber](https://github.com/jsvine/pdfplumber) | Estrazione testo/tabelle per un futuro adapter PDF; `adapters/statements.py` al momento è solo stub. | Evita di implementare geometria PDF, righe e tabelle di basso livello; **non** evita il parser specifico dell'estratto, stimato non stimabile senza campione. | MIT verificata. Dipendenze dirette dichiarate: `pdfminer.six`, Pillow, `pypdfium2`; MIT verificata per pdfminer.six, licenze/versioni esatte degli altri pacchetti e dipendenze transitive da completare prima di una decisione. | Python 3.12 testato secondo README. Compatibilità PyInstaller onedir/Windows su ContaFlow non verificata. Dipendenze native/immagini possono incidere sul bundle; aumento non misurato. | Alto; variazioni di layout, PDF scansiti (non OCR), peso e licenze della catena. | **STUDIARE**; non dichiarare parser bancario completo senza estratto campione e test. |
| 5 | [Actual Budget — flusso di import e budgeting](https://github.com/actualbudget/actual) | Solo riferimento di prodotto per anteprima e mapping CSV; può informare `services/imports.py`/GUI. Il budget per categorie/sottovoci di ContaFlow esiste già: nessuna sostituzione proposta. | Risparmio architetturale non quantificabile; studiare flussi e test edge case. Nessun codice da portare nel backend Python/Tkinter. | MIT verificata sul repository; riuso solo studio, quindi nessuna dipendenza proposta. Licenze transitive non esaminate perché non si propone distribuzione di suoi moduli. | Applicazione TypeScript/Node, non compatibile come modulo Python/Tkinter; compatibilità PyInstaller non pertinente. | Basso per studio; alto se si tentasse di portare un intero modello di budget, con differenze di semantica (envelope vs budget proporzionale). | **STUDIARE** solo flusso import/UX, nessun porting. |

Beneficio netto stimato in ordine qualitativo. Gli unici due riusi candidati all'adozione eliminano codice circoscritto o evitano di scriverlo; le altre voci sono soprattutto studio o parser ancora privi di input bancario verificabile.

## 4. Tabella delle decisioni

| Progetto | URL | Lacuna colmata | Licenza (progetto e dipendenze, verificata sì/no) | Modalità di riuso | Compatibilità (dichiarata / verificata / non verificata) | Decisione | Priorità | Rischio principale | Prossimo passo |
|---|---|---|---|---|---|---|---:|---|---|
| openpyxl | [GitHub](https://github.com/ericgazoni/openpyxl) · [PyPI](https://pypi.org/project/openpyxl/) | Lettura XLSX strutturata | MIT e `et-xmlfile` MIT: sì | Dipendenza proposta | Python/Windows dichiarati; Python 3.12 ricade in `>=3.8`; PyInstaller e onedir non verificati | ADOTTARE | 1 | Inclusione bundle e semantica celle/formule | Test comparativo sintetico, poi build Windows onedir |
| RapidFuzz | [GitHub](https://github.com/rapidfuzz/RapidFuzz) · [PyPI](https://pypi.org/project/RapidFuzz/) | Candidati di somiglianza fornitore | MIT, dipendenze runtime obbligatorie assenti dai metadati; sì | Dipendenza proposta | Python 3.12/Windows dichiarati e wheel osservata; PyInstaller hook documentato; build ContaFlow non verificata | ADOTTARE | 2 | Scambiare score con certezza | Test solo di proposta, soglie e ambiguità; onedir Windows |
| ofxparse | [GitHub](https://github.com/jseutter/ofxparse) | Import OFX/QFX | MIT dichiarata; dipendenze runtime/transitive non verificate | Dipendenza da valutare | OFX/QFX dichiarato; Python 3.12, Windows, PyInstaller non verificati | STUDIARE | 3 | Manutenzione, dipendenze e varianti bancarie | Verificare metadati PyPI, issues e fixture sintetiche/reali autorizzate |
| pdfplumber | [GitHub](https://github.com/jsvine/pdfplumber) · [PyPI](https://pypi.org/project/pdfplumber/) | Estrazione da PDF digitali | MIT sì; licenze/versioni catena non tutte verificate | Dipendenza da valutare | Python 3.12 dichiarato; Windows/PyInstaller ContaFlow non verificati | STUDIARE | 4 | Dipendenze, peso e layout banca non stabile | Audit licenze transitive e acquisire campione non sensibile |
| Actual Budget | [GitHub](https://github.com/actualbudget/actual) | UX import CSV e modelli budget | MIT progetto verificata; dipendenze non esaminate, nessun codice da integrare | Solo studio | TypeScript/Node; Python/Tkinter e PyInstaller non applicabili | STUDIARE | 5 | Semantica budget differente | Confrontare flusso UX, non copiare il motore budget |
| Money Manager Ex | [App](https://github.com/moneymanagerex/moneymanagerex) · [schema DB](https://github.com/moneymanagerex/database) | Schema SQLite, subcategorie, mapping CSV/QIF | GPL-2.0 verificata per app e repository schema | Solo studio | C++/wxWidgets; Python 3.12/PyInstaller non applicabili | STUDIARE | 6 | Copyleft e schema molto più ampio | Usare solo come catalogo di casi e invarianti, senza copiare/adattare |
| Beancount | [GitHub](https://github.com/beancount/beancount) | Invarianti della partita doppia e validazione | GPL-2.0-only verificata; dipendenze progetto: Click, python-dateutil, regex | Solo studio | Python ≥3.9 dichiarato; Windows/PyInstaller ContaFlow non verificati | STUDIARE | 7 | Cambierebbe il modello contabile e licenza copyleft | Studiare test/invarianti, non innestare il ledger |
| Firefly III | [GitHub](https://github.com/firefly-iii/firefly-iii) | Import workflow e regole | AGPL-3.0 verificata; stack PHP | Solo studio | Non integrabile come libreria Python/Tkinter | STUDIARE | 8 | AGPL e architettura web/server | Riferimento di flusso, nessun codice |
| GnuCash | [GitHub](https://github.com/Gnucash/gnucash) | Partita doppia e riconciliazione | GPL-2.0 verificata a livello repository | Solo studio | C/C++, GUI e packaging diversi | STUDIARE | 9 | Modello e complessità non proporzionati allo sprint | Consultare invarianti e casi, non portare componenti |
| hledger | [GitHub](https://github.com/simonmichael/hledger) | Import rules e ledger a partita doppia | Licenza repository e dipendenze da verificare in dettaglio prima di ogni riuso; codice Haskell | Solo studio | Non applicabile direttamente a Python/Tkinter | STUDIARE | 10 | Licenza/dipendenze e semantica testuale diversa | Leggere regole CSV come fonte di casi di test |
| ofxtools | [GitHub](https://github.com/csingley/ofxtools) | OFX parsing alternativo | GPL-3.0-only verificata | Solo studio | Python ≥3.10, classificatore 3.12; Windows/PyInstaller non testati | NON ADOTTARE come dipendenza; studio possibile | 11 | GPL-3.0 incompatibile col vincolo di non integrare copyleft | Preferire valutazione di ofxparse, previa verifica completa |
| pycamt | [GitHub](https://github.com/ODAncona/pycamt) | CAMT.053 | GPL-3.0 verificata | Solo studio | Versioni Python e PyInstaller non verificate | STUDIARE | 12 | Copyleft, progetto piccolo e dialetto da verificare | Consultare la struttura XML, senza copiare codice |
| tksheet | [GitHub](https://github.com/ragardner/tksheet) · [PyPI](https://pypi.org/project/tksheet/) | Widget tabellare Tkinter | Licenza e dipendenze dirette da verificare sul pacchetto/revisione scelta | Non adottare ora; possibile studio | Dichiarazione Python/Windows e PyInstaller non verificata qui | STUDIARE | 13 | Nuovo widget non necessario per le funzioni già presenti | Valutare solo se il collaudo GUI rileva limiti di Treeview |

### Progetti esaminati ma non selezionati per approfondimento

- `ofxtools`: parser OFX dichiarato production/stable, ma GPL-3.0-only. Non adottare come codice o dipendenza secondo i vincoli del progetto.
- `pycamt`: parser CAMT interessante ma GPL-3.0; non adottare. Un parser non assicura compatibilità con il file BPER dell'utente.
- `GnuCash`: modello contabile ricco, ma C/C++ e GPL; lo studio di concetti non giustifica il porting del suo modello nell'app.
- `hledger`: flusso di regole CSV utile come lettura di casi; runtime Haskell e licenza/dipendenze non sottoposti a verifica legale completa. Non candidato all'integrazione.
- `tksheet`: possibile widget per celle e navigazione; il registro attuale ha già filtri, ordinamento e scroll. Beneficio concreto non dimostrato e licenza/pacchetto da riverificare prima di proporlo.

## 5. Schede dei primi otto progetti

### 5.1 openpyxl — ADOTTARE proposto

- **Funzione/lacuna:** lettura e scrittura XLSX OOXML, contro il parser XML manuale in `adapters/chart.py`.
- **Equivalente e vantaggio:** ContaFlow ha mappatura di colonne, validazione e anteprima proprie (da mantenere), ma reimplementa con circa 87 LOC lettura fogli, relazioni, stringhe condivise e alcune formattazioni. La libreria può sostituire la parte di protocollo XLSX e gestire più casi standard.
- **Componente separabile:** sì, il reader può rimanere dietro `workbook_rows`/l'adapter. Non valutare o eseguire formule: `data_only=False`, segnalare le celle formula come attualmente previsto; mantenere il codice conto testuale e gli zeri iniziali.
- **Licenza/dipendenze:** MIT. `et-xmlfile`, dipendenza richiesta, MIT. Nessun obbligo copyleft rilevato; mantenere licenze/attribuzioni secondo i pacchetti distribuiti. PyPI indica wheel openpyxl 3.1.5 di 245 KB e release 28 giugno 2024; dimensione totale del bundle non misurata.
- **Salute:** PyPI lo dichiara production/stable, due maintainer elencati; release non recente rispetto alla data di questa ricerca, ma non risulta dichiarato archiviato dalle fonti consultate. Issue aperte e cadenza commit non conteggiate in questa analisi.
- **Compatibilità:** progetto dichiara Python `>=3.8` e Windows; l'ambiente di ricerca non ha installato il pacchetto. Prova Python 3.12/Linux e Windows/PyInstaller onedir **pendente**.
- **Rischi:** celle formula, formati numerici di codici, file corrotti o grandi, regressione del lettore manuale.
- **Test prima dell'integrazione:** stessa fixture sintetica letta sia dal parser corrente sia da openpyxl; stringhe/codici con zeri iniziali, fogli multipli e nomi Unicode, formule rifiutate, celle vuote, date/float, mappatura, errori riga, import ripetuto senza duplicati. Verificare nessun dato di conto/movimento cambia.

### 5.2 RapidFuzz — ADOTTARE proposto come suggeritore

- **Funzione/lacuna:** ricerca di candidati fornitori/alias quando il testo cambia lievemente; codice esatto attuale in `contaflow/store.py` resta fonte autorevole.
- **Equivalente e vantaggio:** oggi non esiste un algoritmo fuzzy da sostituire. RapidFuzz evita di scrivere uno scorer e diverse metriche, fornendo ranking veloce e implementazione testata; stima qualitativa 20–50 LOC di logica propria evitabili, più i test e l'integrazione.
- **Componente separabile:** sì, una funzione pura che riceve descrizione e alias attivi e restituisce N candidati con punteggio/motivo. L'utente deve confermare. Non modificare alias, movimenti o classificazioni; non accettare automaticamente soglie alte.
- **Licenza/dipendenze:** MIT. Metadati `pyproject.toml`: nessuna dipendenza runtime obbligatoria; NumPy opzionale. Wheel include moduli nativi C++ e il progetto dichiara un plugin PyInstaller; includere la licenza MIT nel bundle/notices secondo le procedure interne.
- **Salute:** release 3.14.6 del 30 agosto 2026; `pyproject.toml` dichiara Python 3.11+ e classificatori 3.12; repository attivo e changelog aggiornato. Issue aperte non analizzate una per una.
- **Compatibilità:** Windows x86-64 e Python 3.12 wheel osservata nei metadati PyPI; PyInstaller hook dichiarato. Nessun test del progetto ContaFlow o build onedir eseguito.
- **Rischi:** punteggio non equivale a identità; nomi comuni o catene di negozi generano falsi candidati. I risultati vanno filtrati per evidenze locali e mostrati separatamente dalla categoria/sottovoce.
- **Test prima dell'integrazione:** alias esatto continua a precedere i suggerimenti; stringhe simili mostrano candidati senza mutazioni; omonimi e differenze di filiale restano ambigui; nessuna modifica di storico; conferma esplicita crea alias/regola solo futura; test di bundle Windows e import DLL.

### 5.3 ofxparse — STUDIARE

- **Funzione/lacuna:** parser OFX/QFX; `adapters/statements.py` non lo implementa.
- **Equivalente e vantaggio:** può fornire parsing di statement bancari/carte/investimenti e campi transazione; non offre la semantica ContaFlow di conto, valuta supportata, stato, commissioni, fingerprint, anteprima o persistenza atomica.
- **Separabilità:** parser concettualmente separabile dietro adapter, ma oggetti parser devono essere tradotti in un modello interno decimal-safe.
- **Licenza/dipendenze:** repository dichiara MIT. Requisiti elencati nella README includono BeautifulSoup4, six e lxml per ambiente di sviluppo/test; non è stato verificato il grafo effettivo di dipendenze runtime del pacchetto PyPI né tutte le licenze/versioni. Decisione bloccata su questo controllo.
- **Salute:** repository non è indicato come archiviato dalla pagina consultata; la pagina mostra 387 commit, ma data dell'ultima release/ultimo commit, issue e manutentori attivi non sono stati verificati in modo affidabile. Non dedurre lo stato dalla sola età.
- **Compatibilità:** supporto OFX/QFX e test con campioni dichiarati dal progetto. Python 3.12/Windows/PyInstaller non verificati.
- **Rischi e test:** estensione nativa `lxml`, formati legacy OFX SGML/XML, date/fusi, segni, valuta, fee e status. Usare fixture sintetiche e statement anonimizzati solo con autorizzazione. Verificare import ripetuto, deduplica e rollback completo.

### 5.4 pdfplumber — STUDIARE

- **Funzione/lacuna:** estrae caratteri, coordinate e tabelle da PDF digitali, mentre l'adapter ContaFlow è stub.
- **Equivalente e vantaggio:** evita implementare primitive di layout e tabella; non identifica da solo colonne/righe bancarie né rende compatibile un PDF BPER.
- **Separabilità:** sì, come estrattore nel parser; il mapping per banca resta locale e testato.
- **Licenze/dipendenze:** MIT per pdfplumber; dipendenze dichiarate `pdfminer.six`, Pillow, `pypdfium2`. Licenza MIT verificata per pdfminer.six; licenza esatta delle versioni e relative dipendenze transitive (inclusi componenti nativi) da completare con lock/audit prima di adottare. Nessuna catena è stata installata.
- **Salute:** README e changelog mostrano versioni 0.11.x nel 2025–2026 e fix recenti; GitHub issues mostrava segnalazioni attive su tabelle, testo e memoria. Un bug report non prova da solo una vulnerabilità; advisory non verificati uno per uno.
- **Compatibilità:** README dichiara test Python 3.10–3.14. Build Windows/PyInstaller di ContaFlow non eseguita; bundle-size non misurata. Funziona meglio su PDF generati da macchina; niente OCR.
- **Test:** fixture sintetiche per più pagine, header ripetuti, valori a cavallo riga, segni, separatori decimali, commissione incorporata/separata e righe pending; non importare finché anteprima non mostra anomalie e la somma non è riconciliabile. Test a parte per scansione (deve dichiarare formato non supportato, senza OCR).

### 5.5 Actual Budget — STUDIARE (solo architettura/UX)

- **Funzione/lacuna:** flussi di import CSV configurabili, documentazione di formati finanziari e pratiche di budget.
- **Equivalente e vantaggio:** ContaFlow già usa anteprima/lotto e ha budget mensile per categorie/sottovoci con proporzione giorni; non sostituire questi servizi con envelope budgeting senza requisito nuovo.
- **Separabilità:** codice TypeScript del core di dominio è separato dal client, ma non è una libreria Python; consultare flussi e casi di test, senza tradurre o copiare moduli.
- **Licenza:** MIT verificata su `LICENSE.txt`. Non è stata proposta una dipendenza né copiato codice, perciò il grafo NPM non è stato sottoposto a licenza completa.
- **Salute:** repository e documentazione mostrano import CSV/OFX/QFX/QIF/CAMT. Ultime release, manutentori e issue non valutati in modo quantitativo per questa scheda; non si fa affidamento su metriche di siti terzi.
- **Compatibilità:** Node/TypeScript, non un adapter Python/Tkinter. Nessuna compatibilità PyInstaller pertinente.
- **Rischi/test:** differenti definizioni di budget e categorie. Studiare soltanto l'anteprima e i controlli import; ogni eventuale cambiamento al budget deve mantenere segni, periodi proporzionali, EUR/CHF separati e i legacy.

### 5.6 Money Manager Ex — STUDIARE (schema come riferimento)

- **Funzione/lacuna:** schema DB, gerarchia categoria/sottocategoria, conti/cassa, import CSV configurabile e QIF.
- **Equivalente e vantaggio:** ContaFlow ha già database e flusso d'import specifici. Lo schema MMEX aiuta a costruire checklist di vincoli, ma un'adozione dello schema causerebbe un'ampia migrazione senza beneficio giustificato.
- **Separabilità:** repository `moneymanagerex/database` pubblica tabelle SQL e UML separatamente dall'app; si possono studiare concetti senza riusare codice.
- **Licenza:** GPL-2.0 verificata sia per MMEX sia per il repository schema; solo studio. Nessuna dipendenza proposta.
- **Salute:** repository app mostra attività di sviluppo e documenta funzionalità; non sono stati conteggiati issue e release. Database è separato, ma segnala alcune relazioni non imposte a livello SQL: non adottare lo schema senza analisi.
- **Compatibilità:** C++/wxWidgets; non libreria Python. Non applicabile PyInstaller.
- **Test:** eventuale uso di pattern richiede test ContaFlow su migrazioni additive, FK, archiviazione, idempotenza, audit e preservazione dati.

### 5.7 Beancount — STUDIARE (solo invarianti)

- **Funzione/lacuna:** modello a partita doppia e verifiche che ogni registrazione bilanci.
- **Equivalente e vantaggio:** ContaFlow non ha un journal generale a partita doppia; ha movimenti originali, categorie, natura contabile e legami di trasferimento. Non è un difetto se il prodotto rimane budgeting personale, ma una possibile direzione architetturale futura.
- **Separabilità:** parser/checker Python separabili tecnicamente, ma incorporamento vietato dalla regola di studio-only su copyleft; gli invarianti possono essere riscritti indipendentemente senza copiare codice.
- **Licenza/dipendenze:** GPL-2.0-only dal `pyproject.toml`; dipendenze dichiarate Click, python-dateutil e regex. Nessun grafo transitivo risolto; non adottare.
- **Salute:** repository e documentazione attivi secondo fonti consultate; metriche precise di release/issue non raccolte. Non risulta dichiarato archiviato.
- **Compatibilità:** progetto Python ≥3.9; 3.12 rientra nel requisito. Windows/PyInstaller ContaFlow non verificati.
- **Test:** se si introduce partita doppia in futuro, disegnare prima schema e migrazione indipendenti, con bilanciamento, storni, valute, trasferimenti e prova di non alterazione dello storico. Fuori dallo sprint corrente.

### 5.8 Firefly III — STUDIARE (solo flusso)

- **Funzione/lacuna:** regole d'import, ricorrenze, categorie, budget, doppia registrazione e report.
- **Equivalente e vantaggio:** servizi ContaFlow coprono già budget, categorie e collegamenti di trasferimento; utile solo confrontare flusso import e gestione delle regole.
- **Separabilità:** applicazione Laravel/PHP e importer collegato al suo modello/API; non separabile come dipendenza Tkinter senza riscrittura significativa.
- **Licenza:** AGPL-3.0 dichiarata dal repository; solo studio, nessuna copia/adattamento.
- **Salute:** repository mostra attività e documentazione; non è stato fatto audit completo di issue, release e catena composer per questo report.
- **Compatibilità:** PHP/web; Python 3.12, Tkinter e PyInstaller non applicabili.
- **Test:** nessuna integrazione proposta. Usare soltanto concetti e casi di test scritti autonomamente.

## 6. Proposte operative circoscritte — non implementate

### Proposta A: lettore XLSX openpyxl

- **Lacuna:** parser OOXML manuale, formati di file XLSX non coperti.
- **Moduli:** solo `adapters/chart.py`; mantenere `services/catalog_import.py`, preview/conferma e database invariati.
- **Dipendenza:** `openpyxl` e `et-xmlfile`, dopo verifica versione/licenze in ambiente isolato; aggiornare `build_windows.bat`/configurazione dipendenze solo nella futura implementazione. Aumento package non misurato.
- **Test prima:** fixture sintetica comparativa con casi elencati nella scheda; nessun import sui dati dell'utente.
- **Collaudo richiesto:** build PyInstaller onedir su Windows x64 Python 3.12; avvio senza Python globale; import fixture XLSX, errori, workbook multipli, file mancante. Controllare licenze incluse e dimensione prima/dopo.
- **Ritorno:** conservare il parser corrente dietro adapter/funzione; ripristinare import adapter e dipendenza dal file di build se un caso regressivo fallisce.
- **Stima:** contenuta, 1 modulo, circa 60–80 LOC di parsing da sostituire più test e build. Stima da affinare durante implementazione.

### Proposta B: suggeritore RapidFuzz

- **Lacuna:** candidati di fornitore per descrizioni simili ma non identiche.
- **Moduli:** nuova funzione pura in servizio classificazione o `contaflow/store.py`; pannello dettagli registro/gestione fornitori. Nessuna modifica automatica a storico o regole correnti.
- **Dipendenza:** RapidFuzz MIT, nessuna dipendenza runtime obbligatoria dichiarata; PyInstaller hook disponibile. Verificare licenza wheel distribuita, DLL/runtime e incremento del bundle, non misurati.
- **Test prima:** alias/regola esatti vincono; fuzzy propone solo candidati; ambiguità resta proposta; nessun match non modifica; scelta utente corrente o memorizzazione esplicita per i futuri compatibili.
- **Collaudo richiesto:** PyInstaller onedir su Windows x64 Python 3.12; test locale con descrizioni sintetiche, avvio pulito su PC senza toolchain, prova anti-falso-positivo con nomi generici.
- **Ritorno:** feature isolata e disattivabile; rimuovere il suggeritore senza toccare alias/regole già confermati.
- **Stima:** piccola, circa 20–50 LOC per ranking/soglie più UI, audit e test; dipendenza e rischio principale sono falsi suggerimenti.

Nessuna proposta autorizza installazione o modifica del repository applicativo prima della conferma dell'utente. La classifica non è approvazione all'integrazione.

## 7. Dati non verificati e collaudi pendenti

- Nessun pacchetto è stato installato, importato o eseguito, in ambiente isolato o altrimenti. Nessun benchmark o test di integrazione è stato eseguito.
- Nessuna build Windows x64 / Python 3.12 / PyInstaller onedir è stata realizzata per i candidati. Tutti i collaudi onedir sono pendenti.
- Versioni e licenze transitive complete di ofxparse non verificate; dettagli della release e stato attuale di issue/manutentori non verificati.
- Catena dipendenze/licenze e peso onedir per pdfplumber non completamente verificati.
- Non è stata verificata compatibilità di alcun parser con BPER o altri estratti italiani; manca un campione autorizzato. Nessun parser PDF/XLSX bancario va dichiarato completo.
- Non è stata verificata la dimensione effettiva dei bundle per i pacchetti candidati.
- Sicurezza: non è stato svolto un audit CVE esaustivo delle versioni e dipendenze candidate. Prima di adottare risolvere versioni bloccate, advisory e licenze tramite inventario isolato.
- Test dell'app citati nell'inventario derivano dallo stato del repository; in questa ricerca non è stata eseguita la suite ContaFlow.

## 8. Fonti primarie

Consultate il 6 novembre 2026. Le pagine di release e metadati sono dinamiche: riverificare prima dell'adozione.

- ContaFlow: [`STATO_SVILUPPO.md`](../STATO_SVILUPPO.md), `adapters/`, `services/`, `contaflow/`, `tests/` alla revisione remota indicata sopra.
- openpyxl: https://github.com/ericgazoni/openpyxl · https://pypi.org/project/openpyxl/ · et-xmlfile https://pypi.org/project/et-xmlfile/
- RapidFuzz: https://github.com/rapidfuzz/RapidFuzz · https://github.com/rapidfuzz/RapidFuzz/blob/main/pyproject.toml · https://github.com/rapidfuzz/RapidFuzz/releases · https://pypi.org/project/RapidFuzz/
- ofxparse: https://github.com/jseutter/ofxparse (README, LICENSE, setup.py, issues/release da rivalutare); PyPI/metadati runtime non accertati.
- pdfplumber: https://github.com/jsvine/pdfplumber · https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt · https://github.com/jsvine/pdfplumber/blob/stable/requirements.txt · https://github.com/pdfminer/pdfminer.six/blob/master/pyproject.toml · https://pypi.org/project/pdfplumber/
- Actual Budget: https://github.com/actualbudget/actual/blob/master/LICENSE.txt · https://github.com/actualbudget/actual/blob/master/packages/docs/docs/transactions/importing.md
- Money Manager Ex: https://github.com/moneymanagerex/moneymanagerex · https://github.com/moneymanagerex/database · https://moneymanagerex.org/docs/features/importexport/
- Beancount: https://github.com/beancount/beancount/blob/master/pyproject.toml
- Firefly III: https://github.com/firefly-iii/firefly-iii
- GnuCash: https://github.com/Gnucash/gnucash
- hledger: https://github.com/simonmichael/hledger
- ofxtools: https://github.com/csingley/ofxtools/blob/master/pyproject.toml
- pycamt: https://github.com/ODAncona/pycamt
- tksheet: https://github.com/ragardner/tksheet · https://pypi.org/project/tksheet/
