import csv
import sqlite3
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from services.finance import FinanceService, RestoreVerificationError
from contaflow.runtime import log_exception, show_error
from contaflow.register import MovementRegister
from adapters.google_sheets import GoogleSheetsAdapter
from adapters.enable_banking import EnableBankingAdapter
from adapters.local_ai import LocalAIAdapter


class App(tk.Tk):
    def __init__(self, service=None):
        super().__init__()
        self.title("ContaFlow · Alpha 0.2 — build intermedia")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.store = service or FinanceService()
        self.adapters = (GoogleSheetsAdapter(), EnableBankingAdapter(), LocalAIAdapter())
        self.account_var = tk.StringVar()
        self.account_rows = []
        self.supplier_var = tk.StringVar()
        self.category_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto")
        self._build_menu()
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
        self.account_box.configure(values=names + ['Tutti i conti'])
        self.account_var.set(names[0] if names else "")
        self.refresh_all()

    def _build_menu(self):
        menu = tk.Menu(self)
        database_menu = tk.Menu(menu, tearoff=False)
        database_menu.add_command(label="Crea backup database", command=self.backup_database)
        database_menu.add_command(label="Ripristina backup...", command=self.restore_database)
        menu.add_cascade(label="Database", menu=database_menu)
        self.configure(menu=menu)

    def report_callback_exception(self, exc_type, exc_value, exc_traceback):
        log_exception(exc_value, "Errore non gestito nella GUI", exc_traceback)
        messagebox.showerror(
            "Errore di ContaFlow",
            "L'operazione non è riuscita. Il dettaglio tecnico è stato salvato nel log locale.",
            parent=self,
        )

    def backup_database(self):
        try:
            path = self.store.backup_database()
            self.status_var.set("Backup creato")
            messagebox.showinfo("Backup completato", f"Copia salvata in:\n{path}", parent=self)
        except Exception as error:
            show_error(self, "Backup non completato",
                       "Non è stato possibile creare il backup.", error, "Creazione backup")

    def restore_database(self):
        path = filedialog.askopenfilename(
            title="Seleziona backup ContaFlow",
            filetypes=[("Database SQLite", "*.sqlite3 *.sqlite *.db"), ("Tutti i file", "*.*")],
        )
        if not path:
            return
        if not messagebox.askyesno(
            "Conferma ripristino",
            "Il ripristino sostituirà i dati attualmente caricati. "
            "Prima verrà creato un backup automatico.",
            parent=self,
        ):
            return
        try:
            safety_copy = self.store.restore_database(path)
        except RestoreVerificationError as error:
            self.status_var.set("Verifica del ripristino fallita")
            show_error(self, "Errore critico di ripristino", str(error), error, "Verifica ripristino")
            return
        except Exception as error:
            show_error(self, "Ripristino non completato",
                       "Il backup non è stato ripristinato.", error, "Ripristino database")
            return
        try:
            self.status_var.set("Database ripristinato")
            self.import_summary.configure(state="normal")
            self.import_summary.delete("1.0", "end")
            self.import_summary.configure(state="disabled")
            self.anomalies.delete(*self.anomalies.get_children())
            self.refresh_all()
            messagebox.showinfo(
                "Ripristino completato",
                f"Database ripristinato. Copia di sicurezza del precedente:\n{safety_copy}",
                parent=self,
            )
        except sqlite3.DatabaseError as error:
            self.status_var.set("Errore critico di lettura")
            show_error(self, "Errore critico di lettura",
                       f"Copia eseguita, ma lettura dei dati fallita. Copia di sicurezza:\n{safety_copy}",
                       error, "Lettura dopo ripristino")
        except Exception as error:
            messagebox.showwarning(
                "Ripristino completato",
                f"Database ripristinato. Riapri ContaFlow per aggiornare le viste.\n{error}\n"
                f"Copia di sicurezza del precedente:\n{safety_copy}",
                parent=self,
            )

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
        self.register = MovementRegister(
            self.movements_tab, self.store, lambda: None if self.account_var.get() == 'Tutti i conti' else self.account_var.get() or None,
            self.edit_movement_classification,
        )
        self.register.pack(fill="both", expand=True)
        self.table = self.register.table

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
                   command=self.import_csv).pack(anchor="w", pady=(0, 6))
        ttk.Button(self.import_tab, text="Gestisci lotti / annullamento",
                   command=self.import_batches).pack(anchor="w", pady=(0, 6))
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
        self.show_archived_suppliers = tk.BooleanVar()
        ttk.Checkbutton(search_bar, text="Includi archiviati",
                        variable=self.show_archived_suppliers,
                        command=self.refresh_suppliers).pack(side="left")
        search = ttk.Entry(search_bar, textvariable=self.supplier_search, width=32)
        search.pack(side="left", padx=6)
        search.bind("<KeyRelease>", lambda event: self.refresh_suppliers())
        ttk.Button(search_bar, text="Nuovo fornitore",
                   command=lambda: self.edit_supplier(new=True)).pack(side="right")
        ttk.Button(search_bar, text="Importa anagrafiche", command=self.import_catalog).pack(side="right", padx=6)
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
        ttk.Button(buttons, text="Archivia / riattiva",
                   command=self.toggle_supplier).pack(side="left", padx=6)
        ttk.Button(buttons, text="Movimenti collegati",
                   command=lambda: self.related_movements("supplier")).pack(side="left")


    def import_catalog(self):
        from services.catalog_import import read_catalog
        messagebox.showinfo(
            "Formato anagrafiche",
            "CSV con separatore ; oppure XLSX con foglio Anagrafiche.\n"
            "Colonne richieste: fornitore, categoria, tipo, alias, note.\n"
            "Tipi: entrata, uscita, trasferimento. Un fornitore per riga.\n"
            "Il file storico originale richiede una mappatura verso questo formato.",
            parent=self,
        )
        path = filedialog.askopenfilename(filetypes=[("Anagrafiche strutturate", "*.csv *.xlsx")])
        if not path:
            return
        try:
            rows = read_catalog(path)
            if messagebox.askyesno("Anteprima anagrafiche",
                                   f"Importare {len(rows)} righe validate? Le duplicazioni bloccano il lotto.",
                                   parent=self):
                self.store.import_catalog(rows)
                self.refresh_all()
        except Exception as error:
            show_error(self, "Anagrafiche non importate", str(error), error, "Import anagrafiche")

    def toggle_supplier(self):
        supplier_id = self._selected_id(self.suppliers_table, "un fornitore")
        if supplier_id is None:
            return
        row = next(r for r in self.store.suppliers(include_archived=True) if r["id"] == supplier_id)
        if messagebox.askyesno("Stato fornitore", "Cambiare lo stato attivo / archiviato?", parent=self):
            self.store.archive_supplier(supplier_id, not row["archived"])
            self.refresh_all()

    def related_movements(self, field):
        table = self.suppliers_table if field == "supplier" else self.categories_table
        identifier = self._selected_id(table, "una voce")
        if identifier is None:
            return
        rows = self.store.suppliers(include_archived=True) if field == "supplier" else self.store.categories(True)
        row = next(r for r in rows if r["id"] == identifier)
        self.account_var.set("Tutti i conti")
        self.register.reset()
        self.register.filters[field].set(f"{identifier} · {row['name']}")
        self.register.refresh()
        self.tabs.select(self.movements_tab)

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
        ttk.Button(actions, text="Movimenti collegati",
                   command=lambda: self.related_movements("category")).pack(side="left", padx=6)
        ttk.Button(actions, text="Fornitori collegati", command=self.category_suppliers).pack(side="left")

    def category_suppliers(self):
        category_id = self._selected_id(self.categories_table, "una categoria")
        if category_id is None:
            return
        rows = self.store.category_suppliers(category_id)
        messagebox.showinfo("Fornitori collegati", "\n".join(r[0] for r in rows) or "Nessun fornitore", parent=self)

    def refresh_all(self):
        self.account_rows = self.store.accounts()
        names = [row["name"] for row in self.account_rows]
        self.account_box.configure(values=names)
        if self.account_var.get() not in names + ['Tutti i conti']:
            self.account_var.set(names[0] if names else "")
        account = None if self.account_var.get() == 'Tutti i conti' else self.account_var.get() or None
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
        if row["opening_balance_confirmed"]:
            balance_label = (
                f"Saldo bancario effettivo: {row['bank_balance']:.2f} {currency} "
                f"(saldo iniziale al {row['opening_as_of']})"
            )
        else:
            balance_label = (
                f"Saldo dei movimenti importati: {row['balance']:.2f} {currency} · "
                "Saldo iniziale non confermato"
            )
        self.account_heading.config(text=f"{row['name']} · {currency} · {balance_label}")
        ttk.Label(
            self.cards,
            text=f"Entrate {row['income']:.2f} {currency}     "
                 f"Uscite {row['expenses']:.2f} {currency}     "
                 f"Commissioni {row['fees']:.2f} {currency}",
            padding=14, relief="groove",
        ).pack(side="left")

    def _refresh_movements(self, account):
        self.register.refresh()

    def refresh_suppliers(self):
        if not hasattr(self, "suppliers_table"):
            return
        self.suppliers_table.delete(*self.suppliers_table.get_children())
        for row in self.store.suppliers(self.supplier_search.get(), self.show_archived_suppliers.get()):
            aliases = ", ".join(
                item["normalized_alias"] for item in self.store.supplier_aliases(row["id"])
            )
            self.suppliers_table.insert(
                "", "end", iid=str(row["id"]),
                values=(row["name"] + (" [archiviato]" if row["archived"] else ""), row["category"] or "", aliases),
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
            row for row in self.store.suppliers(include_archived=True)
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
        ttk.Label(form, text="Note").grid(row=3, column=0, sticky="w")
        notes = tk.Text(form, height=3, width=38)
        notes.grid(row=3, column=1)
        notes.insert("1.0", "" if is_new else current["notes"])
        ttk.Label(form, text="Categorie alternative").grid(row=4, column=0, sticky="w")
        alternatives = tk.Listbox(form, selectmode="multiple", exportselection=False, height=5)
        alternatives.grid(row=4, column=1, sticky="ew")
        existing_alternatives = [] if is_new else self.store.supplier_categories(supplier_id)
        for index, category in enumerate(categories):
            alternatives.insert("end", category["name"])
            if category["id"] in existing_alternatives:
                alternatives.selection_set(index)
        def save():
            try:
                category_id = next(
                    (row["id"] for row in categories if row["name"] == category_var.get()),
                    None,
                )
                self.store.save_supplier(
                    name_var.get(), category_id, alias_var.get(), notes.get("1.0", "end-1c"),
                    [categories[index]["id"] for index in alternatives.curselection()],
                    supplier_id,
                )
                win.destroy()
                self.refresh_all()
            except Exception as error:
                show_error(win, "Fornitore non salvato", "Controlla i dati inseriti.", error, "Salvataggio fornitore")
        ttk.Button(form, text="Salva", command=save).grid(
            row=5, column=1, sticky="e", pady=(10, 0)
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
            show_error(self, 'Alias non salvato', 'Impossibile aggiungere l\'alias.', error, 'Salvataggio alias')

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
            show_error(self, 'Alias non rimosso', 'Impossibile rimuovere l\'alias.', error, 'Rimozione alias')

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
                show_error(win, "Categoria non salvata", "Controlla i dati inseriti.", error, "Salvataggio categoria")
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
        from contaflow.movement_editor import edit_movements
        edit_movements(self)

    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[("CSV Revolut", "*.csv"), ("Tutti i file", "*.*")])
        if not path:
            return
        try:
            preview = self.store.preview_import(path, self.account_var.get())
            report = (
                f"Conto: {preview.account}\nValuta: {preview.currency}\n"
                f"Righe totali: {preview.total}\nImportabili: {preview.importable}\n"
                f"Duplicati: {preview.duplicates}\nEscluse: {preview.excluded}\n"
                f"Anomalie di riconciliazione: {len(preview.anomalies)}\n"
            )
            self.tabs.select(self.import_tab)
            self.import_summary.configure(state="normal")
            self.import_summary.delete("1.0", "end")
            self.import_summary.insert("1.0", "ANTEPRIMA — nessun dato ancora importato\n" + report)
            self.import_summary.configure(state="disabled")
            self.anomalies.delete(*self.anomalies.get_children())
            for anomaly in preview.anomalies:
                self.anomalies.insert("", "end", values=(
                    anomaly["row"], anomaly["currency"], anomaly["expected_delta"], anomaly["actual_delta"]))
            if not messagebox.askyesno("Conferma importazione", report + "\nImportare queste righe?", parent=self):
                self.status_var.set("Importazione annullata")
                return
            result = self.store.confirm_import(preview)
            self.refresh_all()
            self.import_summary.configure(state="normal")
            self.import_summary.insert("end", f"\nIMPORTATO — lotto {result['batch_id']}\n"
                                       f"Importati: {result['imported']}\nDuplicati: {result['duplicates']}")
            self.import_summary.configure(state="disabled")
            self.status_var.set(f"Importazione completata · lotto {result['batch_id']}")
        except Exception as error:
            show_error(self, "Importazione non completata", "Controlla il file e il conto selezionato.",
                       error, "Import CSV Revolut")

    def import_batches(self):
        win = tk.Toplevel(self)
        win.title("Lotti di importazione")
        table = ttk.Treeview(win, columns=("file", "account", "when", "status", "count"), show="headings", height=12)
        for key, label in (("file","File"), ("account","Conto"), ("when","Data"), ("status","Esito"), ("count","Movimenti")):
            table.heading(key, text=label)
            table.column(key, width=170)
        table.pack(fill="both", expand=True)

        def refresh():
            table.delete(*table.get_children())
            for row in self.store.import_batches():
                table.insert("", "end", iid=str(row["id"]), values=(
                    row["file_name"], row["account"], row["imported_at"], row["result"], row["movements"]))

        def cancel():
            if not table.selection():
                return
            batch_id = int(table.selection()[0])
            dependencies = self.store.batch_dependencies(batch_id)
            extra = any(dependencies[key] for key in ("manual", "transfers", "refunds"))
            text = (f"Annullare lotto {batch_id}? Movimenti da rimuovere: {dependencies['movements']}.\n"
                    f"Modificati manualmente: {dependencies['manual']}. "
                    f"Collegamenti trasferimenti: {dependencies['transfers']}, rimborsi: {dependencies['refunds']}.\n")
            if extra:
                text += ("CONFERMA SPECIFICA — saranno rimossi anche i collegamenti. "
                         "Le altre gambe di trasferimento torneranno In attesa. "
                         "I valori rimossi saranno conservati nell'audit.")
            if not messagebox.askyesno("Conferma annullamento lotto", text, parent=win):
                return
            try:
                self.store.cancel_batch(batch_id, confirm_dependencies=extra)
                refresh()
                self.refresh_all()
            except Exception as error:
                show_error(win, "Lotto non annullato", str(error), error, "Annullamento lotto")
        ttk.Button(win, text="Annulla lotto selezionato", command=cancel).pack(anchor="w", padx=8, pady=8)
        refresh()


def main():
    try:
        App().mainloop()
    except Exception as error:
        log_path = log_exception(error, "Avvio applicazione")
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "ContaFlow non avviato",
            "L'applicazione non è riuscita ad avviarsi. "
            f"Il dettaglio è nel log locale:\n{log_path}",
            parent=root,
        )
        root.destroy()
