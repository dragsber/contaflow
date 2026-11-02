import csv
import sqlite3
import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store


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
    def test_existing_database_migrates_and_sets_providers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'legacy.db'
            db = sqlite3.connect(path)
            db.execute('CREATE TABLE accounts(id INTEGER PRIMARY KEY,name TEXT UNIQUE,currency TEXT NOT NULL)')
            db.execute("INSERT INTO accounts(name,currency) VALUES('Revolut EUR','EUR')")
            db.commit()
            db.close()
            store = Store(path)
            self.assertEqual(store.db.execute("SELECT provider FROM accounts WHERE name='Revolut EUR'").fetchone()[0], 'REVOLUT')
            self.assertEqual({row['provider'] for row in store.accounts()}, {'REVOLUT','BPER','CASH'})
            store.db.close()

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
