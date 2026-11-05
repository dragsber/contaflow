import logging
import sqlite3
import tempfile
import tkinter as tk
import unittest
from contextlib import closing, contextmanager
from pathlib import Path
from unittest.mock import Mock, patch

from contaflow.app import App
from contaflow.diagnostics import backup_summary
from contaflow.store import Store
from services.finance import FinanceService, RestoreVerificationError


class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(self.folder / "active.db"))
        self.active = self.service.store.db
        self.addCleanup(self.active.close)
        self.service.create_category("Salvata")
        self.source = self.folder / "saved.db"
        self.service.backup_database(self.source)
        with self.active:
            self.active.execute("UPDATE categories SET name='Attiva' WHERE name='Salvata'")

    @staticmethod
    def categories(db):
        return [row[0] for row in db.execute("SELECT name FROM categories ORDER BY name")]

    @contextmanager
    def track_restore(self, factory=sqlite3.Connection):
        # Strong references expose leaks even on platforms that allow unlinking open files.
        connect = sqlite3.connect
        connections = []
        folders = []

        def tracked(path, **kwargs):
            db = connect(path, factory=factory, **kwargs)
            connections.append(db)
            if Path(path).name == "validated.sqlite3":
                folders.append(Path(path).parent)
            return db

        try:
            with patch("services.finance.sqlite3.connect", side_effect=tracked):
                yield
        finally:
            try:
                self.assertTrue(folders)
                for db in connections:
                    with self.assertRaises(sqlite3.ProgrammingError):
                        db.execute("SELECT 1")
                for folder in folders:
                    self.assertFalse(folder.exists())
            finally:
                for db in connections:
                    db.close()

    def test_restore_reads_wal_and_releases_handles_and_directory(self):
        with closing(sqlite3.connect(self.source)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            with writer:
                writer.execute("INSERT INTO categories(name) VALUES ('Dal WAL')")
            self.assertTrue(Path(str(self.source) + "-wal").exists())
            with self.track_restore():
                safety = self.service.restore_database(self.source)
        self.assertIs(self.service.store.db, self.active)
        self.assertEqual(self.categories(self.active), ["Dal WAL", "Salvata"])
        with closing(sqlite3.connect(safety)) as db:
            self.assertEqual(self.categories(db), ["Attiva"])
        with closing(sqlite3.connect(self.service.store.path)) as db:
            self.assertEqual(self.categories(db), self.categories(self.active))
        for suffix in ("-wal", "-shm"):
            self.assertFalse(Path(str(self.source) + suffix).exists())

    def test_corrupt_backup_preserves_active(self):
        self.source.write_bytes(b"corrupt synthetic backup")
        with self.assertRaises(sqlite3.DatabaseError), self.track_restore():
            self.service.restore_database(self.source)
        self.assertEqual(self.categories(self.active), ["Attiva"])

    def test_broken_foreign_key_preserves_active(self):
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("PRAGMA foreign_keys=OFF")
            db.execute("INSERT INTO suppliers(name, habitual_category_id) VALUES ('Test',99999)")
            db.commit()
        with self.assertRaises(sqlite3.IntegrityError), self.track_restore():
            self.service.restore_database(self.source)
        self.assertEqual(self.categories(self.active), ["Attiva"])

    def test_pending_transaction_is_not_committed_by_restore(self):
        self.active.execute("INSERT INTO categories(name) VALUES ('In corso')")
        with self.assertRaisesRegex(ValueError, "in corso"):
            self.service.restore_database(self.source)
        self.assertTrue(self.active.in_transaction)
        self.active.rollback()
        self.assertEqual(self.categories(self.active), ["Attiva"])

    def test_safety_backup_failure_stops_restore(self):
        with patch.object(self.service, "backup_database", side_effect=OSError("backup")):
            with self.assertRaises(OSError), self.track_restore():
                self.service.restore_database(self.source)
        self.assertEqual(self.categories(self.active), ["Attiva"])

    def test_interrupted_sqlite_copy_leaves_destination_unchanged(self):
        active = self.active

        class InterruptedCopy(sqlite3.Connection):
            def backup(self, target, **kwargs):
                def stop(status, remaining, total):
                    if remaining:
                        raise sqlite3.OperationalError("Copia interrotta")

                if target is active:
                    kwargs.update(pages=1, progress=stop)
                return super().backup(target, **kwargs)

        with self.assertRaisesRegex(sqlite3.OperationalError, "interrotta"), self.track_restore(InterruptedCopy):
            self.service.restore_database(self.source)
        self.assertEqual(self.categories(self.active), ["Attiva"])
        self.assertEqual(len(list((self.folder / "backups").glob("*.sqlite3"))), 1)

    def test_cleanup_failure_is_logged_after_success(self):
        cleanup = tempfile.TemporaryDirectory.cleanup

        def fail_cleanup(directory):
            cleanup(directory)
            raise PermissionError("Pulizia interrotta")

        with patch.object(tempfile.TemporaryDirectory, "cleanup", fail_cleanup):
            with patch("services.finance.log_exception") as log:
                safety = self.service.restore_database(self.source)
        self.assertEqual(log.call_args.kwargs["level"], logging.WARNING)
        self.assertIsInstance(log.call_args.args[0], PermissionError)
        self.assertTrue(Path(safety).is_file())
        self.assertEqual(self.categories(self.active), ["Salvata"])

    def test_active_verification_failure_is_critical(self):
        def deny_integrity(action, name, *unused):
            if action == sqlite3.SQLITE_PRAGMA and name == "integrity_check":
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        self.active.set_authorizer(deny_integrity)
        with self.assertRaises(RestoreVerificationError) as caught, self.track_restore():
            self.service.restore_database(self.source)
        safety, = (self.folder / "backups").glob("*.sqlite3")
        self.assertIn(str(safety), str(caught.exception))
        self.assertIsInstance(caught.exception.__cause__, sqlite3.DatabaseError)
        self.assertEqual(self.categories(self.active), ["Salvata"])

    def gui_dialogs(self):
        self.enterContext(patch("contaflow.app.filedialog.askopenfilename", return_value=str(self.source)))
        dialogs = self.enterContext(patch("contaflow.app.messagebox"))
        dialogs.askyesno.return_value = True
        return dialogs

    def test_preview_counts_legacy_backup_without_modifying_it(self):
        with closing(sqlite3.connect(self.source)) as db, db:
            db.execute("UPDATE schema_version SET version=5")
            db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json) "
                "VALUES (1,'2026-01-01','Privato sintetico',-7,'EUR','CARD_PAYMENT','COMPLETATO','{}')"
            )
        before = self.source.read_bytes()
        summary = backup_summary(self.source)
        self.assertIn("Movimenti: 1", summary)
        self.assertIn("Schema: 5", summary)
        self.assertNotIn("Privato sintetico", summary)
        self.assertEqual(self.source.read_bytes(), before)
        self.assertEqual(self.active.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 0)

    def test_unreadable_backup_is_rejected_before_confirmation(self):
        self.source.write_bytes(b"corrupt synthetic backup")
        dialogs = self.gui_dialogs()
        app = self.mock_restore_app()
        App.restore_database(app)
        dialogs.showerror.assert_called_once()
        dialogs.askyesno.assert_not_called()
        self.assertEqual(self.categories(self.active), ["Attiva"])

    def mock_restore_app(self):
        app = Mock(store=self.service)
        app._pick_backup.side_effect = lambda: App._pick_backup(app)
        app._backup_preview.side_effect = lambda path: App._backup_preview(app, path)
        return app

    def test_gui_refresh_failure_reports_success_with_warning(self):
        dialogs = self.gui_dialogs()
        app = self.mock_restore_app()
        app.anomalies.get_children.return_value = ()
        app.refresh_all.side_effect = tk.TclError("Widget non disponibile")
        with patch("contaflow.app.show_error") as error:
            App.restore_database(app)
        error.assert_not_called()
        dialogs.showwarning.assert_called_once()
        dialogs.showinfo.assert_not_called()
        self.assertEqual(self.categories(self.active), ["Salvata"])

    def test_gui_database_read_failure_is_critical(self):
        dialogs = self.gui_dialogs()
        app = self.mock_restore_app()
        app.anomalies.get_children.return_value = ()
        app.refresh_all.side_effect = sqlite3.DatabaseError("Lettura fallita")
        with patch("contaflow.app.show_error") as error:
            App.restore_database(app)
        self.assertEqual(error.call_args.args[1], "Errore critico di lettura")
        dialogs.showwarning.assert_not_called()
        dialogs.showinfo.assert_not_called()

    def test_tk_refreshes_restored_account_views_and_import_state(self):
        dialogs = self.gui_dialogs()
        try:
            app = App(self.service)
        except tk.TclError as error:
            if "display" in str(error).lower():
                self.skipTest(str(error))
            raise
        app.withdraw()
        self.addCleanup(app.destroy)
        self.assertEqual(app.empty_archive.winfo_manager(), "pack")
        with closing(sqlite3.connect(self.source)) as db:
            db.execute("UPDATE accounts SET name='Conto ripristinato' WHERE id=1")
            db.execute("INSERT INTO suppliers(name) VALUES ('Fornitore test')")
            db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,"
                "kind,status,source_json) VALUES (1,'2026-01-01','Movimento test',-7,'EUR',"
                "'CARD_PAYMENT','COMPLETATO','{}')"
            )
            db.commit()
        app.account_var.set("Conto assente nel backup")
        app.import_summary.configure(state="normal")
        app.import_summary.insert("1.0", "Vecchio rapporto")
        app.anomalies.insert("", "end", values=("1", "EUR", "2", "3"))
        app.restore_database()
        dialogs.showinfo.assert_called_once()
        self.assertIn("Movimenti: 1", dialogs.askyesno.call_args.args[1])
        self.assertEqual(app.empty_archive.winfo_manager(), "")
        self.assertIn(app.account_var.get(), app.account_box["values"])
        self.assertEqual(app.account_var.get(), "Tutti i conti")
        self.assertIn("Conto ripristinato", app.account_box["values"])
        self.assertTrue(any("-7.00 EUR" in card.cget("text") for card in app.cards.winfo_children()))
        movement, = app.table.get_children()
        self.assertEqual(app.table.set(movement, "description"), "Movimento test")
        supplier, = app.suppliers_table.get_children()
        self.assertEqual(app.suppliers_table.item(supplier, "values")[0], "Fornitore test")
        item, = app.categories_table.get_children()
        self.assertEqual(app.categories_table.item(item, "values")[0], "Salvata")
        self.assertEqual(app.import_summary.get("1.0", "end-1c"), "")
        self.assertFalse(app.anomalies.get_children())
        self.assertIn("Filtro conto bancario non valido ignorato", app.status_var.get())
