import tempfile
import unittest
import csv
import sqlite3
from contextlib import closing
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from unittest.mock import patch

from contaflow.store import Store
from services.finance import FinanceService
from services import subcategories as sub


class SubcategoryTests(unittest.TestCase):
    def setUp(self):
        folder = self.enterContext(tempfile.TemporaryDirectory())
        self.service = FinanceService(Store(Path(folder)/"synthetic.db"))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)
        self.category = self.service.create_category("Alimentazione")
        self.a = sub.create(self.db,self.category,"Colazione")
        self.b = sub.create(self.db,self.category,"Pranzo")

    def summary(self,start="2026-04-01",end="2026-04-30"):
        return next(r for r in sub.report(self.db,start,end) if r["type"]=="subtotale_categoria" and r["currency"]=="EUR")

    def test_legacy_and_partial_conflict_without_double_count(self):
        with self.db:
            self.db.execute("INSERT INTO budgets(year,month,category_id,currency,amount,amount_minor) VALUES(2026,4,?,'EUR',300,30000)",(self.category,))
        self.assertEqual(self.summary()["budget"],Decimal("-300.00"))
        sub.save_budget(self.db,self.a,2026,4,"EUR","-100")
        row = self.summary()
        self.assertEqual(row["budget"],Decimal("-100.00"))
        self.assertIn("Budget parziale",row["warning"])
        self.assertIn("Conflitto legacy",row["warning"])
        self.assertEqual(row["legacy_exact"],Fraction(-300))
        sub.save_budget(self.db,self.b,2026,4,"EUR","0")
        self.assertNotIn("Budget parziale",self.summary()["warning"])
        rows = sub.report(self.db,"2026-04-01","2026-04-30")
        self.assertEqual(next(r for r in rows if r.get("subcategory_id")==self.b and r["currency"]=="EUR")["budget"],Decimal("0.00"))
        self.assertEqual(self.summary()["budget"],Decimal("-100.00"))

    def test_unrounded_additivity_and_rounding_difference(self):
        for identifier in (self.a,self.b):
            sub.save_budget(self.db,identifier,2026,4,"EUR","-100")
        intervals = [("2026-04-01","2026-04-10"),("2026-04-11","2026-04-20"),("2026-04-21","2026-04-30")]
        self.assertEqual(sum((self.summary(a,b)["budget_exact"] for a,b in intervals),Fraction()),Fraction(-200))
        self.assertEqual(self.summary(*intervals[0])["budget"],Decimal("-66.67"))
        self.assertEqual(self.summary(*intervals[0])["rounding_difference"],Decimal("-0.01"))

    def test_month_lengths_year_boundary_and_currencies(self):
        for year,month in ((2023,2),(2024,2),(2026,4),(2026,1),(2025,12),(2026,1)):
            sub.save_budget(self.db,self.a,year,month,"EUR","-100")
        sub.save_budget(self.db,self.a,2026,1,"CHF","-200")
        for year,month,days in ((2023,2,28),(2024,2,29),(2026,4,30),(2026,1,31)):
            first=f"{year:04d}-{month:02d}-01"
            last=f"{year:04d}-{month:02d}-{days:02d}"
            total=self.summary(first,last)
            self.assertEqual(total["budget_exact"],Fraction(-100))
        rows=sub.report(self.db,"2025-12-31","2026-01-01")
        euro=next(r for r in rows if r["type"]=="subtotale_categoria" and r["currency"]=="EUR")
        self.assertEqual(euro["budget_exact"],Fraction(-200,31))
        self.assertEqual({r["currency"] for r in rows},{"EUR","CHF"})

    def test_three_rows_show_rounding_difference_without_adjustment(self):
        third=sub.create(self.db,self.category,"Cena")
        for identifier in (self.a,self.b,third):
            sub.save_budget(self.db,identifier,2026,4,"EUR","-100")
        rows=sub.report(self.db,"2026-04-01","2026-04-10")
        details=[r for r in rows if r["type"]=="dettaglio" and r["currency"]=="EUR"]
        total=self.summary("2026-04-01","2026-04-10")
        self.assertEqual([r["budget"] for r in details],[Decimal("-33.33")]*3)
        self.assertEqual(total["budget"],Decimal("-100.00"))
        self.assertEqual(total["rounding_difference"],Decimal("-0.01"))

    def test_no_budget_differs_from_zero_and_income_is_positive(self):
        self.assertIsNone(self.summary()["budget"])
        sub.save_budget(self.db,self.a,2026,4,"EUR","0")
        self.assertEqual(self.summary()["budget"],Decimal("0.00"))
        income=self.service.create_category("Entrate","entrata")
        salary=sub.create(self.db,income,"Stipendio")
        sub.save_budget(self.db,salary,2026,4,"EUR","100")
        with self.db:
            self.db.execute("INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,category_id,subcategory_id) VALUES(1,'2026-04-01','Stipendio',120,'EUR','BONIFICO','COMPLETATO','{}',?,?)",(income,salary))
        row=next(r for r in sub.report(self.db,"2026-04-01","2026-04-30") if r["type"]=="subtotale_categoria" and r["category_id"]==income and r["currency"]=="EUR")
        self.assertEqual(row["difference"],Decimal("20.00"))
        self.assertEqual(row["meaning"],"sopra budget")

    def test_category_consistency_and_audit(self):
        with self.db:
            identifier = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,category_id) "
                "VALUES(1,'2026-04-01','Test',-80,'EUR','CARD','COMPLETATO','{}',?)",(self.category,)
            ).lastrowid
        sub.assign(self.db,[identifier],self.a)
        with self.assertRaises(ValueError):
            self.service.update_category(self.category,"Alimentazione","entrata")
        other = self.service.create_category("Altro")
        with self.assertRaises(ValueError):
            self.service.update_movements([identifier],{"category_id":other})
        row = self.db.execute("SELECT category_id,subcategory_id,amount FROM transactions WHERE id=?",(identifier,)).fetchone()
        self.assertEqual(tuple(row),(self.category,self.a,-80))
        self.assertTrue(self.service.movement_audit(identifier))
        sub.assign(self.db,[identifier],None)
        self.service.update_movements([identifier],{"category_id":other})
        self.assertIsNone(self.db.execute("SELECT subcategory_id FROM transactions WHERE id=?",(identifier,)).fetchone()[0])

    def test_non_ripartito_and_signs(self):
        with self.db:
            self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,category_id) "
                "VALUES(1,'2026-04-01','Test',-80,'EUR','CARD','COMPLETATO','{}',?)",(self.category,))
        sub.save_budget(self.db,self.a,2026,4,"EUR","-100")
        rows = sub.report(self.db,"2026-04-01","2026-04-30")
        self.assertEqual(next(r for r in rows if r["type"]=="non_ripartito")["actual"],Decimal(-80))
        self.assertEqual(self.summary()["difference"],Decimal("20.00"))
        self.assertEqual(self.summary()["meaning"],"risparmio")

    def test_allocation_is_explicit_atomic_and_legacy_remains(self):
        with self.db:
            self.db.execute("INSERT INTO budgets(year,month,category_id,currency,amount,amount_minor) VALUES(2026,4,?,'EUR',100,10000)",(self.category,))
        with self.assertRaises(ValueError):
            sub.allocate_legacy(self.db,self.category,2026,4,"EUR",{self.a:"20"})
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM subcategory_budgets").fetchone()[0],0)
        sub.allocate_legacy(self.db,self.category,2026,4,"EUR",{self.a:"60",self.b:"40"})
        row = self.summary()
        self.assertEqual(row["budget"],Decimal("-100.00"))
        self.assertIn("legacy ripartito",row["warning"])
        self.assertEqual(self.db.execute("SELECT amount FROM budgets").fetchone()[0],100)
        self.assertEqual([r[0] for r in self.db.execute("SELECT amount_minor FROM subcategory_budgets ORDER BY subcategory_id")],[-6000,-4000])

    def test_subcategory_candidates_and_new_import(self):
        supplier = self.service.create_supplier("SHOP",["SHOP"])
        sub.associate(self.db,supplier,[self.a,self.b])
        self.assertEqual(set(sub.candidates(self.service.store,"SHOP",supplier)),{self.a,self.b})
        filename = Path(self.service.store.path).parent / "statement.csv"
        with filename.open("w",encoding="utf-8",newline="") as handle:
            writer=csv.writer(handle)
            writer.writerow(("Tipo","Data di inizio","Data di completamento","Descrizione","Importo","Valuta","Costo","State","Saldo"))
            writer.writerow(("CARD","2026-04-01","2026-04-01","SHOP","-10","EUR","0","COMPLETATO","90"))
        self.service.import_revolut(filename,"Revolut EUR")
        row = self.service.movements()[0]
        self.assertIsNone(row["subcategory_id"])
        self.assertEqual(row["classification_status"],"proposto")
        sub.associate(self.db,supplier,[self.a,self.b],habitual=self.b)
        self.assertEqual(sub.candidates(self.service.store,"SHOP",supplier),[self.b])
        filename.write_text(filename.read_text().replace("2026-04-01","2026-04-02"),encoding="utf-8")
        self.service.import_revolut(filename,"Revolut EUR")
        row = self.service.movements()[0]
        self.assertEqual(row["subcategory_id"],self.b)
        self.assertEqual(row["category_id"],self.category)

    def test_alias_and_confirmed_manual_rule_and_preserve_history(self):
        supplier = self.service.create_supplier("SHOP",["SHOP"])
        alias = self.service.supplier_aliases(supplier)[0]["id"]
        sub.associate(self.db,supplier,[self.a,self.b])
        sub.associate(self.db,supplier,[self.a],alias_id=alias)
        self.assertEqual(sub.candidates(self.service.store,"SHOP",supplier),[self.a])
        with self.db:
            identifier = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,category_id) "
                "VALUES(1,'2026-04-01','SHOP',-1,'EUR','CARD','COMPLETATO','{}',?)",(self.category,)
            ).lastrowid
            other = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json,category_id) "
                "VALUES(1,'2026-04-02','SHOP',-1,'EUR','CARD','COMPLETATO','{}',?)",(self.category,)
            ).lastrowid
        sub.assign(self.db,[identifier],self.b,remember=True,normalize=self.service.store.normalize_description)
        self.assertEqual(sub.candidates(self.service.store,"SHOP",supplier),[self.b])
        self.assertIsNone(self.db.execute("SELECT subcategory_id FROM transactions WHERE id=?",(other,)).fetchone()[0])
        self.assertTrue(any(row["field"]=="regola_sottovoce" for row in self.service.movement_audit(identifier)))

    def test_gui_csv_formula_injection_and_row_types(self):
        from contaflow.app import App
        from tkinter import ttk
        unsafe_category = self.service.create_category("=Pericoloso")
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        sub.create(self.db,self.category,"=Test")
        sub.create(self.db,unsafe_category,"Sottovoce")
        sub.save_budget(self.db,self.a,2026,4,"EUR","-100")
        target = Path(self.service.store.path).parent/"synthetic.csv"
        with patch("contaflow.subcategories.simpledialog.askstring",side_effect=["2026-04-01","2026-04-30"]):
            app.subcategory_panel.report()
        win = next(w for w in app.subcategory_panel.winfo_children() if w.winfo_class()=="Toplevel")
        with patch("contaflow.subcategories.filedialog.asksaveasfilename",return_value=str(target)):
            next(w for w in win.winfo_children() if isinstance(w,ttk.Button)).invoke()
        with target.open(encoding="utf-8-sig",newline="") as handle:
            rows = list(csv.DictReader(handle,delimiter=";"))
        self.assertIn("subtotale_categoria",{r["tipo riga"] for r in rows})
        self.assertIn("'=Test",{r["sottovoce"] for r in rows})
        self.assertIn("'=Pericoloso",{r["categoria"] for r in rows})
        self.assertTrue(any("Budget parziale" in r["avviso"] for r in rows))
        self.assertTrue(all(r["dal"]=="2026-04-01" and r["al"]=="2026-04-30" for r in rows))

    def test_gui_preset_trimestre_uses_full_calendar_period(self):
        from contaflow.app import App
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        with patch("contaflow.subcategories.simpledialog.askstring",return_value="trimestre"), \
             patch("contaflow.subcategories.simpledialog.askinteger",side_effect=[2026,2]):
            app.subcategory_panel.report_preset()
        win = next(w for w in app.subcategory_panel.winfo_children() if w.winfo_class()=="Toplevel")
        self.assertIn("2026-04-01",win.title())
        self.assertIn("2026-06-30",win.title())

    def test_gui_and_csv_report_same_unadjusted_rounding(self):
        from contaflow.app import App
        from tkinter import ttk, Text
        third = sub.create(self.db,self.category,"Cena")
        for identifier in (self.a,self.b,third):
            sub.save_budget(self.db,identifier,2026,4,"EUR","-100")
        app = App(self.service)
        app.withdraw()
        self.addCleanup(app.destroy)
        with patch("contaflow.subcategories.simpledialog.askstring",side_effect=["2026-04-01","2026-04-10"]):
            app.subcategory_panel.report()
        win = next(w for w in app.subcategory_panel.winfo_children() if w.winfo_class()=="Toplevel")
        frame = next(w for w in win.winfo_children() if isinstance(w,ttk.Frame))
        view = next(w for w in frame.winfo_children() if isinstance(w,Text)).get("1.0","end")
        self.assertIn("Budget -100,00",view)
        self.assertIn("budget -0,01",view)
        target=Path(self.service.store.path).parent/"rounding.csv"
        with patch("contaflow.subcategories.filedialog.asksaveasfilename",return_value=str(target)):
            next(w for w in win.winfo_children() if isinstance(w,ttk.Button)).invoke()
        with target.open(encoding="utf-8-sig",newline="") as handle:
            rows=list(csv.DictReader(handle,delimiter=";"))
        details=[r for r in rows if r["tipo riga"]=="dettaglio" and r["categoria"]=="Alimentazione" and r["valuta"]=="EUR"]
        total=next(r for r in rows if r["tipo riga"]=="subtotale_categoria" and r["categoria"]=="Alimentazione" and r["valuta"]=="EUR")
        self.assertEqual([r["budget"] for r in details],["-33,33"]*3)
        self.assertEqual(total["budget"],"-100,00")
        self.assertIn("budget -0,01",total["differenza da arrotondamento"])
        self.assertIn("non sommare",total["nota"])


class MigrationTests(unittest.TestCase):
    def test_failed_v8_migration_rolls_back_with_recoverable_backup(self):
        from db.migrations import MigrationError
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"synthetic.db"
            with patch("db.migrations.LATEST_SCHEMA_VERSION",7):
                old=Store(path)
            old.db.close()
            def fail(db):
                db.execute("ALTER TABLE transactions ADD COLUMN temporary_test TEXT")
                raise RuntimeError("Errore sintetico")
            with patch("db.migrations._migration_8",side_effect=fail):
                with self.assertRaises(MigrationError):
                    Store(path)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0],7)
                self.assertNotIn("temporary_test",{r[1] for r in db.execute("PRAGMA table_info(transactions)")})
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
            self.assertTrue(list((Path(folder)/"backups").glob("*v7*")))

    def test_v7_to_v8_preserves_five_movements_and_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"synthetic.db"
            with patch("db.migrations.LATEST_SCHEMA_VERSION",7):
                old=Store(path)
            with old.db:
                for i,amount in enumerate((500,-100,-5,-1,-0.4)):
                    old.db.execute("INSERT INTO transactions(fingerprint,account_id,occurred_at,description,amount,fee,currency,kind,status,source_json,classification_status) VALUES(?,1,'2026-01-01','Test',?,?,'EUR','CARD','COMPLETATO','{}','classificato')",
                                   (f"test-{i}",amount,0.5 if i==0 else 0))
            before=[tuple(r) for r in old.db.execute("SELECT fingerprint,amount,fee,classification_status FROM transactions ORDER BY id")]
            old.db.close()
            for _ in range(2):
                new=Store(path)
                with closing(new.db):
                    self.assertEqual(before,[tuple(r) for r in new.db.execute("SELECT fingerprint,amount,fee,classification_status FROM transactions ORDER BY id")])
                    self.assertEqual(FinanceService(new).summary("Revolut EUR")[0]["balance"],Decimal("393.10"))
            backup=next((Path(folder)/"backups").glob("*v7*"))
            with closing(sqlite3.connect(backup)) as db:
                self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0],"ok")
                self.assertEqual(db.execute("SELECT version FROM schema_version").fetchone()[0],7)
