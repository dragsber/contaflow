import csv, os, sqlite3, hashlib, json
from pathlib import Path
from datetime import datetime

DEFAULT_ACCOUNTS = [('Revolut EUR','EUR'),('Revolut CHF','CHF'),('BPER EUR','EUR'),('Cassa contanti','EUR')]

def data_path():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ContaFlow'
    root.mkdir(parents=True, exist_ok=True)
    return root / 'contaflow.sqlite3'

class Store:
    def __init__(self, path=None):
        self.path = str(path or data_path())
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,name TEXT UNIQUE,currency TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS merchants(id INTEGER PRIMARY KEY,name TEXT UNIQUE,category_id INTEGER REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, account_id INTEGER REFERENCES accounts(id), occurred_at TEXT NOT NULL, description TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, fee REAL NOT NULL DEFAULT 0, kind TEXT NOT NULL, status TEXT NOT NULL, category_id INTEGER REFERENCES categories(id), source_json TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,transaction_id INTEGER,field TEXT,old_value TEXT,new_value TEXT,changed_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')
        self.db.executemany('INSERT OR IGNORE INTO accounts(name,currency) VALUES(?,?)', DEFAULT_ACCOUNTS)
        self.db.commit()
    def import_revolut(self, file, account='Revolut EUR'):
        count=skipped=0
        aid=self.db.execute('SELECT id FROM accounts WHERE name=?',(account,)).fetchone()[0]
        with open(file,encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            required={'Tipo','Data di inizio','Descrizione','Importo','Valuta','State'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames): raise ValueError('Schema CSV Revolut non riconosciuto')
            with self.db:
                for r in reader:
                    if r.get('State','').upper()!='COMPLETATO': skipped+=1; continue
                    when=r.get('Data di completamento') or r.get('Data di inizio')
                    amount=float(r['Importo']); fee=float(r.get('Costo') or 0); currency=r['Valuta'].upper()
                    raw=json.dumps(r,ensure_ascii=False,sort_keys=True)
                    fp=hashlib.sha256((account+'|'+when+'|'+r['Tipo']+'|'+r['Descrizione']+'|'+str(amount)+'|'+currency+'|'+str(fee)).encode()).hexdigest()
                    cur=self.db.execute('INSERT OR IGNORE INTO transactions(fingerprint,account_id,occurred_at,description,amount,currency,fee,kind,status,source_json) VALUES(?,?,?,?,?,?,?,?,?,?)',(fp,aid,when,r['Descrizione'],amount,currency,fee,r['Tipo'],'COMPLETATO',raw))
                    if cur.rowcount: count+=1
                    else: skipped+=1
        return count,skipped
    def summary(self):
        return self.db.execute('SELECT a.name,a.currency,COALESCE(SUM(t.amount-t.fee),0) balance,COALESCE(SUM(CASE WHEN t.amount>0 THEN t.amount ELSE 0 END),0) income,COALESCE(SUM(CASE WHEN t.amount<0 THEN t.amount ELSE 0 END),0) expenses FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id AND t.status="COMPLETATO" GROUP BY a.id ORDER BY a.id').fetchall()
    def recent(self): return self.db.execute('SELECT occurred_at,description,amount,currency,fee,kind FROM transactions ORDER BY id DESC LIMIT 100').fetchall()
