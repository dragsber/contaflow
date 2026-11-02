# Stato sviluppo ContaFlow · Alpha 0.1

- Ultimo commit funzionale pubblicato: 530cbc1d2b783821d21b6b73202cc932bc241fd8.
- Incremento UI fornitori/classificazione: db4e96ee29405211f8498f48c627f5818a890c40.
- Branch remoto: codex/contaflow-sviluppo; ultimo ref verificato durante la sessione: 530cbc1d2b783821d21b6b73202cc932bc241fd8.
- Fase attiva: Alpha Windows 0.1.
- Architettura: Python, Tkinter/ttk, SQLite; GUI usa FinanceService; database sotto la cartella utente/configurabile; migrazioni versionate schema 3.
- Implementato: schermate Dashboard, Movimenti, Importazione, Fornitori e Categorie; filtro conto; gestione fornitori/alias/categorie; revisione e riuso delle associazioni confermate.
- Implementato: import Revolut con verifica conto/provider/valuta, duplicati, commissioni, stato transazionale e riconciliazione.
- Implementato: backup/ripristino via SQLite, conferma prima del ripristino, copia di sicurezza automatica, log locale e script PyInstaller onedir.
- Non implementato nell'Alpha: gestione GUI dei saldi iniziali; collegamenti bancari reali, servizi esterni, trasferimenti/rimborsi e budget.
- Esecutore Python: blocco registrato una volta; python.exe risolve all'alias WindowsApps che non si avvia (Impossibile accedere al file). Nessun tentativo ripetuto; si è continuato tramite GitHub.
- Collaudi del codice aggiornato: non eseguiti. I test sintetici precedenti sul classificatore e sulla migrazione v2 precedono queste modifiche e non coprono questo commit.
- Build: EXE NON PRODOTTO. La build onedir è predisposta, ma non è stata compilata né avviata.
- GUI grafica Windows: DA ESEGUIRE.
- Stato Alpha: NON UTILIZZABILE con dati bancari reali finché i controlli a-f e il collaudo Windows non siano completati.

| Controllo Alpha | Esito in questa sessione |
|---|---|
| a. Avvio applicazione/headless | NON ESEGUITO |
| b. Migrazione database sintetico preesistente | NON ESEGUITO su questa versione |
| c. Import sintetico Revolut e rifiuto conto incompatibile | NON ESEGUITO |
| d. Conferma classificazione e riuso in import successivo | NON ESEGUITO |
| e. Persistenza dopo chiusura/riapertura | NON ESEGUITO |
| f. Backup e ripristino sintetici | NON ESEGUITO |

| Fase | Avanzamento stimato |
|---|---:|
| 01 Conti e movimenti | 80% |
| 02 Importazioni | 65% |
| 03 Dashboard e report | 40% |
| 04 Trasferimenti e rimborsi | 10% |
| 05 Esportazioni | 0% |
| 06 Fornitori e categorie | 60% |
| 07 Ricorrenze | 0% |
| 08 Budget | 10% |
| 09 Architettura/integrazione | 15% |
| 10 Predisposizione AI locale | 0% |
| 11 Backup e sicurezza locale | 30% |
| 12 Distribuzione stabile | 15% |
