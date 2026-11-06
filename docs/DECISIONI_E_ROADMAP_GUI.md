# ContaFlow — continuità, decisioni tecniche e roadmap UI

**Aggiornamento:** 2026-11-06. **Fonte primaria per le prossime sessioni:** questo documento insieme a [RIUSO_OPEN_SOURCE.md](RIUSO_OPEN_SOURCE.md) e `STATO_SVILUPPO.md`.

## Decisioni confermate dall'utente
- **Obiettivo:** app desktop locale Windows per finanze personali, interfaccia italiana, semplice/intuitiva/moderna; preservare dati, backup e movimenti.
- **Repository:** `dragsber/ContaFlow`; sviluppo su `codex/contaflow-sviluppo`; fetch HEAD remoto a ogni sessione.
- **Riuso open source prima dello sviluppo da zero:** verificare licenze e compatibilità; incorporare solo quando c'è vantaggio concreto, senza riavviare il progetto o riscrivere servizi già collaudati.
- **Primo riuso approvato:** `openpyxl` per la lettura XLSX. Controllare **sia** `adapters/chart.py` **sia** `services/catalog_import.py`: entrambi leggono ZIP/XML direttamente. Preservare interfacce, mapping, anteprima, conferme, audit, codici con zeri iniziali, formule bloccate, CSV e deduplicazione. Nessuna importazione automatica di dati personali.
- **RapidFuzz:** candidato successivo, NON ancora approvato per integrazione; solo suggerimenti senza riclassificazione o fusione automatica.
- **statement-normalizer, pdfplumber e altri parser:** verifiche ulteriori, non dichiararli compatibili con BPER senza campioni autorizzati.
- **GUI:** l'utente giudica la GUI attuale vecchia e poco gradevole. Vuole un'esperienza semplice, intuitiva e moderna. Valutare opzioni in parallelo alla fase Excel; nessuna migrazione globale del toolkit senza nuovo collaudo e approvazione.
- **Sicurezza:** non committare dati bancari, workbook personali, database, log, token o backup. Nessuna migrazione database necessaria per integrare un lettore XLSX o tema grafico.
- **Incidente storico:** EXE aveva aperto archivio con quattro conti e zero movimenti; l'utente ha recuperato i dati dal backup. La causa originaria non è definitivamente chiarita; preservare diagnostica, recupero backup e non-regressione.
- **Comunicazione stato:** dichiarare separatamente codice implementato, test automatici, build Windows, collaudo manuale, limitazioni.

## Audit UX del codice attuale (2026-11-06)

Osservazioni verificabili nel codice, non test con utenti:
1. `contaflow/app.py`: `ttk.Notebook` contiene otto sezioni principali (Dashboard, Movimenti, Importazione, Fornitori, Categorie, Budget, Piano dei conti, Sottovoci). La navigazione è piatta e frammenta funzioni collegate.
2. `contaflow/register.py`: `ttk.Treeview` con 12 colonne e scrollbar orizzontale; filtri distribuiti su più righe; numerosi bottoni sempre visibili. Densità elevata e scansione lenta.
3. `contaflow/accounts.py`: gestione conti in `Toplevel` con tabella a molte colonne e otto azioni orizzontali; su finestre strette l'accessibilità è limitata.
4. Dashboard con riepilogo e diagnostica, ma gerarchia visiva frammentata; saldo dichiarato/calcolato/riconciliato deve essere esplicitamente distinto.
5. Controlli basati su `ttk` e `tk.Text`/`tk.Listbox`; i componenti base potrebbero reagire diversamente a un tema esterno. Sono presenti test GUI che verificano classi e gerarchia dei widget: cambiare framework può causare regressioni.
6. La finestra ha geometria iniziale 1120×760 e minima 900×620; servono prove con ridimensionamento, DPI elevato e scaling Windows.

## Proposta di IA (information architecture): prototipo prima della migrazione

- **Navigazione primaria (5 aree):** Panoramica; Movimenti; Importazioni; Budget e report; Organizza (Fornitori, Categorie, Sottovoci, Piano dei conti). Conti e cassa raggiungibili immediatamente dalla Panoramica e da un selettore persistente; riconciliazione in Conti.
- **Panoramica:** selettore periodo/conti; saldo per valuta senza sommare EUR+CHF; badge testuali per "non verificato", "da riconciliare"; riquadri riepilogativi; due azioni primarie (Importa estratto, Esamina movimenti).
- **Movimenti:** colonne iniziali Data, Descrizione, Importo/valuta, Conto, Categoria/sottovoce, Stato; fornitore, commissione, conto contabile e dettagli nel pannello laterale o nella vista configurabile. Filtri collassabili, ricerca sempre disponibile, azzera filtri e contatore "N di M" sempre visibili. Le modifiche multiple restano accessibili come azione contestuale dopo una selezione.
- **Importazione:** percorso guidato in 3 passaggi (scegli file e conto → anteprima e anomalie → conferma) senza importare in automatico.
- **Organizza:** gestione gerarchie e alias in un'unica area, senza eliminare o nascondere funzionalità.
- **Stile:** tipografia Segoe UI coerente, spaziature 8/12/16/24 px, massimo due livelli di enfasi, superfici neutre, indicatori di stato con testo oltre al colore, contrasto adeguato, pulsanti distinguibili per priorità, etichette in italiano. Nessuna decorazione che confonda entrate, uscite e saldi.
- **Accessibilità:** navigazione tastiera, focus visibile, ridimensionamento finestre, DPI/scaling 125% e 150%, temi chiaro/scuro; verificare Treeview, dialog, modal e notifiche in Windows.

## Opzioni tecniche: confronto preliminare

| Opzione | Vantaggio | Costo/rischio | Decisione |
|---|---|---|---|
| **ttkbootstrap** (https://github.com/israel-dryer/ttkbootstrap; https://pypi.org/project/ttkbootstrap/) | Theming di widget `ttk`, temi chiari/scuri, componenti aggiuntivi, compatibilità dichiarata con Python 3.12; documentati hook PyInstaller nelle release 2.x | Dipendenza Pillow; licenza SPDX su PyPI `MIT AND (Apache-2.0 OR BSD-2-Clause)` da verificare nell'esatta release; test di bundle, stili `tk.Text` e widget reali necessari | **Prima scelta per prototipo isolato**, non integrazione automatica |
| **sv-ttk** (https://github.com/rdbende/Sun-Valley-ttk-theme; https://pypi.org/project/sv-ttk/) | Tema Sun Valley simile a Windows 11, MIT, modifica limitata, conserva `ttk` | Meno componenti di interfaccia e meno controllo semantico; tema non risolve affollamento e navigazione | Alternativa leggera |
| **ttk nativo con style personalizzato** | Nessuna dipendenza nuova, minimo rischio distribuzione | Più lavoro nel mantenere palette e comportamenti; look moderno limitato | Piano di fallback |
| **CustomTkinter** (https://github.com/TomSchimansky/CustomTkinter) | Controlli e superfici moderni, MIT | Diversi widget e comportamento, `ttk.Treeview` da integrare o sostituire, regressioni sui test Tk e maggior refactoring | **Non adottare ora** per la GUI esistente |

Verifiche documentali: PyPI/README consultati il 2026-11-06. Non sono stati installati né provati i framework nel bundle ContaFlow. Compatibilità di produzione e licenze transitive non completamente verificate.

## Sequenza proposta

**UI-0 (solo analisi, questo documento):** inventario dei problemi, alternative e UX target.

**UI-1 (prototipo isolato, dopo autorizzazione):** schermata Panoramica e Registro su soli dati sintetici con due temi alternativi (ttkbootstrap e sv-ttk o ttk nativo); nessuna migrazione del DB, confronto a fianco della GUI attuale; verificare Tk 3.12 e bundle onedir.

**UI-2 (incremento graduale):** design system, layout e gerarchia visiva; prima Panoramica e Movimenti, poi Importazioni, poi Organizza/Budget. Non cambiare il backend. Conservare controlli, scorciatoie e semantica esistenti.

**UI-3 (collaudo utente):** prove guidate: (1) trovare il saldo EUR e distinguerlo da CHF; (2) importare un CSV sintetico; (3) identificare un movimento da classificare; (4) correggere la sottovoce; (5) riconciliare un conto. Verificare leggibilità a 900×620, 1120×760, finestra massimizzata, scaling 125–150%. Registrare problemi e correzioni.

## Ripresa delle prossime sessioni
1. `git fetch`, verifica HEAD del branch e `STATO_SVILUPPO.md`, poi leggi questo documento e `docs/RIUSO_OPEN_SOURCE.md`.
2. Verifica se l'integrazione `openpyxl` è stata eseguita **su entrambi** i percorsi XLSX e se i test/EXE Windows sono stati davvero eseguiti. Non dichiararla completata per la sola documentazione.
3. Se il primo intervento è chiuso, proponi collaudo Windows e selezione del prototipo grafico; per la GUI evita riscritture globali.
4. Successivamente valuta RapidFuzz (richiede approvazione), parser OFX/CAMT e BPER (campione reale autorizzato), PDF digitale.
5. Per ogni decisione successiva aggiorna qui la sezione corrispondente, `STATO_SVILUPPO.md` e le istruzioni `AGENTS.md`.

**Regola permanente di sviluppo approvata nel principio:** prima di scrivere un componente complesso verificare riuso open source, licenze, costo di integrazione e test. Non copiare codice copyleft nel progetto senza valutazione legale.
