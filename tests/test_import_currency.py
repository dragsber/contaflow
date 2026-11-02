import csv
import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store


FIELDS = [
    'Tipo', 'Prodotto', 'Data di inizio', 'Data di completamento',
    'Descrizione', 'Importo', 'Costo', 'Valuta', 'State', 'Saldo',
]


class CurrencyImportTest(unittest.TestCase):
    def write_csv(self, path, rows):
        with path.open('w', newline='', encoding='utf-8-sig') as handle:
            writer = csv.writer(handle)
            writer.writerow(FIELDS)
            writer.writerows(rows)

    def row(self, description, currency, status='COMPLETATO'):
        return [
            'Pagamento', 'Attuale', '2026-01-01 10:00:00',
            '2026-01-01 10:01:00', description, '-10.00', '0.00',
            currency, status, '90.00',
        ]

    def test_chf_csv_imports_into_chf_account(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.db')
            path = Path(directory) / 'chf.csv'
            self.write_csv(path, [self.row('Synthetic CHF purchase', 'CHF')])
            self.assertEqual(store.import_revolut(path, 'Revolut CHF'), (1, 0))
            transaction = store.recent()[0]
            self.assertEqual(transaction['currency'], 'CHF')
            store.db.close()

    def test_currency_mismatch_rejects_entire_import(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.db')
            path = Path(directory) / 'mixed.csv'
            self.write_csv(path, [
                self.row('Synthetic EUR purchase', 'EUR'),
                self.row('Synthetic CHF purchase', 'CHF'),
            ])
            with self.assertRaisesRegex(ValueError, 'incompatibile'):
                store.import_revolut(path, 'Revolut EUR')
            self.assertEqual(store.recent(), [])
            store.db.close()


if __name__ == '__main__':
    unittest.main()
