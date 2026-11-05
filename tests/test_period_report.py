import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService


class PeriodReportTests(unittest.TestCase):
    def setUp(self):
        self.folder = self.enterContext(tempfile.TemporaryDirectory())
        self.service = FinanceService(Store(Path(self.folder) / "synthetic.db"))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)
        self.service.ledger.import_chart(({"code":"001","description":"Test"},), "sintetico")
        self.ledger_id = self.service.ledger.accounts()[0]["id"]

    def test_partial_months_leap_year_and_inclusive_dates(self):
        with self.db:
            self.db.execute("INSERT INTO ledger_budgets VALUES(2024,1,?,'EUR',-31000)",(self.ledger_id,))
            self.db.execute("INSERT INTO ledger_budgets VALUES(2024,2,?,'EUR',-29000)",(self.ledger_id,))
        with self.db:
            for when, amount in (("2024-01-14",-100),("2024-01-15",-10),
                                 ("2024-02-15",-20),("2024-02-16",-100)):
                self.db.execute(
                    "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,fee,"
                    "kind,status,source_json,ledger_account_id) VALUES(1,?,'Test',?,'EUR',0,"
                    "'CARD','COMPLETATO','{}',?)", (when,amount,self.ledger_id))
        row, = self.service.ledger.period_report("2024-01-15","2024-02-15")
        self.assertEqual(row["budget"], Decimal("-320.00"))
        self.assertEqual(row["actual"], Decimal("-30"))
        self.assertEqual(row["difference"], Decimal("290.00"))
        self.assertEqual(row["missing_months"], 0)

    def test_missing_budget_and_separate_currencies(self):
        with self.db:
            self.db.execute("INSERT INTO ledger_budgets VALUES(2026,1,?,'EUR',-3100)",(self.ledger_id,))
            self.db.execute("INSERT INTO ledger_budgets VALUES(2026,1,?,'CHF',-6200)",(self.ledger_id,))
        rows = self.service.ledger.period_report("2026-01-16","2026-02-02")
        self.assertEqual({r["currency"]:r["budget"] for r in rows},
                         {"EUR":Decimal("-16.00"),"CHF":Decimal("-32.00")})
        self.assertTrue(all(r["missing_months"] == 1 for r in rows))
        with self.assertRaises(ValueError):
            self.service.ledger.period_report("2026-02-01","2026-01-01")
