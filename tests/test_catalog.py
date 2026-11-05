import tempfile
import unittest
import zipfile
from pathlib import Path

from contaflow.store import Store
from services.finance import FinanceService
from services.catalog_import import apply_associations, association_plan, read_catalog


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(self.folder / "test.db"))
        self.addCleanup(self.service.store.db.close)

    def test_supplier_alternatives_archive_and_alias_collision(self):
        category = self.service.create_category("Abituale")
        other = self.service.create_category("Alternativa")
        supplier = self.service.save_supplier(" TEST SHOP ", category, "CARD PAYMENT SHOP", "Nota", [other])
        self.assertEqual(self.service.suppliers()[0]["notes"], "Nota")
        self.assertEqual(self.service.supplier_categories(supplier), [other])
        self.assertEqual(self.service.category_suppliers(other)[0][0], "TEST SHOP")
        with self.assertRaises(ValueError):
            self.service.save_supplier("test shop")
        another = self.service.save_supplier("Altro")
        with self.assertRaises(ValueError):
            self.service.add_supplier_alias(another, "CARD PAYMENT SHOP")
        self.service.archive_supplier(supplier)
        self.assertNotIn(supplier, [r["id"] for r in self.service.suppliers()])
        self.assertEqual(len(self.service.suppliers(include_archived=True)), 2)
        self.assertEqual(self.service.store.classify_description("CARD PAYMENT SHOP")["status"], "in_attesa")

    def test_structured_csv_import_and_duplicate_rollback(self):
        path = self.folder / "catalog.csv"
        path.write_text("fornitore;categoria;tipo;alias;note\nSHOP;Spesa;uscita;SHOP;Test\n", encoding="utf-8")
        records = read_catalog(path)
        self.assertEqual(self.service.import_catalog(records), 1)
        with self.assertRaises(ValueError):
            self.service.import_catalog(records)
        self.assertEqual(len(self.service.suppliers()), 1)
        self.assertEqual(len(self.service.categories()), 1)

    def test_structured_xlsx_layout_is_explicit(self):
        path = self.folder / "catalog.xlsx"
        with zipfile.ZipFile(path, "w") as book:
            book.writestr("xl/workbook.xml",
                          '<workbook xmlns:r="urn:r"><sheets><sheet name="Anagrafiche" r:id="r1"/></sheets></workbook>')
            book.writestr("xl/_rels/workbook.xml.rels",
                          '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            rows = [("fornitore", "categoria", "tipo", "alias", "note"),
                    ("TEST", "Spesa", "uscita", "TEST", "Nota")]
            xmlrows = []
            for number, row in enumerate(rows, 1):
                xmlrows.append("<row>" + "".join(
                    f'<c r="{chr(65+i)}{number}" t="inlineStr"><is><t>{value}</t></is></c>'
                    for i, value in enumerate(row)) + "</row>")
            book.writestr("xl/worksheets/sheet1.xml",
                          "<worksheet><sheetData>" + "".join(xmlrows) + "</sheetData></worksheet>")
        records = read_catalog(path)
        self.assertEqual(records[0]["fornitore"], "TEST")
        self.service.import_catalog(records)

        db = self.service.store.db
        normalize = self.service.store.normalize_description
        mapped = read_catalog(path, sheet_name="Anagrafiche", mapping={"fornitore": 1, "alias": 5})
        plan = association_plan(db, mapped, normalize)
        self.assertEqual([item[0] for item in plan], ["alias"])
        apply_associations(db, mapped, normalize, plan)
        self.assertEqual(association_plan(db, mapped, normalize), [])
        apply_associations(db, mapped, normalize, [])
        self.assertEqual(len(self.service.suppliers()), 1)
        self.assertEqual(self.service.suppliers()[0]["notes"], "Nota")

    def test_alias_edit_archive_and_distinct_future_category(self):
        normal = self.service.create_category("Consueta")
        special = self.service.create_category("Specifica")
        supplier = self.service.create_supplier("Bar sintetico", ["Bar 123", "Bar 456"], normal)
        store = self.service.store
        store.confirm_supplier_alias(supplier, "Bar 123", special)
        self.assertEqual(store.classify_description("BAR 123")["category_id"], special)
        self.assertEqual(store.classify_description("BAR 456")["category_id"], normal)
        alias = self.service.supplier_aliases(supplier)[0]["id"]
        self.service.edit_supplier_alias(alias, description="Bar nuova sigla")
        self.assertIsNone(store.classify_description("Bar 123")["supplier_id"])
        self.assertEqual(store.classify_description("Bar nuova sigla")["supplier_id"], supplier)
        self.service.edit_supplier_alias(alias, archived=True)
        self.assertIsNone(store.classify_description("Bar nuova sigla")["supplier_id"])
        self.service.edit_supplier_alias(alias, archived=False)
        self.assertEqual(store.classify_description("Bar nuova sigla")["category_id"], special)

    def test_real_supplier_editor_and_navigation(self):
        from contaflow.app import App
        from tkinter import ttk, Text, Listbox
        self.service.create_category("Categoria")
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        app.edit_supplier(new=True)
        win = next(w for w in app.winfo_children() if w.winfo_class() == "Toplevel")
        form = win.winfo_children()[0]
        entries = [w for w in form.winfo_children() if isinstance(w, ttk.Entry) and not isinstance(w, ttk.Combobox)]
        entries[0].insert(0, "Fornitore GUI")
        notes = next(w for w in form.winfo_children() if isinstance(w, Text))
        notes.insert("1.0", "Nota GUI")
        alternatives = next(w for w in form.winfo_children() if isinstance(w, Listbox))
        alternatives.selection_set(0)
        next(w for w in form.winfo_children() if isinstance(w, ttk.Button) and w.cget("text") == "Salva").invoke()
        self.assertEqual(self.service.suppliers()[0]["notes"], "Nota GUI")
        supplier = self.service.suppliers()[0]["id"]
        app.suppliers_table.selection_set(str(supplier))
        app.related_movements("supplier")
        self.assertEqual(app.tabs.select(), str(app.movements_tab))
