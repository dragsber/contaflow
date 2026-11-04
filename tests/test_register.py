import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService
from services.register import money


class RegisterTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(self.folder / "register.db"))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)
        self.category = self.service.create_category("Spesa test")
        self.supplier = self.service.create_supplier("Negozio test")
        with self.db:
            for i in range(150):
                self.db.execute(
                    "INSERT INTO transactions(account_id,occurred_at,description,amount,"
                    "currency,fee,kind,status,source_json,category_id,supplier_id,classification_status)"
                    " VALUES(1,?,?,?,?,0,'CARD','COMPLETATO','{}',?,?,?)",
                    ("2026-01-02 09:30:00", f"Test {i}", -i, "EUR", self.category,
                     self.supplier, "proposto" if i % 2 else "classificato"),
                )

    def test_combined_filters_and_all_rows(self):
        self.assertEqual(len(self.service.movements()), 150)
        rows = self.service.movements("Revolut EUR", search="Test",
                                      start="2026-01-01", end="2026-01-02",
                                      category=self.category, supplier=self.supplier,
                                      status="da_classificare", sort="amount", descending=False)
        self.assertEqual(len(rows), 75)
        self.assertEqual(rows[0]["amount"], -149)
        self.assertEqual(self.service.movements("Revolut CHF"), [])
        self.assertEqual(self.service.movements(start="2026-02-01"), [])
        for kwargs in ({"sort": "SQL"}, {"start": "errata"}, {"start":"2026-02-01", "end":"2026-01-01"}):
            with self.assertRaises(ValueError):
                self.service.movements(**kwargs)

    def test_money_italian_decimal(self):
        self.assertEqual(money("-1234.56", "EUR"), "-1.234,56 €")
        self.assertEqual(money("2.50", "CHF"), "2,50 CHF")

    def test_real_gui_register(self):
        from contaflow.app import App
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        register = app.register
        self.assertEqual(len(app.table.get_children()), 150)
        register.unclassified()
        self.assertEqual(len(app.table.get_children()), 75)
        register.order("amount")
        first = app.table.get_children()[0]
        app.table.selection_set(first)
        register.show_detail()
        self.assertIn("Dati bancari originali", register.detail.get("1.0", "end"))
        self.assertTrue(app.table.cget("xscrollcommand"))
        self.assertTrue(app.table.cget("yscrollcommand"))
        register.reset()
        self.assertEqual(len(app.table.get_children()), 150)
