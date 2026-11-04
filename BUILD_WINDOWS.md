# Build Windows portable ContaFlow

## Requisiti di compilazione

- Windows x64 autorizzato.
- Python 3.12 con Tcl/Tk.
- Connessione disponibile per scaricare la dipendenza PyInstaller indicata in requirements-build.txt.

La procedura crea un ambiente Python locale .venv-build; non installa pacchetti Python a livello globale.

## Compilazione

1. Estrai o clona il repository in una cartella di lavoro.
2. Verifica che py -3.12 --version mostri Python 3.12.
3. Avvia build_windows.bat.
4. Attendi la creazione di dist\ContaFlow\ContaFlow.exe e della cartella _internal.
5. Avvia ContaFlow.exe con doppio clic e verifica l'apertura prima di distribuirlo.

La build è onedir: consegna l'intera cartella dist\ContaFlow, non il solo file EXE. Lo script rifiuta ambienti non Windows e non prova cross-compilazioni.

## Aggiornamento Alpha 0.1 → Alpha 0.2

Prima del primo avvio della nuova versione, chiudi ContaFlow e conserva una copia separata
del database Alpha 0.1 da %LOCALAPPDATA%\ContaFlow. La versione 0.2 crea inoltre
una copia automatica verificata prima di modificare lo schema di un database esistente.
Un errore di verifica o migrazione interrompe l'avvio e indica la copia da conservare.

La Alpha 0.2 corrente è una build intermedia. I sorgenti sono collaudati automaticamente
su Windows. La compilazione e il collaudo manuale dell'EXE restano da eseguire.
Per il primo collaudo usa un database sintetico e una cartella dati separata.

## Dati, log e backup

Il pacchetto non contiene database né credenziali. Al primo avvio, database e log vengono creati in %LOCALAPPDATA%\ContaFlow. Per scegliere un'altra posizione, imposta CONTAFLOW_DATA_DIR prima dell'avvio.

Dal menu Database puoi creare un backup datato o ripristinare un backup SQLite. Prima del ripristino ContaFlow verifica il file e salva una copia di sicurezza del database attuale nella sottocartella backups. Verifica il funzionamento su dati sintetici prima di usare il programma con estratti personali.
