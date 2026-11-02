import csv
import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService


class AlphaServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "synthetic.sqlite3")
        self.service = FinanceService(self.store)

    def tearDown(self):
        self.store.db.close()
        self.temp.cleanup()

    def test_supplier_category_edit_and_alias(self):
        category_id = self.service.create_category("Spesa test", "uscita")
        supplier_id = self.service.create_supplier("Negozio test", ["SHOP 42"], category_id)
        self.service.update_supplier(supplier_id, "Negozio demo", category_id)
        supplier = self.service.suppliers()[0]
        self.assertEqual(supplier["name"], "NEGOZIO DEMO")
        aliases = self.service.supplier_aliases(supplier_id)
        self.assertEqual(aliases[0]["normalized_alias"], "SHOP 42")
        self.service.remove_supplier_alias(aliases[0]["id"])
        self.assertEqual(self.service.supplier_aliases(supplier_id), [])
        renamed_category_id = self.service.create_category("Altro", "entrata")
        self.service.update_category(renamed_category_id, "Altro demo", "entrata")
        self.assertEqual(
            self.service.categories()[-1]["name"], "Spesa test"
        )
        self.service.archive_category(renamed_category_id)
        self.assertNotIn(renamed_category_id, [row["id"] for row in self.service.categories()])

    def test_confirmed_movement_association_reused_on_import(self):
        category_id = self.service.create_category("Alimentari test", "uscita")
        supplier_id = self.service.create_supplier("ACME MARKET", (), category_id)
        account_id = self.store.db.execute(
            "SELECT id FROM accounts WHERE name='Revolut EUR'"
        ).fetchone()["id"]
        with self.store.db:
            movement_id = self.store.db.execute(
                "INSERT INTO transactions(fingerprint,account_id,occurred_at,description,"
                "amount,currency,fee,kind,status,source_json,classification_status) "
                "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                ("synthetic-manual", account_id, "2026-01-01", 
                 "CARD PAYMENT ACME MARKET REF:123", -8.5, "EUR", 0.0,
                 "CARD_PAYMENT", "COMPLETATO", "{}", "in_attesa"),
            ).lastrowid
        self.service.reconcile_movement(movement_id, supplier_id, category_id)
        saved = self.store.db.execute(
            "SELECT classification_status,classification_origin FROM transactions WHERE id=?",
            (movement_id,),
        ).fetchone()
        self.assertEqual((saved["classification_status"], saved["classification_origin"]),
                         ("classificato", "confermata"))
        csv_path = Path(self.temp.name) / "synthetic_revolut.csv"
        headers = ["Tipo", "Data di inizio", "Data di completamento", "Descrizione",
                   "Importo", "Valuta", "State", "Costo", "Saldo"]
        with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=headers)
            writer.writeheader()
            writer.writerow({
                "Tipo": "CARD_PAYMENT", "Data di inizio": "2026-01-02 09:00:00",
                "Data di completamento": "2026-01-02 09:00:00",
                "Descrizione": "CARD PAYMENT ACME MARKET REF:999",
                "Importo": "-4.25", "Valuta": "EUR", "State": "COMPLETATO",
                "Costo": "0", "Saldo": "87.25",
            })
        result = self.service.import_revolut(str(csv_path), "Revolut EUR")
        self.assertEqual(result["imported"], 1)
        self.assertEqual(result["classified"], 1)
        imported = self.store.db.execute(
            "SELECT supplier_id,category_id,classification_status,classification_origin "
            "FROM transactions WHERE description LIKE '%REF:999'"
        ).fetchone()
        self.assertEqual(imported["supplier_id"], supplier_id)
        self.assertEqual(imported["category_id"], category_id)
        self.assertEqual(imported["classification_status"], "classificato")
        self.assertEqual(imported["classification_origin"], "confermata")


if __name__ == "__main__":
    unittest.main()
