# Audit open source e proposte di riuso ContaFlow

**Consultazione:** 6 novembre 2026. **Repository analizzato:** `dragsber/ContaFlow`, branch `codex/contaflow-sviluppo`, HEAD remoto `f071337abb338eeb6fc25a654cfff2ec2bd56ae4` (`docs: analizza riusi open source per ContaFlow`). **Perimetro:** sola analisi documentale; nessun pacchetto di terzi è stato installato o eseguito, nessun database è stato aperto e nessun codice applicativo è stato modificato.

Le affermazioni sono marcate **Fatto** (fonte primaria/codice presente), **Stima** (intervallo ragionato, non misurazione) o **Non verificato**. L'assenza di una prova eseguibile significa che compatibilità e comportamento d'integrazione restano da collaudare.

## 1. Sintesi esecutiva

Le opportunità concrete non sono la sostituzione del nucleo contabile: ContaFlow ha già servizi locali con test per import Revolut, classificazione deterministica, sottovoci, budget, conti, trasferimenti, cassa, riconciliazione e migrazioni SQLite. Le lacune più nette sono parser bancari oltre Revolut, lettura XLSX robusta rispetto a OOXML complesso, estrazione di PDF digitali e candidati fuzzy non automatici.

**Raccomandazioni preliminari:** valutare `openpyxl` per rimuovere il lettore ZIP/XML scritto in casa; valutare `RapidFuzz` solo come generatore di candidati da confermare; mettere alla prova `statement-normalizer` su fixture sintetiche perché promette più formati ma è ancora poco maturo; usare `pdfplumber` solo dopo avere un esempio BPER autorizzato. Studiare i flussi di `ledgerbridge`, Actual Budget e Beancount senza importare i loro modelli nel database di ContaFlow.

Nessuna proposta qui è un'autorizzazione d'integrazione. Per ciascuna dipendenza occorre una successiva approvazione e una build Windows/PyInstaller onedir prima di adottarla.

## 2. Inventario di ContaFlow

Riferimenti al codice in `adapters/`, `services/`, `contaflow/` e `tests/`. I conteggi di righe sono indicativi del checkout consultato e non misurano da soli il lavoro necessario. Lo stato di collaudo è quello riportato in `STATO_SVILUPPO.md`; questo audit non ha rieseguito la suite.

| Area | Moduli e funzione presente | Stato e limite reale | Quantità personalizzata indicativa | Opportunità / rischio |
|---|---|---|---:|---|
| Revolut CSV | `adapters/revolut.py` (59 righe), `services/imports.py` (131), `services/finance.py` (406): parsing, anteprima/importazione, valuta, stati, deduplica | Operativo e coperto dai test sintetici; manuale Windows/EXE pendente per l'incremento più recente | 200–350 righe rilevanti | Preservare provider, fingerprint e import atomico. Un parser generico va dietro l'adapter, mai in sostituzione diretta |
| BPER, PDF, XLSX bancari, OFX/QIF/CAMT | `adapters/statements.py` (23) definisce il punto d'estensione; non risultano parser bancari BPER/PDF/XLSX né OFX/QIF/CAMT completi | Predisposto, non operativo. Per BPER servono campioni autorizzati; parser PDF generico non basta | Da zero: molto variabile; non stimabile senza formati e campioni | Miglior area per nuova capacità, ma specifica banca, anteprima e verifica saldi rimangono codice ContaFlow |
| Excel / workbook | `adapters/chart.py` (87) legge XLSX con ZIP/XML; `services/catalog_import.py` (201) mappa fogli/colonne, valida, mostra anteprima e importa associazioni | Importatore operativo con XLSX sintetico; parser OOXML scritto ad hoc e limiti su formule, stili, celle condivise e casi non previsti. Esportazione budget presente come CSV, non XLSX | 288 righe, di cui 87 parser | `openpyxl` può eliminare il parser OOXML manuale; controllare rigorosamente formule e non importare dati senza conferma |
| Workbook di riferimento | Interpretazione di `Budget 2025_Marco.xlsx` annotata in `STATO_SVILUPPO.md` | Il proprietario lo descrive come esempio incompleto, non schema normativo. Nessun codice/relazione va inventato o importato automaticamente | Funzione di mappatura configurabile esistente | Librerie XLSX aiutano la lettura, non determinano il significato di celle o formule |
| Classificazione / fornitori | `contaflow/store.py` (310), `services/subcategories.py` (369), GUI `contaflow/register.py` (354), editor movimento e fornitori nell'app | Alias esatti e regole confermate; ambiguità mantenuta come proposta. Test automatici presenti; collaudo manuale recente pendente | Circa 700–1.000 righe distribuite tra servizio, persistenza e GUI | Similarità fuzzy solo candidati; sostituire l'ordine o riclassificare storico sarebbe regressione |
| Budget / report | `services/budget.py` (93), `services/period_report.py` (52), `contaflow/budget.py` (95), `contaflow/subcategories.py` (295) | Budget per sottovoce, consuntivo, legacy, periodi proporzionali, EUR/CHF separati, CSV; test sintetici riportati. Manuale GUI/export pendente | Circa 535 righe specifiche | Nessun progetto generalista è sostituzione vantaggiosa: preservare regole approvate su segni, quote giornaliere e arrotondamenti |
| Conti, saldi, trasferimenti, cassa, riconciliazione | `services/accounts.py` (126), `transfers.py` (174), `cash.py` (48), `reconciliation.py` (84), GUI `contaflow/accounts.py` (271) | Operativo e testato su dati sintetici secondo lo stato; collaudo Windows pendente. Limiti funzionali dettagliati nello stato | Circa 700 righe | Nessuna libreria plug-in risolve la semantica locale senza migrazione e rischio elevati |
| Partita doppia / piano dei conti | Riferimento contabile aggiuntivo; non è un giornale generalizzato a partita doppia | Funzione non implementata come ledger generale; i codici del workbook non sono autorità e non vanno inventati | Nuovo dominio consistente; non stimabile senza requisiti | Studiare Beancount/GnuCash per invarianti; non adottarne schema o motore senza decisione architetturale |
| GUI | `contaflow/app.py` (791) e viste Tkinter/ttk specializzate; Treeview, ricerca, filtri, ordinamento, dettagli | Operativa; test widget parzialmente saltati quando manca display. Non sono indicate necessità di grafici avanzati | Circa 1.500 righe GUI complessive | Nuovo toolkit o framework comporta riscrittura non giustificata. No beneficio sufficiente per una dipendenza grafica |
| SQLite, migrazioni, backup, audit | `services/finance.py`, `contaflow/store.py`, `contaflow/diagnostics.py` (123), `tests/test_restore.py` e test migrazioni | SQLite locale, migrazioni additive, controlli/backup e ripristino esplicitamente testati nello stato di progetto | Circa 700 righe principali più test | Nessun ORM o database alternativo consigliato. Rischio dati alto; non sostituire |

**Dato di regressione da preservare:** lo stato del progetto riporta cinque movimenti sintetici con variazione netta `393,10 EUR`. Questo audit non ha rieseguito né modificato quei test/dati.

## 3. Metodo di ricerca

### Query e fonti

Consultate il 6 novembre 2026: ricerche GitHub per `bank statement parser Python`, `CSV OFX CAMT parser`, `statement normalization Decimal`, `bank transaction reconciliation`, `merchant matching Python`, `double-entry accounting`, `personal finance budget import`; ricerche PyPI per i pacchetti Python; pagine ufficiali README, licenze, documentazione, `pyproject.toml`/metadati e release. Le schede sotto linkano le fonti primarie, non classifiche o aggregatori come prova di licenza.

Nessun repository terzo è stato clonato, scaricato, installato o eseguito. Non è stata risolta una catena completa di dipendenze con ambiente isolato; pertanto le licenze transitive non dichiarate sotto sono **non verificate**. Le issue sono state usate come segnale qualitativo, non come conteggio di bug o prova di vulnerabilità. Data di consultazione comune: 2026-11-06.

### Lista breve (massimo 15)

| Progetto | Repository / pacchetto | Cosa è emerso |
|---|---|---|
| statement-normalizer | [GitHub](https://github.com/Maxed-OSS/statement-normalizer) | Parser deterministico multi-formato, Decimal, dedup; promettente ma appena 5 commit, nessuna release PyPI verificata |
| ledgerbridge | [GitHub](https://github.com/MugenLab/ledgerbridge) | CLI multi-formato, profili, controlli saldo e test sintetici dichiarati; giovane e accoppiato a esportatori contabili |
| openpyxl | [PyPI](https://pypi.org/project/openpyxl/) · [documentazione](https://openpyxl.readthedocs.io/) | Lettura/scrittura OOXML XLSX; corrisponde al parser manuale ContaFlow |
| RapidFuzz | [GitHub](https://github.com/rapidfuzz/RapidFuzz) · [PyPI](https://pypi.org/project/RapidFuzz/) | Similarità stringhe ad alte prestazioni; utile solo per suggerimenti |
| pdfplumber | [GitHub](https://github.com/jsvine/pdfplumber) · [documentazione](https://github.com/jsvine/pdfplumber/blob/stable/README.md) | Estrazione testo/geometria/tabelle da PDF digitali; nessun profilo BPER |
| ofxparse | [GitHub](https://github.com/jseutter/ofxparse) · [PyPI](https://pypi.org/project/ofxparse/) | Parser OFX/QFX; progetto MIT, compatibilità Python moderna e grafo dipendenze da verificare |
| Actual Budget | [GitHub](https://github.com/actualbudget/actual) · [guide import](https://actualbudget.org/docs/transactions/importing/) | Formati e UX import/budget; TypeScript, riferimento architetturale |
| Beancount | [GitHub](https://github.com/beancount/beancount) · [documentazione](https://beancount.github.io/docs/) | Validazione contabile a partita doppia; GPL, studio soltanto |
| Money Manager Ex | [GitHub](https://github.com/moneymanagerex/moneymanagerex) · [schema DB](https://github.com/moneymanagerex/database) | Applicazione personale e schema SQLite; GPL, studio soltanto |
| Firefly III | [GitHub](https://github.com/firefly-iii/firefly-iii) · [documentazione](https://docs.firefly-iii.org/) | Flussi contabili e regole; AGPL/PHP, studio soltanto |
| GnuCash | [GitHub](https://github.com/Gnucash/gnucash) · [documentazione](https://www.gnucash.org/docs.phtml) | Modello contabile maturo e riconciliazione; stack C/Guile, studio soltanto |
| hledger | [GitHub](https://github.com/simonmichael/hledger) · [documentazione](https://hledger.org/) | Ledger a partita doppia, import e report; Haskell/GPL, studio soltanto |
| ofxtools | [GitHub](https://github.com/csingley/ofxtools) · [PyPI](https://pypi.org/project/ofxtools/) | OFX parser/generator; GPL, Python moderno dichiarato; studio soltanto |
| ofxstatement | [GitHub](https://github.com/kedder/ofxstatement) · [PyPI](https://pypi.org/project/ofxstatement/) | Interfaccia a plugin per profili bancari; GPL, studio del contratto plug-in |
| bankstatementparser | [GitHub](https://github.com/sebastienrousseau/bankstatementparser) · [PyPI](https://pypi.org/project/bankstatementparser/) | Parser ampio con dipendenze numerose, inclusi componenti nativi; beneficio netto dubbio per un'app desktop leggera |

`pycamt` è stato esaminato come alternativa CAMT ma non entra nella lista breve perché la licenza GPL-3.0 e la specializzazione dichiarata su dialetti CAMT non risolvono un bisogno ContaFlow senza un file campione. `pdfplumber` non esegue OCR. `openpyxl` non ricalcola formule Excel: il valore calcolato va letto solo se presente nel file e deve essere trattato come tale.

## 4. Tabella comparativa delle decisioni

| Progetto | Repository | Funzione | Licenza | Modalità di riuso | Compatibilità | Beneficio atteso | Decisione | Priorità |
|---|---|---|---|---|---|---|---|---|
| openpyxl | [foss.heptapod.net/openpyxl/openpyxl](https://foss.heptapod.net/openpyxl/openpyxl), [PyPI](https://pypi.org/project/openpyxl/) | Parser e writer XLSX | MIT; `et-xmlfile` MIT; transitive complete non risolte (verifica parziale) | Dipendenza | Python ≥3.8 dichiarato; wheel disponibile; Windows/PyInstaller ContaFlow non testati | Sostituisce 87 righe di ZIP/XML artigianale e riduce casi OOXML da mantenere | **ADOTTARE** dopo test e approvazione | Alta |
| RapidFuzz | [rapidfuzz/RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | Scoring stringhe | MIT; dipendenze runtime Python/C++ del pacchetto, catena completa non risolta | Dipendenza | Python ≥3.11 e wheel Windows x64 dichiarati; PyInstaller hook documentato; build ContaFlow non testata | Nuovi candidati fornitore, nessuna sostituzione del classificatore | **ADOTTARE** solo come suggeritore dopo test e approvazione | Media |
| pdfplumber | [jsvine/pdfplumber](https://github.com/jsvine/pdfplumber) | Estrazione PDF testuale/geometrica | MIT; pdfminer.six MIT; licenze/avvisi dell'intera catena e componenti nativi da completare | Dipendenza dopo audit | Py 3.10–3.14 dichiarato dal README; Windows/PyInstaller non testati | Evita primitive PDF generiche; il profilo bancario resta da scrivere | **STUDIARE** | Alta, condizionata ai campioni |
| statement-normalizer | [Maxed-OSS/statement-normalizer](https://github.com/Maxed-OSS/statement-normalizer) | Normalizzazione CSV/OFX/QFX/MT940/CAMT/QIF/testo | Apache-2.0 dichiarata; dipendenze runtime assenti dichiarate; release/pacchetto non verificati | Componente/dipendenza da valutare | CI e Python 3.9+ dichiarati; Windows/PyInstaller solo spot check del progetto, non replicato | Potrebbe ridurre parser multi-formato da zero; non include profili BPER, PDF o flusso ContaFlow | **STUDIARE** | Alta, ma immaturo |
| ledgerbridge | [MugenLab/ledgerbridge](https://github.com/MugenLab/ledgerbridge) | Import e controlli saldi/duplicati | MIT dichiarata dal repository; licenze di dipendenze da confermare; nessun pacchetto PyPI verificato | Solo studio / prova isolata | Python ≥3.10 e assenza dipendenze dichiarati; Windows/PyInstaller non verificati | Test cases e idea di profili/controllo saldi, non sostituisce la riconciliazione | **STUDIARE** | Media |
| ofxparse | [jseutter/ofxparse](https://github.com/jseutter/ofxparse) | Parsing OFX/QFX | MIT dichiarata; BeautifulSoup/lxml/six e catena da verificare per versione | Dipendenza candidata | Python classifiers datati; Python 3.12 e PyInstaller non verificati | Aggiunge solo parsing OFX/QFX | **STUDIARE** | Media-bassa |
| Actual Budget | [actualbudget/actual](https://github.com/actualbudget/actual) | Import e budget personale | MIT; dipendenze NPM non audit per questo studio | Solo studio | TypeScript/Node; non plug-in Python/Tkinter | Flussi di anteprima, import e casi di test; budget diverso da quello approvato | **STUDIARE** | Bassa |
| Beancount | [beancount/beancount](https://github.com/beancount/beancount) | Contabilità a partita doppia e validazione | GPL-2.0-only; dipendenze Python: licenze transitive non esaminate | Solo studio | Python attuale dichiarato; integrazione e PyInstaller non verificate | Invarianti e report, nessuna sostituzione sicura del database corrente | **STUDIARE** | Bassa |
| Money Manager Ex | [moneymanagerex/moneymanagerex](https://github.com/moneymanagerex/moneymanagerex) | Applicazione finanze e schema DB | GPL-2.0 | Solo studio | C++/wxWidgets, non componente Python | Idee di schema/import; conversione schema è rischio e costo alto | **STUDIARE** | Bassa |
| Firefly III | [firefly-iii/firefly-iii](https://github.com/firefly-iii/firefly-iii) | Contabilità personale e regole | AGPL-3.0 | Solo studio | PHP/server, non desktop Python | Casi d'uso per regole e report; diversa architettura | **STUDIARE** | Bassa |
| GnuCash | [Gnucash/gnucash](https://github.com/Gnucash/gnucash) | Contabilità e riconciliazione | GPL; perimetro esatto delle licenze componenti non auditato | Solo studio | C/Guile e stack proprio | Riferimento contabile, non riuso plug-in | **STUDIARE** | Bassa |
| hledger | [simonmichael/hledger](https://github.com/simonmichael/hledger) | Ledger, import e report | GPL-3.0 | Solo studio | Haskell; nessuna integrazione diretta | Idee di report/validazione, non sostituzione | **STUDIARE** | Bassa |
| ofxtools | [csingley/ofxtools](https://github.com/csingley/ofxtools) | Parsing/creazione OFX | GPL-3.0-only | Solo studio | Python moderno classificato; PyInstaller non provato | Alternativa tecnica, bloccata dalla licenza per incorporazione | **NON UTILIZZARE** come codice/dipendenza | Bassa |
| ofxstatement | [kedder/ofxstatement](https://github.com/kedder/ofxstatement) | Framework plugin per profili bancari | GPL-3.0 (verificare release specifica prima di ogni uso) | Solo studio | Python; Windows/PyInstaller non testati | Contratto plugin e test per banca utili, ma ContaFlow ha già un adapter seam | **STUDIARE** | Bassa |
| bankstatementparser | [sebastienrousseau/bankstatementparser](https://github.com/sebastienrousseau/bankstatementparser) | Parser multi-formato | Apache-2.0 OR MIT dichiarate; catena diretta/transitiva non verificata integralmente | Non adottare ora | Core dipendenze ampie; presenza di lxml/Pandas/Pydantic dichiarata, impatto EXE non misurato | Rischio di dipendenze superiore alla capacità attualmente necessaria | **NON ADOTTARE** ora | Bassa |

Per `ADOTTARE`, la licenza principale e le dipendenze dirette evidenti sono state controllate su PyPI/repository, ma il grafo transitivo non è stato risolto in un lock isolato. L'adozione resta subordinata all'audit licenze completo delle versioni selezionate, test Windows x64/Python 3.12 e bundle PyInstaller. “ADOTTARE” qui significa raccomandazione per un incremento futuro, non implementazione autorizzata.

## 5. Schede approfondite degli 8 candidati migliori

### 5.1 openpyxl — ADOTTARE dopo approvazione e prove

- **Fonti (2026-11-06):** [PyPI e metadati/versione](https://pypi.org/project/openpyxl/), [documentazione](https://openpyxl.readthedocs.io/), [repository upstream](https://foss.heptapod.net/openpyxl/openpyxl), [licenza su PyPI](https://pypi.org/project/openpyxl/), [et-xmlfile](https://pypi.org/project/et-xmlfile/).
- **Fatto:** openpyxl legge/scrive XLSX/XLSM/XLTX/XLTM; PyPI consultato riportava versione 3.1.5, MIT, Python ≥3.8, release 28 giugno 2024, due maintainer. Dipendenza runtime diretta: `et-xmlfile`, MIT. Quest'ultimo aveva release 25 ottobre 2024. La documentazione avverte che la protezione da XML Billion Laughs/quadratic blowup richiede `defusedxml`.
- **Cosa sostituisce:** il parser OOXML ZIP/XML locale `adapters/chart.py` (87 righe), non l'importatore e le sue regole. `services/catalog_import.py` resta responsabile di mapping, validazione, anteprima, conflitti, conferma e audit.
- **Beneficio:** evita mantenere un lettore casalingo di shared strings, celle e fogli; migliore copertura di file XLSX ordinari. Non ricalcola formule e non deve inferire categorie dai nomi. Il workbook utente resta un riferimento configurabile.
- **Stima, non misurata:** implementare e mantenere parsing XLSX robusto in casa: circa 12–24 ore per testare casi OOXML comuni, date, celle vuote/formule, shared strings e errori; integrazione openpyxl: 4–10 ore più test. Risparmio netto atteso 2–20 ore, con valore soprattutto nella riduzione del rischio e non nei LOC.
- **Compatibilità:** documentata Python ≥3.8 e wheel pure Python; Windows 11 e PyInstaller onedir non testati in ContaFlow. SQLite/Tkinter non coinvolti. Aumento EXE non misurato.
- **Rischi/condizioni:** audit versione per `et-xmlfile`, attribuzione MIT, XML non fidato, mantenere import solo dopo anteprima. Test sintetici con formule (valore cached assente/presente), date, codici con zeri, fogli e righe vuote; confrontare l'anteprima e il risultato dell'attuale importatore. Piano di ritorno: mantenere l'interfaccia dell'adapter e reindirizzarla al parser precedente se il test Windows fallisce.

### 5.2 RapidFuzz — ADOTTARE solo come suggeritore

- **Fonti (2026-11-06):** [GitHub](https://github.com/rapidfuzz/RapidFuzz), [documentazione](https://rapidfuzz.github.io/RapidFuzz/), [PyPI versione 3.14.6](https://pypi.org/project/RapidFuzz/), [manifesto progetto](https://github.com/rapidfuzz/RapidFuzz/blob/main/pyproject.toml), [PyInstaller hook](https://github.com/rapidfuzz/RapidFuzz/blob/main/rapidfuzz/__init__.py).
- **Fatto:** MIT; 3.14.6 pubblicata 30 agosto 2026; Python ≥3.11 e classificatore 3.12 dichiarati. Implementazione C++ con binding Python; wheels Windows x86-64 presenti nei metadati. PyPI descrive metriche multiple e API di ricerca. Repository consultato: issue e PR aperte, sviluppo non fermo. PyInstaller hook/metadata presenti; non prova il bundle ContaFlow.
- **Cosa affianca:** `contaflow/store.py` e `services/subcategories.py` mantengono l'ordine classificatorio esistente. RapidFuzz aggiungerebbe soltanto candidati suggeriti quando alias e regole deterministiche non danno un risultato certo. Non assegna né fonde fornitori.
- **Stima:** prima implementazione autonoma di normalizzazione, scoring e ranking candidato, con limiti e test: 12–32 ore. Integrazione limitata nel servizio e GUI: 8–20 ore; beneficio netto stimato da −8 a +24 ore. È una nuova capacità, quindi il vantaggio netto potrebbe essere modesto; vale se si desidera una coda di revisione utile.
- **Compatibilità:** Python 3.12 e wheel Windows x64 documentati; PyInstaller hook presente; non installato né provato su Windows/PyInstaller. Componente nativo C++ implica controllo DLL/wheel; dimensione EXE non misurata.
- **Rischi/test:** falsi positivi di nomi simili. Test devono provare alias esatto sempre prioritario, soglie conservative, candidati senza scrittura DB, nomi ambigui lasciati in proposta/in attesa, nessuna riclassificazione dello storico e assenza di mutazioni prima della conferma. Rollback semplice: disabilitare suggeritore mantenendo regole correnti.

### 5.3 pdfplumber — STUDIARE, attivare solo con campione bancario

- **Fonti (2026-11-06):** [repository](https://github.com/jsvine/pdfplumber), [README](https://github.com/jsvine/pdfplumber/blob/stable/README.md), [licenza](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt), [PyPI](https://pypi.org/project/pdfplumber/), [pdfminer.six](https://github.com/pdfminer/pdfminer.six), [dipendenze](https://github.com/jsvine/pdfplumber/blob/stable/requirements.txt).
- **Fatto:** MIT; estrae caratteri, posizioni, linee e tabelle. README dichiara test su Python 3.10–3.14 e migliore comportamento con PDF digitali. Si appoggia a pdfminer.six; dipendenze/versioni rilevate nel file di requisiti includono Pillow e pypdfium2. Non fa OCR né identifica da solo la semantica bancaria. Issues attive comprendono temi estrazione tabelle/memoria; non si è verificato un advisory di sicurezza specifico.
- **Equivalente:** `adapters/statements.py` non ha parser PDF. La libreria può fornire primitive geometriche; mapping colonne, righe spezzate, segni, valuta, commissioni, data e saldo devono restare in adapter specifico.
- **Stima:** estrazione robusta di layout PDF digitale da zero 40–100 ore; integrare un estrattore con anteprima 8–20 ore, beneficio netto potenziale 20–92 ore **solo per primitive riutilizzabili**. Il parser BPER rimane stimabile soltanto con un PDF d'esempio (ulteriori 16–40+ ore ipotetiche, non incluse nel beneficio).
- **Compatibilità:** Python moderno documentato; nessuna prova Windows 11/PyInstaller. Dipendenze native/ruote e licenze transitive non auditate completamente; aumento EXE non misurato.
- **Rischi/test:** usare esclusivamente campione sintetico o debitamente autorizzato e fixture senza dati personali. Test multi-pagina, righe che vanno a capo, header, separatori decimali, importo/commissione, pagine vuote e scansione. Se file immagine/scansione: dichiarare non supportato, senza OCR. Nessuna dichiarazione “parser BPER pronto” prima di test reali autorizzati.

### 5.4 statement-normalizer — STUDIARE e verificare maturità

- **Fonti (2026-11-06):** [repository](https://github.com/Maxed-OSS/statement-normalizer), [README](https://github.com/Maxed-OSS/statement-normalizer/blob/main/README.md), [licenza](https://github.com/Maxed-OSS/statement-normalizer/blob/main/LICENSE), [manifesto](https://github.com/Maxed-OSS/statement-normalizer/blob/main/pyproject.toml), [test](https://github.com/Maxed-OSS/statement-normalizer/tree/main/tests).
- **Fatto dichiarato dal progetto:** normalizza CSV, OFX/QFX, MT940, CAMT.053, QIF e testo in un modello con importi Decimal; deduplica via identificativo o hash di contenuto; dichiara zero dipendenze runtime, Apache-2.0 e Python 3.9+. La pagina GitHub consultata mostrava 5 commit, CI dichiarata su Python 3.9–3.13 e test sintetici. L'installazione PyPI non è stata verificata: nessuna release registrata verificata durante la ricerca.
- **Equivalente:** l'adapter Revolut è specifico e operativo; `adapters/statements.py` è solo predisposizione. Il progetto potrebbe fornire parser/formato e modello normalizzato, non preview/lotto, import atomico, saldo, controlli conto/provider o persistenza ContaFlow. Nessun parser PDF o BPER specifico verificato.
- **Stima:** parser di base per 4–6 formati da zero: 60–140 ore (parser, date/segni, edge cases e fixture); integrare e adattare un parser di terzi: 12–28 ore, potenziale risparmio 32–128 ore. Intervallo ampio dato il progetto giovane; esclusi mapping specifici di ciascuna banca, UI e test con campioni reali.
- **Compatibilità:** CI e Python 3.9–3.13 dichiarati; nessuna prova indipendente né build Windows/PyInstaller. Licenza principale verificata nel file, dipendenze runtime nulle dichiarate, versione e pacchetto non verificati, dimensione non misurata.
- **Test/rischi:** prima audit codice e API, poi fixture sintetiche per ogni parser; importi `Decimal`, timezone, valute, duplicati tra intervalli, pending, segno e identità originali. Confronto byte/dati di origine con modello ContaFlow. Nessun passaggio automatico da parser a classificazione. Ritorno: adapter indipendente selezionabile, senza cambiare database.

### 5.5 ledgerbridge — STUDIARE casi di test e controlli di saldo

- **Fonti (2026-11-06):** [repository](https://github.com/MugenLab/ledgerbridge), [README](https://github.com/MugenLab/ledgerbridge/blob/main/README.md), [licenza](https://github.com/MugenLab/ledgerbridge/blob/main/LICENSE), [test](https://github.com/MugenLab/ledgerbridge/tree/main/tests).
- **Fatto dichiarato:** CLI offline senza dipendenze runtime, formati CSV/OFX/QFX/QIF/CAMT.053, esportatori Beancount/hledger/Firefly, profili banca, deduplica e verifiche running-balance. Repository trovato tramite topic GitHub; dichiara MIT e attività al 9 settembre 2026. README dichiara Python ≥3.10 e test sintetici. La distribuzione PyPI non è stata verificata; non è stato clonato o eseguito. La license chain degli exporter non è stata auditata.
- **Equivalente:** `services/reconciliation.py` (84 righe) confronta saldo dichiarato e calcolato; `adapters/revolut.py` ha validazioni specifiche. ledgerbridge non sostituisce questa riconciliazione né gestisce i dati ContaFlow; utile come checklist per controlli di import e fixture.
- **Stima:** progettare profili e running-balance checks trasversali ai parser: 20–50 ore; esaminare e tradurre soltanto checklist/test: 4–12 ore; risparmio 8–40 ore potenziale, non dimostrato. Non è stimabile il beneficio di adozione diretta senza verificare API, licenze e precisione sui formati target.
- **Compatibilità:** Python e Windows/PyInstaller non verificati indipendentemente; zero dipendenze è dichiarato. Non proporre come dipendenza né incorporare codice nella fase attuale.
- **Rischio/test:** formato del saldo progressivo può essere assente o diverso, operazioni pending e commissioni possono avere semantiche bancarie diverse. Adattare solo concetti e test sintetici; nessun auto-fix degli importi o segnalazione certa di movimento mancante.

### 5.6 ofxparse — STUDIARE, non preferire senza confronto

- **Fonti (2026-11-06):** [repository](https://github.com/jseutter/ofxparse), [PyPI](https://pypi.org/project/ofxparse/), [setup.py e dipendenze dichiarate](https://github.com/jseutter/ofxparse/blob/master/setup.py), [licenza](https://github.com/jseutter/ofxparse/blob/master/LICENSE).
- **Fatto:** PyPI consultato riportava 0.21, MIT e release 31 maggio 2021; repository dichiara supporto a OFX. `setup.py` elenca dipendenze/prove con BeautifulSoup, lxml e six; i classificatori Python sono datati e non attestano 3.12. `lxml` introduce un'estensione nativa.
- **Equivalente e vantaggio:** nessun parser OFX attuale in ContaFlow, quindi capacità aggiuntiva, non sostituzione. Può essere un'alternativa più specifica di un normalizzatore generico, ma non sono stati esaminati profondamente parser edge case né release moderne.
- **Stima:** parser OFX fatto in casa 20–50 ore; integrazione 8–20 ore, beneficio potenziale 0–42 ore. Le ore si sovrappongono allo sviluppo con statement-normalizer e non vanno sommate.
- **Compatibilità:** metadata Python 3.12/Windows/PyInstaller non dimostrati. Dipendenze e licenze vanno risolte per versione; bundle non misurato.
- **Test/rischi:** OFX XML e SGML, date/timezone, split, fee, investimenti e stati. Import sintetici e confronti con saldo; non modificare fingerprint né dati sorgenti. Prima di scegliere confrontare copertura, manutenzione e packaging con `statement-normalizer`.

### 5.7 Actual Budget — SOLO STUDIO di import/UX

- **Fonti (2026-11-06):** [repository](https://github.com/actualbudget/actual), [licenza](https://github.com/actualbudget/actual/blob/master/LICENSE.txt), [documenti import](https://actualbudget.org/docs/transactions/importing/), [test](https://github.com/actualbudget/actual/tree/master/packages).
- **Fatto:** app local-first in TypeScript/JavaScript, MIT; documentazione descrive import CSV e formati finanziari tra cui QIF/OFX/QFX/CAMT. Non è una libreria Python o un componente Tk. Non è stata verificata integralmente la licenza NPM transitiva.
- **Valore:** studiare la UX di mapping/anteprima/errori e la copertura di fixture, non sostituire il motore budget di ContaFlow. ContaFlow ha già budget per sottovoce, periodo inclusivo e proporzione giornaliera.
- **Stima:** import UX autonomo è in parte già esistente; studiare flussi può evitare 4–12 ore di rifiniture, ma il risparmio non è misurabile con precisione. Integrare l'app o tradurne il codice è sconsigliato.
- **Compatibilità/rischi:** nessuna compatibilità Python/PyInstaller. Mantenere i segni, le regole legacy e il modello di budget ContaFlow. Nessuna dipendenza da aggiungere.

### 5.8 Beancount — SOLO STUDIO di invarianti contabili

- **Fonti (2026-11-06):** [repository](https://github.com/beancount/beancount), [licenza](https://github.com/beancount/beancount/blob/master/LICENSE), [documentazione](https://beancount.github.io/docs/), [manifesto e dipendenze](https://github.com/beancount/beancount/blob/master/pyproject.toml), [test](https://github.com/beancount/beancount/tree/master/beancount).
- **Fatto:** progetto Python per contabilità a partita doppia e validazione di giornali; licenza `GPL-2.0-only`; metadati Python ≥3.9. Il progetto usa dipendenze tra cui Click, python-dateutil e regex; licenze transitive non esaminate per un'integrazione perché non è proposta.
- **Valore:** studiare quadratura, conti, vincoli e rappresentazione multi-valuta prima di eventuali sviluppi contabili più formali. ContaFlow al momento registra movimenti bancari e trasferimenti collegati, ma non un motore generalizzato di scritture doppie.
- **Decisione:** non copiare/adattare né introdurre come dipendenza sotto questo mandato. La licenza copyleft richiede revisione umana per qualunque possibile distribuzione/integrazione.
- **Compatibilità/rischi:** ambiente Windows/PyInstaller non verificato; importo e modello di persistenza sono diversi. Nessuna migrazione di schema giustificata. Stimare una futura partita doppia non è possibile senza definire requisiti.

## 6. Classifica dei cinque interventi a beneficio atteso

Le stime sono **ore di sviluppo indicative**, non misure né preventivi; assumono un solo sviluppatore che conosce già ContaFlow, test sintetici e nessun requisito bancario non documentato. Gli interventi 1, 3, 4 e 5 coprono aree parziali e non sono sommabili automaticamente: OFX normalizer e OFX parser sono alternative.

| Pos. | Intervento | Codice/moduli interessati | Lavoro autonomo evitabile → integrazione | Beneficio netto atteso | Difficoltà / rischio | Verifica e priorità |
|---:|---|---|---|---|---|---|
| 1 | Valutare `statement-normalizer` come parser dietro adapter | Aggiungere adapter accanto a `adapters/statements.py`; preservare `services/imports.py`, fingerprint e lotto | 60–140 h parser multi-formato → 12–28 h adattamento e audit | +32–128 h teorici; progetto giovane rende intervallo incerto | Media-alta; rischio maturità, corner case, nessun profilo BPER/PDF | **STUDIARE prima**; priorità massima solo dopo audit API e prove su fixture |
| 2 | `openpyxl` per lettura workbook | Sostituire solo `adapters/chart.py`; preservare `services/catalog_import.py` | 12–24 h lettore/manutenzione OOXML → 4–10 h integrazione | +2–20 h e meno rischio di formati XLSX | Bassa-media; formule non ricalcolate, sicurezza XML e bundle | **ADOTTARE** dopo approvazione, test sintetici e PyInstaller |
| 3 | `pdfplumber` come estrattore del PDF digitale | Nuovo adapter PDF in `adapters/statements.py` | 40–100 h primitive PDF → 8–20 h estrattore | +20–92 h sulle primitive, non sul parser bancario | Media-alta; layout bancario resta specifico, dipendenze native/packaging | **STUDIARE**; sbloccare solo dopo campione BPER autorizzato |
| 4 | `RapidFuzz` per generare candidati di fornitori | Affiancare `services/subcategories.py`/classificazione; GUI mostra motivazione e alternative | 12–32 h scoring autonomo → 8–20 h integrazione | −8 a +24 h; beneficio più qualitativo che di volume | Bassa-media; falsi positivi e C++/DLL su Windows | **ADOTTARE** come suggeritore solo con conferma e test anti-autoassegnazione |
| 5 | Matrice di profili/check saldi ispirata a `ledgerbridge` | Rafforzare test/import service, senza sostituire `services/reconciliation.py` | 20–50 h per regole/check ripetuti → 4–12 h studio/adattamento | +8–40 h ipotetici, non validati | Media; codice/API/licenze non auditati, formato estratto variabile | **STUDIARE** test e flussi; niente incorporazione |

### Interventi selezionati — piano operativo non autorizzativo

**A. openpyxl** — Obiettivo: sostituire la lettura OOXML artigianale e mantenere invariato il workflow di import associazioni. Versione di riferimento: 3.1.5, PyPI. Moduli coinvolti: `adapters/chart.py`; preservare `services/catalog_import.py`, mapping e anteprima. Test prima: fogli multipli, righe vuote, codici con zero iniziale, formule con/senza cached result, errori e import rieseguito senza duplicati. Sequenza: adapter dietro interfaccia esistente → confronto con parser precedente su fixture sintetiche → integrazione → test full → build Windows Python 3.12/PyInstaller onedir. Ritorno: revert del solo adapter/dipendenza, database immutato. `build_windows.bat`: aggiungere pacchetto soltanto al manifest/build se necessario. Impatto pacchetto: openpyxl + et-xmlfile, dimensione non misurata. Licenze MIT e attribuzioni da registrare secondo policy, audit transitive prima di distribuire. Stima 4–10 h d'integrazione e 2–20 h nette potenziali.

**B. RapidFuzz** — Obiettivo: presentare candidati di fornitore senza assegnare o unire automaticamente. Moduli: servizio di classificazione e dettaglio registro; preservare alias esatto, regole e stati. Test prima: l'ordine deterministico non cambia; nessuna scrittura quando appare un candidato; ambiguità senza abituale resta proposta/in attesa; conferma esplicita può solo registrare regola futura; fixture storiche byte/logicamente invariate. Integrazione isolata dietro funzione suggerimenti e flag disattivabile; Windows/PyInstaller x64 deve caricare le estensioni. Ritorno: disabilitare/rimuovere suggeritore senza migrazioni. `build_windows.bat`: assicurare wheel cp312-win_amd64 e raccolta DLL. Impatto pacchetto non misurato. MIT verificata per RapidFuzz; risolvere il grafo packaging e mantenere attribuzione. Stima integrazione 8–20 h, beneficio netto incerto.

Per `statement-normalizer`, `pdfplumber` e ledgerbridge non si propone ancora adozione: prima servono audit tecnico/legale e fixture; non modificare il build né il database in questa fase.

## 7. Licenze, dipendenze e salute: cautele

- **openpyxl:** MIT. Dipendenza diretta `et-xmlfile` MIT. Verificare lock e licenze complete al momento dell'adozione; il messaggio di sicurezza XML è rilevante quando workbook non fidati vengono aperti. La documentazione stessa indica `defusedxml` per protezione da espansioni XML; valutare se necessario senza aggiungerlo automaticamente.
- **RapidFuzz:** MIT e libreria C++/Python; wheel Windows osservate nei metadati PyPI. Verificare licenza dei binari inclusi, wheel Python 3.12 esatta e hook di PyInstaller. Nessuna dipendenza runtime ulteriore dichiarata dai metadati esaminati; non è stata eseguita la risoluzione.
- **pdfplumber:** MIT; pdfminer.six MIT. Componenti dipendenti e transitive devono essere enumerati alla versione scelta. Pillow/PDFium possono aggiungere binari e peso; licenze e dimensioni non convalidate in un bundle. Nessuna scansione PDF/OCR.
- **statement-normalizer:** Apache-2.0 nel repository e “zero runtime dependency” dichiarato; 5 commit e assenza di release verificata impongono review manuale del codice, delle licenze incluse e della stabilità API prima dell'uso.
- **ledgerbridge:** MIT dichiarata e zero dipendenze runtime dichiarate; distribuzione PyPI e licenze/esportatori non verificati. La struttura CLI non dimostra un'API riutilizzabile.
- **ofxparse:** MIT nel repository/PyPI, ma dipendenze BeautifulSoup, lxml e six vanno fissate e sottoposte a licenze/SBOM. `lxml` è estensione nativa; il supporto 3.12 non risulta dichiarato in modo attuale.
- **Actual, Beancount, MMEX, Firefly, GnuCash, hledger, ofxtools, ofxstatement:** utile studiarne i comportamenti e i test. Le licenze copyleft non autorizzano a copiare o adattare codice in ContaFlow sotto questo piano. Revisione legale umana prima di qualunque eccezione.
- **bankstatementparser:** progetto dichiara licenza doppia Apache-2.0/MIT ma dipendenze ampie, con lxml e pandas nel core e componenti opzionali PDF/AI; nessuna risoluzione completa o misura EXE effettuata. Il fatto che AI sia opzionale non cambia il divieto di servizi AI esterni per ContaFlow. Non adottare finché una soluzione leggera non risulta insufficiente.

Non sono stati consultati advisory di sicurezza per ogni release e dipendenza, né contato il numero effettivo di manutentori per tutti i progetti. Nessuna affermazione di “assenza di vulnerabilità note” viene fatta.

## 8. Compatibilità e prove

| Candidato | Documentato dai maintainer/metadati | Prova eseguita in questo audit | Da verificare |
|---|---|---|---|
| openpyxl 3.1.5 | Python ≥3.8, XLSX OOXML, MIT; et-xmlfile diretto | Nessuna installazione o test | Python 3.12 Windows, fixture reali/sintetiche, formule, attribuzione, PyInstaller onedir e dimensione |
| RapidFuzz 3.14.6 | Python ≥3.11, wheel Windows x64, MIT, hook PyInstaller nel repo | Nessuna installazione o test | Caricamento DLL, cp312 Windows x64, suggerimenti non mutanti, bundle/dimensione |
| pdfplumber | README dichiara test Py 3.10–3.14; MIT; PDF digitali | Nessuna installazione o test | Catena licenze, wheel/native DLL, memory, BPER e Windows/PyInstaller |
| statement-normalizer | CI Python 3.9–3.13 e zero dipendenze dichiarati | Nessun clone o test | release/packaging, audit sorgenti, test di parser, Windows e bundle |
| ledgerbridge | Python ≥3.10 e zero dipendenze dichiarati | Nessun clone o test | licenze effettive, API/importabilità, parser, Windows/PyInstaller |
| ofxparse | OFX supportato, MIT, release PyPI 0.21 | Nessun test | Python 3.12, dipendenze, OFX/QFX campione, packaging |
| Actual/Beancount | Funzioni descritte in doc/repository | Nessun codice eseguito | Non applicabile come dipendenza prevista; solo analisi aggiuntiva se richiesto |

SQLite e Tkinter restano quelli di ContaFlow; nessuna compatibilità “di progetto” di librerie parser li sostituisce. **Windows/PyInstaller onedir non è stato eseguito per nessun candidato.** La suite ContaFlow non è stata eseguita in questa ricerca documentale.

## 9. Progetti scartati o non prioritari

- **pycamt:** specializzazione CAMT, GPL-3.0 e orientamento a dialetto bancario specifico; non si è individuato un vantaggio legale/tecnico prima di avere un estratto BPER autorizzato.
- **openpyxl GitHub `ericgazoni/openpyxl`:** non considerare quel vecchio mirror come upstream corrente; usare PyPI e repository indicato dai metadati/documentazione (Heptapod).
- **Toolkit GUI alternativi:** nessuna necessità concreta rispetto a Treeview/ttk esistente; costo di riscrittura alto, nessun beneficio misurato.
- **ORM o database alternativo:** nessuna lacuna dimostrata che giustifichi migrare SQLite e mettere a rischio backup, migrazioni e dati storici.
- **OCR/LLM o parser AI in cloud:** esclusi dai vincoli permanenti dell'applicazione.

## 10. Informazioni non verificate e prossimi controlli

1. Nessun ambiente Windows 11 x64/Python 3.12/PyInstaller è stato usato in questo audit; le prove d'integrazione restano pendenti.
2. Nessuna variazione di dimensione dell'EXE è stata misurata.
3. Nessun BPER XLSX/PDF autorizzato è stato disponibile e testato qui; non si certifica alcun parser BPER.
4. Non è stata risolta la catena completa transitiva delle dipendenze. Prima di distribuire ogni pacchetto: scegliere versione, generare SBOM, controllare licenze/NOTICE e vulnerabilità, poi aggiornare gli avvisi terze parti.
5. `statement-normalizer` e `ledgerbridge` sono promettenti ma piccoli/giovani; la loro attività, API pubblica e stabilità non bastano ancora a una decisione ADOTTARE.
6. Issue aperte e advisory non sono stati censiti sistematicamente per tutti i candidati; non si dichiara assenza di bug o vulnerabilità.
7. Le stime di ore sono intervalli basati sulla quantità/funzione dei moduli ContaFlow e sulla portata tipica, non preventivi né benchmark.
8. L'audit non ha installato dipendenze, eseguito codice di terzi, letto database utente, fatto migrazioni o rieseguito i test ContaFlow.

## 11. Proposta di regola per il metodo futuro

**Testo da sottoporre all'approvazione dell'utente (non adottato automaticamente):**

> Prima di sviluppare una funzione complessa, verificare se esistono librerie o componenti open source maturi, legalmente riutilizzabili e compatibili con ContaFlow. Integrare una soluzione esterna solo quando riduce concretamente sviluppo e manutenzione; altrimenti realizzare codice specifico per ContaFlow, preservando i dati e il comportamento già collaudato.

L'approvazione richiesta riguarda l'inserimento permanente di questa regola nelle istruzioni del progetto. Ogni dipendenza o codice incorporato richiede comunque una decisione separata e specifica.

## Fonti primarie consultate

Consultate il 2026-11-06; versione indicata soltanto quando verificata nei metadati alla data.

| Fonte | Pagine di licenza/documentazione/metadati |
|---|---|
| [openpyxl](https://pypi.org/project/openpyxl/) | [docs](https://openpyxl.readthedocs.io/) · [upstream](https://foss.heptapod.net/openpyxl/openpyxl) · [et-xmlfile PyPI](https://pypi.org/project/et-xmlfile/) |
| [RapidFuzz](https://github.com/rapidfuzz/RapidFuzz) | [docs](https://rapidfuzz.github.io/RapidFuzz/) · [PyPI](https://pypi.org/project/RapidFuzz/) · [license](https://github.com/rapidfuzz/RapidFuzz/blob/main/LICENSE) |
| [pdfplumber](https://github.com/jsvine/pdfplumber) | [README](https://github.com/jsvine/pdfplumber/blob/stable/README.md) · [license](https://github.com/jsvine/pdfplumber/blob/stable/LICENSE.txt) · [requirements](https://github.com/jsvine/pdfplumber/blob/stable/requirements.txt) |
| [statement-normalizer](https://github.com/Maxed-OSS/statement-normalizer) | [README](https://github.com/Maxed-OSS/statement-normalizer/blob/main/README.md) · [license](https://github.com/Maxed-OSS/statement-normalizer/blob/main/LICENSE) · [pyproject](https://github.com/Maxed-OSS/statement-normalizer/blob/main/pyproject.toml) |
| [ledgerbridge](https://github.com/MugenLab/ledgerbridge) | [README](https://github.com/MugenLab/ledgerbridge/blob/main/README.md) · [license](https://github.com/MugenLab/ledgerbridge/blob/main/LICENSE) · [tests](https://github.com/MugenLab/ledgerbridge/tree/main/tests) |
| [ofxparse](https://github.com/jseutter/ofxparse) | [PyPI](https://pypi.org/project/ofxparse/) · [setup.py](https://github.com/jseutter/ofxparse/blob/master/setup.py) · [license](https://github.com/jseutter/ofxparse/blob/master/LICENSE) |
| [Actual Budget](https://github.com/actualbudget/actual) | [license](https://github.com/actualbudget/actual/blob/master/LICENSE.txt) · [import docs](https://actualbudget.org/docs/transactions/importing/) |
| [Beancount](https://github.com/beancount/beancount) | [license](https://github.com/beancount/beancount/blob/master/LICENSE) · [docs](https://beancount.github.io/docs/) · [pyproject](https://github.com/beancount/beancount/blob/master/pyproject.toml) |
| [MMEX](https://github.com/moneymanagerex/moneymanagerex) | [repository](https://github.com/moneymanagerex/moneymanagerex) · [database schema](https://github.com/moneymanagerex/database) |
| [Firefly III](https://github.com/firefly-iii/firefly-iii) | [license](https://github.com/firefly-iii/firefly-iii/blob/main/LICENSE) · [docs](https://docs.firefly-iii.org/) |
| [GnuCash](https://github.com/Gnucash/gnucash) | [repository/license](https://github.com/Gnucash/gnucash) · [docs](https://www.gnucash.org/docs.phtml) |
| [hledger](https://github.com/simonmichael/hledger) | [repository/license](https://github.com/simonmichael/hledger) · [docs](https://hledger.org/) |
| [ofxtools](https://github.com/csingley/ofxtools) | [PyPI](https://pypi.org/project/ofxtools/) · [license](https://github.com/csingley/ofxtools/blob/master/LICENSE) |
| [ofxstatement](https://github.com/kedder/ofxstatement) | [repository/license](https://github.com/kedder/ofxstatement) · [PyPI](https://pypi.org/project/ofxstatement/) |
| [bankstatementparser](https://github.com/sebastienrousseau/bankstatementparser) | [repository](https://github.com/sebastienrousseau/bankstatementparser) · [PyPI](https://pypi.org/project/bankstatementparser/) |
| [pycamt](https://github.com/mbakouny/pycamt) | [repository/license](https://github.com/mbakouny/pycamt) |
