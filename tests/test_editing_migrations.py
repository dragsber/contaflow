import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from contaflow.store import Store
from db.migrations import MigrationError
from services.finance import FinanceService


class EditingMigrationTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.folder / "alpha01.db"
        with patch("db.migrations.LATEST_SCHEMA_VERSION", 3):
            old = Store(self.path)
        with old.db:
            old.db.execute(
                "INSERT INTO transactions(fingerprint,account_id,occurred_at,description,amount,"
                "currency,fee,kind,status,source_json) "
                "VALUES('immutable',1,'2026-01-01','TEST',-1.25,'EUR',0.1,'CARD','COMPLETATO','{}')"
            )
        old.db.close()

    def test_backup_precedes_migration_and_reopening_is_idempotent(self):
        service = FinanceService(Store(self.path))
        with closing(service.store.db):
            row = service.movements()[0]
            self.assertEqual(row["fingerprint"], "immutable")
            self.assertEqual(row["amount"], -1.25)
            self.assertEqual(row["notes"], "")
        backups = list((self.folder / "backups").glob("*v3_*.sqlite3"))
        self.assertTrue(backups)
        with closing(sqlite3.connect(backups[0])) as backup:
            self.assertEqual(backup.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertEqual(backup.execute("SELECT version FROM schema_version").fetchone()[0], 3)
            self.assertNotIn("notes", {r[1] for r in backup.execute("PRAGMA table_info(transactions)")})
            self.assertEqual(backup.execute("SELECT fingerprint FROM transactions").fetchone()[0], "immutable")
        count = len(list((self.folder / "backups").glob("*")))
        for _ in range(2):
            with closing(Store(self.path).db) as db:
                self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0], 4)
        self.assertEqual(len(list((self.folder / "backups").glob("*"))), count)

    def test_failed_migration_rolls_back_and_keeps_original_backup(self):
        def fail(db):
            db.execute("ALTER TABLE transactions ADD COLUMN temporary_test TEXT")
            raise sqlite3.OperationalError("Sintetico")
        with patch("db.migrations._migration_4", side_effect=fail):
            with self.assertRaisesRegex(MigrationError, "Versione attesa 3, rilevata 3"):
                Store(self.path)
        with closing(sqlite3.connect(self.path)) as db:
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")
            self.assertNotIn("temporary_test", {r[1] for r in db.execute("PRAGMA table_info(transactions)")})
            self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0], 3)
        self.assertTrue(list((self.folder / "backups").glob("*v3_*.sqlite3")))

    def test_invalid_safety_copy_blocks_schema_changes(self):
        connect = sqlite3.connect

        class InvalidBackup(sqlite3.Connection):
            def execute(self, sql, *args):
                if sql == "PRAGMA integrity_check":
                    return super().execute("SELECT 'corrupt'")
                return super().execute(sql, *args)

        with patch("db.migrations.sqlite3.connect",
                   side_effect=lambda *a, **kw: connect(*a, factory=InvalidBackup, **kw)):
            with self.assertRaisesRegex(MigrationError, "copia di sicurezza"):
                Store(self.path)
        with closing(connect(self.path)) as db:
            self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0], 3)

    def test_bulk_edit_audit_persistence_and_immutable_amounts(self):
        service = FinanceService(Store(self.path))
        with closing(service.store.db):
            category = service.create_category("Categoria test")
            service.update_movements([1], {"category_id": category, "notes": "Nota test",
                                          "classification_status": "classificato"})
            self.assertEqual(len(service.movement_audit(1)), 4)
            with self.assertRaises(ValueError):
                service.update_movements([1], {"amount": 7})
            with self.assertRaises(ValueError):
                service.update_movements([1, 999], {"notes": "Rollback"})
            self.assertEqual(service.movements()[0]["notes"], "Nota test")
        with closing(Store(self.path).db) as db:
            self.assertEqual(db.execute("SELECT amount,notes FROM transactions").fetchone()["notes"], "Nota test")
            self.assertEqual(db.execute("SELECT amount FROM transactions").fetchone()[0], -1.25)

    def test_gui_editor_saves_with_explicit_confirmation(self):
        from contaflow.app import App
        from tkinter import ttk
        service = FinanceService(Store(self.path))
        self.addCleanup(service.store.db.close)
        service.create_category("Categoria GUI")
        app = App(service)
        app.withdraw()
        self.addCleanup(app.destroy)
        app.table.selection_set("1")
        app.edit_movement_classification()
        window = next(w for w in app.winfo_children() if w.winfo_class() == "Toplevel")
        form = window.winfo_children()[0]
        boxes = [w for w in form.winfo_children() if isinstance(w, ttk.Combobox)]
        boxes[1].set(boxes[1]["values"][-1])
        boxes[2].set("✓ Classificato")
        save = next(w for w in form.winfo_children()
                    if isinstance(w, ttk.Button) and w.cget("text") == "Salva")
        with patch("contaflow.movement_editor.messagebox.askyesno", return_value=True) as confirm:
            save.invoke()
        self.assertIn("1 movimenti", confirm.call_args.args[1])
        self.assertEqual(service.movements()[0]["category"], "Categoria GUI")
        self.assertTrue(service.movement_audit(1))
