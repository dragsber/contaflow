import os
import re
import sqlite3
import sys
from contextlib import closing
from datetime import datetime
from pathlib import Path

from contaflow.store import data_directory, data_path, default_data_path
from db.migrations import LATEST_SCHEMA_VERSION, schema_version
from services.register import STATUSES


BUILD = f"Alpha 0.2 — diagnostica schema {LATEST_SCHEMA_VERSION} / build 1"


def backup_summary(filename):
    path = Path(filename).resolve()
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("BEGIN")
        tables = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"accounts", "categories", "transactions"} <= tables:
            raise ValueError("Il file selezionato non è un database ContaFlow.")
        version = schema_version(db)
        if type(version) is not int or not 0 <= version <= LATEST_SCHEMA_VERSION:
            raise ValueError("Versione del backup non supportata.")
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Il backup non supera il controllo di integrità.")
        movements = db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0]
        accounts = db.execute("SELECT COUNT(*) FROM accounts").fetchone()[0]
    return f"File: {path}\nMovimenti: {movements}\nConti bancari: {accounts}\nSchema: {version}"


def report(store, active_filters=()):
    db = store.db
    path = Path(db.execute("PRAGMA database_list").fetchone()[2])
    lines = [f"ContaFlow {BUILD}", f"Rapporto: {datetime.now().astimezone().isoformat()}",
             f"Database aperto: {path}"]
    try:
        info = path.stat()
        lines.extend((f"Dimensione: {info.st_size} byte",
                      f"Modifica: {datetime.fromtimestamp(info.st_mtime).astimezone().isoformat()}"))
    except OSError:
        lines.append("Metadati database non disponibili")
    for suffix in ("-wal", "-shm"):
        try:
            lines.append(f"{suffix}: presente ({Path(str(path) + suffix).stat().st_size} byte)")
        except FileNotFoundError:
            lines.append(f"{suffix}: assente")
        except OSError:
            lines.append(f"{suffix}: non verificabile")
    local = os.environ.get("LOCALAPPDATA")
    lines.append(f"LOCALAPPDATA: {Path(local).resolve() if local else 'non impostata'}")
    candidates = (default_data_path(), data_path(), Path.cwd() / path.name,
                  Path(sys.executable).parent / path.name)
    for candidate in dict.fromkeys(p.resolve() for p in candidates):
        lines.append(f"Candidato: {candidate} — {'presente' if candidate.is_file() else 'assente'}")

    versions = [row[0] for row in db.execute("SELECT version FROM schema_version")]
    numeric = [str(v) if type(v) is int else "non valida" for v in versions]
    lines.append("schema_version: " + ", ".join(numeric))
    if len(versions) == 1 and type(versions[0]) is int and 1 <= versions[0] <= LATEST_SCHEMA_VERSION:
        lines.append("Migrazioni applicate (da versione): " + ", ".join(map(str, range(1, versions[0] + 1))))
    checks = db.execute("PRAGMA integrity_check").fetchall()
    lines.append("PRAGMA integrity_check: " + ("ok" if len(checks) == 1 and checks[0][0] == "ok"
                                             else f"{len(checks)} segnalazioni"))
    violations = sum(1 for _ in db.execute("PRAGMA foreign_key_check"))
    lines.append(f"PRAGMA foreign_key_check: {violations} violazioni")
    for table in ("accounts", "transactions", "suppliers", "categories", "supplier_aliases",
                  "classification_rules", "audit", "importations", "ledger_accounts", "subcategories"):
        count = db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        lines.append(f"{table}: {count}")
    grouped = dict(db.execute("SELECT classification_status, COUNT(*) FROM transactions GROUP BY classification_status"))
    for status in STATUSES:
        lines.append(f"Stato {status}: {grouped.pop(status, 0)}")
    lines.append(f"Stato altro/non impostato: {sum(grouped.values())}")
    lines.extend(("Filtri persistiti: nessuno, l'app non li salva.",
                  "Filtri predefiniti: tutti i conti, nessun filtro sul registro.",
                  "Filtri attivi (solo tipi): " + (", ".join(active_filters) or "nessuno")))
    log = data_directory() / "contaflow-avvio.log"
    try:
        entries = log.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeError):
        entries = []
    allowed = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3} "
                         r"(Avvio applicazione|Lettura/interfaccia): "
                         r"(migrazione/apertura|lettura SQLite|errore applicativo)")
    lines.append("Eventi recenti (log diagnostico):")
    lines.extend([entry for entry in entries if allowed.fullmatch(entry)][-10:] or ["Nessun evento disponibile"])
    return "\n".join(lines) + "\n"


def show_report(app):
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    content = report(app.store.store, app.register.active_filters())
    window = tk.Toplevel(app)
    window.title("Diagnostica — anteprima del rapporto")
    ttk.Label(window, text="Il rapporto include percorsi locali e conteggi tecnici.").pack(padx=10, pady=8)
    preview = tk.Text(window, width=100, height=24, wrap="word")
    preview.pack(fill="both", expand=True, padx=10)
    preview.insert("1.0", content)
    preview.configure(state="disabled")

    def save():
        target = filedialog.asksaveasfilename(
            parent=window, title="Esporta rapporto diagnostico", defaultextension=".txt",
            initialfile="ContaFlow-diagnostica.txt", filetypes=[("Testo", "*.txt")],
        )
        if target:
            if Path(target).suffix.lower() != ".txt":
                messagebox.showerror("Esportazione", "Scegli un file con estensione .txt.", parent=window)
                return
            try:
                with Path(target).open("x", encoding="utf-8") as handle:
                    handle.write(content)
            except FileExistsError:
                messagebox.showerror("Esportazione", "Il file esiste già. Scegli un nome nuovo.", parent=window)
            except OSError:
                messagebox.showerror("Esportazione", "Impossibile salvare il rapporto in questa cartella.", parent=window)

    ttk.Button(window, text="Esporta rapporto…", command=save).pack(pady=8)
