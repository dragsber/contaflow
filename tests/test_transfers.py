import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from contaflow.store import Store
from services.finance import FinanceService


class TransferTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(self.folder / "test.db"))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)

    def movement(self, amount, account=1, currency="EUR", fee=0):
        with self.db:
            return self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,fee,"
                "kind,status,source_json) VALUES(?,'2026-01-01','Test',?,?,?,'TRANSFER','COMPLETATO','{}')",
                (account, amount, currency, fee),
            ).lastrowid

    def test_internal_transfer_and_separate_fees(self):
        outgoing = self.movement(-100, fee=1)
        incoming = self.movement(100, account=3)
        self.service.link_movements(outgoing, incoming, "trasferimento")
        rows = self.service.summary()
        self.assertEqual(sum(r["income"] for r in rows), Decimal(0))
        self.assertEqual(sum(r["expenses"] for r in rows), Decimal(0))
        self.assertEqual(rows[0]["balance"], Decimal(-101))
        self.assertEqual(rows[0]["fees"], Decimal(1))
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 2)
        with self.assertRaises(ValueError):
            self.service.update_movements([outgoing], {"classification_status": "classificato"})
        self.service.unlink_movement(outgoing)
        self.assertEqual(self.service.summary("Revolut EUR")[0]["expenses"], Decimal(100))

    def test_cross_currency_keeps_original_amounts_without_rate(self):
        outgoing = self.movement(-100, account=2, currency="CHF")
        incoming = self.movement(90)
        self.service.link_movements(outgoing, incoming, "giroconto")
        self.assertIsNone(self.db.execute("SELECT exchange_rate FROM transfers").fetchone()[0])
        self.assertEqual({r["currency"] for r in self.service.movements()}, {"CHF", "EUR"})

    def test_candidates_do_not_link_and_exclude_same_account_and_other_currency(self):
        from services.transfers import transfer_candidates

        outgoing = self.movement(-100, fee=1)
        self.movement(100)
        self.movement(100, account=2, currency="CHF")
        valid = self.movement(100, account=3)
        late = self.movement(100, account=3)
        with self.db:
            self.db.execute("UPDATE transactions SET occurred_at='2026-01-10' WHERE id=?", (late,))
        self.assertEqual([row["id"] for row in transfer_candidates(self.db, outgoing)], [valid])
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transfers").fetchone()[0], 0)
        self.service.link_movements(outgoing, valid, "trasferimento")
        self.assertEqual(transfer_candidates(self.db, outgoing), [])

    def test_refund_reduces_expense_and_cannot_exceed_original(self):
        original = self.movement(-100)
        refund = self.movement(40)
        self.service.link_movements(original, refund, "rimborso")
        self.assertEqual(self.service.summary("Revolut EUR")[0]["expenses"], Decimal(60))
        another = self.movement(80)
        with self.assertRaises(ValueError):
            self.service.link_movements(original, another, "rimborso")
        self.service.unlink_movement(refund)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM refunds").fetchone()[0], 0)

    def test_cancellation_requires_link_confirmation(self):
        outgoing = self.movement(-100)
        incoming = self.movement(100, account=3)
        with self.db:
            batch = self.db.execute("INSERT INTO importations(file_name,account_id) VALUES('Test',1)").lastrowid
            self.db.execute("UPDATE transactions SET importation_id=? WHERE id=?", (batch, outgoing))
        self.service.link_movements(outgoing, incoming, "trasferimento")
        with self.assertRaises(ValueError):
            self.service.cancel_batch(batch)
        self.service.cancel_batch(batch, True)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transfers").fetchone()[0], 0)
        self.assertEqual(self.db.execute("SELECT classification_status FROM transactions").fetchone()[0], "in_attesa")

    def test_gui_link_selected_movements(self):
        from contaflow.app import App
        from tkinter import ttk
        outgoing = self.movement(-20)
        incoming = self.movement(20, account=3)
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        app.account_var.set("Tutti i conti")
        app.refresh_all()
        app.table.selection_set(str(outgoing), str(incoming))
        app.register.link_selected()
        win = next(w for w in app.register.winfo_children() if w.winfo_class() == "Toplevel")
        next(w for w in win.winfo_children() if isinstance(w, ttk.Button)).invoke()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transfers").fetchone()[0], 1)

    def test_transfer_category_is_consistent_with_dashboard(self):
        movement = self.movement(-20)
        category = self.service.create_category("Giroconti", "trasferimento")
        self.service.update_movements([movement], {"category_id":category})
        self.assertEqual(self.service.movements()[0]["classification_status"], "trasferimento")
        self.assertEqual(self.service.summary("Revolut EUR")[0]["expenses"], Decimal(0))
