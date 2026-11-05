import csv
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from contaflow.store import Store
from services.finance import FinanceService


class ImportWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(self.folder / "test.db"))
        self.addCleanup(self.service.store.db.close)
        self.path = self.folder / "synthetic.csv"
        self.write_csv()

    def write_csv(self, currency="EUR"):
        with self.path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("Tipo","Data di inizio","Data di completamento","Descrizione",
                             "Importo","Valuta","Costo","State","Saldo"))
            for i in range(2):
                writer.writerow(("CARD","2026-01-01 09:00:00","2026-01-01 09:00:00",
                                 f"TEST {i}","-10",currency,"0","COMPLETATO",str(90-i*10)))

    def test_preview_snapshot_and_compatible_fingerprints(self):
        preview = self.service.preview_import(self.path, "Revolut EUR")
        self.assertEqual(preview.importable, 2)
        self.assertEqual(self.service.movements(), [])
        self.path.write_text("file changed after preview", encoding="utf-8")
        result = self.service.confirm_import(preview)
        self.assertEqual(result["imported"], 2)
        old_identity = hashlib.sha256(
            "Revolut EUR|2026-01-01 09:00:00|CARD|TEST 0|-10.0|EUR|0.0".encode()
        ).hexdigest()
        self.assertIn(old_identity, [r["fingerprint"] for r in self.service.movements()])
        self.assertEqual(self.service.confirm_import(preview)["duplicates"], 2)

    def test_chf_and_rollback_mid_import(self):
        self.write_csv("CHF")
        preview = self.service.preview_import(self.path, "Revolut CHF")
        original = self.service.store.classify_description
        with patch.object(self.service.store, "classify_description",
                          side_effect=[original("TEST"), RuntimeError("mid import")]):
            with self.assertRaisesRegex(RuntimeError, "mid import"):
                self.service.confirm_import(preview)
        self.assertEqual(self.service.movements(), [])
        self.assertEqual(self.service.import_batches(), [])
        self.assertEqual(self.service.confirm_import(preview)["imported"], 2)

    def test_cancel_dependencies_and_reimport_preserves_audit_identity(self):
        preview = self.service.preview_import(self.path, "Revolut EUR")
        batch = self.service.confirm_import(preview)["batch_id"]
        first = self.service.movements()[0]["id"]
        self.service.update_movements([first], {"notes": "Manuale"})
        with self.assertRaisesRegex(ValueError, "conferma specifica"):
            self.service.cancel_batch(batch)
        self.assertEqual(len(self.service.movements()), 2)
        self.service.cancel_batch(batch, True)
        self.assertEqual(self.service.movements(), [])
        self.assertTrue(self.service.movement_audit(first))
        self.service.confirm_import(preview)
        self.assertGreater(min(r["id"] for r in self.service.movements()), first)

    def test_cancel_without_dependencies(self):
        preview = self.service.preview_import(self.path, "Revolut EUR")
        result = self.service.confirm_import(preview)
        self.service.cancel_batch(result["batch_id"])
        self.assertEqual(self.service.movements(), [])
        self.assertEqual(self.service.import_batches()[0]["result"], "cancelled")

    def test_gui_import_requires_confirmation(self):
        from contaflow.app import App
        app = App(self.service)
        app.withdraw()
        app.account_var.set("Revolut EUR")
        self.addCleanup(app.destroy)
        with patch("contaflow.app.filedialog.askopenfilename", return_value=str(self.path)):
            with patch("contaflow.app.messagebox.askyesno", return_value=False) as confirmation:
                app.import_csv()
            confirmation.assert_called_once()
            self.assertEqual(self.service.movements(), [])
            with patch("contaflow.app.messagebox.askyesno", return_value=True):
                app.import_csv()
        self.assertEqual(len(self.service.movements()), 2)

    def test_non_finite_or_out_of_range_amounts_are_rejected(self):
        original = self.path.read_bytes()
        for invalid in (b"NaN", b"Infinity", b"1e999"):
            self.path.write_bytes(original.replace(b",-10,", b"," + invalid + b","))
            with self.assertRaises(ValueError):
                self.service.preview_import(self.path, "Revolut EUR")
            self.assertEqual(self.service.movements(), [])
