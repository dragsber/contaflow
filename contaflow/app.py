import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from services.finance import FinanceService
from adapters.google_sheets import GoogleSheetsAdapter
from adapters.enable_banking import EnableBankingAdapter
from adapters.local_ai import LocalAIAdapter


class App(tk.Tk):
    def __init__(self, service=None):
        super().__init__()
        self.title("ContaFlow · Alpha 0.1")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.store = service or FinanceService()
        self.adapters = (GoogleSheetsAdapter(), EnableBankingAdapter(), LocalAIAdapter())
        self.account_var = tk.StringVar()
        self.account_rows = []
        self.supplier_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto")
        self._build_header()
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True, padx=10, pady=(0, 10))
        self.dashboard_tab = ttk.Frame(self.tabs, padding=14)
        self.movements_tab = ttk.Frame(self.tabs, padding=10)
        self.import_tab = ttk.Frame(self.tabs, padding=10)
        self.suppliers_tab = ttk.Frame(self.tabs, padding=10)
        self.categories_tab = ttk.Frame(self.tabs, padding=10)
        for frame, title in [
            (self.dashboard_tab, "Dashboard"),
            (self.movements_tab, "Movimenti"),
            (self.import_tab, "Importazione"),
            (self.suppliers_tab, "Fornitori"),
            (self.categories_tab, "Categorie"),
        ]:
            self.tabs.add(frame, text=title)
        self._build_dashboard()
        self._build_movements()
        self._build_import()
        self._build_suppliers()
        self._build_categories()
        ttk.Label(self, textvariable=self.status_var, anchor="w", padding=(12, 4)).pack(fill="x")
        accounts = self.store.accounts()
        names = [row["name"] for row in accounts]
        self.account_rows = accounts
        self.account_box.configure(values=names)
        self.account_var.set(names[0] if names else "")
        self.refresh_all()

    def _build_header(self):
        header = ttk.Frame(self, padding=(12, 10))
        header.pack(fill="x")
        ttk.Label(header, text="ContaFlow", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text="Conto attivo", padding=(20, 0)).pack(side="left")
        self.account_box = ttk.Combobox(
            header, textvariable=self.account_var, state="readonly", width=24
        )
        self.account_box.pack(side="left")
        self.account_box.bind("<<ComboboxSelected>>", lambda event: self.refresh_all())

    def _build_dashboard(self):
        ttk.Label(
            self.dashboard_tab, text="Panoramica del conto selezionato",
            font=("Segoe UI", 16, "bold"),
        ).pack(anchor="w", pady=(0, 12))
        self.account_heading = ttk.Label(
            self.dashboard_tab, font=("Segoe UI", 12, "bold"), padding=8
        )
        self.account_heading.pack(anchor="w", fill="x")
        self.cards = ttk.Frame(self.dashboard_tab, padding=(0, 12))
        self.cards.pack(fill="x")
        ttk.Label(
            self.dashboard_tab,
            text="Il saldo visualizzato deriva dai movimenti importati. "
                 "Il saldo bancario effettivo richiede un saldo iniziale confermato.",
            wraplength=820,
        ).pack(anchor="w")

    def _build_movements(self):
        ttk.Label(
            self.movements_tab, text="Registro del conto selezionato",
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(0, 8))
        columns = ("date", "description", "amount", "fee", "currency",
                   "kind", "classification", "supplier", "category")
        self.table = ttk.Treeview(
            self.movements_tab, columns=columns, show="headings", height=22
        )
        headings = [
            ("date", "Data", 135, "w"), ("description", "Descrizione", 300, "w"),
            ("amount", "Importo", 100, "e"), ("fee", "Commissione", 95, "e"),
            ("currency", "Valuta", 65, "center"), ("kind", "Tipo", 115, "w"),
            ("classification", "Stato", 105, "center"),
            ("supplier", "Fornitore", 120, "w"), ("category", "Categoria", 120, "w"),
        ]
        for key, title, width, anchor in headings:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor=anchor)
        for tag, color in [("classificato", "#176b37"), ("proposto", "#9a6700"),
                           ("in_attesa", "#8b3a3a")]:
            self.table.tag_configure(tag, foreground=color)
        self.table.pack(fill="both", expand=True)
        actions = ttk.Frame(self.movements_tab, padding=(0, 8, 0, 0))
        actions.pack(fill="x")
        ttk.Button(actions, text="Conferma / correggi classificazione",
                   command=self.edit_movement_classification).pack(side="left")
        ttk.Button(actions, text="Aggiorna", command=self.refresh_all).pack(side="right")

    def _build_import(self):
        ttk.Label(self.import_tab, text="Importazione CSV Revolut",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            self.import_tab,
            text="L'importazione usa il conto selezionato in alto e accetta solo "
                 "un conto Revolut con valuta compatibile.",
            wraplength=900, padding=(0, 8),
        ).pack(anchor="w")
        ttk.Button(self.import_tab, text="Seleziona CSV Revolut",
                   command=self.import_csv).pack(anchor="w", pady=(0, 12))
        self.import_summary = tk.Text(self.import_tab, height=7, wrap="word", state="disabled")
        self.import_summary.pack(fill="x", pady=(0, 12))
        ttk.Label(self.import_tab, text="Anomalie di riconciliazione",
                  font=("Segoe UI", 12, "bold")).pack(anchor="w")
        columns = ("row", "currency", "expected", "actual")
        self.anomalies = ttk.Treeview(
            self.import_tab, columns=columns, show="headings", height=10
        )
        for key, title, width in [
            ("row", "Riga CSV", 100), ("currency", "Valuta", 100),
            ("expected", "Variazione attesa", 220), ("actual", "Variazione rilevata", 220),
        ]:
            self.anomalies.heading(key, text=title)
            self.anomalies.column(key, width=width)
        self.anomalies.pack(fill="both", expand=True)

    def _build_suppliers(self):
        ttk.Label(self.suppliers_tab, text="Fornitori",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w")
        search_bar = ttk.Frame(self.suppliers_tab, padding=(0, 8))
        search_bar.pack(fill="x")
        ttk.Label(search_bar, text="Cerca").pack(side="left")
        self.supplier_search = tk.StringVar()
        search = ttk.Entry(search_bar, textvariable=self.supplier_search, width=32)
        search.pack(side="left", padx=6)
        search.bind("<KeyRelease>", lambda event: self.refresh_suppliers())
        ttk.Button(search_bar, text="Nuovo fornitore",
                   command=lambda: self.edit_supplier(new=True)).pack(side="right")
        self.suppliers_table = ttk.Treeview(
            self.suppliers_tab, columns=("name", "category", "aliases"),
            show="headings", height=19,
        )
        for key, title, width in [
            ("name", "Fornitore", 260), ("category", "Categoria abituale", 220),
            ("aliases", "Alias bancari", 520),
        ]:
            self.suppliers_table.heading(key, text=title)
            self.suppliers_table.column(key, width=width)
        self.suppliers_table.pack(fill="both", expand=True)
        buttons = ttk.Frame(self.suppliers_tab, padding=(0, 8, 0, 0))
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Modifica selezionato",
                   command=self.edit_supplier).pack(side="left")
        ttk.Button(buttons, text="Aggiungi alias",
                   command=self.add_alias).pack(side="left", padx=6)
        ttk.Button(buttons, text="Rimuovi alias selezionato",
                   command=self.remove_alias).pack(side="left")

    def _build_categories(self):
        ttk.Label(self.categories_tab, text="Categorie",
                  font=("Segoe UI", 14, "bold")).pack(anchor="w", pady=(0, 8))
        self.categories_table = ttk.Treeview(
            self.categories_tab, columns=("name", "type", "custom"),
            show="headings", height=21,
        )
        for key, title, width in [
            ("name", "Nome", 360), ("type", "Tipo", 240), ("custom", "Personalizzata", 160)
        ]:
            self.categories_table.heading(key, text=title)
            self.categories_table.column(key, width=width)
        self.categories_table.pack(fill="both", expand=True)
        actions = ttk.Frame(self.categories_tab, padding=(0, 8, 0, 0))
        actions.pack(fill="x")
        ttk.Button(actions, text="Nuova categoria",
                   command=lambda: self.edit_category(new=True)).pack(side="left")
        ttk.Button(actions, text="Modifica selezionata",
                   command=self.edit_category).pack(side="left", padx=6)
        ttk.Button(actions, text="Archivia selezionata",
                   command=self.archive_category).pack(side="left")

    def refresh_all(self):
        self.account_rows = self.store.accounts()
        names = [row["name"] for row in self.account_rows]
        self.account_box.configure(values=names)
        if self.account_var.get() not in names:
            self.account_var.set(names[0] if names else "")
        account = self.account_var.get() or None
        self._refresh_dashboard(account)
        self._refresh_movements(account)
        self.refresh_suppliers()
        self.refresh_categories()

    def _refresh_dashboard(self, account):
        rows = self.store.summary(account)
        for child in self.cards.winfo_children():
            child.destroy()
        if not rows:
            self.account_heading.config(text="Nessun conto configurato")
            return
        row = rows[0]
        currency = row["currency"]
        self.account_heading.config(
            text=f"{row['name']} · {currency} · Saldo dei movimenti importati: "
                 f"{row['balance']:.2f} {currency} · Saldo iniziale non confermato"
        )
        ttk.Label(
            self.cards,
            text=f"Entrate {row['income']:.2f} {currency}     "
                 f"Uscite {row['expenses']:.2f} {currency}",
            padding=14, relief="groove",
        ).pack(side="left")

    def _refresh_movements(self, account):
        self.table.delete(*self.table.get_children())
        for row in self.store.movements(account):
            status = row["classification_status"] or "in_attesa"
            self.table.insert(
                "", "end", iid=str(row["id"]),
                values=(row["occurred_at"], row["description"],
                        f"{row['amount']:+.2f}", f"{row['fee']:.2f}",
                        row["currency"], row["kind"], status,
                        row["supplier"] or "", row["category"] or ""),
                tags=(status,),
            )

    def refresh_suppliers(self):
        if not hasattr(self, "suppliers_table"):
            return
        self.suppliers_table.delete(*self.suppliers_table.get_children())
        for row in self.store.suppliers(self.supplier_search.get()):
            aliases = ", ".join(
                item["normalized_alias"] for item in self.store.supplier_aliases(row["id"])
            )
            self.suppliers_table.insert(
                "", "end", iid=str(row["id"]),
                values=(row["name"], row["category"] or "", aliases),
            )

    def refresh_categories(self):
        if not hasattr(self, "categories_table"):
            return
        self.categories_table.delete(*self.categories_table.get_children())
        for row in self.store.categories():
            self.categories_table.insert(
                "", "end", iid=str(row["id"]),
                values=(row["name"], row["category_type"],
                        "Sì" if row["is_custom"] else "No"),
            )

    def _selected_id(self, widget, label):
        selected = widget.selection()
        if not selected:
            messagebox.showinfo("Selezione richiesta", f"Seleziona {label}.", parent=self)
            return None
        return int(selected[0])

    def edit_supplier(self, new=False):
        supplier_id = None if new else self._selected_id(self.suppliers_table, "un fornitore")
        if not new and supplier_id is None:
            return
        is_new = new
        if not is_new and not supplier_id:
            return
        current = None if is_new else next(
            row for row in self.store.suppliers()
            if int(row["id"]) == supplier_id
        )
        categories = self.store.categories()
        category_names = ["— Nessuna —"] + [row["name"] for row in categories]
        win = tk.Toplevel(self)
        win.title("Nuovo fornitore" if is_new else "Modifica fornitore")
        win.transient(self)
        form = ttk.Frame(win, padding=14)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text="Nome").grid(row=0, column=0, sticky="w", pady=5)
        name_var = tk.StringVar(value="" if is_new else current["name"])
        ttk.Entry(form, textvariable=name_var, width=38).grid(row=0, column=1, sticky="ew")
        ttk.Label(form, text="Categoria abituale").grid(row=1, column=0, sticky="w", pady=5)
        category_var = tk.StringVar(
            value="— Nessuna —" if is_new else (current["category"] or "— Nessuna —")
        )
        ttk.Combobox(form, textvariable=category_var, values=category_names,
                     state="readonly", width=35).grid(row=1, column=1, sticky="ew")
        ttk.Label(form, text="Alias iniziale (facoltativo)").grid(
            row=2, column=0, sticky="w", pady=5
        )
        alias_var = tk.StringVar()
        ttk.Entry(form, textvariable=alias_var, width=38).grid(row=2, column=1, sticky="ew")
        def save():
            try:
                category_id = next(
                    (row["id"] for row in categories if row["name"] == category_var.get()),
                    None,
                )
                if is_new:
                    self.store.create_supplier(
                        name_var.get(), [alias_var.get()] if alias_var.get().strip() else (),
                        category_id,
                    )
                else:
                    self.store.update_supplier(supplier_id, name_var.get(), category_id)
                    if alias_var.get().strip():
                        self.store.add_supplier_alias(supplier_id, alias_var.get())
                win.destroy()
                self.refresh_all()
            except Exception as error:
                messagebox.showerror("Fornitore non salvato", str(error), parent=win)
        ttk.Button(form, text="Salva", command=save).grid(
            row=3, column=1, sticky="e", pady=(10, 0)
        )
        form.columnconfigure(1, weight=1)
        win.grab_set()

    def add_alias(self):
        supplier_id = self._selected_id(self.suppliers_table, "un fornitore")
        if supplier_id is None:
            return
        alias = simpledialog.askstring("Nuovo alias", "Descrizione bancaria:", parent=self)
        if alias is None:
            return
        try:
            self.store.add_supplier_alias(supplier_id, alias)
            self.refresh_suppliers()
        except Exception as error:
            messagebox.showerror("Alias non salvato", str(error), parent=self)

    def remove_alias(self):
        supplier_id = self._selected_id(self.suppliers_table, "un fornitore")
        if supplier_id is None:
            return
        aliases = self.store.supplier_aliases(supplier_id)
        if not aliases:
            messagebox.showinfo("Alias", "Il fornitore non ha alias.", parent=self)
            return
        choices = [f"{row['id']} · {row['normalized_alias']}" for row in aliases]
        picked = simpledialog.askstring(
            "Rimuovi alias", "Inserisci ID alias da rimuovere:\n" + "\n".join(choices),
            parent=self,
        )
        if not picked:
            return
        try:
            self.store.remove_supplier_alias(int(picked.strip().split("·")[0]))
            self.refresh_suppliers()
        except Exception as error:
            messagebox.showerror("Alias non rimosso", str(error), parent=self)

    def edit_category(self, new=False):
        category_id = None if new else self._selected_id(self.categories_table, "una categoria")
        if not new and category_id is None:
            return
        is_new = new
        if not is_new and not category_id:
            return
        current = None if is_new else next(
            row for row in self.store.categories() if int(row["id"]) == category_id
        )
        win = tk.Toplevel(self)
        win.title("Nuova categoria" if is_new else "Modifica categoria")
        win.transient(self)
        form = ttk.Frame(win, padding=14)
        form.pack(fill="both", expand=True)
        name_var = tk.StringVar(value="" if is_new else current["name"])
        type_var = tk.StringVar(value="uscita" if is_new else current["category_type"])
        ttk.Label(form, text="Nome").grid(row=0, column=0, sticky="w", pady=5)
        ttk.Entry(form, textvariable=name_var, width=34).grid(row=0, column=1)
        ttk.Label(form, text="Tipo").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(
            form, textvariable=type_var, values=("entrata", "uscita", "trasferimento"),
            state="readonly",
        ).grid(row=1, column=1, sticky="ew")
        def save():
            try:
                if is_new:
                    self.store.create_category(name_var.get(), type_var.get())
                else:
                    self.store.update_category(category_id, name_var.get(), type_var.get())
                win.destroy()
                self.refresh_all()
            except Exception as error:
                messagebox.showerror("Categoria non salvata", str(error), parent=win)
        ttk.Button(form, text="Salva", command=save).grid(
            row=2, column=1, sticky="e", pady=(10, 0)
        )
        win.grab_set()

    def archive_category(self):
        category_id = self._selected_id(self.categories_table, "una categoria")
        if category_id is None:
            return
        if messagebox.askyesno("Archivia categoria", "Archiviare la categoria selezionata?",
                               parent=self):
            self.store.archive_category(category_id)
            self.refresh_all()

    def edit_movement_classification(self):
        movement_id = self._selected_id(self.table, "un movimento")
        if movement_id is None:
            return
        movement = next(
            row for row in self.store.movements(self.account_var.get())
            if int(row["id"]) == movement_id
        )
        suppliers = self.store.suppliers()
        categories = self.store.categories()
        supplier_names = ["— Nessuno —"] + [row["name"] for row in suppliers]
        category_names = ["— Nessuna —"] + [row["name"] for row in categories]
        win = tk.Toplevel(self)
        win.title("Classificazione movimento")
        win.transient(self)
        form = ttk.Frame(win, padding=14)
        form.pack(fill="both", expand=True)
        ttk.Label(form, text=movement["description"], wraplength=500).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        supplier_var = tk.StringVar(value=movement["supplier"] or "— Nessuno —")
        category_var = tk.StringVar(value=movement["category"] or "— Nessuna —")
        ttk.Label(form, text="Fornitore").grid(row=1, column=0, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=supplier_var, values=supplier_names,
                     state="readonly").grid(row=1, column=1, sticky="ew")
        ttk.Label(form, text="Categoria").grid(row=2, column=0, sticky="w", pady=5)
        ttk.Combobox(form, textvariable=category_var, values=category_names,
                     state="readonly").grid(row=2, column=1, sticky="ew")
        remember_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            form, text="Conferma e riusa questa descrizione nei prossimi import",
            variable=remember_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=8)
        def save():
            supplier_id = next(
                (row["id"] for row in suppliers if row["name"] == supplier_var.get()), None
            )
            category_id = next(
                (row["id"] for row in categories if row["name"] == category_var.get()), None
            )
            try:
                self.store.classify_movement(
                    movement_id, supplier_id, category_id, remember_var.get()
                )
                win.destroy()
                self.refresh_all()
            except Exception as error:
                messagebox.showerror("Classificazione non salvata", str(error), parent=win)
        ttk.Button(form, text="Salva classificazione", command=save).grid(
            row=4, column=1, sticky="e", pady=(10, 0)
        )
        form.columnconfigure(1, weight=1)
        win.grab_set()

    def import_csv(self):
        path = filedialog.askopenfilename(
            filetypes=[("CSV Revolut", "*.csv"), ("Tutti i file", "*.*")]
        )
        if not path:
            return
        try:
            with open(path, encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or "Valuta" not in reader.fieldnames:
                    raise ValueError("Il CSV non contiene la colonna Valuta")
                currencies = {
                    row["Valuta"].strip().upper()
                    for row in reader
                    if row.get("State", "").strip().upper() == "COMPLETATO"
                }
            account = self.account_var.get()
            selected = next((row for row in self.account_rows if row["name"] == account), None)
            if selected is None or selected["provider"] != "REVOLUT":
                raise ValueError("Seleziona un conto Revolut. BPER e Cassa non sono compatibili.")
            if currencies != {selected["currency"].upper()}:
                raise ValueError(
                    f"Valuta CSV ({', '.join(sorted(currencies)) or 'non rilevata'}) "
                    f"non compatibile con {account} ({selected['currency']})."
                )
            self.tabs.select(self.import_tab)
            self.anomalies.delete(*self.anomalies.get_children())
            result = self.store.import_revolut(path, account)
            anomalies = result.pop("anomalies")
            for anomaly in anomalies:
                self.anomalies.insert(
                    "", "end",
                    values=(anomaly["row"], anomaly["currency"],
                            anomaly["expected_delta"], anomaly["actual_delta"]),
                )
            self.refresh_all()
            report = (
                f"Conto: {account}\nValuta: {', '.join(sorted(currencies))}\n"
                f"Importati: {result['imported']}\n"
                f"Duplicati saltati: {result['duplicates']}\n"
                f"Escluse (non completate): {result['excluded']}\n"
                f"Classificati automaticamente: {result['classified']}\n"
                f"Proposte da confermare: {result['proposed']}\n"
                f"In attesa: {result['pending']}\n"
                f"Anomalie: {len(anomalies)}\nErrori: 0"
            )
            self.import_summary.configure(state="normal")
            self.import_summary.delete("1.0", "end")
            self.import_summary.insert("1.0", report)
            self.import_summary.configure(state="disabled")
            self.status_var.set(f"Importazione completata · {result['imported']} movimenti importati")
        except Exception as error:
            self.status_var.set("Importazione non completata")
            messagebox.showerror("Importazione non completata", str(error), parent=self)


def main():
    App().mainloop()
