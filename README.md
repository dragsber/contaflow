# ContaFlow

Local-first Windows personal finance prototype using Python, Tkinter and SQLite.

## Run

Install Python 3.10+ with Tk support, then run `python -m contaflow`. Data is stored under `%LOCALAPPDATA%\ContaFlow\contaflow.sqlite3`.

CSV import supports the Revolut export columns `Tipo, Prodotto, Data di inizio, Data di completamento, Descrizione, Importo, Costo, Valuta, State, Saldo`. Only completed rows are imported. Fees are represented separately; canceled rows are skipped. No bank files are included.

Google Sheets, local AI and Enable Banking are future adapters; no credentials or external connections are needed for the core app.
