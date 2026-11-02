import tempfile
import unittest
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService


class ClassificationTests(unittest.TestCase):
    def test_unknown_description_is_never_classified_automatically(self):
        with tempfile.TemporaryDirectory() as folder:
            store=Store(Path(folder)/'test.db')
            result=store.classify_description('UNKNOWN SHOP 991122')
            self.assertEqual(result['status'],'in_attesa')
            self.assertIsNone(result['category_id'])
            store.db.close()

    def test_confirmed_alias_is_reused_on_later_classification(self):
        with tempfile.TemporaryDirectory() as folder:
            service=FinanceService(Store(Path(folder)/'test.db'))
            service.create_category('Spese casa')
            category=service.categories()[0]['id']
            supplier=service.create_supplier('Synthetic Shop',habitual_category_id=category)
            service.store.confirm_supplier_alias(supplier,'CARD PAYMENT Synthetic Shop REF 991122',category)
            result=service.store.classify_description('CARD PAYMENT Synthetic Shop REF 887766')
            self.assertEqual(result['status'],'classificato')
            self.assertEqual(result['origin'],'confermata')
            self.assertEqual(result['supplier_id'],supplier)
            self.assertEqual(result['category_id'],category)
            service.store.db.close()


if __name__ == '__main__':
    unittest.main()
