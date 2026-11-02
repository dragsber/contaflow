import csv
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from .store import Store


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('ContaFlow')
        self.geometry('1080x700')
        self.store = Store()

        bar = ttk.Frame(self, padding=10)
        bar.pack(fill='x')
        ttk.Label(bar, text='ContaFlow · Finanza personale',
                  font=('Segoe UI', 18, 'bold')).pack(side='left')
        self.account_var = tk.StringVar(value='Revolut EUR')
        accounts = self.store.accounts()
        self.account_box = ttk.Combobox(
            bar, textvariable=self.account_var, state='readonly', width=20,
            values=[row['name'] for row in accounts])
        self.account_box.pack(side='right', padx=8)
        self.account_box.bind('<<ComboboxSelected>>',
                              lambda event: self.refresh())
        ttk.Button(bar, text='Importa CSV Revolut',
                   command=self.import_csv).pack(side='right')

        self.account_heading = ttk.Label(self, padding=(12, 5),
                                         font=('Segoe UI', 12, 'bold'))
        self.account_heading.pack(anchor='w')
        self.cards = ttk.Frame(self, padding=10)
        self.cards.pack(fill='x')

        ttk.Label(self, text='Movimenti del conto selezionato',
                  font=('Segoe UI', 13, 'bold')).pack(anchor='w', padx=12)
        columns = ('date', 'description', 'amount', 'fee', 'currency',
                   'kind', 'classification')
        self.table = ttk.Treeview(self, columns=columns, show='headings')
        headings = [('date', 'Data', 155, 'w'),
                    ('description', 'Descrizione', 360, 'w'),
                    ('amount', 'Importo', 115, 'e'),
                    ('fee', 'Commissione', 105, 'e'),
                    ('currency', 'Valuta', 75, 'center'),
                    ('kind', 'Tipo', 130, 'w'),
                    ('classification', 'Classificazione', 135, 'w')]
        for key, title, width, anchor in headings:
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor=anchor)
        self.table.tag_configure('pending', foreground='#9a6700')
        self.table.pack(fill='both', expand=True, padx=12, pady=8)

        ttk.Label(self, text='Anomalie riconciliazione CSV',
                  font=('Segoe UI', 12, 'bold')).pack(anchor='w', padx=12)
        self.anomalies = ttk.Treeview(
            self, columns=('row', 'currency', 'expected', 'actual'),
            show='headings', height=4)
        for key, title, width in [('row', 'Riga CSV', 100),
                                  ('currency', 'Valuta', 100),
                                  ('expected', 'Variazione attesa', 200),
                                  ('actual', 'Variazione rilevata', 200)]:
            self.anomalies.heading(key, text=title)
            self.anomalies.column(key, width=width)
        self.anomalies.pack(fill='x', padx=12, pady=(4, 10))
        self.refresh()

    def refresh(self):
        account = self.account_var.get()
        rows = self.store.summary(account)
        for child in self.cards.winfo_children():
            child.destroy()
        if rows:
            row = rows[0]
            self.account_heading.config(
                text=f"{row['name']} · {row['currency']} · "
                     f"Saldo dei movimenti importati: "
                     f"{row['balance']:.2f} {row['currency']} · "
                     "Saldo iniziale non confermato")
            ttk.Label(
                self.cards,
                text=f"Entrate {row['income']:.2f} {row['currency']}   "
                     f"Uscite {row['expenses']:.2f} {row['currency']}",
                padding=10, relief='groove').pack(side='left')
        self.table.delete(*self.table.get_children())
        for row in self.store.recent(account):
            self.table.insert(
                '', 'end',
                values=(row['occurred_at'], row['description'],
                        f"{row['amount']:+.2f}", f"{row['fee']:.2f}",
                        row['currency'], row['kind'], 'In attesa'),
                tags=('pending',))
    
    def import_csv(self):
        path = filedialog.askopenfilename(filetypes=[('CSV Revolut', '*.csv')])
        if not path:
            return
        try:
            with open(path, encoding='utf-8-sig', newline='') as handle:
                reader = csv.DictReader(handle)
                if not reader.fieldnames or 'Valuta' not in reader.fieldnames:
                    raise ValueError('Il CSV non contiene la colonna Valuta')
                currencies = {row['Valuta'].strip().upper()
                              for row in reader if row.get('State', '').strip().upper()
                              == 'COMPLETATO'}
            compatible = [row for row in self.store.accounts()
                          if row['provider'] == 'REVOLUT'
                          and row['currency'].upper() in currencies]
            names = [row['name'] for row in compatible]
            if not names:
                raise ValueError('Nessun conto Revolut compatibile con la valuta del CSV')
            if self.account_var.get() not in names:
                self.account_var.set(names[0])
            self.account_box.configure(values=names)
            result = self.store.import_revolut_detailed(path, self.account_var.get())
            anomalies = self.store.reconcile_revolut_csv(path)
            self.anomalies.delete(*self.anomalies.get_children())
            for anomaly in anomalies:
                self.anomalies.insert(
                    '', 'end',
                    values=(anomaly['row'], anomaly['currency'],
                            anomaly['expected_delta'], anomaly['actual_delta']))
            self.refresh()
            messagebox.showinfo(
                'Esito importazione',
                f"Conto: {self.account_var.get()}\n"
                f"Valuta: {', '.join(sorted(currencies))}\n"
                f"Importati: {result['imported']}\n"
                f"Duplicati saltati: {result['duplicates']}\n"
                f"Escluse (non completate): {result['excluded']}\n"
                f"Anomalie di riconciliazione: {len(anomalies)}\n"
                "Errori: 0")
        except Exception as error:
            messagebox.showerror('Importazione non completata', str(error))


def main():
    App().mainloop()
