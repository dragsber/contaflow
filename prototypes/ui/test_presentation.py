"""Test senza grafica né database personale per il prototipo UI-1."""
import ast
from datetime import date
from decimal import Decimal
from pathlib import Path
import unittest

from prototypes.ui.presentation import (
    currency_totals, date_it, filter_rows, label_for_balance,
    money, period_bounds, shown_count,
)


class TestPresentation(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"description": "POS BAR CAMPIONE", "account": "Revolut EUR", "occurred_at": "2026-11-03",
             "classification_status": "proposto", "supplier": None, "category": "Alimentari", "subcategory": None},
            {"description": "Pagamento CH", "account": "Revolut CHF", "occurred_at": "2026-11-04",
             "classification_status": "classificato", "supplier": None, "category": "Mobilità", "subcategory": "Treno"},
        ]

    def test_money_format(self):
        self.assertEqual(money(Decimal("-1234.56"), "EUR"), "-1.234,56 €")
        self.assertEqual(money("1234.56", "CHF"), "+1.234,56 CHF")
        self.assertEqual(money("0.00", "EUR"), "0,00 €")

    def test_filters_and_counter(self):
        self.assertEqual(shown_count(filter_rows(self.rows), self.rows), "2 di 2 movimenti")
        selected = filter_rows(self.rows, search="bar", status="proposto")
        self.assertEqual(shown_count(selected, self.rows), "1 di 2 movimenti")
        self.assertEqual(len(filter_rows(self.rows, account="Revolut CHF")), 1)

    def test_currency_isolation(self):
        result = currency_totals([
            {"currency": "EUR", "balance": Decimal("300.10")},
            {"currency": "CHF", "balance": Decimal("200.50")},
            {"currency": "EUR", "balance": Decimal("10.00")},
        ])
        self.assertEqual(result, {"EUR": Decimal("310.10"), "CHF": Decimal("200.50")})

    def test_balance_semantics(self):
        summary = {"balance": Decimal("393.10"), "bank_balance": None}
        self.assertEqual(label_for_balance(summary, None)[0], "Variazione netta dei movimenti")
        summary["bank_balance"] = Decimal("1393.10")
        self.assertEqual(label_for_balance(summary, None)[0], "Saldo calcolato")
        self.assertEqual(label_for_balance(summary, {"status": "da verificare"})[0], "Saldo calcolato")
        label = label_for_balance(summary, {"status": "confermata", "as_of": "2026-11-05"})[0]
        self.assertTrue(label.startswith("Saldo riconciliato"))

    def test_period(self):
        self.assertEqual(period_bounds("Questo mese", date(2026, 11, 6)), ("2026-11-01", "2026-11-06"))
        self.assertEqual(date_it("2026-11-05 12:00:00"), "05/11/2026")

    def test_isolation_static(self):
        """Controllo statico, non una prova runtime dell'intero progetto."""
        root = Path(__file__).resolve().parent
        for name in ("run.py", "sample_data.py"):
            code = (root / name).read_text(encoding="utf-8").lower()
            self.assertNotIn("os.environ['localappdata'", code)
            self.assertNotIn("getenv('localappdata'", code)
        tree = ast.parse((root / "sample_data.py").read_text(encoding="utf-8"))
        self.assertTrue(any(isinstance(item, ast.FunctionDef) and item.name == "synthetic_snapshot" for item in tree.body))


if __name__ == "__main__":
    unittest.main()
