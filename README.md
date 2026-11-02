# ContaFlow

Applicazione locale per la gestione della finanza personale con Python,
Tkinter/ttk e SQLite.

## Avvio da sorgente

1. Installa Python 3.12 con supporto Tcl/Tk.
2. Scarica o clona il branch codex/contaflow-sviluppo.
3. Apri un terminale nella cartella del repository.
4. Esegui: python -m contaflow

Il database e il log restano in %LOCALAPPDATA%\ContaFlow. Per scegliere un'altra
cartella, imposta CONTAFLOW_DATA_DIR prima dell'avvio.

## Funzioni Alpha presenti nel codice

- Conti Revolut EUR/CHF, BPER EUR e Cassa.
- Registro movimenti filtrato per conto e saldo aggregato.
- Import CSV Revolut con controllo provider/valuta, deduplicazione e riconciliazione.
- Anagrafica fornitori, alias e categorie.
- Revisione manuale delle classificazioni e riuso degli abbinamenti confermati.
- Backup e ripristino dal menu Database.

La versione Alpha non è collaudata e non va usata con dati bancari reali
finché i controlli essenziali non siano stati eseguiti.

## Build Windows portable

La build onedir viene prodotta con build_windows.bat in un ambiente Windows
autorizzato. Il pacchetto non include database o credenziali. Consulta
BUILD_WINDOWS.md per la procedura e i dettagli di backup/ripristino.
