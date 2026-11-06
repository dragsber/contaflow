"""ContaFlow UI-1: solo prototipo, mai un database personale.

Avvio: python -m prototypes.ui.run --tema nativo|ttkbootstrap|sv-ttk
"""

import argparse
from datetime import date
from decimal import Decimal
import tkinter as tk
from tkinter import ttk, messagebox

from prototypes.ui.presentation import (
    PERIODS, STATES, date_it, filter_rows, label_for_balance,
    money, period_bounds, shown_count,
)
from prototypes.ui.sample_data import synthetic_snapshot

PALETTE = {
    "bg": "#F5F7FB", "surface": "#FFFFFF", "ink": "#142038",
    "muted": "#66758B", "accent": "#245ADE",
}
NAVIGATION = (
    ("Panoramica", "overview"), ("Movimenti", "movements"),
    ("Importazioni", "placeholder"), ("Budget e report", "placeholder"),
    ("Organizza", "placeholder"),
)


def apply_theme(root, theme):
    """Stessi widget e stesso layout per ogni tema."""
    if theme == "ttkbootstrap":
        try:
            import ttkbootstrap
        except ImportError as exc:
            raise RuntimeError("ttkbootstrap non installato nel venv del prototipo") from exc
        ttkbootstrap.Style(theme="flatly")
    elif theme == "sv-ttk":
        try:
            import sv_ttk
        except ImportError as exc:
            raise RuntimeError("sv-ttk non installato nel venv del prototipo") from exc
        sv_ttk.set_theme("light")
    elif theme == "nativo":
        ttk.Style(root).theme_use("clam")
    else:
        raise ValueError("Tema non disponibile")

    style = ttk.Style(root)
    style.configure("Surface.TFrame", background=PALETTE["surface"])
    style.configure("Sidebar.TFrame", background=PALETTE["surface"])
    style.configure("Content.TFrame", background=PALETTE["bg"])
    style.configure("Title.TLabel", background=PALETTE["bg"], foreground=PALETTE["ink"], font=("Segoe UI", 20, "bold"))
    style.configure("Subtitle.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=("Segoe UI", 10))
    style.configure("Section.TLabel", background=PALETTE["bg"], foreground=PALETTE["ink"], font=("Segoe UI", 11, "bold"))
    style.configure("Body.TLabel", background=PALETTE["surface"], foreground=PALETTE["ink"], font=("Segoe UI", 10))
    style.configure("Muted.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
    style.configure("Amount.TLabel", background=PALETTE["surface"], foreground=PALETTE["ink"], font=("Segoe UI", 17, "bold"))
    style.configure("Brand.TLabel", background=PALETTE["surface"], foreground=PALETTE["ink"], font=("Segoe UI", 18, "bold"))
    style.configure("SideCaption.TLabel", background=PALETTE["surface"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
    style.configure("Nav.TButton", font=("Segoe UI", 10), padding=(12, 11), anchor="w")
    style.configure("NavActive.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 11),
                    anchor="w", background="#E8EFFC", foreground=PALETTE["accent"])
    style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(12, 10))
    style.configure("Secondary.TButton", font=("Segoe UI", 10), padding=(12, 9))
    style.configure("Info.TLabel", background=PALETTE["bg"], foreground=PALETTE["muted"], font=("Segoe UI", 9))
    style.configure("Data.Treeview", rowheight=34, font=("Segoe UI", 9))
    style.configure("Data.Treeview.Heading", font=("Segoe UI", 9, "bold"))
    style.map("Data.Treeview", background=[("selected", "#E2ECFD")], foreground=[("selected", PALETTE["ink"])])
    return style


class UI1(tk.Tk):
    def __init__(self, snapshot, theme="nativo"):
        super().__init__()
        self.title(f"ContaFlow · UI-1 · {theme} · SOLO DATI SINTETICI")
        self.geometry("1120x760")
        self.minsize(900, 620)
        self.snapshot = snapshot
        apply_theme(self, theme)
        self.active = None
        self.rows = {}
        self.buttons = {}
        self.account_names = ["Tutti i conti"] + [row["name"] for row in snapshot.accounts]
        self.account_var = tk.StringVar(value="Tutti i conti")
        self.period_var = tk.StringVar(value="Tutti i movimenti")
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Tutti gli stati")
        self.filters_expanded = False
        self._build()
        self.show_screen("overview")
        self.bind_all("<Control-f>", self.focus_search)
        self.bind_all("<Escape>", self.clear_selection)

    def _build(self):
        self.configure(background=PALETTE["bg"])
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)
        sidebar = ttk.Frame(self, style="Sidebar.TFrame", width=178, padding=(15, 21))
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.columnconfigure(0, weight=1)
        ttk.Label(sidebar, text="ContaFlow", style="Brand.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Label(sidebar, text="PROTOTIPO UI-1", style="SideCaption.TLabel").grid(row=1, column=0, sticky="w", pady=(0, 26))
        for index, (label, route) in enumerate(NAVIGATION, 2):
            button = ttk.Button(sidebar, text=label, style="Nav.TButton",
                                command=lambda r=route, title=label: self.show_screen(r, title))
            button.grid(row=index, column=0, sticky="ew", pady=3)
            if route != "placeholder":
                self.buttons[route] = button
        sidebar.rowconfigure(8, weight=1)
        ttk.Label(sidebar, text="Solo dati dimostrativi\nNessun archivio personale",
                  style="SideCaption.TLabel", justify="left").grid(row=9, column=0, sticky="sw", pady=(18, 0))

        shell = ttk.Frame(self, style="Content.TFrame", padding=(22, 20, 22, 16))
        shell.grid(row=0, column=1, sticky="nsew")
        shell.columnconfigure(0, weight=1)
        shell.rowconfigure(1, weight=1)
        top = ttk.Frame(shell, style="Content.TFrame")
        top.grid(row=0, column=0, sticky="ew", pady=(0, 15))
        top.columnconfigure(0, weight=1)
        ttk.Label(top, text="Controllo delle finanze, senza complicazioni",
                  style="Subtitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(top, text="DEMO • NESSUNA SCRITTURA",
                  style="Info.TLabel").grid(row=0, column=1, sticky="e")

        self.container = ttk.Frame(shell, style="Content.TFrame")
        self.container.grid(row=1, column=0, sticky="nsew")
        self.container.columnconfigure(0, weight=1)
        self.container.rowconfigure(0, weight=1)
        self.overview = ttk.Frame(self.container, style="Content.TFrame")
        self.register = ttk.Frame(self.container, style="Content.TFrame")
        self._overview_widgets()
        self._register_widgets()

    @staticmethod
    def _heading(parent, name, subtitle):
        ttk.Label(parent, text=name, style="Title.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(parent, text=subtitle, style="Subtitle.TLabel").grid(row=1, column=0, sticky="w", pady=(4, 14))

    def _overview_widgets(self):
        page = self.overview
        page.columnconfigure(0, weight=1)
        self._heading(page, "Panoramica", "Conti e movimenti • Importi sintetici")
        toolbar = ttk.Frame(page, style="Content.TFrame")
        toolbar.grid(row=2, column=0, sticky="ew", pady=(0, 16))
        ttk.Label(toolbar, text="Conto", style="Subtitle.TLabel").pack(side="left", padx=(0, 8))
        ttk.Combobox(toolbar, textvariable=self.account_var,
                     values=self.account_names, state="readonly", width=21).pack(side="left", padx=(0, 18))
        ttk.Label(toolbar, text="Periodo attività", style="Subtitle.TLabel").pack(side="left", padx=(0, 8))
        ttk.Combobox(toolbar, textvariable=self.period_var, values=PERIODS,
                     state="readonly", width=19).pack(side="left")
        self.account_var.trace_add("write", lambda *_: self.refresh())
        self.period_var.trace_add("write", lambda *_: self.refresh())
        ttk.Label(page, text="SALDI E CONTI", style="Section.TLabel").grid(row=3, column=0, sticky="w", pady=(0, 10))
        self.card_area = ttk.Frame(page, style="Content.TFrame")
        self.card_area.grid(row=4, column=0, sticky="ew")
        self.card_area.columnconfigure((0, 1), weight=1, uniform="card")
        self.activity = ttk.Label(page, style="Subtitle.TLabel")
        self.activity.grid(row=5, column=0, sticky="w", pady=(18, 18))
        actions = ttk.Frame(page, style="Content.TFrame")
        actions.grid(row=6, column=0, sticky="w")
        ttk.Button(actions, text="Importa estratto", style="Primary.TButton",
                   command=lambda: self.placeholder("Importazioni")).pack(side="left", padx=(0, 10))
        ttk.Button(actions, text="Esamina movimenti", style="Secondary.TButton",
                   command=lambda: self.show_screen("movements")).pack(side="left")
        ttk.Label(page, text="Il periodo filtra l'attività, non modifica il saldo storico.",
                  style="Info.TLabel").grid(row=7, column=0, sticky="w", pady=(21, 0))

    def _card(self, parent, index, account, summary):
        card = ttk.Frame(parent, style="Surface.TFrame", padding=(15, 15))
        card.grid(row=index // 2, column=index % 2, sticky="nsew",
                  padx=(0, 10) if index % 2 == 0 else (0, 0), pady=(0, 10))
        label, value, status = label_for_balance(summary, self.snapshot.reconciliations.get(summary["id"]))
        ttk.Label(card, text=f"{account['name']}  •  {account['currency']}", style="Body.TLabel").pack(anchor="w")
        ttk.Label(card, text=label, style="Muted.TLabel").pack(anchor="w", pady=(10, 3))
        ttk.Label(card, text=money(value, account["currency"]), style="Amount.TLabel").pack(anchor="w")
        ttk.Label(card, text=status, style="Muted.TLabel").pack(anchor="w", pady=(8, 0))

    def _register_widgets(self):
        page = self.register
        page.columnconfigure(0, weight=1)
        page.rowconfigure(5, weight=1)
        self._heading(page, "Movimenti", "Registro sintetico • ricerca e dettagli senza cambiare dati")
        searchline = ttk.Frame(page, style="Content.TFrame")
        searchline.grid(row=2, column=0, sticky="ew", pady=(0, 8))
        searchline.columnconfigure(1, weight=1)
        ttk.Label(searchline, text="Ricerca", style="Subtitle.TLabel").grid(row=0, column=0, padx=(0, 9))
        self.search_entry = ttk.Entry(searchline, textvariable=self.search_var)
        self.search_entry.grid(row=0, column=1, sticky="ew")
        self.search_entry.bind("<KeyRelease>", lambda _: self.refresh())
        ttk.Button(searchline, text="Filtri ▾", command=self.toggle_filters).grid(row=0, column=2, padx=(8, 0))
        ttk.Button(searchline, text="Azzera filtri", command=self.reset_filters).grid(row=0, column=3, padx=(8, 0))
        self.filterrow = ttk.Frame(page, style="Content.TFrame")
        self.filterrow.grid(row=3, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(self.filterrow, text="Conto bancario", style="Subtitle.TLabel").pack(side="left")
        ttk.Combobox(self.filterrow, textvariable=self.account_var, values=self.account_names,
                     state="readonly", width=18).pack(side="left", padx=(8, 18))
        ttk.Label(self.filterrow, text="Stato", style="Subtitle.TLabel").pack(side="left")
        ttk.Combobox(self.filterrow, textvariable=self.status_var,
                     values=("Tutti gli stati", *STATES.keys()), state="readonly", width=18).pack(side="left", padx=(8, 0))
        self.status_var.trace_add("write", lambda *_: self.refresh())
        self.filterrow.grid_remove()
        counter = ttk.Frame(page, style="Content.TFrame")
        counter.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        counter.columnconfigure(1, weight=1)
        self.count_label = ttk.Label(counter, style="Info.TLabel")
        self.count_label.grid(row=0, column=0, sticky="w")
        self.bulk = ttk.Button(counter, text="Modifica multipla (demo)", state="disabled")
        self.bulk.grid(row=0, column=2, sticky="e")
        self.bulk.grid_remove()

        split = ttk.Panedwindow(page, orient="horizontal")
        split.grid(row=5, column=0, sticky="nsew")
        area = ttk.Frame(split)
        detail = ttk.Frame(split, style="Surface.TFrame", padding=(12, 14))
        split.add(area, weight=4)
        split.add(detail, weight=2)
        area.rowconfigure(0, weight=1)
        area.columnconfigure(0, weight=1)
        self.table = ttk.Treeview(
            area, columns=("date", "description", "amount", "account", "category", "status"),
            show="headings", selectmode="extended", style="Data.Treeview",
        )
        for key, heading, width, anchor in (
            ("date", "Data", 82, "w"), ("description", "Descrizione", 160, "w"),
            ("amount", "Importo/valuta", 110, "e"), ("account", "Conto bancario", 105, "w"),
            ("category", "Categoria / sottovoce", 125, "w"), ("status", "Stato", 118, "w"),
        ):
            self.table.heading(key, text=heading)
            self.table.column(key, width=width, minwidth=72, anchor=anchor, stretch=False)
        self.table.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(area, orient="vertical", command=self.table.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar = ttk.Scrollbar(area, orient="horizontal", command=self.table.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        self.table.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.table.bind("<<TreeviewSelect>>", self.select_row)
        self.table.tag_configure("classificato", foreground="#1D5D45")
        self.table.tag_configure("in_attesa", foreground="#844C09")
        self.table.tag_configure("proposto", foreground="#765D19")
        ttk.Label(detail, text="Dettaglio movimento", style="Body.TLabel").pack(anchor="w", pady=(0, 14))
        self.detail_title = ttk.Label(detail, text="Seleziona un movimento", style="Body.TLabel", wraplength=165)
        self.detail_title.pack(anchor="w", pady=(0, 8))
        self.detail_content = tk.StringVar(value="Qui vedrai fornitore, commissione e conto contabile.")
        ttk.Label(detail, textvariable=self.detail_content, style="Muted.TLabel",
                  justify="left", wraplength=165).pack(anchor="w", fill="x")
        ttk.Label(page, text="Solo anteprima: nessun comando può modificare l'archivio.",
                  style="Info.TLabel").grid(row=6, column=0, sticky="w", pady=(10, 0))

    def show_screen(self, route, title=""):
        if route == "placeholder":
            self.placeholder(title)
            return
        self.overview.grid_remove()
        self.register.grid_remove()
        (self.overview if route == "overview" else self.register).grid(row=0, column=0, sticky="nsew")
        self.active = route
        for name, button in self.buttons.items():
            button.configure(style="NavActive.TButton" if name == route else "Nav.TButton")
        self.refresh()

    def placeholder(self, title):
        messagebox.showinfo(title, f"{title}: non incluso nel prototipo UI-1.", parent=self)

    def toggle_filters(self):
        self.filters_expanded = not self.filters_expanded
        if self.filters_expanded:
            self.filterrow.grid()
        else:
            self.filterrow.grid_remove()

    def reset_filters(self):
        self.search_var.set("")
        self.status_var.set("Tutti gli stati")
        self.account_var.set("Tutti i conti")
        self.period_var.set("Tutti i movimenti")
        self.refresh()

    def focus_search(self, event=None):
        self.show_screen("movements")
        self.search_entry.focus_set()
        return "break"

    def clear_selection(self, event=None):
        self.table.selection_remove(*self.table.selection())

    def selected_rows(self):
        start, end = period_bounds(self.period_var.get(), today=date(2026, 11, 6))
        return filter_rows(self.snapshot.movements, search=self.search_var.get(), account=self.account_var.get(),
                           status=self.status_var.get(), start=start, end=end)

    def refresh(self):
        selected = self.selected_rows()
        for child in self.card_area.winfo_children():
            child.destroy()
        summaries = {row["id"]: row for row in self.snapshot.summaries}
        for n, account in enumerate(self.snapshot.accounts):
            if self.account_var.get() in ("Tutti i conti", account["name"]):
                self._card(self.card_area, n, account, summaries[account["id"]])
        review = sum(row["classification_status"] in ("proposto", "in_attesa") for row in selected)
        amount_by_currency = {}
        for row in selected:
            code = row["currency"]
            amount_by_currency[code] = amount_by_currency.get(code, Decimal(0)) + Decimal(str(row["amount"])) - Decimal(str(row["fee"]))
        totals = "   ·   ".join(
            f"Variazione nel periodo {money(amount, code)}" for code, amount in sorted(amount_by_currency.items())
        )
        self.activity.configure(text=f"{len(selected)} movimenti · {review} da rivedere\n{totals or 'Nessuna attività nel periodo'}")
        self.count_label.configure(text=shown_count(selected, self.snapshot.movements))
        selected_ids = set(self.table.selection())
        self.table.delete(*self.table.get_children())
        self.rows = {str(row["id"]): row for row in selected}
        for row in selected:
            category = row["category"] or "Da classificare"
            if row["subcategory"]:
                category += " / " + row["subcategory"]
            self.table.insert(
                "", "end", iid=str(row["id"]),
                values=(date_it(row["occurred_at"]), row["description"], money(row["amount"], row["currency"]),
                        row["account"], category, STATES.get(row["classification_status"], "In attesa")),
                tags=(row["classification_status"],),
            )
        for identifier in selected_ids.intersection(self.rows):
            self.table.selection_add(identifier)
        self.select_row()

    def select_row(self, event=None):
        selected = self.table.selection()
        if len(selected) > 1:
            self.bulk.grid()
        else:
            self.bulk.grid_remove()
        if not selected:
            self.detail_title.configure(text="Seleziona un movimento")
            self.detail_content.set("Qui vedrai fornitore, commissione e conto contabile.")
            return
        row = self.rows.get(selected[0])
        if row is None:
            return
        self.detail_title.configure(text=row["description"])
        self.detail_content.set("\n".join((
            f"Data: {date_it(row['occurred_at'])}",
            f"Importo: {money(row['amount'], row['currency'])}",
            f"Conto: {row['account']}",
            f"Stato: {STATES.get(row['classification_status'], 'In attesa')}",
            f"Fornitore: {row['supplier'] or 'Non assegnato'}",
            f"Categoria: {row['category'] or 'Non assegnata'}",
            f"Sottovoce: {row['subcategory'] or 'Non assegnata'}",
            f"Commissione: {money(row['fee'], row['currency'])}",
            f"Conto contabile: {row['ledger_code'] or 'Non assegnato'}",
        )))


def main(argv=None):
    parser = argparse.ArgumentParser(description="ContaFlow UI-1, prototipo sintetico indipendente")
    parser.add_argument("--tema", choices=("nativo", "sv-ttk", "ttkbootstrap"), default="nativo")
    args = parser.parse_args(argv)
    snapshot = synthetic_snapshot()  # Mai FinanceService() senza un archivio sintetico.
    try:
        app = UI1(snapshot, args.tema)
    except (ImportError, RuntimeError) as exc:
        parser.error(str(exc))
    app.mainloop()


if __name__ == "__main__":
    main()
