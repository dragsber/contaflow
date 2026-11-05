import json
import tkinter as tk
from datetime import datetime
from tkinter import ttk, messagebox

from services.register import STATUSES, money


class MovementRegister(ttk.Frame):
    def __init__(self, parent, service, account, edit):
        super().__init__(parent)
        self.service, self.account = service, account
        self.sort, self.descending = "date", True
        self.rows = {}
        self.filters = {name: tk.StringVar() for name in
                        ("search", "start", "end", "category", "supplier", "status", "ledger")}
        filters = ttk.Frame(self)
        filters.pack(fill="x")
        for column, (name, label) in enumerate((
            ("search", "Ricerca"), ("start", "Dal (AAAA-MM-GG)"), ("end", "Al (AAAA-MM-GG)"),
        )):
            ttk.Label(filters, text=label).grid(row=0, column=column, sticky="w")
            entry = ttk.Entry(filters, textvariable=self.filters[name])
            entry.grid(row=1, column=column, sticky="ew", padx=(0, 8))
            entry.bind("<Return>", lambda event: self.refresh())
            filters.columnconfigure(column, weight=1)
        self.boxes = {}
        for column, (name, label) in enumerate((
            ("category", "Categoria"), ("supplier", "Fornitore"), ("status", "Stato"),
        )):
            ttk.Label(filters, text=label).grid(row=2, column=column, sticky="w")
            box = ttk.Combobox(filters, textvariable=self.filters[name], state="readonly")
            box.grid(row=3, column=column, sticky="ew", padx=(0, 8), pady=(0, 6))
            box.bind("<<ComboboxSelected>>", lambda event: self.refresh())
            self.boxes[name] = box
        ttk.Label(filters,text="Conto contabile").grid(row=4,column=0,sticky="w")
        ledger_box = ttk.Combobox(filters,textvariable=self.filters["ledger"],state="readonly")
        ledger_box.grid(row=5,column=0,columnspan=3,sticky="ew",pady=(0,5))
        ledger_box.bind("<<ComboboxSelected>>",lambda event:self.refresh())
        self.boxes["ledger"] = ledger_box
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=4)
        ttk.Button(actions, text="Applica filtri", command=self.refresh).pack(side="left")
        ttk.Button(actions, text="Azzera filtri", command=self.reset).pack(side="left", padx=6)
        ttk.Button(actions, text="Da classificare", command=self.unclassified).pack(side="left")
        ttk.Button(actions, text="Modifica selezionati", command=edit).pack(side="left", padx=6)
        links = ttk.Frame(self)
        links.pack(fill="x", pady=3)
        ttk.Button(links, text="Collega due movimenti",
                   command=self.link_selected).pack(side="left")
        ttk.Button(links, text="Scollega", command=self.unlink_selected).pack(side="left")
        ttk.Button(links,text="Assegna conto contabile",command=self.assign_ledger).pack(side="left",padx=8)
        ttk.Button(links,text="Assegna sottovoce",command=self.assign_subcategory).pack(side="left")
        self.count = ttk.Label(actions)
        self.count.pack(side="right")
        headings = (
            ("date", "Data e ora", 145), ("account", "Conto bancario", 145),
            ("description", "Descrizione", 300), ("amount", "Importo", 135),
            ("fee", "Commissione", 115), ("currency", "Valuta", 70),
            ("kind", "Tipo bancario", 125), ("classification", "Stato", 210),
            ("supplier", "Fornitore", 160), ("category", "Categoria", 160),
            ("ledger", "Conto contabile", 170),
            ("subcategory", "Sottovoce", 170),
        )
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(area, columns=[h[0] for h in headings],
                                  show="headings", selectmode="extended", height=12)
        for key, label, width in headings:
            self.table.heading(key, text=label, command=lambda k=key: self.order(k))
            self.table.column(key, width=width, minwidth=60, stretch=False,
                              anchor="e" if key in ("amount", "fee") else "w")
        self.table.grid(row=0, column=0, sticky="nsew")
        for orient, row, column, axis in (
            ("vertical", 0, 1, "y"), ("horizontal", 1, 0, "x"),
        ):
            bar = ttk.Scrollbar(area, orient=orient, command=getattr(self.table, axis+"view"))
            bar.grid(row=row, column=column, sticky="ns" if axis=="y" else "ew")
            self.table.configure(**{axis+"scrollcommand": bar.set})
        for tag, color in (
            ("classificato", "#176b37"), ("proposto", "#8a5900"),
            ("in_attesa", "#8b3a3a"), ("trasferimento", "#245ba0"), ("escluso", "#626262"),
        ):
            self.table.tag_configure(tag, foreground=color)
        ttk.Label(self, text="Legenda  " + "   |   ".join(STATUSES.values()),
                  wraplength=1000).pack(fill="x", pady=5)
        self.detail = tk.Text(self, height=5, wrap="word", state="disabled")
        self.detail.pack(fill="x")
        self.table.bind("<<TreeviewSelect>>", self.show_detail)

    def assign_subcategory(self):
        from services.subcategories import assign
        selected = [int(value) for value in self.table.selection()]
        if not selected:
            messagebox.showinfo("Sottovoce","Seleziona i movimenti.",parent=self)
            return
        categories = {self.rows[str(identifier)]["category_id"] for identifier in selected}
        if len(categories) != 1 or None in categories:
            messagebox.showerror("Sottovoce","Seleziona movimenti con la stessa categoria.",parent=self)
            return
        rows = self.service.store.db.execute(
            "SELECT id,name FROM subcategories WHERE category_id=? AND archived=0 ORDER BY name",
            (next(iter(categories)),),
        ).fetchall()
        win = tk.Toplevel(self)
        win.title("Assegna sottovoce")
        choices = {f"{r['id']} · {r['name']}":r["id"] for r in rows}
        value = tk.StringVar(value="Non ripartito")
        ttk.Combobox(win,textvariable=value,values=["Non ripartito"]+list(choices),state="readonly",width=55).pack(padx=12,pady=12)
        remember = tk.BooleanVar()
        ttk.Checkbutton(win,text="Memorizza la scelta per i futuri movimenti compatibili",variable=remember).pack()
        def save():
            if not messagebox.askyesno("Conferma",f"Verranno modificati {len(selected)} movimenti. Procedere?",parent=win):
                return
            try:
                assign(self.service.store.db,selected,choices.get(value.get()),remember=remember.get(),
                       normalize=self.service.store.normalize_description)
                win.destroy()
                self.winfo_toplevel().refresh_all()
            except Exception as error:
                messagebox.showerror("Assegnazione non riuscita",str(error),parent=win)
        ttk.Button(win,text="Salva",command=save).pack(pady=8)

    def assign_ledger(self):
        from contaflow.ledger import assign_selected
        assign_selected(self.winfo_toplevel())

    def unlink_selected(self):
        selected = self.table.selection()
        if len(selected) != 1:
            messagebox.showinfo("Scollegamento", "Seleziona un solo movimento.", parent=self)
            return
        if messagebox.askyesno("Conferma scollegamento",
                              "Rimuovere tutti i collegamenti contabili del movimento selezionato?",
                              parent=self):
            self.service.unlink_movement(int(selected[0]))
            self.winfo_toplevel().refresh_all()

    def link_selected(self):
        selected = [self.rows[iid] for iid in self.table.selection()]
        if len(selected) != 2:
            messagebox.showwarning("Collegamento", "Seleziona due movimenti, un'uscita e un'entrata.", parent=self)
            return
        selected.sort(key=lambda row: row["amount"])
        outgoing, incoming = selected
        win = tk.Toplevel(self)
        win.title("Collegamento contabile")
        ttk.Label(win, text=(
            f"Uscita: {outgoing['account']} — {money(outgoing['amount'], outgoing['currency'])}\n"
            f"Entrata: {incoming['account']} — {money(incoming['amount'], incoming['currency'])}\n"
            "Saranno collegate le registrazioni esistenti. Commissioni separate."
        ), padding=12).pack()
        kind = tk.StringVar(value="trasferimento")
        ttk.Combobox(win, textvariable=kind, state="readonly", values=(
            "trasferimento", "prelievo", "giroconto", "rimborso", "storno",
        )).pack(padx=12, pady=6)

        def save():
            try:
                self.service.link_movements(outgoing["id"], incoming["id"], kind.get())
                win.destroy()
                self.winfo_toplevel().refresh_all()
            except Exception as error:
                messagebox.showerror("Collegamento non salvato", str(error), parent=win)
        ttk.Button(win, text="Conferma collegamento", command=save).pack(pady=12)

    def reset(self):
        for var in self.filters.values():
            var.set("")
        self.refresh()

    def unclassified(self):
        self.filters["status"].set("Da classificare")
        self.refresh()

    def order(self, column):
        self.descending = not self.descending if self.sort == column else False
        self.sort = column
        self.refresh()

    def refresh(self):
        categories = self.service.categories(include_archived=True)
        suppliers = self.service.suppliers(include_archived=True)
        maps = {
            "ledger": {"Non assegnato":"unassigned",**{f"{r['code']} — {r['description']}":r["id"] for r in self.service.ledger.accounts(include_archived=True)}},
            "category": {f"{r['id']} · {r['name']}": r["id"] for r in categories},
            "supplier": {f"{r['id']} · {r['name']}": r["id"] for r in suppliers},
            "status": {**{label: key for key, label in STATUSES.items()},
                       "Da classificare": "da_classificare"},
        }
        for name in maps:
            self.boxes[name].configure(values=[""] + list(maps[name]))
        values = {key: var.get() for key, var in self.filters.items()}
        for name in maps:
            values[name] = maps[name].get(values[name])
        try:
            rows = self.service.movements(self.account(), **values, sort=self.sort,
                                          descending=self.descending)
        except ValueError as error:
            messagebox.showerror("Filtri non validi", str(error), parent=self)
            return
        selected = self.table.selection()
        self.table.delete(*self.table.get_children())
        self.rows = {str(row["id"]): dict(row) for row in rows}
        for iid, row in self.rows.items():
            when = row["occurred_at"]
            try:
                when = datetime.fromisoformat(when).strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
            state = row["classification_status"] or "in_attesa"
            self.table.insert("", "end", iid=iid, values=(
                when, row["account"], row["description"], money(row["amount"], row["currency"]),
                money(row["fee"], row["currency"]), row["currency"], row["kind"],
                STATUSES.get(state, state), row["supplier"] or "", row["category"] or "",
                row["ledger_code"] if row["ledger_code"] is not None else "Non assegnato",
                row["subcategory"] or "Non ripartito",
            ), tags=(state,))
        self.table.selection_set([iid for iid in selected if iid in self.rows])
        self.count.configure(text=f"{len(rows)} movimenti")
        self.show_detail()

    def show_detail(self, event=None):
        selected = self.table.selection()
        text = "Seleziona un movimento per visualizzare i dettagli."
        if len(selected) == 1:
            row = self.rows[selected[0]]
            details = (
                ("Identificativo", row["id"]), ("Conto bancario", row["account"]),
                ("Conto contabile",row["ledger_code"] if row["ledger_code"] is not None else "Non assegnato"),
                ("Sottovoce",row["subcategory"] or "Non ripartito"),
                ("Data e ora", row["occurred_at"]), ("Descrizione", row["description"]),
                ("Importo", money(row["amount"],row["currency"])),
                ("Commissione", money(row["fee"],row["currency"])),
                ("Stato", STATUSES.get(row["classification_status"],row["classification_status"])),
                ("Fornitore", row["supplier"] or ""), ("Categoria", row["category"] or ""),
                ("Note", row.get("notes", "")), ("Natura contabile", row.get("accounting_nature", "")),
                ("Lotto", row["importation_id"]),
            )
            text = "\n".join(f"{label}: {value}" for label, value in details)
            if row["ledger_account_id"] is None and row["proposed_ledger_code"]:
                text += "\nConto contabile proposto dalla sottovoce: " + row["proposed_ledger_code"]
            choices = self.service.ledger.candidates(row["description"],row["supplier_id"])
            if row["ledger_account_id"] is None and choices:
                candidates = [r["code"] for r in self.service.ledger.accounts() if r["id"] in choices]
                text += "\nConti contabili candidati (scelta richiesta): " + ", ".join(candidates)
            if row["subcategory_id"] is None:
                from services.subcategories import candidates as subcategory_candidates
                choices = subcategory_candidates(self.service.store,row["description"],row["supplier_id"])
                if choices:
                    available = self.service.store.db.execute("SELECT id,name FROM subcategories WHERE archived=0").fetchall()
                    text += "\nSottovoci candidate (scelta richiesta): " + ", ".join(r["name"] for r in available if r["id"] in choices)
            text += "\nDati bancari originali\n" + json.dumps(
                json.loads(row["source_json"]), ensure_ascii=False, indent=2)
        elif selected:
            text = f"{len(selected)} movimenti selezionati"
        self.detail.configure(state="normal")
        self.detail.delete("1.0", "end")
        self.detail.insert("1.0", text)
        self.detail.configure(state="disabled")
