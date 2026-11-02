# Stato sviluppo ContaFlow · Alpha 0.1

- Ultimo commit verificato alla ripresa: 8d4f18be7e2d43ff37820c5f5a1151ec7817d3b5.
- Fase attiva: Alpha Windows 0.1.
- Architettura realizzata: Python, Tkinter/ttk, SQLite; `FinanceService`; database sotto la cartella utente; migrazioni versionate schema 3.
- Funzionalità già presenti: import CSV Revolut con controllo conto/provider e valuta, duplicati, commissioni, riconciliazione; fornitori, alias e classificatore con riuso delle associazioni confermate.
- Incremento 1 in corso: schermate principali collegate a `FinanceService` per dashboard, movimenti, importazione, fornitori e categorie; classificazione correggibile e associazioni riusabili.
- Incremento 2 in corso: predisposizione portable PyInstaller onedir, log locale e backup/ripristino del database.
- Collaudi già disponibili: test sintetici selettivi del classificatore e migrazione legacy v2 su database sintetico, eseguiti prima di questa revisione.
- Incremento 1: implementato, NON COLLAUDATO con esecuzione Python in questa sessione.
- Blocco esecutore registrato una volta: `python.exe` risolve all'alias WindowsApps, che non si avvia (`Impossibile accedere al file`). Nessun tentativo ripetuto; si prosegue via GitHub come richiesto.
- Collaudi Alpha a-f: da eseguire sui sorgenti aggiornati; GUI grafica Windows da eseguire se non disponibile.
- Distribuzione: EXE non prodotto finché non viene compilato e avviato in ambiente Windows autorizzato.
- Stato Alpha: NON UTILIZZABILE con dati bancari reali finché i controlli essenziali a-f non siano superati e la GUI Windows non sia collaudata.

| Fase | Avanzamento stimato |
|---|---:|
| 01 Conti e movimenti | 80% |
| 02 Importazioni | 65% |
| 03 Dashboard e report | 30% |
| 04 Trasferimenti e rimborsi | 10% |
| 05 Esportazioni | 0% |
| 06 Fornitori e categorie | 45% |
| 07 Ricorrenze | 0% |
| 08 Budget | 10% |
| 09 Architettura/integrazione | 15% |
| 10 Predisposizione AI locale | 0% |
| 11 Sicurezza e backup | 10% |
| 12 Distribuzione stabile | 0% |
