import tkinter as tk
from tkinter import messagebox, ttk

from services.accounts import (
    archive_account, balance_movements, list_accounts, opening_balance, save_account, save_opening,
)
from services.register import money


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
    columns = ("nome", "tipo", "valuta", "istituto", "variazione", "saldo", "ultimo", "stato")
    table = ttk.Treeview(window, columns=columns, show="headings", selectmode="browse", height=8)
    for column, title, width in zip(columns,
        ("Nome", "Tipo", "Valuta", "Istituto", "Variazione netta", "Saldo calcolato", "Ultimo movimento", "Stato"),
        (150, 145, 65, 100, 120, 120, 130, 90)):
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
            table.insert("", "end", iid=identifier, values=(
                row["name"], next((name for name, code in TYPES.items() if code == row["provider"]), row["provider"]),
                currency, row["institution"], money(summary["balance"], currency),
                money(balance, currency) if balance is not None else "Non impostato",
                row["last_movement"] or "—", "Archiviato" if row["archived"] else "Attivo",
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

    actions = ttk.Frame(window)
    actions.pack(fill="x", padx=8, pady=8)
    for label, command in (
        ("Nuovo", lambda: edit(True)), ("Modifica", edit), ("Archivia / riattiva", archive),
        ("Saldo iniziale", opening), ("Movimenti del conto", movements),
        ("Movimenti nel calcolo", lambda: movements(True)),
    ):
        ttk.Button(actions, text=label, command=command).pack(side="left", padx=3)
    refresh()


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
