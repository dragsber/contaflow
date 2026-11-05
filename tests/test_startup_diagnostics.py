import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from contaflow.app import App
from contaflow.diagnostics import report
from contaflow.runtime import log_startup_event
from contaflow.store import Store
from db.migrations import LATEST_SCHEMA_VERSION, MigrationError
from services.finance import FinanceService


class StartupTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {"LOCALAPPDATA": folder}))
        os.environ.pop("CONTAFLOW_DATA_DIR", None)
        self.path = Path(folder) / "ContaFlow" / "contaflow.sqlite3"
        self.path.parent.mkdir()

    def test_existing_invalid_database_is_rejected_without_writes(self):
        for kind in ("corrupt", "unrelated", "future"):
            with self.subTest(kind=kind):
                if self.path.exists():
                    self.path.unlink()
                if kind == "corrupt":
                    self.path.write_bytes(b"not sqlite")
                elif kind == "unrelated":
                    with closing(sqlite3.connect(self.path)) as db:
                        db.execute("CREATE TABLE unrelated(x)")
                else:
                    with closing(Store().db) as db, db:
                        db.execute("UPDATE schema_version SET version=999")
                before = self.path.read_bytes()
                with self.assertRaises(MigrationError) as failure:
                    Store()
                self.assertIn(str(self.path), str(failure.exception))
                self.assertEqual(self.path.read_bytes(), before)

    def seed(self):
        with patch("db.migrations.LATEST_SCHEMA_VERSION", 7):
            store = Store()
        with closing(store.db) as db, db:
            supplier = db.execute("INSERT INTO suppliers(name) VALUES('Fornitore sintetico segreto')").lastrowid
            category = db.execute("INSERT INTO categories(name) VALUES('Categoria sintetica segreta')").lastrowid
            for i, amount in enumerate((500, -100, -5, -1, -0.4)):
                db.execute(
                    "INSERT INTO transactions(fingerprint,account_id,occurred_at,description,"
                    "amount,fee,currency,kind,status,source_json,classification_status,supplier_id,category_id) "
                    "VALUES(?,2,'2020-01-01','TEST-PRIVATO IT60X0542811101000000123456',"
                    "?,?,'CHF','CARD','COMPLETATO','{}','classificato',?,?)",
                    (f"synthetic-{i}", amount, 0.5 if i == 0 else 0, supplier, category),
                )
            db.execute("UPDATE accounts SET name='Conto sintetico EUR', currency='EUR' WHERE id=2")
            db.execute("UPDATE transactions SET currency='EUR'")

    def test_startup_shows_old_movements_on_second_account(self):
        self.seed()
        for _ in range(2):
            service = FinanceService()
            with closing(service.store.db):
                self.assertEqual(len(service.movements()), 5)
                self.assertEqual(service.summary("Conto sintetico EUR")[0]["balance"], Decimal("393.10"))
                app = App(service)
                try:
                    app.withdraw()
                    self.assertEqual(len(app.register.rows), 5)
                    self.assertEqual(app.register.count.cget("text"), "5 di 5 movimenti")
                    app.account_var.set("Revolut EUR")
                    app.refresh_all()
                    self.assertEqual(app.register.count.cget("text"), "0 di 5 movimenti")
                    self.assertIn("li nascondono", app.register.filter_summary.cget("text"))
                    app.register.reset()
                    app.register.filters["supplier"].set("fornitore non più esistente")
                    app.register.refresh()
                    self.assertIn("ignorati", app.register.filter_summary.cget("text"))
                    self.assertEqual(app.register.count.cget("text"), "5 di 5 movimenti")
                    self.assertIn("4 di 4", app.account_count.cget("text"))
                finally:
                    app.update_idletasks()
                    app.destroy()

    def test_report_preview_and_export(self):
        self.seed()
        service = FinanceService()
        with closing(service.store.db):
            app = App(service)
            try:
                app.withdraw()
                target = self.path.parent / "diagnostica.txt"
                with patch("tkinter.filedialog.asksaveasfilename", return_value=str(target)):
                    app.show_diagnostics()
                    preview = next(child for child in app.winfo_children() if child.winfo_class() == "Toplevel")
                    text = next(child for child in preview.winfo_children() if child.winfo_class() == "Text")
                    self.assertFalse(target.exists())
                    self.assertEqual(text.cget("state"), "disabled")
                    button = next(child for child in preview.winfo_children() if child.winfo_class() == "TButton")
                    button.invoke()
                self.assertEqual(target.read_text(encoding="utf-8"), text.get("1.0", "end-1c"))
            finally:
                app.update_idletasks()
                app.destroy()

    def test_wrong_missing_override_does_not_create_another_database(self):
        self.seed()
        wrong = self.path.parent / "wrong"
        with patch.dict(os.environ, {"CONTAFLOW_DATA_DIR": str(wrong)}):
            with self.assertRaisesRegex(MigrationError, "Archivio predefinito presente"):
                Store()
        self.assertFalse(wrong.exists())

    def test_migration_reads_committed_wal_and_report_contains_only_metadata(self):
        self.seed()
        with closing(sqlite3.connect(self.path)) as writer:
            self.assertEqual(writer.execute("PRAGMA journal_mode=WAL").fetchone()[0], "wal")
            writer.execute("PRAGMA wal_autocheckpoint=0")
            writer.execute("UPDATE transactions SET description=description || ' WAL'")
            writer.commit()
            self.assertGreater(Path(str(self.path) + "-wal").stat().st_size, 0)
            service = FinanceService()
            with closing(service.store.db):
                self.assertTrue(all(row["description"].endswith(" WAL") for row in service.movements()))
                log_startup_event("Avvio applicazione", RuntimeError("CONTENUTO-RISERVATO"))
                content = report(service.store, ["Ricerca"])
                self.assertIn(f"schema_version: {LATEST_SCHEMA_VERSION}", content)
                self.assertIn("transactions: 5", content)
                self.assertIn("-wal: presente", content)
                self.assertIn("PRAGMA integrity_check: ok", content)
                self.assertIn("Avvio applicazione: errore applicativo", content)
                for private in ("TEST-PRIVATO", "IT60X0542811101000000123456", "393.10",
                                "Fornitore sintetico segreto", "Categoria sintetica segreta",
                                "Conto sintetico EUR", "CONTENUTO-RISERVATO"):
                    self.assertNotIn(private, content)
