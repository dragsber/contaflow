import csv, os, sqlite3, hashlib, json
from pathlib import Path
from datetime import datetime

DEFAULT_ACCOUNTS = [('Revolut EUR','EUR','REVOLUT'),('Revolut CHF','CHF','REVOLUT'),('BPER EUR','EUR','BPER'),('Cassa contanti','EUR','CASH')]

def data_path():
    root = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ContaFlow'
    root.mkdir(parents=True, exist_ok=True)
    return root / 'contaflow.sqlite3'

class Store:
    def __init__(self, path=None):
        self.path = str(path or data_path())
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        PRAGMA foreign_keys=ON;
        CREATE TABLE IF NOT EXISTS accounts(id INTEGER PRIMARY KEY,name TEXT UNIQUE,currency TEXT NOT NULL,provider TEXT NOT NULL DEFAULT 'UNKNOWN');
        CREATE TABLE IF NOT EXISTS categories(id INTEGER PRIMARY KEY,name TEXT UNIQUE);
        CREATE TABLE IF NOT EXISTS merchants(id INTEGER PRIMARY KEY,name TEXT UNIQUE,category_id INTEGER REFERENCES categories(id));
        CREATE TABLE IF NOT EXISTS transactions(id INTEGER PRIMARY KEY, fingerprint TEXT UNIQUE, account_id INTEGER REFERENCES accounts(id), occurred_at TEXT NOT NULL, description TEXT NOT NULL, amount REAL NOT NULL, currency TEXT NOT NULL, fee REAL NOT NULL DEFAULT 0, kind TEXT NOT NULL, status TEXT NOT NULL, category_id INTEGER REFERENCES categories(id), source_json TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,transaction_id INTEGER,field TEXT,old_value TEXT,new_value TEXT,changed_at TEXT DEFAULT CURRENT_TIMESTAMP);
        """)
        columns = {row['name'] for row in self.db.execute('PRAGMA table_info(accounts)')}
        if 'provider' not in columns:
            self.db.execute("ALTER TABLE accounts ADD COLUMN provider TEXT NOT NULL DEFAULT 'UNKNOWN'")
        for name, currency, provider in DEFAULT_ACCOUNTS:
            self.db.execute('INSERT OR IGNORE INTO accounts(name,currency,provider) VALUES(?,?,?)', (name,currency,provider))
            self.db.execute('UPDATE accounts SET provider=? WHERE name=? AND provider=\'UNKNOWN\'', (provider,name))
        self.db.commit()
    def accounts(self):
        return self.db.execute('SELECT name,currency,provider FROM accounts ORDER BY id').fetchall()
    def import_revolut(self, file, account='Revolut EUR'):
        count=skipped=0
        account_row=self.db.execute('SELECT id,currency,provider FROM accounts WHERE name=?',(account,)).fetchone()
        if account_row is None:
            raise ValueError(f"Conto non configurato: {account}")
        if account_row['provider'] != 'REVOLUT':
            raise ValueError(f"Il conto {account} non è un conto Revolut")
        aid, account_currency=account_row['id'], account_row['currency'].upper()
        with open(file,encoding='utf-8-sig',newline='') as f:
            reader=csv.DictReader(f)
            required={'Tipo','Data di inizio','Descrizione','Importo','Valuta','State'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames): raise ValueError('Schema CSV Revolut non riconosciuto')
            with self.db:
                for r in reader:
                    if r.get('State','').upper()!='COMPLETATO': skipped+=1; continue
                    when=r.get('Data di completamento') or r.get('Data di inizio')
                    amount=float(r['Importo']); fee=float(r.get('Costo') or 0); currency=r['Valuta'].strip().upper()
                    if currency != account_currency:
                        raise ValueError(f"Valuta {currency} incompatibile con il conto {account} ({account_currency})")
                    raw=json.dumps(r,ensure_ascii=False,sort_keys=True)
                    fp=hashlib.sha256((account+'|'+when+'|'+r['Tipo']+'|'+r['Descrizione']+'|'+str(amount)+'|'+currency+'|'+str(fee)).encode()).hexdigest()
                    cur=self.db.execute('INSERT OR IGNORE INTO transactions(fingerprint,account_id,occurred_at,description,amount,currency,fee,kind,status,source_json) VALUES(?,?,?,?,?,?,?,?,?,?)',(fp,aid,when,r['Descrizione'],amount,currency,fee,r['Tipo'],'COMPLETATO',raw))
                    if cur.rowcount: count+=1
                    else: skipped+=1
        return count,skipped
    def summary(self, account=None):
        sql='SELECT a.name,a.currency,COALESCE(SUM(t.amount-t.fee),0) balance,COALESCE(SUM(CASE WHEN t.amount>0 THEN t.amount ELSE 0 END),0) income,COALESCE(SUM(CASE WHEN t.amount<0 THEN t.amount ELSE 0 END),0) expenses FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id AND t.status="COMPLETATO"'
        if account: return self.db.execute(sql+' WHERE a.name=? GROUP BY a.id',(account,)).fetchall()
        return self.db.execute(sql+' GROUP BY a.id ORDER BY a.id').fetchall()
    def recent(self, account=None):
        sql='SELECT occurred_at,description,amount,currency,fee,kind FROM transactions'
        if account: return self.db.execute(sql+' WHERE account_id=(SELECT id FROM accounts WHERE name=?) ORDER BY id DESC LIMIT 100',(account,)).fetchall()
        return self.db.execute(sql+' ORDER BY id DESC LIMIT 100').fetchall()

    def reconcile_revolut_csv(self, file):
        """Return CSV row numbers whose reported balance does not reconcile."""
        from decimal import Decimal, InvalidOperation

        with open(file, encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            required = {'Data di completamento', 'Importo', 'Costo', 'Valuta', 'State', 'Saldo'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError('Schema CSV Revolut incompleto per la riconciliazione')
            completed = []
            for row_number, row in enumerate(reader, start=2):
                if row['State'].strip().upper() != 'COMPLETATO':
                    continue
                if not row['Data di completamento'] or not row['Saldo']:
                    raise ValueError(f'Data o saldo mancante alla riga {row_number}')
                try:
                    amount = Decimal(row['Importo'])
                    fee = Decimal(row['Costo'] or '0')
                    balance = Decimal(row['Saldo'])
                except InvalidOperation as error:
                    raise ValueError(f'Numero non valido alla riga {row_number}') from error
                completed.append((row['Data di completamento'], row_number,
                                  row['Valuta'].strip().upper(), amount - fee, balance))

        previous_by_currency = {}
        anomalies = []
        for _, row_number, currency, movement, balance in sorted(completed):
            previous = previous_by_currency.get(currency)
            if previous is not None and balance - previous != movement:
                anomalies.append(row_number)
            previous_by_currency[currency] = balance
        return anomalies
