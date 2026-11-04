import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService


class BudgetTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.folder / "test.db"
        self.service = FinanceService(Store(self.path))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)
        self.category = self.service.create_category("Spesa")

    def movement(self, amount, currency="EUR", state="classificato"):
        with self.db:
            self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,fee,kind,"
                "status,source_json,category_id,classification_status) "
                "VALUES(1,'2026-01-01','TEST',?,?,0.1,'CARD','COMPLETATO','{}',?,?)",
                (amount, currency, self.category, state),
            )

    def test_exact_budget_and_currency_separation(self):
        self.service.save_budget(2026, 1, self.category, "EUR", "100,10")
        self.service.save_budget(2026, 1, self.category, "CHF", "80,20")
        self.movement(-10.1)
        self.movement(-20.2, "CHF")
        self.movement(-500, state="trasferimento")
        self.movement(-100, state="escluso")
        rows, totals = self.service.budget_report(2026, 1)
        self.assertEqual(len(rows), 2)
        by_currency = {r["currency"]:r for r in rows}
        self.assertEqual(by_currency["EUR"]["planned"], Decimal("100.10"))
        self.assertEqual(by_currency["EUR"]["actual"], Decimal("10.1"))
        self.assertEqual(totals["CHF"]["expenses"], Decimal("20.2"))
        self.assertEqual(self.db.execute("SELECT amount_minor FROM budgets WHERE currency='EUR'").fetchone()[0], 10010)
        self.service.save_budget(2026, 1, self.category, "EUR", "110")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM budgets").fetchone()[0], 2)
        with self.assertRaises(ValueError):
            self.service.save_budget(2026, 1, self.category, "EUR", "1,001")

    def test_gui_budget_save_and_reload(self):
        from contaflow.app import App
        from contextlib import closing
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        panel = app.budget
        panel.category.set(next(iter(panel.categories)))
        panel.amount.set("123,45")
        panel.save()
        item, = panel.table.get_children()
        self.assertEqual(panel.table.set(item, "planned"), "123,45 €")
        with closing(Store(self.path).db) as reopened:
            self.assertEqual(reopened.execute("SELECT amount_minor FROM budgets").fetchone()[0], 12345)

    def test_cancelled_transfer_restores_previous_classification(self):
        with self.db:
            outgoing = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json) "
                "VALUES(1,'2026-01-01','Out',-10,'EUR','TRANSFER','COMPLETATO','{}')"
            ).lastrowid
            incoming = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,"
                "classification_status,category_id) "
                "VALUES(3,'2026-01-01','In',10,'EUR','TRANSFER','COMPLETATO','{}','classificato',?)",
                (self.category,),
            ).lastrowid
            batch = self.db.execute("INSERT INTO importations(file_name,account_id) VALUES('test',1)").lastrowid
            self.db.execute("UPDATE transactions SET importation_id=? WHERE id=?", (batch,outgoing))
        self.service.link_movements(outgoing,incoming,"trasferimento")
        self.service.cancel_batch(batch,True)
        remaining = self.service.movements()[0]
        self.assertEqual(remaining["classification_status"], "classificato")
        self.assertEqual(remaining["category_id"],self.category)
