import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .store import Store

class App(tk.Tk):
 def __init__(self):
  super().__init__(); self.title('ContaFlow'); self.geometry('1000x650'); self.store=Store()
  bar=ttk.Frame(self,padding=10);bar.pack(fill='x');ttk.Label(bar,text='ContaFlow · Finanza personale',font=('Segoe UI',18,'bold')).pack(side='left');ttk.Button(bar,text='Importa CSV Revolut',command=self.import_csv).pack(side='right')
  self.cards=ttk.Frame(self,padding=10);self.cards.pack(fill='x')
  ttk.Label(self,text='Movimenti recenti',font=('Segoe UI',13,'bold')).pack(anchor='w',padx=12)
  self.table=ttk.Treeview(self,columns=('date','description','amount','currency','type'),show='headings');
  for c,w in [('date',160),('description',450),('amount',120),('currency',90),('type',150)]: self.table.heading(c,text=c.capitalize());self.table.column(c,width=w)
  self.table.pack(fill='both',expand=True,padx=12,pady=8);self.refresh()
 def refresh(self):
  for w in self.cards.winfo_children(): w.destroy()
  for row in self.store.summary():
   ttk.Label(self.cards,text=f"{row['name']}  ·  saldo movimenti {row['balance']:.2f} {row['currency']}\nEntrate {row['income']:.2f}  |  Uscite {row['expenses']:.2f}",padding=12,relief='groove').pack(side='left',padx=4)
  self.table.delete(*self.table.get_children())
  for r in self.store.recent(): self.table.insert('','end',values=(r['occurred_at'],r['description'],f"{r['amount']-r['fee']:.2f}",r['currency'],r['kind']))
 def import_csv(self):
  p=filedialog.askopenfilename(filetypes=[('CSV','*.csv')]);
  if not p:return
  try:
   n,s=self.store.import_revolut(p);self.refresh();messagebox.showinfo('Importazione',f'Importati {n}; duplicati o non completati saltati: {s}')
  except Exception as e: messagebox.showerror('Errore importazione',str(e))
def main(): App().mainloop()
