import tkinter as tk
from decimal import Decimal
from tkinter import messagebox, ttk

from services.accounts import (
    archive_account, balance_movements, list_accounts, opening_balance, save_account, save_opening,
)
from services.register import money
from services.reconciliation import latest_reconciliation, preview_reconciliation, save_reconciliation
from services.cash import record_cash_movement


TYPES = {
    "Conto bancario Revolut": "REVOLUT",
    "Conto bancario BPER": "BPER",
    "Altro conto bancario": "UNKNOWN",
    "Cassa contanti": "CASH",
}


def show_accounts(app):
    db = app.store.store.db
    window = tk.Toplevel(app)
    window.title("Conti bancari e cassa contanti")
    columns = ("nome", "tipo", "valuta", "istituto", "variazione", "saldo", "ultimo", "stato", "riconciliazione")
    table = ttk.Treeview(window, columns=columns, show="headings", selectmode="browse", height=8)
    for column, title, width in zip(columns,
        ("Nome", "Tipo", "Valuta", "Istituto", "Variazione netta", "Saldo calcolato",
         "Ultimo movimento", "Stato", "Ultima riconciliazione"),
        (150, 145, 65, 100, 120, 120, 130, 90, 220)):
        table.heading(column, text=title)
        table.column(column, width=width, stretch=False)
    scrollbar = ttk.Scrollbar(window, orient="horizontal", command=table.xview)
    table.configure(xscrollcommand=scrollbar.set)
    table.pack(fill="both", expand=True, padx=8, pady=(8, 0))
    scrollbar.pack(fill="x", padx=8)
    rows = {}

    def refresh():
        rows.clear()
        rows.update({str(row["id"]): row for row in list_accounts(db)})
        summaries = {str(row["id"]): row for row in app.store.summary()}
        table.delete(*table.get_children())
        for identifier, row in rows.items():
            summary, currency = summaries[identifier], row["currency"]
            balance = summary["bank_balance"]
            check = latest_reconciliation(db, row["id"])
            reconciliation = "Non verificato"
            if check:
                reconciliation = (f"Saldo riconciliato al {check['as_of']}: "
                                  f"{money(Decimal(check['actual_minor']).scaleb(-2), currency)}"
                                  if check["status"] == "confermata" else f"{check['as_of']} · Da verificare")
            table.insert("", "end", iid=identifier, values=(
                row["name"], next((name for name, code in TYPES.items() if code == row["provider"]), row["provider"]),
                currency, row["institution"], money(summary["balance"], currency),
                money(balance, currency) if balance is not None else "Non impostato",
                row["last_movement"] or "—", "Archiviato" if row["archived"] else "Attivo", reconciliation,
            ))

    def selection():
        selected = table.selection()
        if selected:
            return rows[selected[0]]
        messagebox.showinfo("Selezione", "Seleziona un conto.", parent=window)
        return None

    def save(operation, dialog=None):
        try:
            operation()
        except ValueError as error:
            messagebox.showerror("Dati non salvati", str(error), parent=dialog or window)
            return
        if dialog:
            dialog.destroy()
        refresh()
        app.refresh_all()

    def edit(create=False):
        row = None if create else selection()
        if not create and row is None:
            return
        dialog = tk.Toplevel(window)
        dialog.title("Nuovo conto" if create else "Modifica conto")
        fields = (
            ("Nome", row["name"] if row else "", ()),
            ("Tipologia", next((k for k, v in TYPES.items() if row and v == row["provider"]),
                              "Altro conto bancario"), tuple(TYPES)),
            ("Valuta", row["currency"] if row else "EUR", ("EUR", "CHF")),
            ("Istituto", row["institution"] if row else "", ()),
            ("Note", row["notes"] if row else "", ()),
        )
        values = form(dialog, fields)

        def persist():
            name, kind, currency, institution, notes = (value.get() for value in values)
            save(lambda: save_account(db, name, TYPES[kind], currency, institution, notes,
                                      row["id"] if row else None), dialog)

        ttk.Button(dialog, text="Salva", command=persist).grid(row=len(fields), column=1, pady=8)

    def opening():
        row = selection()
        if row is None:
            return
        existing = opening_balance(db, row["id"])
        dialog = tk.Toplevel(window)
        dialog.title("Saldo iniziale")
        fields = (("Fine giornata (AAAA-MM-GG)", existing["as_of"] if existing else "", ()),
                  (f"Importo in {row['currency']}", str(existing["amount"]) if existing else "", ()))
        day, amount = form(dialog, fields)
        ttk.Label(dialog, text="Concorrono solo i movimenti completati con data successiva.").grid(
            row=2, column=0, columnspan=2, padx=8)
        ttk.Button(dialog, text="Salva", command=lambda: save(
            lambda: save_opening(db, row["id"], day.get(), amount.get()), dialog,
        )).grid(row=3, column=1, pady=8)

    def movements(calculation=False):
        row = selection()
        if row is None:
            return
        if not calculation:
            app.register.reset()
            app.account_var.set(row["name"])
            app.refresh_all()
            app.tabs.select(app.movements_tab)
            window.destroy()
            return
        initial = opening_balance(db, row["id"])
        items = balance_movements(db, row["id"], after=initial["as_of"] if initial else None)
        dialog = tk.Toplevel(window)
        dialog.title("Movimenti che concorrono al calcolo")
        text = tk.Text(dialog, width=95, height=18, wrap="word")
        text.pack(fill="both", expand=True, padx=8, pady=8)
        text.insert("1.0", "\n".join(
            f"{item['occurred_at']} · {item['description']} · {money(item['amount'], row['currency'])}"
            f" · Commissione {money(item['fee'], row['currency'])}" for item in items
        ) or "Nessun movimento completato nel periodo.")
        text.configure(state="disabled")

    def archive():
        row = selection()
        if row and messagebox.askyesno("Conferma", "Cambiare lo stato di archiviazione?", parent=window):
            save(lambda: archive_account(db, row["id"], not row["archived"]))

    def reconcile():
        row = selection()
        if row is not None:
            show_reconciliation(window, db, row, save)

    def cash():
        row = selection()
        if row is None:
            return
        if row["provider"] != "CASH" or row["archived"]:
            messagebox.showinfo("Cassa contanti", "Seleziona una cassa contanti attiva.", parent=window)
            return
        show_cash_entry(window, db, row, save)

    actions = ttk.Frame(window)
    actions.pack(fill="x", padx=8, pady=8)
    for label, command in (
        ("Nuovo", lambda: edit(True)), ("Modifica", edit), ("Archivia / riattiva", archive),
        ("Saldo iniziale", opening), ("Movimenti del conto", movements),
        ("Movimenti nel calcolo", lambda: movements(True)),
        ("Riconciliazione…", reconcile), ("Movimento di cassa…", cash),
    ):
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=3)
    refresh()


def show_reconciliation(parent, db, account, save):
    dialog = tk.Toplevel(parent)
    dialog.title(f"Riconciliazione · {account['name']}")
    currency = account["currency"]
    latest = latest_reconciliation(db, account["id"])
    fields = (("Data di fine giornata (AAAA-MM-GG)", latest["as_of"] if latest else "", ()),
              (f"Saldo effettivo dichiarato in {currency}",
               str(Decimal(latest["actual_minor"]).scaleb(-2)) if latest else "", ()))
    day, amount = form(dialog, fields)
    content = tk.Text(dialog, width=90, height=17, wrap="word", state="disabled")
    content.grid(row=3, column=0, columnspan=2, padx=8, pady=5, sticky="nsew")
    snapshot = None

    def compare():
        nonlocal snapshot
        snapshot = None
        persist.configure(state="disabled")
        try:
            snapshot = preview_reconciliation(db, account["id"], day.get(), amount.get())
        except ValueError as error:
            messagebox.showerror("Confronto non disponibile", str(error), parent=dialog)
            return
        lines = [
            f"Saldo calcolato al {snapshot.day}: {money(snapshot.calculated, currency)}",
            f"Saldo effettivo dichiarato: {money(snapshot.actual, currency)}",
            f"Differenza (effettivo − calcolato): {money(snapshot.difference, currency)}",
            "Esito: " + ("confermata" if snapshot.difference == 0 else "da verificare"),
            f"Movimenti completati dopo il {snapshot.opening_day}: {len(snapshot.movements)}",
        ]
        for date, count in snapshot.duplicates:
            lines.append(f"Possibile duplicato il {date}: {count} movimenti con stessa descrizione e importo.")
        if snapshot.difference and not snapshot.duplicates:
            lines.append("Nessuna anomalia di duplicazione rilevata. La differenza richiede verifica sull'estratto.")
        lines.extend(f"{row['occurred_at']} · {row['description']} · {money(row['amount'], currency)}"
                     f" · Commissione {money(row['fee'], currency)}" for row in snapshot.movements)
        content.configure(state="normal")
        content.delete("1.0", "end")
        content.insert("1.0", "\n".join(lines))
        content.configure(state="disabled")
        persist.configure(state="normal")

    def persist_result():
        if snapshot is not None:
            save(lambda: save_reconciliation(db, snapshot), dialog)

    def invalidate(*_):
        persist.configure(state="disabled")

    ttk.Button(dialog, text="Confronta", command=compare).grid(row=2, column=0, pady=8)
    persist = ttk.Button(dialog, text="Salva esito", command=persist_result, state="disabled")
    persist.grid(row=2, column=1, pady=8)
    day.trace_add("write", invalidate)
    amount.trace_add("write", invalidate)
    dialog.rowconfigure(3, weight=1)


def show_cash_entry(parent, db, account, save):
    dialog = tk.Toplevel(parent)
    dialog.title(f"Movimento di cassa · {account['name']}")
    categories = {row["name"]: row["id"] for row in db.execute(
        "SELECT id,name FROM categories WHERE archived=0 AND category_type IN ('entrata','uscita') ORDER BY name"
    )}
    fields = (
        ("Data (AAAA-MM-GG)", "", ()),
        ("Descrizione", "", ()),
        (f"Importo in {account['currency']} (+ entrata, − uscita)", "", ()),
        ("Categoria", "", ("", *categories)),
        ("Sottovoce", "", ("",)),
    )
    day, description, amount, category, subcategory = form(dialog, fields)
    sub_box = dialog.grid_slaves(row=4, column=1)[0]
    subcategories = {}

    def update_subcategories(*_):
        subcategories.clear()
        subcategories.update({row["name"]: row["id"] for row in db.execute(
            "SELECT id,name FROM subcategories WHERE category_id=? AND archived=0 ORDER BY name",
            (categories.get(category.get()),),
        )})
        sub_box.configure(values=("", *subcategories))
        subcategory.set("")

    category.trace_add("write", update_subcategories)
    ttk.Label(dialog, text="Per un prelievo o versamento, lascia la categoria vuota e collega le due gambe dal registro.",
              wraplength=450).grid(row=5, column=0, columnspan=2, padx=8)
    ttk.Button(dialog, text="Registra", command=lambda: save(
        lambda: record_cash_movement(db, account["id"], day.get(), description.get(), amount.get(),
                                     categories.get(category.get()), subcategories.get(subcategory.get())), dialog,
    )).grid(row=6, column=1, pady=8)


def form(window, fields):
    values = []
    for index, (label, initial, options) in enumerate(fields):
        variable = tk.StringVar(master=window, value=initial)
        ttk.Label(window, text=label).grid(row=index, column=0, sticky="w", padx=8, pady=5)
        widget = (ttk.Combobox(window, textvariable=variable, values=options, state="readonly", width=34)
                  if options else ttk.Entry(window, textvariable=variable, width=34))
        widget.grid(row=index, column=1, sticky="ew", padx=8, pady=5)
        values.append(variable)
    return values
