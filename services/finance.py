from contaflow.store import Store


class FinanceService:
    """Application boundary for accounts, movements, imports and classification."""

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
        return {**result, "anomalies": anomalies}

    def categories(self, include_archived=False):
        sql = "SELECT id,name,category_type,is_custom,archived FROM categories"
        if not include_archived:
            sql += " WHERE archived=0"
        return self.store.db.execute(sql + " ORDER BY archived,name").fetchall()

    def create_category(self, name, category_type="uscita", is_custom=True):
        name = name.strip()
        if not name:
            raise ValueError("Nome categoria obbligatorio")
        if category_type not in {"entrata", "uscita", "trasferimento"}:
            raise ValueError("Tipo categoria non valido")
        with self.store.db:
            return self.store.db.execute(
                "INSERT INTO categories(name,category_type,is_custom) VALUES(?,?,?)",
                (name, category_type, int(is_custom)),
            ).lastrowid

    def update_category(self, category_id, name, category_type):
        name = name.strip()
        if not name:
            raise ValueError("Nome categoria obbligatorio")
        if category_type not in {"entrata", "uscita", "trasferimento"}:
            raise ValueError("Tipo categoria non valido")
        with self.store.db:
            self.store.db.execute(
                "UPDATE categories SET name=?,category_type=? WHERE id=? AND archived=0",
                (name, category_type, category_id),
            )

    def archive_category(self, category_id):
        with self.store.db:
            self.store.db.execute(
                "UPDATE categories SET archived=1 WHERE id=? AND is_custom=1",
                (category_id,),
            )

    def suppliers(self, search=""):
        term = f"%{search.strip().upper()}%"
        return self.store.db.execute(
            "SELECT s.id,s.name,s.habitual_category_id,c.name AS category "
            "FROM suppliers s LEFT JOIN categories c "
            "ON c.id=s.habitual_category_id WHERE s.archived=0 AND UPPER(s.name) LIKE ? "
            "ORDER BY s.name",
            (term,),
        ).fetchall()

    def supplier_aliases(self, supplier_id):
        return self.store.db.execute(
            "SELECT id,normalized_alias,confirmed FROM supplier_aliases "
            "WHERE supplier_id=? ORDER BY normalized_alias",
            (supplier_id,),
        ).fetchall()

    def create_supplier(self, name, aliases=(), habitual_category_id=None):
        normalized_name = " ".join(name.upper().split())
        if not normalized_name:
            raise ValueError("Nome fornitore obbligatorio")
        with self.store.db:
            supplier_id = self.store.db.execute(
                "INSERT INTO suppliers(name,habitual_category_id) VALUES(?,?)",
                (normalized_name, habitual_category_id),
            ).lastrowid
            for alias in aliases:
                key = self.store.normalize_description(alias)
                if key:
                    self.store.db.execute(
                        "INSERT INTO supplier_aliases(normalized_alias,supplier_id) VALUES(?,?)",
                        (key, supplier_id),
                    )
        return supplier_id

    def update_supplier(self, supplier_id, name, habitual_category_id=None):
        normalized_name = " ".join(name.upper().split())
        if not normalized_name:
            raise ValueError("Nome fornitore obbligatorio")
        with self.store.db:
            self.store.db.execute(
                "UPDATE suppliers SET name=?,habitual_category_id=? "
                "WHERE id=? AND archived=0",
                (normalized_name, habitual_category_id, supplier_id),
            )

    def add_supplier_alias(self, supplier_id, alias, confirmed=False):
        key = self.store.normalize_description(alias)
        if not key:
            raise ValueError("Alias vuoto")
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) "
                "VALUES(?,?,?) ON CONFLICT(normalized_alias) DO UPDATE SET "
                "supplier_id=excluded.supplier_id,confirmed=MAX(confirmed,excluded.confirmed)",
                (key, supplier_id, int(confirmed)),
            )

    def remove_supplier_alias(self, alias_id):
        with self.store.db:
            self.store.db.execute("DELETE FROM supplier_aliases WHERE id=?", (alias_id,))

    def classify_movement(
        self, movement_id, supplier_id=None, category_id=None, remember_alias=False
    ):
        row = self.store.db.execute(
            "SELECT description FROM transactions WHERE id=?", (movement_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Movimento non trovato")
        status = "classificato" if category_id is not None else "proposto"
        origin = "manuale"
        with self.store.db:
            if remember_alias and supplier_id is not None:
                alias = self.store.normalize_description(row["description"])
                if not alias:
                    raise ValueError("Descrizione non valida per l'associazione")
                self.store.db.execute(
                    "INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) "
                    "VALUES(?,?,1) ON CONFLICT(normalized_alias) DO UPDATE SET "
                    "supplier_id=excluded.supplier_id,confirmed=1",
                    (alias, supplier_id),
                )
                self.store.db.execute(
                    "UPDATE suppliers SET habitual_category_id=? WHERE id=?",
                    (category_id, supplier_id),
                )
                origin = "confermata"
            self.store.db.execute(
                "UPDATE transactions SET supplier_id=?,category_id=?,"
                "classification_status=?,classification_origin=? WHERE id=?",
                (supplier_id, category_id, status, origin, movement_id),
            )

    def reconcile_movement(self, movement_id, supplier_id, category_id):
        """Confirm a movement and remember its exact normalized bank description."""
        return self.classify_movement(
            movement_id, supplier_id, category_id, remember_alias=True
        )
