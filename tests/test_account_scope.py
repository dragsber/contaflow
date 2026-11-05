import csv
import sqlite3
import tempfile
import unittest
from contextlib import closing
from decimal import Decimal
from pathlib import Path

from contaflow.store import Store
from db.migrations import LATEST_SCHEMA_VERSION
from services.accounts import archive_account, balance_movements, save_account, save_opening
from services.finance import FinanceService


FIELDS = ['Tipo','Prodotto','Data di inizio','Data di completamento',
          'Descrizione','Importo','Costo','Valuta','State','Saldo']


def csv_file(folder, currency='EUR'):
    path = Path(folder) / 'statement.csv'
    with path.open('w', encoding='utf-8-sig', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(FIELDS)
        writer.writerow(['Pagamento','Attuale','2026-01-01 10:00:00',
                         '2026-01-01 10:01:00','Synthetic expense',
                         '-12.00','1.00',currency,'COMPLETATO','87.00'])
    return path


class AccountScopeTests(unittest.TestCase):
    def test_account_rename_preserves_csv_identity_and_archives_without_loss(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.db")
            with closing(store.db) as db:
                service = FinanceService(store)
                csv_path = csv_file(folder)
                service.import_revolut(csv_path, "Revolut EUR")
                identifier = db.execute("SELECT id FROM accounts WHERE name='Revolut EUR'").fetchone()[0]
                fingerprint = service.movements()[0]["fingerprint"]
                save_account(db, "Conto rinominato", "REVOLUT", "EUR", "Istituto sintetico", "", identifier)
                preview = service.preview_import(csv_path, "Conto rinominato")
                self.assertEqual(preview.duplicates, 1)
                self.assertEqual(service.confirm_import(preview)["imported"], 0)
                archive_account(db, identifier, True)
                with self.assertRaises(ValueError):
                    service.preview_import(csv_path, "Conto rinominato")
                self.assertEqual(service.movements("Conto rinominato")[0]["fingerprint"], fingerprint)

    def test_opening_balance_day_pending_and_fees(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / "test.db")
            with closing(store.db) as db:
                service = FinanceService(store)
                identifier = save_account(db, "Conto sintetico", "UNKNOWN", "EUR", "", "")
                self.assertIsNone(service.summary("Conto sintetico")[0]["bank_balance"])
                with db:
                    db.executemany(
                        "INSERT INTO transactions(account_id,occurred_at,description,amount,fee,currency,kind,status,source_json) "
                        "VALUES(?,?,'Sintetico',?,?,'EUR','CARD',?,'{}')",
                        [(identifier, day, amount, fee, status) for day, amount, fee, status in (
                            ("2026-01-01T23:00", 500, 0.5, "COMPLETATO"),
                            ("2026-01-02", -100, 0, "COMPLETATO"), ("2026-01-03", -5, 0, "COMPLETATO"),
                            ("2026-01-04", -1, 0, "COMPLETATO"), ("2026-01-05", -0.4, 0, "COMPLETATO"),
                            ("2026-01-06", -99, 0, "IN SOSPESO"),
                        )],
                    )
                self.assertEqual(service.summary("Conto sintetico")[0]["balance"], Decimal("393.10"))
                save_opening(db, identifier, "2026-01-01", "50,00")
                item = service.summary("Conto sintetico")[0]
                self.assertEqual(item["balance"], Decimal("393.10"))
                self.assertEqual(item["bank_balance"], Decimal("-56.40"))
                self.assertEqual(len(balance_movements(db, identifier, after="2026-01-01")), 4)
                save_opening(db, identifier, "2026-01-01", "60")
                self.assertEqual(service.summary("Conto sintetico")[0]["bank_balance"], Decimal("-46.40"))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE field='saldo_iniziale'").fetchone()[0], 2)
    def test_existing_database_migrates_and_sets_providers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT UNIQUE,currency TEXT NOT NULL)')
            db.execute("INSERT INTO accounts(name,currency) VALUES('Revolut EUR','EUR')")
            db.commit()
            db.close()
            store = Store(path)
            with closing(store.db):
                self.assertEqual(store.db.execute("SELECT provider FROM accounts WHERE name='Revolut EUR'").fetchone()[0], 'REVOLUT')
                self.assertEqual({row['provider'] for row in store.accounts()}, {'REVOLUT','BPER','CASH'})
                self.assertEqual(store.db.execute('SELECT version FROM schema_version').fetchone()[0], LATEST_SCHEMA_VERSION)

    def test_account_filter_and_balance_are_scoped(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.db')
            path = csv_file(folder)
            store.import_revolut(path, 'Revolut EUR')
            self.assertEqual(len(store.recent('Revolut EUR')), 1)
            self.assertEqual(store.recent('Revolut CHF'), [])
            self.assertEqual(store.summary('Revolut EUR')[0]['balance'], -13.0)
            self.assertEqual(store.summary('Revolut CHF')[0]['balance'], 0)
            store.db.close()

    def test_import_rejects_non_revolut_and_wrong_currency_without_writes(self):
        for account, currency in [('BPER EUR','EUR'),('Cassa contanti','EUR'),
                                  ('Revolut CHF','EUR')]:
            with self.subTest(account=account), tempfile.TemporaryDirectory() as folder:
                store = Store(Path(folder) / 'test.db')
                with self.assertRaises(ValueError):
                    store.import_revolut(csv_file(folder,currency), account)
                self.assertEqual(store.db.execute('SELECT COUNT(*) FROM transactions').fetchone()[0], 0)
                store.db.close()

    def test_matching_revolut_account_accepts_csv(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder) / 'test.db')
            result = store.import_revolut_detailed(csv_file(folder,'CHF'),'Revolut CHF')
            self.assertEqual(result['imported'], 1)
            self.assertEqual(store.recent('Revolut CHF')[0]['currency'], 'CHF')
            store.db.close()


if __name__ == '__main__':
    unittest.main()
