import csv
import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store


class ReconciliationTest(unittest.TestCase):
    def test_balance_accounts_for_fees_and_reports_anomaly(self):
        fields = ['Tipo', 'Prodotto', 'Data di inizio', 'Data di completamento',
                  'Descrizione', 'Importo', 'Costo', 'Valuta', 'State', 'Saldo']
        rows = [
            ['Pagamento', 'Attuale', '2026-01-01 09:00:00', '2026-01-01 09:01:00',
             'Synthetic A', '-10.00', '0.50', 'EUR', 'COMPLETATO', '89.50'],
            ['Pagamento', 'Attuale', '2026-01-02 09:00:00', '2026-01-02 09:01:00',
             'Synthetic B', '-5.00', '0.00', 'EUR', 'COMPLETATO', '84.50'],
            ['Pagamento', 'Attuale', '2026-01-03 09:00:00', '',
             'Synthetic cancellation', '-2.00', '0.00', 'EUR', 'OPERAZIONE ANNULLATA', ''],
            ['Pagamento', 'Attuale', '2026-01-04 09:00:00', '2026-01-04 09:01:00',
             'Synthetic mismatch', '-3.00', '0.00', 'EUR', 'COMPLETATO', '82.50'],
        ]
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'test.db')
            statement = Path(directory) / 'statement.csv'
            with statement.open('w', encoding='utf-8-sig', newline='') as handle:
                writer = csv.writer(handle)
                writer.writerow(fields)
                writer.writerows(rows)
            try:
                self.assertEqual(store.reconcile_revolut_csv(statement), [
                    {'row': 5, 'currency': 'EUR', 'expected_delta': '-3.00', 'actual_delta': '-2.00'}])
            finally:
                store.db.close()


if __name__ == '__main__':
    unittest.main()
