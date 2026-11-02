import csv, os, sqlite3, hashlib, json
from pathlib import Path
from datetime import datetime
from db.migrations import migrate

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
        migrate(self.db)
    @staticmethod
    def normalize_description(value):
        import re
        text=' '.join(value.upper().split())
        text=re.sub(r'^(CARD PAYMENT|PAGAMENTO CARTA|PAGAMENTO CON CARTA)\\s+', '', text)
        text=re.sub(r'\\b(?:REF|REFERENCE|ID|CARD)[:#]?\\s*[A-Z0-9-]+\\b', ' ', text)
        return ' '.join(text.split())

    def classify_description(self, description):
        key=self.normalize_description(description)
        aliases=self.db.execute(
            'SELECT sa.supplier_id,sa.confirmed,s.name,s.habitual_category_id '
            'FROM supplier_aliases sa JOIN suppliers s ON s.id=sa.supplier_id '
            'WHERE sa.normalized_alias=? AND s.archived=0',(key,)).fetchone()
        if aliases and aliases['confirmed']:
            status='classificato' if aliases['habitual_category_id'] else 'proposto'
            return {'supplier_id':aliases['supplier_id'],'category_id':aliases['habitual_category_id'],'status':status,'origin':'confermata'}
        if aliases:
            status='classificato' if aliases['habitual_category_id'] else 'proposto'
            return {'supplier_id':aliases['supplier_id'],'category_id':aliases['habitual_category_id'],'status':status,'origin':'alias' if status=='classificato' else 'proposta'}
        for rule in self.db.execute('SELECT * FROM classification_rules WHERE enabled=1'):
            if self.normalize_description(rule['exact_description'])==key:
                return {'supplier_id':rule['supplier_id'],'category_id':rule['category_id'],'status':'classificato','origin':'regola'}
        supplier=self.db.execute('SELECT id,habitual_category_id FROM suppliers WHERE UPPER(name)=? AND archived=0',(key,)).fetchone()
        if supplier:
            return {'supplier_id':supplier['id'],'category_id':supplier['habitual_category_id'],'status':'proposto','origin':'proposta'}
        return {'supplier_id':None,'category_id':None,'status':'in_attesa','origin':None}

    def confirm_supplier_alias(self, supplier_id, description, category_id=None):
        key=self.normalize_description(description)
        with self.db:
            self.db.execute('INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) VALUES(?,?,1) ON CONFLICT(normalized_alias) DO UPDATE SET supplier_id=excluded.supplier_id,confirmed=1',(key,supplier_id))
            if category_id is not None:
                self.db.execute('UPDATE suppliers SET habitual_category_id=? WHERE id=?',(category_id,supplier_id))
            self.db.execute('UPDATE transactions SET supplier_id=?,category_id=COALESCE(?,category_id),classification_status=CASE WHEN ? IS NULL THEN classification_status ELSE \'classificato\' END,classification_origin=\'confermata\' WHERE description=?',(supplier_id,category_id,category_id,description))

    def accounts(self):
        return self.db.execute('SELECT name,currency,provider FROM accounts ORDER BY id').fetchall()
    @staticmethod
    def normalize_description(value):
        import re
        text=' '.join(value.upper().split())
        text=re.sub(r'^(CARD PAYMENT|PAGAMENTO CARTA|PAGAMENTO CON CARTA)\\s+', '', text)
        text=re.sub(r'\\b(?:REF|REFERENCE|ID|CARD)[:#]?\\s*[A-Z0-9-]+\\b', ' ', text)
        return ' '.join(text.split())

    def classify_description(self, description):
        key=self.normalize_description(description)
        alias=self.db.execute(
            'SELECT a.supplier_id,a.confirmed,s.habitual_category_id '
            'FROM supplier_aliases a JOIN suppliers s ON s.id=a.supplier_id '
            'WHERE a.normalized_alias=? AND s.archived=0',(key,)).fetchone()
        if alias and alias['confirmed']:
            status='classificato' if alias['habitual_category_id'] else 'proposto'
            return {'supplier_id':alias['supplier_id'],'category_id':alias['habitual_category_id'],'status':status,'origin':'confermata'}
        if alias:
            status='classificato' if alias['habitual_category_id'] else 'proposto'
            return {'supplier_id':alias['supplier_id'],'category_id':alias['habitual_category_id'],'status':status,'origin':'alias' if status=='classificato' else 'proposta'}
        for rule in self.db.execute('SELECT * FROM classification_rules WHERE enabled=1'):
            if self.normalize_description(rule['exact_description']) == key:
                return {'supplier_id':rule['supplier_id'],'category_id':rule['category_id'],'status':'classificato','origin':'regola'}
        supplier=self.db.execute('SELECT id,habitual_category_id FROM suppliers WHERE UPPER(name)=? AND archived=0',(key,)).fetchone()
        if supplier:
            return {'supplier_id':supplier['id'],'category_id':supplier['habitual_category_id'],'status':'proposto','origin':'proposta'}
        return {'supplier_id':None,'category_id':None,'status':'in_attesa','origin':None}

    def confirm_supplier_alias(self, supplier_id, description, category_id=None):
        key=self.normalize_description(description)
        with self.db:
            self.db.execute('INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) VALUES(?,?,1) ON CONFLICT(normalized_alias) DO UPDATE SET supplier_id=excluded.supplier_id,confirmed=1',(key,supplier_id))
            if category_id is not None:
                self.db.execute('UPDATE suppliers SET habitual_category_id=? WHERE id=?',(category_id,supplier_id))
            self.db.execute("UPDATE transactions SET supplier_id=?,category_id=COALESCE(?,category_id),classification_status='classificato',classification_origin='confermata' WHERE description=?",(supplier_id,category_id,description))

    def import_revolut(self, file, account='Revolut EUR'):
        result=self.import_revolut_detailed(file,account)
        return result['imported'],result['duplicates']+result['excluded']

    def import_revolut_detailed(self, file, account='Revolut EUR'):
        imported=duplicates=excluded=classified=proposed=pending=0
        account_row=self.db.execute('SELECT id,currency,provider FROM accounts WHERE name=?',(account,)).fetchone()
        if account_row is None:
            raise ValueError(f"Conto non configurato: {account}")
        if account_row['provider'] != 'REVOLUT':
            raise ValueError(f"Il conto {account} non è un conto Revolut")
        account_id,currency_expected=account_row['id'],account_row['currency'].upper()
        with open(file,encoding='utf-8-sig',newline='') as handle:
            reader=csv.DictReader(handle)
            required={'Tipo','Data di inizio','Descrizione','Importo','Valuta','State'}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError('Schema CSV Revolut non riconosciuto')
            with self.db:
                batch=self.db.execute('INSERT INTO importations(file_name,account_id,result) VALUES(?,?,?)',(Path(file).name,account_id,'in_progress')).lastrowid
                for row in reader:
                    if row.get('State','').strip().upper()!='COMPLETATO':
                        excluded+=1
                        continue
                    when=row.get('Data di completamento') or row.get('Data di inizio')
                    amount=float(row['Importo']); fee=float(row.get('Costo') or 0)
                    currency=row['Valuta'].strip().upper()
                    if currency != currency_expected:
                        raise ValueError(f"Valuta {currency} incompatibile con il conto {account} ({currency_expected})")
                    description=row['Descrizione']
                    fingerprint=hashlib.sha256((account+'|'+when+'|'+row['Tipo']+'|'+description+'|'+str(amount)+'|'+currency+'|'+str(fee)).encode()).hexdigest()
                    classification=self.classify_description(description)
                    cursor=self.db.execute(
                        'INSERT OR IGNORE INTO transactions(fingerprint,account_id,occurred_at,description,amount,currency,fee,kind,status,source_json,supplier_id,category_id,classification_status,classification_origin,importation_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                        (fingerprint,account_id,when,description,amount,currency,fee,row['Tipo'],'COMPLETATO',json.dumps(row,ensure_ascii=False,sort_keys=True),classification['supplier_id'],classification['category_id'],classification['status'],classification['origin'],batch))
                    if cursor.rowcount:
                        imported+=1
                        if classification['status']=='classificato': classified+=1
                        elif classification['status']=='proposto': proposed+=1
                        else: pending+=1
                    else:
                        duplicates+=1
                self.db.execute("UPDATE importations SET result='completed' WHERE id=?",(batch,))
        return {'imported':imported,'duplicates':duplicates,'excluded':excluded,'classified':classified,'proposed':proposed,'pending':pending}
    def summary(self, account=None):
        sql='SELECT a.name,a.currency,COALESCE(SUM(t.amount-t.fee),0) balance,COALESCE(SUM(CASE WHEN t.amount>0 THEN t.amount ELSE 0 END),0) income,COALESCE(SUM(CASE WHEN t.amount<0 THEN t.amount ELSE 0 END),0) expenses FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id AND t.status="COMPLETATO"'
        if account: return self.db.execute(sql+' WHERE a.name=? GROUP BY a.id',(account,)).fetchall()
        return self.db.execute(sql+' GROUP BY a.id ORDER BY a.id').fetchall()
    def recent(self, account=None):
        sql='SELECT occurred_at,description,amount,currency,fee,kind FROM transactions'
        if account: return self.db.execute(sql+' WHERE account_id=(SELECT id FROM accounts WHERE name=?) ORDER BY id DESC LIMIT 100',(account,)).fetchall()
        return self.db.execute(sql+' ORDER BY id DESC LIMIT 100').fetchall()

    def reconcile_revolut_csv(self, file):
        """Return reconciliation anomalies with source row numbers."""
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
                anomalies.append({'row':row_number,'currency':currency,'expected_delta':str(movement),'actual_delta':str(balance-previous)})
            previous_by_currency[currency] = balance
        return anomalies
