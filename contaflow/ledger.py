import csv
import tkinter as tk
from pathlib import Path
from tkinter import ttk, filedialog, messagebox, simpledialog

from adapters.chart import mapped_records
from services.register import money


class LedgerPanel(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=12)
        self.service = service
        self.search = tk.StringVar()
        self.archived = tk.BooleanVar()
        controls = ttk.Frame(self)
        controls.pack(fill="x")
        ttk.Label(controls,text="Cerca conto contabile").pack(side="left")
        entry = ttk.Entry(controls,textvariable=self.search)
        entry.pack(side="left",padx=5)
        entry.bind("<KeyRelease>",lambda event:self.refresh())
        ttk.Checkbutton(controls,text="Includi archiviati",variable=self.archived,command=self.refresh).pack(side="left")
        ttk.Button(controls,text="Importa piano dei conti",command=self.import_dialog).pack(side="left",padx=6)
        ttk.Button(controls,text="Descrizione / archiviazione",command=self.edit).pack(side="left")
        ttk.Button(controls,text="Associazioni fornitori e alias",command=self.associate).pack(side="left",padx=6)
        self.info = ttk.Label(self,wraplength=1000)
        self.info.pack(fill="x",pady=8)
        area = ttk.Frame(self)
        area.pack(fill="both",expand=True)
        area.rowconfigure(0,weight=1)
        area.columnconfigure(0,weight=1)
        self.table = ttk.Treeview(area,columns=("code","description","categories","origin","state"),show="headings")
        for column,label,width in (("code","Codice conto contabile",180),("description","Descrizione",470),
                                   ("categories","Categorie esplicite dal workbook",240),
                                   ("origin","Origine",100),("state","Stato",110)):
            self.table.heading(column,text=label)
            self.table.column(column,width=width,stretch=False)
        self.table.grid(row=0,column=0,sticky="nsew")
        for axis,orientation,row,column,sticky in (("y","vertical",0,1,"ns"),("x","horizontal",1,0,"ew")):
            bar = ttk.Scrollbar(area,orient=orientation,command=getattr(self.table,axis+"view"))
            bar.grid(row=row,column=column,sticky=sticky)
            self.table.configure(**{axis+"scrollcommand":bar.set})
        self.year,self.month = tk.StringVar(value="2026"),tk.StringVar(value="1")
        report_controls = ttk.Frame(self)
        report_controls.pack(fill="x",pady=8)
        for label,var in (("Anno",self.year),("Mese",self.month)):
            ttk.Label(report_controls,text=label).pack(side="left")
            ttk.Entry(report_controls,textvariable=var,width=7).pack(side="left",padx=4)
        ttk.Button(report_controls,text="Consuntivo / budget per codice",command=self.report).pack(side="left",padx=6)
        ttk.Button(report_controls,text="Confronto conti precedente",command=self.period_report).pack(side="left",padx=6)

    def refresh(self):
        self.table.delete(*self.table.get_children())
        rows = self.service.accounts(self.search.get(),self.archived.get())
        for row in rows:
            self.table.insert("","end",iid=str(row["id"]),values=(
                row["code"],row["description"],row["category_labels"] or "",row["origin"],"Archiviato" if row["archived"] else "Attivo"))
        self.info.configure(text="Archivio vuoto. Importa il piano dei conti originale con mappatura esplicita."
                            if not self.service.accounts(include_archived=True) else
                            "Conto contabile distinto dal conto bancario. Le assegnazioni non modificano lo storico automaticamente.")

    def selected(self):
        selected = self.table.selection()
        if not selected:
            messagebox.showinfo("Selezione richiesta","Seleziona un conto contabile.",parent=self)
            return None
        return int(selected[0])

    def edit(self):
        identifier = self.selected()
        if identifier is None:
            return
        row = next(r for r in self.service.accounts(include_archived=True) if r["id"]==identifier)
        description = simpledialog.askstring("Descrizione conto contabile","Descrizione",initialvalue=row["description"],parent=self)
        if description is None:
            return
        archived = messagebox.askyesnocancel("Stato conto contabile","Archiviare? Sì = archiviato, No = attivo.",parent=self)
        if archived is None:
            return
        try:
            self.service.edit(identifier,description,archived)
            self.winfo_toplevel().refresh_all()
        except Exception as error:
            messagebox.showerror("Conto non salvato",str(error),parent=self)

    def import_dialog(self):
        path = filedialog.askopenfilename(filetypes=[("Piano dei conti","*.xlsx *.csv")])
        if not path:
            return
        win = tk.Toplevel(self)
        win.title("Mappatura piano dei conti")
        variables = {}
        fields = (("sheet","Nome esatto foglio XLSX",""),("first","Prima riga dati","2"),
                  ("code","Colonna codice","A"),("description","Colonna descrizione","B"),
                  ("category","Colonna categoria (facoltativa)",""),("supplier","Colonna fornitore (facoltativa)",""))
        for number,(key,label,default) in enumerate(fields):
            ttk.Label(win,text=label).grid(row=number,column=0,sticky="w",padx=10,pady=4)
            var = tk.StringVar(value=default)
            variables[key] = var
            ttk.Entry(win,textvariable=var,width=40).grid(row=number,column=1,padx=10)
        ttk.Label(win,text="Colonne con lettere Excel. CSV con separatore ;. Formule nei campi mappati bloccate.",
                  wraplength=600).grid(row=6,column=0,columnspan=2,padx=10,pady=8)
        def preview():
            try:
                mapping = {key:variables[key].get() for key in ("code","description","category","supplier")}
                records = mapped_records(path,variables["sheet"].get(),mapping,int(variables["first"].get()))
                differences = self.service.preview(records)
                signature = self.service.signature()
            except Exception as error:
                messagebox.showerror("Importazione non pronta",str(error),parent=win)
                return
            dialog = tk.Toplevel(win)
            dialog.title("Anteprima differenze")
            text = tk.Text(dialog,width=100,height=22,wrap="word")
            text.pack(fill="both",expand=True)
            text.insert("1.0","\n".join(differences) or "Nessuna differenza nei conti contabili")
            text.configure(state="disabled")
            def confirm():
                if not messagebox.askyesno("Conferma importazione","Applicare le differenze visualizzate?",parent=dialog):
                    return
                try:
                    self.service.import_chart(records,Path(path).name,signature)
                    dialog.destroy()
                    win.destroy()
                    self.winfo_toplevel().refresh_all()
                except Exception as error:
                    messagebox.showerror("Importazione interrotta",str(error),parent=dialog)
            ttk.Button(dialog,text="Conferma importazione",command=confirm).pack(pady=8)
        ttk.Button(win,text="Valida e mostra differenze",command=preview).grid(row=7,column=1,pady=10)

    def associate(self):
        suppliers = self.service.suppliers()
        accounts = self.service.accounts()
        if not suppliers or not accounts:
            messagebox.showinfo("Associazioni","Occorrono fornitori e conti contabili importati.",parent=self)
            return
        win = tk.Toplevel(self)
        win.title("Associazioni fornitore / alias a conti contabili")
        supplier = tk.StringVar()
        supplier_map = {f"{r['id']} · {r['name']}":r["id"] for r in suppliers}
        supplier_box = ttk.Combobox(win,textvariable=supplier,values=list(supplier_map),state="readonly",width=60)
        supplier_box.pack(padx=12,pady=8)
        alias = tk.StringVar(value="Fornitore")
        alias_box = ttk.Combobox(win,textvariable=alias,state="readonly",width=60)
        alias_box.pack(padx=12)
        listing = tk.Listbox(win,selectmode="multiple",exportselection=False,width=70,height=12)
        listing.pack(padx=12,pady=8)
        for row in accounts:
            listing.insert("end",f"{row['code']} — {row['description']}")
        preferred = tk.StringVar(value="Nessuno")
        preferred_map = {r["code"]:r["id"] for r in accounts}
        ttk.Label(win,text="Conto abituale del fornitore (opzionale)").pack()
        ttk.Combobox(win,textvariable=preferred,values=["Nessuno"]+list(preferred_map),state="readonly").pack()
        aliases = {}
        def reload(event=None):
            if supplier.get() not in supplier_map:
                return
            nonlocal aliases
            aliases = {r["normalized_alias"]:r["id"] for r in self.service.aliases(supplier_map[supplier.get()])}
            alias_box.configure(values=["Fornitore"]+list(aliases))
            if alias.get() not in aliases:
                alias.set("Fornitore")
            relations = self.service.associations(supplier_map[supplier.get()],aliases.get(alias.get()))
            selected = {r[0] for r in relations}
            listing.selection_clear(0,"end")
            preferred.set("Nessuno")
            for index,row in enumerate(accounts):
                if row["id"] in selected:
                    listing.selection_set(index)
                if (row["id"],1) in relations:
                    preferred.set(row["code"])
        supplier_box.bind("<<ComboboxSelected>>",reload)
        alias_box.bind("<<ComboboxSelected>>",reload)
        def save():
            try:
                if supplier.get() not in supplier_map:
                    raise ValueError("Seleziona un fornitore")
                self.service.associate(supplier_map[supplier.get()],
                                       [accounts[i]["id"] for i in listing.curselection()],
                                       preferred_map.get(preferred.get()) if alias.get()=="Fornitore" else None,
                                       aliases.get(alias.get()))
                win.destroy()
            except Exception as error:
                messagebox.showerror("Associazione non salvata",str(error),parent=win)
        ttk.Button(win,text="Salva associazioni future",command=save).pack(pady=10)

    def save_budget(self):
        identifier = self.selected()
        if identifier is None:
            return
        currency = simpledialog.askstring("Budget per conto contabile","Valuta EUR o CHF",initialvalue="EUR",parent=self)
        if currency is None:
            return
        amount = simpledialog.askstring("Budget per conto contabile","Importo netto con segno (uscite negative)",parent=self)
        if amount is None:
            return
        try:
            self.service.save_budget(int(self.year.get()),int(self.month.get()),identifier,currency,amount)
        except Exception as error:
            messagebox.showerror("Budget non salvato",str(error),parent=self)

    def period_report(self):
        start = simpledialog.askstring("Periodo", "Dal (AAAA-MM-GG)", parent=self)
        if start is None:
            return
        end = simpledialog.askstring("Periodo", "Al (AAAA-MM-GG), incluso", parent=self)
        if end is None:
            return
        try:
            rows = self.service.period_report(start, end)
        except ValueError as error:
            messagebox.showerror("Periodo non valido", str(error), parent=self)
            return
        win = tk.Toplevel(self)
        win.title(f"Budget e consuntivo dal {start} al {end}")
        ttk.Label(win, text="Budget proporzionale ai giorni di ciascun mese · Scostamento = consuntivo − budget · Uscite negative").pack()
        area = ttk.Frame(win)
        area.pack(fill="both", expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        table = ttk.Treeview(area, columns=("code","description","currency","budget","actual","difference","fees","missing"), show="headings")
        for key,label in (("code","Conto contabile"),("description","Descrizione"),("currency","Valuta"),
                          ("budget","Budget"),("actual","Consuntivo"),("difference","Differenza"),("fees","Commissioni"),("missing","Mesi senza budget")):
            table.heading(key, text=label)
            table.column(key, width=150, stretch=False, anchor="e" if key in ("budget","actual","difference","fees") else "w")
        table.grid(row=0, column=0, sticky="nsew")
        vertical = ttk.Scrollbar(area, orient="vertical", command=table.yview)
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(area, orient="horizontal", command=table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        for row in rows:
            table.insert("", "end", values=(row["code"],row["description"],row["currency"],
                         money(row["budget"],row["currency"]),money(row["actual"],row["currency"]),
                         money(row["difference"],row["currency"]),money(row["fees"],row["currency"]),row["missing_months"]))
        def export():
            path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV","*.csv")])
            if path:
                with open(path,"w",encoding="utf-8-sig",newline="") as handle:
                    writer = csv.writer(handle, delimiter=";")
                    writer.writerow(("dal","al","conto","descrizione","valuta","budget","consuntivo","differenza","commissioni","mesi_senza_budget"))
                    for row in rows:
                        writer.writerow((start,end,row["code"],row["description"],row["currency"],
                                         row["budget"],row["actual"],row["difference"],row["fees"],row["missing_months"]))
        ttk.Button(win, text="Esporta CSV", command=export).pack(pady=8)

    def report(self):
        try:
            rows = self.service.report(int(self.year.get()),int(self.month.get()))
        except Exception as error:
            messagebox.showerror("Periodo non valido",str(error),parent=self)
            return
        win = tk.Toplevel(self)
        win.title("Budget e consuntivo per codice conto contabile")
        text = tk.Text(win,width=110,height=25,wrap="word")
        text.pack(fill="both",expand=True)
        for row in rows:
            text.insert("end",f"{row['code']} — {row['description']} · {row['currency']} · {row['categories']}\n"
                        f"Budget {money(row['budget'],row['currency'])} · Netto {money(row['actual'],row['currency'])} · "
                        f"Scostamento {money(row['actual']-row['budget'],row['currency'])} · "
                        f"Commissioni {money(row['fees'],row['currency'])}\n\n")
        text.configure(state="disabled")
        def export():
            path = filedialog.asksaveasfilename(defaultextension=".csv",filetypes=[("CSV","*.csv")])
            if path:
                with open(path,"w",encoding="utf-8-sig",newline="") as handle:
                    writer = csv.DictWriter(handle,fieldnames=("code","description","categories","currency","actual","fees","budget"),delimiter=";")
                    writer.writeheader()
                    writer.writerows(rows)
        ttk.Button(win,text="Esporta consuntivo CSV per codice",command=export).pack(pady=8)


def assign_selected(app):
    ids = [int(i) for i in app.table.selection()]
    if not ids:
        messagebox.showinfo("Conto contabile","Seleziona uno o più movimenti.",parent=app)
        return
    accounts = app.store.ledger.accounts()
    if not accounts:
        messagebox.showinfo("Conto contabile","Importa prima il piano dei conti.",parent=app)
        return
    win = tk.Toplevel(app)
    win.title("Conto contabile del movimento")
    choices = {f"{r['code']} — {r['description']}":r["id"] for r in accounts}
    var = tk.StringVar(value="Non assegnato")
    ttk.Combobox(win,textvariable=var,values=["Non assegnato"]+list(choices),state="readonly",width=80).pack(padx=12,pady=12)
    remember = tk.BooleanVar()
    ttk.Checkbutton(win,text="Memorizza come regola per futuri compatibili",variable=remember).pack(padx=12)
    def save():
        if not messagebox.askyesno("Conferma conto contabile",f"Assegnare il conto contabile a {len(ids)} movimenti?",parent=win):
            return
        try:
            app.store.ledger.assign(ids,choices.get(var.get()),remember.get())
            win.destroy()
            app.refresh_all()
        except Exception as error:
            messagebox.showerror("Conto non assegnato",str(error),parent=win)
    ttk.Button(win,text="Salva conto contabile",command=save).pack(pady=12)
