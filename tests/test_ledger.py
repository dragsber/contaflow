import csv
import sqlite3
import tempfile
import unittest
import zipfile
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from contaflow.store import Store
from db.migrations import MigrationError, _preserved_data, _verify_preserved
from services.finance import FinanceService
from services.ledger import manual_account
from adapters.chart import mapped_records


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.folder / "synthetic.db"
        self.service = FinanceService(Store(self.path))
        self.addCleanup(self.service.store.db.close)
        self.db = self.service.store.db

    def records(self):
        return ({"code":"0010","description":"Descrizione esatta ","category":"","supplier":""},
                {"code":"0020","description":"Altro conto","category":"","supplier":""})

    def movement(self, description="SHOP", amount=-1):
        with self.db:
            return self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json) "
                "VALUES(1,'2026-01-01',?,?,'EUR','CARD','COMPLETATO','{}')",(description,amount),
            ).lastrowid

    def test_empty_archive_and_manual_creation_gate(self):
        self.assertEqual(self.service.ledger.accounts(),[])
        with self.assertRaises(ValueError):
            manual_account(self.db,"001","Manuale",explicit_request=True)
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        with self.assertRaises(ValueError):
            manual_account(self.db,"0030","Manuale")
        identifier = manual_account(self.db,"0030","Manuale",explicit_request=True)
        self.assertEqual(self.db.execute("SELECT origin FROM ledger_accounts WHERE id=?",(identifier,)).fetchone()[0],"manuale")

    def test_idempotent_import_exact_codes_and_no_inferred_category(self):
        self.service.create_category("Descrizione esatta ")
        before = self.movement()
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        rows = self.service.ledger.accounts()
        self.assertEqual([r["code"] for r in rows],["0010","0020"])
        self.assertEqual(rows[0]["description"],"Descrizione esatta ")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ledger_categories").fetchone()[0],0)
        self.assertIsNone(self.db.execute("SELECT ledger_account_id FROM transactions WHERE id=?",(before,)).fetchone()[0])
        changes = ({"code":"0010","description":"Nuova descrizione"},)
        self.assertIn("Modifica",self.service.ledger.preview(changes)[0])
        self.assertEqual(self.service.ledger.accounts()[0]["description"],"Descrizione esatta ")

    def test_explicit_category_many_to_many_and_supplier_links(self):
        category = self.service.create_category("Categoria")
        records = tuple({**r,"category":"Categoria","supplier":"Supplier"} for r in self.records())
        self.service.ledger.import_chart(records,"synthetic.xlsx")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM ledger_categories WHERE category_id=?",(category,)).fetchone()[0],2)
        supplier = self.service.suppliers()[0]["id"]
        self.assertEqual(len(self.service.ledger.associations(supplier)),2)
        self.assertEqual(len(self.service.ledger.candidates("Unknown",supplier)),2)
        ids = [r["id"] for r in self.service.ledger.accounts()]
        self.service.ledger.associate(supplier,ids,habitual=ids[1])
        self.assertEqual(self.service.ledger.candidates("Unknown",supplier),[ids[1]])

    def test_assignment_audit_rule_alias_and_history_unchanged(self):
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        identifier = self.service.ledger.accounts()[0]["id"]
        supplier = self.service.create_supplier("SHOP",aliases=["SHOP"])
        alias = self.service.supplier_aliases(supplier)[0]["id"]
        self.service.ledger.associate(supplier,[identifier],alias_id=alias)
        self.assertEqual(self.service.ledger.candidates("SHOP",supplier),[identifier])
        old, other = self.movement(),self.movement()
        self.service.ledger.assign([old],identifier,remember=True)
        self.assertTrue(self.service.movement_audit(old))
        self.assertIsNone(self.db.execute("SELECT ledger_account_id FROM transactions WHERE id=?",(other,)).fetchone()[0])
        self.assertEqual(len(self.service.movements(ledger=identifier)),1)
        self.assertEqual(self.service.movements(ledger=identifier)[0]["ledger_code"],"0010")
        self.assertEqual(len(self.service.movements(ledger="unassigned")),1)
        other_account = self.service.ledger.accounts()[1]["id"]
        self.service.ledger.assign([old],other_account,remember=True)
        self.assertEqual(self.service.ledger.candidates("SHOP",supplier),[other_account])

    def test_automatic_new_import_and_ambiguous_supplier(self):
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        supplier = self.service.create_supplier("SHOP",aliases=["SHOP"])
        ids = [r["id"] for r in self.service.ledger.accounts()]
        self.service.ledger.associate(supplier,ids)
        path = self.folder/"statement.csv"
        with path.open("w",encoding="utf-8",newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("Tipo","Data di inizio","Data di completamento","Descrizione","Importo","Valuta","Costo","State","Saldo"))
            writer.writerow(("CARD","2026-01-01","2026-01-01","SHOP","-1","EUR","0","COMPLETATO","99"))
        self.service.import_revolut(path,"Revolut EUR")
        row = self.service.movements()[0]
        self.assertIsNone(row["ledger_account_id"])
        self.assertEqual(row["classification_status"],"proposto")
        self.service.ledger.associate(supplier,ids,ids[0])
        path.write_text(path.read_text().replace("2026-01-01","2026-01-02"),encoding="utf-8")
        self.service.import_revolut(path,"Revolut EUR")
        self.assertEqual(self.service.movements()[0]["ledger_account_id"],ids[0])

    def test_report_retains_unassigned_and_separates_currency(self):
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        identifier = self.service.ledger.accounts()[0]["id"]
        first = self.movement(amount=-10)
        self.movement(amount=5)
        self.service.ledger.assign([first],identifier)
        with self.db:
            self.db.execute("INSERT INTO ledger_budgets VALUES(2026,1,?,'EUR',-2001)",(identifier,))
        with self.assertRaises(ValueError):
            self.service.ledger.save_budget(2026,1,identifier,"EUR","-20,01")
        rows = self.service.ledger.report(2026,1)
        self.assertEqual({r["code"] for r in rows},{"0010","Non assegnato"})
        assigned = next(r for r in rows if r["code"]=="0010")
        self.assertEqual(assigned["budget"],Decimal("-20.01"))
        self.assertEqual(assigned["actual"],Decimal("-10"))

    def test_read_mapping_csv_and_numeric_xlsx_zeros(self):
        path = self.folder/"chart.csv"
        path.write_text("Codice;Descrizione\n0001;Esatta \n",encoding="utf-8")
        records = mapped_records(path,"",{"code":"A","description":"B"})
        self.assertEqual(records[0]["code"],"0001")
        self.assertEqual(records[0]["description"],"Esatta ")
        path = self.folder/"chart.xlsx"
        with zipfile.ZipFile(path,"w") as book:
            book.writestr("xl/workbook.xml",'<workbook xmlns:r="urn:r"><sheets><sheet name="Piano" r:id="r1"/></sheets></workbook>')
            book.writestr("xl/_rels/workbook.xml.rels",'<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            book.writestr("xl/styles.xml",'<styleSheet><numFmts><numFmt numFmtId="164" formatCode="0000"/></numFmts><cellXfs><xf numFmtId="164"/></cellXfs></styleSheet>')
            book.writestr("xl/worksheets/sheet1.xml",'<worksheet><sheetData><row r="2"><c r="A2"><v>1</v></c><c r="B2" t="inlineStr"><is><t>Test</t></is></c></row></sheetData></worksheet>')
        records = mapped_records(path,"Piano",{"code":"A","description":"B"})
        self.assertEqual(records[0]["code"],"0001")

    def test_gui_archive_filter_and_manual_assignment(self):
        from contaflow.app import App
        from tkinter import ttk
        self.service.ledger.import_chart(self.records(),"synthetic.xlsx")
        first = self.movement()
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        self.assertEqual(len(app.ledger_panel.table.get_children()),2)
        app.table.selection_set(str(first))
        app.register.assign_ledger()
        win = next(w for w in app.winfo_children() if w.winfo_class()=="Toplevel")
        box = next(w for w in win.winfo_children() if isinstance(w,ttk.Combobox))
        box.set(box["values"][1])
        with patch("contaflow.ledger.messagebox.askyesno",return_value=True):
            next(w for w in win.winfo_children() if isinstance(w,ttk.Button)).invoke()
        self.assertEqual(app.table.set(str(first),"ledger"),"0010")
        app.register.filters["ledger"].set("0010 — Descrizione esatta ")
        app.register.refresh()
        self.assertEqual(len(app.table.get_children()),1)


class LedgerMigrationTests(unittest.TestCase):
    def test_migration_preserves_five_movements_393_10_and_reopens_twice(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"old.db"
            with patch("db.migrations.LATEST_SCHEMA_VERSION",6):
                old = Store(path)
            with old.db:
                for index,amount in enumerate((500,-100,-5,-1,Decimal("-0.40"))):
                    old.db.execute(
                        "INSERT INTO transactions(fingerprint,account_id,occurred_at,description,amount,fee,currency,kind,status,source_json,classification_status) "
                        "VALUES(?,1,'2026-01-01','Originale',?,?,'EUR','CARD','COMPLETATO','{}','classificato')",
                        (f"immutable-{index}",str(amount),"0.50" if index==0 else "0"),
                    )
                old.db.execute("INSERT INTO categories(name) VALUES('Originale')")
                old.db.execute("INSERT INTO suppliers(name) VALUES('Originale')")
                old.db.execute("INSERT INTO supplier_aliases(normalized_alias,supplier_id,confirmed) VALUES('ORIGINALE',1,1)")
                old.db.execute("INSERT INTO audit(transaction_id,field,new_value) VALUES(1,'test','originale')")
            before = _preserved_data(old.db)
            self.assertEqual(FinanceService(old).summary("Revolut EUR")[0]["balance"],Decimal("393.10"))
            old.db.close()
            for _ in range(2):
                reopened = Store(path)
                with closing(reopened.db):
                    _verify_preserved(reopened.db,before)
                    summary = FinanceService(reopened).summary("Revolut EUR")[0]
                    self.assertEqual(summary["balance"],Decimal("393.10"))
            backups = list((Path(folder)/"backups").glob("*v6*"))
            self.assertTrue(backups)
            with closing(sqlite3.connect(backups[0])) as copy:
                self.assertEqual(copy.execute("PRAGMA integrity_check").fetchone()[0],"ok")
                self.assertEqual(copy.execute("SELECT version FROM schema_version").fetchone()[0],6)

    def test_migration_data_change_is_detected_and_rolled_back(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"old.db"
            with patch("db.migrations.LATEST_SCHEMA_VERSION",6):
                old = Store(path)
            old.db.close()
            def wrong(db):
                db.execute("UPDATE accounts SET name='Corrotto' WHERE id=1")
            with patch("db.migrations._migration_7",side_effect=wrong):
                with self.assertRaises(MigrationError):
                    Store(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT name FROM accounts WHERE id=1").fetchone()[0],"Revolut EUR")
                self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0],6)

    def test_stale_preview_is_rejected_without_catalog_changes(self):
        with tempfile.TemporaryDirectory() as folder:
            store = Store(Path(folder)/"test.db")
            with closing(store.db):
                service = FinanceService(store)
                records = ({"code":"0010","description":"Test"},)
                signature = service.ledger.signature()
                service.create_category("Modifica concorrente")
                with self.assertRaisesRegex(ValueError,"cambiate"):
                    service.ledger.import_chart(records,"synthetic.xlsx",signature)
                self.assertEqual(service.ledger.accounts(),[])
