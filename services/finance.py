import json
import logging
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from contaflow.runtime import log_exception
from contaflow.store import Store
from db.migrations import migrate
from services.register import movements


class RestoreVerificationError(RuntimeError):
    """La copia SQLite è terminata, ma la verifica del database attivo è fallita."""


def _restore_counts(db):
    if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
        raise sqlite3.DatabaseError("Controllo di integrità non superato")
    if db.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise sqlite3.IntegrityError("Riferimenti contabili non validi")
    row = db.execute(
        "SELECT (SELECT COUNT(*) FROM accounts), (SELECT COUNT(*) FROM transactions)"
    ).fetchone()
    return tuple(row)


class FinanceService:
    """Application boundary for accounts, movements, imports and classification."""

    def __init__(self, store=None):
        self.store = store or Store()
        from services.ledger import LedgerService
        self.ledger = LedgerService(self.store)

    def accounts(self):
        return self.store.accounts()

    def summary(self, account=None):
        from services.accounts import balance_movements, calculated_balance, opening_balance
        from services.transfers import account_summary
        summaries = account_summary(self.store, account)
        enriched = []
        for row in summaries:
            item = dict(row)
            account_id = item["id"]
            opening = opening_balance(self.store.db, account_id)
            item["opening_balance_confirmed"] = opening is not None
            if opening is not None:
                movements_after = balance_movements(self.store.db, account_id, after=opening["as_of"])
                item["opening_as_of"] = opening["as_of"]
                item["bank_balance"] = calculated_balance(opening, movements_after)
            else:
                item["opening_as_of"] = None
                item["bank_balance"] = None
            enriched.append(item)
        return enriched

    def save_budget(self, year, month, category_id, currency, amount):
        raise ValueError("I budget per categoria sono storici. Imposta il budget sulle sottovoci.")

    def budget_report(self, year, month):
        from services.budget import budget_report
        return budget_report(self.store.db, year, month)

    def unlink_movement(self, movement_id):
        from services.transfers import unlink_movement
        return unlink_movement(self.store.db, movement_id)

    def link_movements(self, outgoing_id, incoming_id, kind):
        from services.transfers import link_movements
        return link_movements(self.store.db, outgoing_id, incoming_id, kind)

    def movements(self, account=None, **filters):
        return movements(self.store.db, account, **filters)

    def preview_import(self, path, account):
        from services.imports import preview_import
        return preview_import(self.store, path, account)

    def confirm_import(self, preview):
        from services.imports import confirm_import
        return confirm_import(self.store, preview)

    def import_revolut(self, path, account):
        return self.confirm_import(self.preview_import(path, account))

    def import_batches(self):
        return self.store.db.execute(
            "SELECT i.*,a.name AS account,(SELECT COUNT(*) FROM transactions t "
            "WHERE t.importation_id=i.id) AS movements FROM importations i "
            "JOIN accounts a ON a.id=i.account_id ORDER BY i.id DESC"
        ).fetchall()

    def batch_dependencies(self, batch_id):
        from services.imports import batch_dependencies
        return batch_dependencies(self.store.db, batch_id)

    def cancel_batch(self, batch_id, confirm_dependencies=False):
        from services.imports import cancel_batch
        return cancel_batch(self.store.db, batch_id, confirm_dependencies)

    def import_catalog(self, records):
        from services.catalog_import import import_catalog
        return import_catalog(self.store.db, records, self.store.normalize_description)

    def category_suppliers(self, category_id):
        return self.store.db.execute(
            "SELECT DISTINCT s.name FROM suppliers s LEFT JOIN supplier_categories a "
            "ON a.supplier_id=s.id WHERE s.habitual_category_id=? OR a.category_id=? ORDER BY s.name",
            (category_id, category_id),
        ).fetchall()

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
        if self.store.db.in_transaction:
            raise ValueError("Completa la transazione in corso")
        with self.store.db:
            self.store.db.execute("BEGIN IMMEDIATE")
            old = self.store.db.execute(
                "SELECT name,category_type FROM categories WHERE id=? AND archived=0",(category_id,)
            ).fetchone()
            if old is None:
                raise ValueError("Categoria non disponibile")
            if old["category_type"] != category_type:
                used = self.store.db.execute(
                    "SELECT EXISTS(SELECT 1 FROM transactions WHERE category_id=?) OR "
                    "EXISTS(SELECT 1 FROM budgets WHERE category_id=?) OR "
                    "EXISTS(SELECT 1 FROM subcategory_budgets b JOIN subcategories s ON s.id=b.subcategory_id WHERE s.category_id=?)",
                    (category_id,category_id,category_id),
                ).fetchone()[0]
                if category_type == "trasferimento" and self.store.db.execute(
                    "SELECT 1 FROM subcategories WHERE category_id=? LIMIT 1",(category_id,)
                ).fetchone():
                    used = True
                if used:
                    raise ValueError("Il tipo non può essere cambiato: la categoria ha movimenti o budget.")
            self.store.db.execute(
                "UPDATE categories SET name=?,category_type=? WHERE id=? AND archived=0",
                (name, category_type, category_id),
            )
            if old["name"] != name or old["category_type"] != category_type:
                import json
                self.store.db.execute(
                    "INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                    (f"categoria:{category_id}",json.dumps(dict(old)),json.dumps({"name":name,"category_type":category_type})),
                )

    def archive_category(self, category_id):
        with self.store.db:
            self.store.db.execute(
                "UPDATE categories SET archived=1 WHERE id=? AND is_custom=1",
                (category_id,),
            )

    def suppliers(self, search="", include_archived=False):
        term = f"%{search.strip().upper()}%"
        return self.store.db.execute(
            "SELECT s.id,s.name,s.habitual_category_id,s.notes,s.archived,c.name AS category "
            "FROM suppliers s LEFT JOIN categories c "
            "ON c.id=s.habitual_category_id WHERE (s.archived=0 OR ?) AND UPPER(s.name) LIKE ? "
            "ORDER BY s.name",
            (include_archived, term),
        ).fetchall()

    def save_supplier(self, name, category_id=None, alias="", notes="", alternatives=(), supplier_id=None):
        name = " ".join(name.upper().split())
        if not name:
            raise ValueError("Nome fornitore obbligatorio")
        db = self.store.db
        with db:
            duplicate = db.execute(
                "SELECT id FROM suppliers WHERE name=? AND id!=COALESCE(?,0)",
                (name, supplier_id),
            ).fetchone()
            if duplicate:
                raise ValueError("Fornitore già presente. Verifica anche i fornitori archiviati.")
            key = self.store.normalize_description(alias) if alias.strip() else ""
            existing = db.execute(
                "SELECT supplier_id FROM supplier_aliases WHERE normalized_alias=?", (key,)
            ).fetchone()
            if existing and existing[0] != supplier_id:
                raise ValueError("Alias già presente per un altro fornitore")
            if supplier_id is None:
                supplier_id = db.execute(
                    "INSERT INTO suppliers(name,habitual_category_id,notes) VALUES(?,?,?)",
                    (name, category_id, notes),
                ).lastrowid
            else:
                db.execute("UPDATE suppliers SET name=?,habitual_category_id=?,notes=? WHERE id=?",
                           (name, category_id, notes, supplier_id))
            db.execute("DELETE FROM supplier_categories WHERE supplier_id=?", (supplier_id,))
            for alternative in set(alternatives):
                db.execute("INSERT INTO supplier_categories VALUES(?,?)", (supplier_id, alternative))
            if key and not existing:
                db.execute("INSERT INTO supplier_aliases(normalized_alias,supplier_id) VALUES(?,?)",
                           (key, supplier_id))
        return supplier_id

    def archive_supplier(self, supplier_id, archived=True):
        with self.store.db:
            self.store.db.execute("UPDATE suppliers SET archived=? WHERE id=?", (int(archived), supplier_id))

    def supplier_categories(self, supplier_id):
        return [row[0] for row in self.store.db.execute(
            "SELECT category_id FROM supplier_categories WHERE supplier_id=?", (supplier_id,)
        )]

    def supplier_aliases(self, supplier_id, include_archived=False):
        return self.store.db.execute(
            "SELECT id,normalized_alias,confirmed,archived FROM supplier_aliases "
            "WHERE supplier_id=? AND (? OR archived=0) ORDER BY normalized_alias",
            (supplier_id, include_archived),
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
        existing = self.store.db.execute(
            "SELECT supplier_id FROM supplier_aliases WHERE normalized_alias=?", (key,)
        ).fetchone()
        if existing is not None and existing[0] != supplier_id:
            raise ValueError("Alias già associato a un altro fornitore. Verifica il duplicato.")
        with self.store.db:
            self.store.db.execute(
                "INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) "
                "VALUES(?,?,?) ON CONFLICT(normalized_alias) DO UPDATE SET "
                "supplier_id=excluded.supplier_id,confirmed=MAX(confirmed,excluded.confirmed)",
                (key, supplier_id, int(confirmed)),
            )

    def remove_supplier_alias(self, alias_id):
        self.edit_supplier_alias(alias_id, archived=True)

    def edit_supplier_alias(self, alias_id, *, description=None, archived=None):
        db = self.store.db
        with db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM supplier_aliases WHERE id=?", (alias_id,)).fetchone()
            if row is None:
                raise ValueError("Alias non trovato")
            key = row["normalized_alias"] if description is None else self.store.normalize_description(description)
            if not key:
                raise ValueError("Alias vuoto")
            if db.execute("SELECT 1 FROM supplier_aliases WHERE normalized_alias=? AND id!=?", (key, alias_id)).fetchone():
                raise ValueError("Alias già registrato. Verifica il duplicato.")
            active_state = row["archived"] if archived is None else int(archived)
            db.execute("UPDATE supplier_aliases SET normalized_alias=?,archived=? WHERE id=?",
                       (key, active_state, alias_id))
            db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
                       ("alias_fornitore", json.dumps(dict(row)),
                        json.dumps({**dict(row), "normalized_alias": key, "archived": active_state})))

    def classify_movement(
        self, movement_id, supplier_id=None, category_id=None, remember_alias=False
    ):
        status = "classificato" if category_id is not None else "proposto"
        return self.update_movements([movement_id], {
            "supplier_id": supplier_id, "category_id": category_id,
            "classification_status": status,
        }, remember=remember_alias)

    def update_movements(self, movement_ids, changes, remember=False):
        from services.editing import update_movements
        return update_movements(self.store, movement_ids, changes, remember)

    def movement_audit(self, movement_id):
        from services.editing import movement_audit
        return movement_audit(self.store.db, movement_id)

    def reconcile_movement(self, movement_id, supplier_id, category_id):
        """Confirm a movement and remember its exact normalized bank description."""
        return self.classify_movement(
            movement_id, supplier_id, category_id, remember_alias=True
        )

    def backup_database(self, destination=None):
        if destination is None:
            backup_dir = Path(self.store.path).parent / "backups"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            destination = backup_dir / f"ContaFlow_backup_{stamp}.sqlite3"
        target = Path(destination).expanduser().resolve()
        source = Path(self.store.path).resolve()
        if target == source:
            raise ValueError("Il file di backup non può coincidere con il database attivo")
        target.parent.mkdir(parents=True, exist_ok=True)
        backup = sqlite3.connect(str(target))
        try:
            self.store.db.backup(backup)
        finally:
            backup.close()
        return str(target)

    def restore_database(self, source_path):
        source = Path(source_path).expanduser().resolve()
        if not source.is_file():
            raise ValueError("Il file di backup selezionato non esiste")
        if source == Path(self.store.path).resolve():
            raise ValueError("Seleziona un backup diverso dal database attivo")
        active = self.store.db
        if active.in_transaction:
            raise ValueError("Completa l'operazione in corso prima del ripristino")
        temp = tempfile.TemporaryDirectory(prefix="contaflow-restore-")
        copied = False
        try:
            staged_path = Path(temp.name) / "validated.sqlite3"
            with closing(sqlite3.connect(str(staged_path))) as staged:
                with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original:
                    if original.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise ValueError("Il backup selezionato non supera il controllo di integrità")
                    table_names = {
                        row[0] for row in original.execute(
                            "SELECT name FROM sqlite_master WHERE type='table'"
                        )
                    }
                    if not {"accounts", "categories", "transactions"}.issubset(table_names):
                        raise ValueError("Il file selezionato non è un database ContaFlow")
                    original.backup(staged)
                migrate(staged)
                staged.commit()
                expected = _restore_counts(staged)
                if not expected[0]:
                    raise ValueError("Il backup non contiene conti")
                safety_copy = self.backup_database()
                staged.backup(active)
                copied = True
            active.execute("PRAGMA foreign_keys=ON")
            if _restore_counts(active) != expected:
                raise sqlite3.IntegrityError("Numero di conti o movimenti incoerente")
            return safety_copy
        except sqlite3.Error as error:
            if not copied:
                raise
            raise RestoreVerificationError(
                "Copia eseguita, ma verifica del database attivo fallita. "
                f"Copia di sicurezza del precedente:\n{safety_copy}"
            ) from error
        finally:
            try:
                temp.cleanup()
            except OSError as error:
                context = f"Pulizia della cartella temporanea di ripristino non riuscita: {temp.name}"
                try:
                    log_exception(error, context, level=logging.WARNING)
                except OSError:
                    logging.getLogger(__name__).warning(context, exc_info=True)
