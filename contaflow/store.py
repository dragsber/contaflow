import csv, os, sqlite3, hashlib, json
from pathlib import Path
from datetime import datetime
from db import migrations
from db.migrations import migrate, backup_before_upgrade, MigrationError, schema_version

DEFAULT_ACCOUNTS = [('Revolut EUR','EUR','REVOLUT'),('Revolut CHF','CHF','REVOLUT'),('BPER EUR','EUR','BPER'),('Cassa contanti','EUR','CASH')]

def default_data_path():
    return Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'ContaFlow' / 'contaflow.sqlite3'


def data_directory():
    configured = os.environ.get('CONTAFLOW_DATA_DIR')
    return (Path(configured).expanduser() if configured else default_data_path().parent).resolve()


def data_path():
    return data_directory() / 'contaflow.sqlite3'

class Store:
    def __init__(self, path=None):
        target = Path(path if path is not None else data_path()).resolve()
        self.path = str(target)
        self.db = None
        safety = None
        try:
            try:
                target.stat()
                is_new = False
            except FileNotFoundError:
                is_new = True
            if is_new:
                default = default_data_path().resolve()
                if path is None and target != default and default.exists():
                    raise MigrationError(f"Il percorso configurato non esiste. Archivio predefinito presente in {default}.")
                if path is None:
                    target.parent.mkdir(parents=True, exist_ok=True)
            mode = "rwc" if is_new else "rw"
            self.db = sqlite3.connect(f"{target.as_uri()}?mode={mode}", uri=True)
            self.db.row_factory = sqlite3.Row
            if not is_new:
                version = self._validate_existing()
                self.db.execute("PRAGMA foreign_keys=ON")
                if version >= 2:
                    migrate(self.db)
                    return
            safety = backup_before_upgrade(self.db)
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
            migrate(self.db, new_database=is_new)
        except Exception as error:
            if self.db is not None:
                self.db.close()
            if isinstance(error, MigrationError):
                reason = str(error)
            else:
                code = getattr(error, "sqlite_errorname", None) or type(error).__name__
                reason = f"Impossibile aprire o leggere il database ({code})."
            raise MigrationError(
                f"Avvio interrotto. Database: {target}\nCausa: {reason}"
                + (f"\nCopia precedente: {safety}" if safety else "")
            ) from error

    def _validate_existing(self):
        tables = {row[0] for row in self.db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
        if "schema_version" in tables:
            versions = [row[0] for row in self.db.execute("SELECT version FROM schema_version")]
            if len(versions) != 1 or type(versions[0]) is not int or not 1 <= versions[0] <= migrations.LATEST_SCHEMA_VERSION:
                raise MigrationError("Versione dello schema non supportata.")
            version = versions[0]
        else:
            version = 0
        required = {"accounts", "transactions", "categories", "merchants", "audit"}
        # The original account-only schema was also supported by the legacy bootstrap.
        account_only = version == 0 and tables - {"sqlite_sequence"} == {"accounts"}
        if account_only:
            required = {"accounts"}
        for first_version, names in (
            (2, {"suppliers", "supplier_aliases", "classification_rules", "importations",
                 "transfers", "refunds", "budgets", "opening_balances"}),
            (5, {"supplier_categories"}),
            (7, {"ledger_accounts", "ledger_categories", "supplier_ledger", "alias_ledger",
                 "ledger_rules", "ledger_imports", "ledger_budgets"}),
            (8, {"subcategories", "subcategory_budgets", "supplier_subcategories",
                 "alias_subcategories", "subcategory_rules", "legacy_allocations"}),
        ):
            if version >= first_version:
                required.update(names)
        if not required <= tables:
            raise MigrationError("Schema ContaFlow inatteso: mancano tabelle richieste.")
        columns = {
            "accounts": {"id", "name", "currency"},
            "transactions": {"id", "account_id", "fingerprint", "occurred_at", "description",
                             "amount", "fee", "currency", "kind", "status", "category_id",
                             "source_json", "imported_at"},
        }
        if account_only:
            del columns["transactions"]
        if version >= 2:
            columns["accounts"].add("provider")
            columns["transactions"].update({"supplier_id", "classification_status",
                                            "classification_origin", "importation_id"})
        if version >= 4:
            columns["transactions"].update({"notes", "accounting_nature"})
        if version >= 7:
            columns["transactions"].add("ledger_account_id")
        if version >= 8:
            columns["transactions"].add("subcategory_id")
        for table, expected in columns.items():
            actual = {row[1] for row in self.db.execute(f"PRAGMA table_info({table})")}
            if not expected <= actual:
                raise MigrationError(f"Schema ContaFlow inatteso: colonne mancanti in {table}.")
        if self.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise MigrationError("Controllo di integrità SQLite fallito.")
        return version
    @staticmethod
    def normalize_description(value):
        import re
        text=' '.join(value.upper().split())
        text=re.sub(r'^(CARD PAYMENT|PAGAMENTO CARTA|PAGAMENTO CON CARTA)\s+', '', text)
        text=re.sub(r'\b(?:REF|REFERENCE|ID|CARD)[:#]?\s*[A-Z0-9-]+\b', ' ', text)
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
        text=re.sub(r'^(CARD PAYMENT|PAGAMENTO CARTA|PAGAMENTO CON CARTA)\s+', '', text)
        text=re.sub(r'\b(?:REF|REFERENCE|ID|CARD)[:#]?\s*[A-Z0-9-]+\b', ' ', text)
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

    def import_revolut_detailed(self, file, account='Revolut EUR', *, rows=None):
        from adapters.revolut import read_rows, fingerprint
        account_row = self.db.execute(
            "SELECT id,currency,provider FROM accounts WHERE name=?", (account,)
        ).fetchone()
        if account_row is None or account_row["provider"] != "REVOLUT":
            raise ValueError("Seleziona un conto Revolut configurato")
        if rows is None:
            rows = read_rows(Path(file).read_bytes())
        result = dict.fromkeys(("imported", "duplicates", "excluded", "classified", "proposed", "pending"), 0)
        with self.db:
            batch = self.db.execute(
                "INSERT INTO importations(file_name,account_id,result) VALUES(?,?,'in_progress')",
                (Path(file).name, account_row["id"]),
            ).lastrowid
            next_id = self.db.execute(
                "SELECT MAX(value)+1 FROM (SELECT COALESCE(MAX(id),0) value FROM transactions "
                "UNION ALL SELECT COALESCE(MAX(transaction_id),0) FROM audit)"
            ).fetchone()[0]
            for row in rows:
                if row.get("State", "").strip().upper() != "COMPLETATO":
                    result["excluded"] += 1
                    continue
                currency = row["Valuta"].strip().upper()
                if currency != account_row["currency"].upper():
                    raise ValueError(f"Valuta {currency} incompatibile con il conto {account}")
                identity = fingerprint(account, row)
                if self.db.execute("SELECT 1 FROM transactions WHERE fingerprint=?", (identity,)).fetchone():
                    result["duplicates"] += 1
                    continue
                classification = self.classify_description(row["Descrizione"])
                if classification["category_id"] is not None:
                    category_type = self.db.execute(
                        "SELECT category_type FROM categories WHERE id=?", (classification["category_id"],)
                    ).fetchone()
                    if category_type and category_type[0] == "trasferimento":
                        classification["status"] = "trasferimento"
                self.db.execute(
                    "INSERT INTO transactions(id,fingerprint,account_id,occurred_at,description,"
                    "amount,currency,fee,kind,status,source_json,supplier_id,category_id,"
                    "classification_status,classification_origin,importation_id) "
                    "VALUES(?,?,?,?,?,?,?,?,?,'COMPLETATO',?,?,?,?,?,?)",
                    (next_id, identity, account_row["id"],
                     row.get("Data di completamento") or row["Data di inizio"], row["Descrizione"],
                     float(row["Importo"]), currency, float(row.get("Costo") or 0), row["Tipo"],
                     json.dumps(row, ensure_ascii=False, sort_keys=True), classification["supplier_id"],
                     classification["category_id"], classification["status"], classification["origin"], batch),
                )
                next_id += 1
                from services.ledger import candidates
                choices = candidates(self, row["Descrizione"], classification["supplier_id"])
                if len(choices) == 1:
                    self.db.execute("UPDATE transactions SET ledger_account_id=? WHERE id=?", (choices[0],next_id-1))
                elif len(choices) > 1 and classification["status"] in ("classificato","proposto","in_attesa"):
                    self.db.execute("UPDATE transactions SET classification_status='proposto' WHERE id=?", (next_id-1,))
                    classification["status"] = "proposto"
                from services.subcategories import candidates as subcategory_candidates
                sub_choices = subcategory_candidates(self, row["Descrizione"], classification["supplier_id"])
                if len(sub_choices) == 1:
                    candidate = self.db.execute("SELECT category_id FROM subcategories WHERE id=?", (sub_choices[0],)).fetchone()
                    if classification["category_id"] is None or classification["category_id"] == candidate[0]:
                        self.db.execute("UPDATE transactions SET category_id=?,subcategory_id=? WHERE id=?",
                                        (candidate[0],sub_choices[0],next_id-1))
                    elif classification["status"] in ("classificato","proposto","in_attesa"):
                        self.db.execute("UPDATE transactions SET classification_status='proposto' WHERE id=?",(next_id-1,))
                        classification["status"] = "proposto"
                elif len(sub_choices) > 1 and classification["status"] in ("classificato","proposto","in_attesa"):
                    self.db.execute("UPDATE transactions SET classification_status='proposto' WHERE id=?",(next_id-1,))
                    classification["status"] = "proposto"
                result["imported"] += 1
                result[{"classificato":"classified", "proposto":"proposed", "in_attesa":"pending", "trasferimento":"classified"}[classification["status"]]] += 1
            self.db.execute("UPDATE importations SET result='completed' WHERE id=?", (batch,))
        return {**result, "batch_id": batch}

    def summary(self, account=None):
        sql='SELECT a.name,a.currency,COALESCE(SUM(t.amount-t.fee),0) balance,COALESCE(SUM(CASE WHEN t.amount>0 THEN t.amount ELSE 0 END),0) income,COALESCE(SUM(CASE WHEN t.amount<0 THEN t.amount ELSE 0 END),0) expenses FROM accounts a LEFT JOIN transactions t ON t.account_id=a.id AND t.status="COMPLETATO"'
        if account: return self.db.execute(sql+' WHERE a.name=? GROUP BY a.id',(account,)).fetchall()
        return self.db.execute(sql+' GROUP BY a.id ORDER BY a.id').fetchall()
    def recent(self, account=None):
        sql = (
            "SELECT t.id,t.occurred_at,t.description,t.amount,t.currency,t.fee,t.kind,"
            "t.classification_status,t.classification_origin,t.supplier_id,t.category_id,"
            "s.name AS supplier,c.name AS category "
            "FROM transactions t LEFT JOIN suppliers s ON s.id=t.supplier_id "
            "LEFT JOIN categories c ON c.id=t.category_id"
        )
        if account:
            return self.db.execute(
                sql + " WHERE t.account_id=(SELECT id FROM accounts WHERE name=?) "
                "ORDER BY t.id DESC LIMIT 100", (account,)
            ).fetchall()
        return self.db.execute(sql + " ORDER BY t.id DESC LIMIT 100").fetchall()

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
