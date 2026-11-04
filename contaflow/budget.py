import tkinter as tk
from tkinter import ttk, messagebox

from services.register import money


class BudgetPanel(ttk.Frame):
    def __init__(self, parent, service):
        super().__init__(parent, padding=12)
        self.service = service
        self.year, self.month = tk.StringVar(value="2026"), tk.StringVar(value="1")
        self.category, self.currency = tk.StringVar(), tk.StringVar(value="EUR")
        self.amount = tk.StringVar(value="0,00")
        form = ttk.Frame(self)
        form.pack(fill="x")
        for column, (label, var, width) in enumerate((
            ("Anno", self.year, 6), ("Mese", self.month, 4), ("Budget", self.amount, 15),
        )):
            ttk.Label(form, text=label).grid(row=0, column=column, sticky="w")
            ttk.Entry(form, textvariable=var, width=width).grid(row=1, column=column, padx=(0,8))
        ttk.Label(form, text="Categoria").grid(row=0, column=3, sticky="w")
        self.category_box = ttk.Combobox(form, textvariable=self.category, state="readonly", width=35)
        self.category_box.grid(row=1, column=3)
        ttk.Label(form, text="Valuta").grid(row=0, column=4, sticky="w")
        ttk.Combobox(form, textvariable=self.currency, values=("EUR","CHF"), state="readonly", width=6).grid(row=1, column=4)
        ttk.Button(form, text="Salva budget", command=self.save).grid(row=1, column=5, padx=8)
        ttk.Button(form, text="Mostra periodo", command=self.refresh).grid(row=1, column=6)
        ttk.Label(self, text="Tutti i conti · Consuntivo per categoria · Valute separate · Scostamento = consuntivo − budget",
                  wraplength=950).pack(fill="x", pady=10)
        area = ttk.Frame(self)
        area.pack(fill="both", expand=True)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(area, columns=("category","currency","planned","actual","difference"),
                                  show="headings", height=15)
        for key, label in (("category","Categoria"), ("currency","Valuta"), ("planned","Budget"),
                           ("actual","Consuntivo"), ("difference","Scostamento")):
            self.table.heading(key, text=label)
            self.table.column(key, width=250 if key=="category" else 145,
                              anchor="w" if key=="category" else "e", stretch=False)
        self.table.grid(row=0, column=0, sticky="nsew")
        for axis, orient, row, column, sticky in (
            ("y","vertical",0,1,"ns"), ("x","horizontal",1,0,"ew"),
        ):
            bar = ttk.Scrollbar(area, orient=orient, command=getattr(self.table,axis+"view"))
            bar.grid(row=row, column=column, sticky=sticky)
            self.table.configure(**{axis+"scrollcommand":bar.set})
        self.totals = ttk.Label(self, wraplength=1000)
        self.totals.pack(fill="x", pady=10)
        self.table.bind("<<TreeviewSelect>>", self.select)
        self.rows = {}

    def refresh(self):
        try:
            year, month = int(self.year.get()), int(self.month.get())
            rows, totals = self.service.budget_report(year, month)
        except ValueError as error:
            messagebox.showerror("Periodo non valido", str(error), parent=self)
            return
        categories = self.service.categories(include_archived=True)
        self.categories = {f"{r['id']} · {r['name']}": r["id"] for r in categories if r["category_type"] != "trasferimento"}
        self.category_box.configure(values=list(self.categories))
        self.table.delete(*self.table.get_children())
        self.rows = {}
        for index, row in enumerate(rows):
            iid = str(index)
            self.rows[iid] = row
            self.table.insert("", "end", iid=iid, values=(
                row["category"], row["currency"], money(row["planned"],row["currency"]),
                money(row["actual"],row["currency"]), money(row["difference"],row["currency"]),
            ))
        self.totals.configure(text="\n".join(
            f"{currency} — Entrate {money(total['income'],currency)} / budget {money(total['planned_income'],currency)} · "
            f"Uscite {money(total['expenses'],currency)} / budget {money(total['planned_expenses'],currency)} · "
            f"Commissioni {money(total['fees'],currency)} · Senza categoria (netto) {money(total['unclassified'],currency)}"
            for currency, total in sorted(totals.items())
        ) or "Nessun budget o movimento nel periodo")

    def select(self, event=None):
        if not self.table.selection():
            return
        row = self.rows[self.table.selection()[0]]
        self.category.set(next(label for label,value in self.categories.items() if value==row["category_id"]))
        self.currency.set(row["currency"])
        self.amount.set(str(row["planned"]).replace(".",","))

    def save(self):
        try:
            if self.category.get() not in self.categories:
                raise ValueError("Scegli una categoria")
            self.service.save_budget(int(self.year.get()), int(self.month.get()),
                                     self.categories[self.category.get()], self.currency.get(), self.amount.get())
            self.refresh()
        except Exception as error:
            messagebox.showerror("Budget non salvato", str(error), parent=self)
