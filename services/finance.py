import logging
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path

from contaflow.runtime import log_exception
from contaflow.store import Store
from db.migrations import migrate


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

    def accounts(self):
        return self.store.accounts()

    def summary(self, account=None):
        summaries = self.store.summary(account)
        enriched = []
        for row in summaries:
            item = dict(row)
            account_id = self.store.db.execute(
                "SELECT id FROM accounts WHERE name=?", (item["name"],)
            ).fetchone()["id"]
            opening = self.store.db.execute(
                "SELECT as_of,amount FROM opening_balances "
                "WHERE account_id=? AND confirmed=1 ORDER BY as_of DESC LIMIT 1",
                (account_id,),
            ).fetchone()
            item["opening_balance_confirmed"] = opening is not None
            if opening is not None:
                movements_after = self.store.db.execute(
                    "SELECT COALESCE(SUM(amount-fee),0) FROM transactions "
                    "WHERE account_id=? AND status='COMPLETATO' "
                    "AND substr(occurred_at,1,10)>?",
                    (account_id, opening["as_of"]),
                ).fetchone()[0]
                item["opening_as_of"] = opening["as_of"]
                item["bank_balance"] = float(opening["amount"]) + float(movements_after)
            else:
                item["opening_as_of"] = None
                item["bank_balance"] = None
            enriched.append(item)
        return enriched

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
