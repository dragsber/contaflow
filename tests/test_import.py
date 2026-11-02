import csv, tempfile, unittest
from pathlib import Path
from contaflow.store import Store

class ImportTest(unittest.TestCase):
 def test_completed_fee_cancel_duplicate(self):
  with tempfile.TemporaryDirectory() as d:
   db=Store(Path(d)/'t.db'); p=Path(d)/'x.csv'
   fields=['Tipo','Prodotto','Data di inizio','Data di completamento','Descrizione','Importo','Costo','Valuta','State','Saldo']
   rows=[['Pagamento','Attuale','2026-01-01 10:00:00','2026-01-01 10:01:00','Synthetic shop','-10.00','0.50','EUR','COMPLETATO','89.50'],['Pagamento','Attuale','2026-01-02 10:00:00','','Canceled synthetic','-4.00','0','EUR','OPERAZIONE ANNULLATA','']]
   with p.open('w',newline='',encoding='utf-8-sig') as f:w=csv.writer(f);w.writerow(fields);w.writerows(rows)
   try:
    self.assertEqual(db.import_revolut(p),(1,1));self.assertEqual(db.import_revolut(p),(0,2));self.assertEqual(db.recent()[0]['amount']-db.recent()[0]['fee'],-10.5)
    self.assertEqual(db.recent()[0]['fee'],0.5)
    self.assertEqual(db.summary()[0]['balance'],-10.5)
   finally:
    db.db.close()
if __name__=='__main__': unittest.main()
