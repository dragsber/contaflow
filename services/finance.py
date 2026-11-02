from contaflow.store import Store

class FinanceService:
    """Application boundary for account, ledger and import operations."""
    def __init__(self, store=None):
        self.store = store or Store()

    def accounts(self):
        return self.store.accounts()

    def summary(self, account=None):
        return self.store.summary(account)

    def movements(self, account=None):
        return self.store.recent(account)

    def import_revolut(self, path, account):
        result = self.store.import_revolut_detailed(path, account)
        anomalies = self.store.reconcile_revolut_csv(path)
        return {**result, 'anomalies': anomalies}

    def categories(self, include_archived=False):
        sql = 'SELECT id,name,category_type,is_custom,archived FROM categories'
        if not include_archived:
            sql += ' WHERE archived=0'
        return self.store.db.execute(sql+' ORDER BY name').fetchall()

    def create_category(self, name, category_type='uscita', is_custom=True):
        if category_type not in {'entrata','uscita','trasferimento'}:
            raise ValueError('Tipo categoria non valido')
        with self.store.db:
            self.store.db.execute(
                'INSERT INTO categories(name,category_type,is_custom) VALUES(?,?,?)',
                (name.strip(),category_type,int(is_custom)))

    def archive_category(self, category_id):
        with self.store.db:
            self.store.db.execute(
                'UPDATE categories SET archived=1 WHERE id=?',(category_id,))

    def suppliers(self):
        return self.store.db.execute(
            'SELECT s.id,s.name,s.habitual_category_id,c.name AS category '
            'FROM suppliers s LEFT JOIN categories c '
            'ON c.id=s.habitual_category_id WHERE s.archived=0 ORDER BY s.name'
        ).fetchall()

    def create_supplier(self, name, aliases=(), habitual_category_id=None):
        normalized_name = ' '.join(name.upper().split())
        if not normalized_name:
            raise ValueError('Nome fornitore obbligatorio')
        with self.store.db:
            cursor=self.store.db.execute(
                'INSERT INTO suppliers(name,habitual_category_id) VALUES(?,?)',
                (normalized_name,habitual_category_id))
            supplier_id=cursor.lastrowid
            for alias in aliases:
                key=' '.join(alias.upper().split())
                if key:
                    self.store.db.execute(
                        'INSERT INTO supplier_aliases(normalized_alias,supplier_id) VALUES(?,?)',
                        (key,supplier_id))
        return supplier_id

    def add_supplier_alias(self, supplier_id, alias):
        key=' '.join(alias.upper().split())
        if not key:
            raise ValueError('Alias vuoto')
        with self.store.db:
            self.store.db.execute(
                'INSERT INTO supplier_aliases(normalized_alias,supplier_id) VALUES(?,?)',
                (key,supplier_id))
