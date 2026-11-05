import csv
import tkinter as tk
import calendar
from decimal import Decimal
from tkinter import ttk, messagebox, simpledialog, filedialog
from services import subcategories


class SubcategoryPanel(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=10)
        self.service = service
        self.db = service.store.db
        self.category = tk.StringVar()
        self.name = tk.StringVar()
        self.generic = tk.BooleanVar()
        self.ledger = tk.StringVar(value="Nessuno")
        form = ttk.Frame(self)
        form.pack(fill="x")
        ttk.Label(form,text="Categoria").pack(side="left")
        self.category_box = ttk.Combobox(form,textvariable=self.category,state="readonly",width=25)
        self.category_box.pack(side="left",padx=5)
        ttk.Entry(form,textvariable=self.name,width=25).pack(side="left")
        ttk.Checkbutton(form,text="Generica",variable=self.generic).pack(side="left")
        self.ledger_box = ttk.Combobox(form,textvariable=self.ledger,state="readonly",width=20)
        self.ledger_box.pack(side="left",padx=4)
        ttk.Button(form,text="Crea sottovoce",command=self.create).pack(side="left")
        actions = ttk.Frame(self)
        actions.pack(fill="x",pady=5)
        ttk.Button(actions,text="Imposta budget mensile",command=self.set_budget).pack(side="left",padx=5)
        ttk.Button(actions,text="Modifica",command=self.edit).pack(side="left")
        ttk.Button(actions,text="Archivia / riattiva",command=self.archive).pack(side="left")
        ttk.Button(actions,text="Associa fornitore / alias",command=self.associate).pack(side="left")
        ttk.Button(actions,text="Ripartisci budget legacy",command=self.allocate).pack(side="left",padx=5)
        self.table = ttk.Treeview(self,columns=("category","name","generic","status"),show="headings",height=10)
        for key,label in (("category","Categoria"),("name","Sottovoce"),("generic","Generica"),("status","Stato")):
            self.table.heading(key,text=label)
        self.table.pack(fill="both",expand=True,pady=8)
        ttk.Button(self,text="Confronto periodo / esporta CSV",command=self.report).pack(anchor="w")
        ttk.Button(self,text="Confronto mese / bimestre / trimestre / anno",command=self.report_preset).pack(anchor="w")

    def refresh(self):
        categories = self.service.categories(include_archived=True)
        self.categories = {f"{r['id']} · {r['name']}":r["id"] for r in categories if not r["archived"]}
        self.category_box.configure(values=list(self.categories))
        self.ledgers = {f"{r['code']} · {r['description']}":r["id"] for r in self.service.ledger.accounts() if r["origin"]=="importato"}
        self.ledger_box.configure(values=["Nessuno"]+list(self.ledgers))
        self.table.delete(*self.table.get_children())
        for row in self.db.execute(
            "SELECT s.*,c.name AS category FROM subcategories s JOIN categories c ON c.id=s.category_id ORDER BY c.name,s.name"
        ):
            self.table.insert("","end",iid=str(row["id"]),values=(row["category"],row["name"],
                              "Sì" if row["generic"] else "No","Archiviata" if row["archived"] else "Attiva"))

    def create(self):
        try:
            subcategories.create(self.db,self.categories[self.category.get()],self.name.get(),self.generic.get(),
                                 self.ledgers.get(self.ledger.get()))
            self.refresh()
        except Exception as error:
            messagebox.showerror("Sottovoce non creata",str(error),parent=self)

    def selected(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showinfo("Selezione richiesta","Seleziona una sottovoce.",parent=self)
            return None
        return int(selection[0])

    def set_budget(self):
        identifier = self.selected()
        if identifier is None:
            return
        year = simpledialog.askinteger("Budget","Anno",initialvalue=2026,parent=self)
        if year is None:
            return
        month = simpledialog.askinteger("Budget","Mese",minvalue=1,maxvalue=12,parent=self)
        if month is None:
            return
        currency = simpledialog.askstring("Budget","Valuta EUR o CHF",initialvalue="EUR",parent=self)
        if currency is None:
            return
        amount = simpledialog.askstring("Budget","Importo con segno: uscite negative, entrate positive. Zero è un budget impostato.",parent=self)
        if amount is None:
            return
        try:
            subcategories.save_budget(self.db,identifier,year,month,currency.upper(),amount)
        except Exception as error:
            messagebox.showerror("Budget non salvato",str(error),parent=self)

    def edit(self):
        identifier = self.selected()
        if identifier is None:
            return
        row = self.db.execute("SELECT name,ledger_account_id FROM subcategories WHERE id=?",(identifier,)).fetchone()
        win = tk.Toplevel(self)
        win.title("Modifica sottovoce")
        name = tk.StringVar(value=row["name"])
        ttk.Entry(win,textvariable=name,width=55).pack(padx=10,pady=8)
        choices = {f"{r['code']} · {r['description']}":r["id"] for r in self.service.ledger.accounts() if r["origin"]=="importato"}
        current = next((label for label,value in choices.items() if value==row["ledger_account_id"]),None)
        keep = "Mantieni conto attuale"
        value = tk.StringVar(value=current or (keep if row["ledger_account_id"] is not None else "Nessuno"))
        ttk.Combobox(win,textvariable=value,values=[keep,"Nessuno"]+list(choices),state="readonly",width=55).pack(padx=10)
        def save():
            try:
                ledger_id = row["ledger_account_id"] if value.get()==keep else choices.get(value.get())
                subcategories.edit(self.db,identifier,name.get(),ledger_id)
                win.destroy()
                self.refresh()
            except Exception as error:
                messagebox.showerror("Sottovoce non salvata",str(error),parent=win)
        ttk.Button(win,text="Salva",command=save).pack(pady=10)

    def archive(self):
        identifier = self.selected()
        if identifier is None or not messagebox.askyesno("Conferma","Cambiare lo stato della sottovoce?",parent=self):
            return
        row = self.db.execute("SELECT archived FROM subcategories WHERE id=?",(identifier,)).fetchone()
        subcategories.archive(self.db,identifier,not row[0])
        self.refresh()

    def associate(self):
        suppliers = self.service.ledger.suppliers()
        choices = {f"{r['id']} · {r['name']}":r["id"] for r in suppliers}
        win = tk.Toplevel(self)
        win.title("Associa sottovoci a fornitore o alias")
        supplier, alias, habitual = tk.StringVar(), tk.StringVar(value="Fornitore"), tk.StringVar(value="Nessuna")
        supplier_box = ttk.Combobox(win,textvariable=supplier,values=list(choices),state="readonly",width=55)
        supplier_box.pack(pady=5)
        alias_box = ttk.Combobox(win,textvariable=alias,state="readonly",width=55)
        alias_box.pack(pady=5)
        items = self.db.execute("SELECT id,name FROM subcategories WHERE archived=0 ORDER BY name").fetchall()
        listing = tk.Listbox(win,selectmode="multiple",exportselection=False,width=55)
        listing.pack(pady=5)
        for item in items:
            listing.insert("end",f"{item['id']} · {item['name']}")
        names = {f"{item['id']} · {item['name']}":item["id"] for item in items}
        ttk.Label(win,text="Sottovoce abituale opzionale (solo fornitore)").pack()
        ttk.Combobox(win,textvariable=habitual,values=["Nessuna"]+list(names),state="readonly").pack()
        aliases = {}
        def reload(event=None):
            nonlocal aliases
            if supplier.get() not in choices:
                return
            sid = choices[supplier.get()]
            aliases = {r["normalized_alias"]:r["id"] for r in self.service.ledger.aliases(sid)}
            alias_box.configure(values=["Fornitore"]+list(aliases))
            alias.set("Fornitore")
            listing.selection_clear(0,"end")
            existing = self.db.execute("SELECT subcategory_id,habitual FROM supplier_subcategories WHERE supplier_id=?",(sid,)).fetchall()
            for index,item in enumerate(items):
                for row in existing:
                    if row[0] == item["id"]:
                        listing.selection_set(index)
                        if row[1]:
                            habitual.set(f"{item['id']} · {item['name']}")
        def load_alias(event=None):
            listing.selection_clear(0,"end")
            if alias.get() in aliases:
                existing = {r[0] for r in self.db.execute("SELECT subcategory_id FROM alias_subcategories WHERE alias_id=?",(aliases[alias.get()],))}
            else:
                existing = {r[0] for r in self.db.execute("SELECT subcategory_id FROM supplier_subcategories WHERE supplier_id=?",(choices[supplier.get()],))}
            for index,item in enumerate(items):
                if item["id"] in existing:
                    listing.selection_set(index)
        supplier_box.bind("<<ComboboxSelected>>",reload)
        alias_box.bind("<<ComboboxSelected>>",load_alias)
        def save():
            try:
                subcategories.associate(self.db,choices[supplier.get()],[items[i]["id"] for i in listing.curselection()],
                                        names.get(habitual.get()) if alias.get()=="Fornitore" else None,aliases.get(alias.get()))
                win.destroy()
            except Exception as error:
                messagebox.showerror("Associazione non salvata",str(error),parent=win)
        ttk.Button(win,text="Salva associazioni future",command=save).pack(pady=8)

    def allocate(self):
        category_id = self.categories.get(self.category.get())
        if category_id is None:
            messagebox.showinfo("Ripartizione","Seleziona una categoria.",parent=self)
            return
        year = simpledialog.askinteger("Ripartizione","Anno",initialvalue=2026,parent=self)
        if year is None:
            return
        month = simpledialog.askinteger("Ripartizione","Mese",minvalue=1,maxvalue=12,parent=self)
        if month is None:
            return
        currency = simpledialog.askstring("Ripartizione","Valuta EUR o CHF",initialvalue="EUR",parent=self)
        if not currency:
            return
        currency = currency.upper()
        legacy = self.db.execute("SELECT amount,amount_minor FROM budgets WHERE category_id=? AND year=? AND month=? AND currency=?",
                                 (category_id,year,month,currency)).fetchone()
        if legacy is None:
            messagebox.showerror("Ripartizione","Budget legacy non presente.",parent=self)
            return
        items = self.db.execute("SELECT id,name FROM subcategories WHERE category_id=? AND archived=0 ORDER BY name",(category_id,)).fetchall()
        win = tk.Toplevel(self)
        win.title("Ripartizione budget legacy")
        total = Decimal(legacy["amount_minor"])/100 if legacy["amount_minor"] is not None else Decimal(str(legacy["amount"]))
        ttk.Label(win,text=f"Budget legacy {total:.2f} {currency}. Lascia vuote le voci non impostate.").pack()
        variables = {}
        for item in items:
            line = ttk.Frame(win)
            line.pack(fill="x")
            ttk.Label(line,text=item["name"],width=30).pack(side="left")
            variables[item["id"]] = tk.StringVar()
            ttk.Entry(line,textvariable=variables[item["id"]]).pack(side="left")
        def preview():
            values = {key:var.get() for key,var in variables.items() if var.get().strip()}
            detail = "\n".join(f"{item['name']}: {values[item['id']]}" for item in items if item["id"] in values)
            if not messagebox.askyesno("Anteprima ripartizione",detail+"\nConfermare?",parent=win):
                return
            try:
                subcategories.allocate_legacy(self.db,category_id,year,month,currency,values)
                win.destroy()
            except Exception as error:
                messagebox.showerror("Ripartizione non eseguita",str(error),parent=win)
        ttk.Button(win,text="Anteprima e conferma",command=preview).pack(pady=8)

    def report_preset(self):
        kind = simpledialog.askstring("Tipo periodo","Scrivi mese, bimestre, trimestre oppure anno",parent=self)
        if not kind:
            return
        kind = kind.strip().lower()
        widths = {"mese":1,"bimestre":2,"trimestre":3,"anno":12}
        if kind not in widths:
            messagebox.showerror("Periodo non valido","Scegli mese, bimestre, trimestre oppure anno.",parent=self)
            return
        year = simpledialog.askinteger("Periodo","Anno",minvalue=1,maxvalue=9999,initialvalue=2026,parent=self)
        if year is None:
            return
        count = 12 // widths[kind]
        index = 1 if kind=="anno" else simpledialog.askinteger(
            "Periodo",f"Numero del {kind} (da 1 a {count})",minvalue=1,maxvalue=count,parent=self)
        if index is None:
            return
        first = (index-1)*widths[kind]+1
        last = first+widths[kind]-1
        self.report(f"{year:04d}-{first:02d}-01",f"{year:04d}-{last:02d}-{calendar.monthrange(year,last)[1]:02d}")

    def report(self,start=None,end=None):
        if start is None:
            start = simpledialog.askstring("Periodo","Dal (AAAA-MM-GG)",parent=self)
            if start is None:
                return
            end = simpledialog.askstring("Periodo","Al (AAAA-MM-GG), incluso",parent=self)
            if end is None:
                return
        try:
            rows = subcategories.report(self.db,start,end)
        except Exception as error:
            messagebox.showerror("Periodo non valido",str(error),parent=self)
            return
        win = tk.Toplevel(self)
        win.title(f"Budget e consuntivo per sottovoce · {start} — {end}")
        area = ttk.Frame(win)
        area.pack(fill="both",expand=True)
        text = tk.Text(area,width=115,height=24,wrap="word")
        text.pack(side="left",fill="both",expand=True)
        scroll = ttk.Scrollbar(area,orient="vertical",command=text.yview)
        scroll.pack(side="right",fill="y")
        text.configure(yscrollcommand=scroll.set)
        text.insert("end","I subtotali sono riepilogativi: somma solo le righe dettaglio e non_ripartito, senza aggiungere i subtotali.\n\n")
        for row in rows:
            display = lambda value: str(value).replace(".",",") if value is not None else "Non impostato"
            budget = display(row["budget"])
            difference = display(row["difference"])
            rounding = (f"budget {display(row['rounding_difference'])}, consuntivo {display(row['rounding_actual'])}, "
                        f"scostamento {display(row.get('rounding_delta'))}") if row["type"]=="subtotale_categoria" else ""
            text.insert("end",f"{row['type']} · {row['category']} · {row['subcategory']} · {row['currency']}\n"
                        f"Budget {budget} · Consuntivo {display(row['actual'])} · Scostamento {difference} · "
                        f"{row.get('meaning','')} · {row.get('warning','')} · Differenza arrotondamento {rounding}\n")
        text.configure(state="disabled")
        def safe(value):
            value = str(value or "")
            return "'" + value if value.lstrip(" \t\r\n").startswith(("=","+","-","@")) else value
        def export():
            path = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")],parent=win)
            if not path:
                return
            with open(path,"w",encoding="utf-8-sig",newline="") as handle:
                writer = csv.writer(handle,delimiter=";")
                writer.writerow(("tipo riga","categoria","sottovoce","codice contabile","valuta","budget","consuntivo","scostamento","avviso","differenza da arrotondamento","nota","dal","al"))
                for row in rows:
                    number = lambda value: str(value).replace(".",",") if value is not None else "non impostato"
                    rounding = (f"budget {number(row['rounding_difference'])}; consuntivo {number(row['rounding_actual'])}; "
                                f"scostamento {number(row.get('rounding_delta'))}") if row["type"]=="subtotale_categoria" else ""
                    writer.writerow((row["type"],safe(row["category"]),safe(row["subcategory"]),safe(row["code"]),
                                     row["currency"],number(row["budget"]),number(row["actual"]),number(row["difference"]),
                                     safe((row.get("meaning","")+" "+row.get("warning","")).strip()),rounding,
                                     "Riepilogo: non sommare ai dettagli" if row["type"]=="subtotale_categoria" else "",
                                     start,end))
        ttk.Button(win,text="Esporta CSV",command=export).pack(pady=5)
