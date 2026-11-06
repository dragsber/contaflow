import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from contaflow.store import Store
from services import subcategories
from services.accounts import save_account, save_opening
from services.cash import record_cash_movement
from services.finance import FinanceService
from services.reconciliation import latest_reconciliation, preview_reconciliation, save_reconciliation


class AccountReconciliationTests(unittest.TestCase):
    def setUp(self):
        folder = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.service = FinanceService(Store(folder / "synthetic.db"))
        self.db = self.service.store.db
        self.addCleanup(self.db.close)
        self.cash = save_account(self.db, "Cassa sintetica", "CASH", "EUR", "", "")

    def test_reconciliation_persists_difference_and_flags_only_evidenced_duplicates(self):
        save_opening(self.db, self.cash, "2026-03-01", "100")
        record_cash_movement(self.db, self.cash, "2026-03-01", "Prima del riferimento", "-30")
        record_cash_movement(self.db, self.cash, "2026-03-02", "Pagamento", "-15")
        record_cash_movement(self.db, self.cash, "2026-03-02", "Pagamento", "-15")
        with self.db:
            self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json) "
                "VALUES(?,'2026-03-02','Sospeso',-999,'EUR','CARD','IN SOSPESO','{}')", (self.cash,),
            )
        before = [tuple(row) for row in self.db.execute("SELECT * FROM transactions ORDER BY id")]
        mismatch = preview_reconciliation(self.db, self.cash, "2026-03-02", "71.20")
        self.assertEqual(mismatch.calculated, Decimal("70"))
        self.assertEqual(mismatch.difference, Decimal("1.20"))
        self.assertEqual(mismatch.duplicates, (("2026-03-02", 2),))
        self.assertEqual(save_reconciliation(self.db, mismatch), "da verificare")
        match = preview_reconciliation(self.db, self.cash, "2026-03-02", "70")
        self.assertEqual(save_reconciliation(self.db, match), "confermata")
        self.assertEqual(latest_reconciliation(self.db, self.cash)["status"], "confermata")
        self.assertEqual(before, [tuple(row) for row in self.db.execute("SELECT * FROM transactions ORDER BY id")])
        save_opening(self.db, self.cash, "2026-03-01", "101")
        self.assertEqual(latest_reconciliation(self.db, self.cash)["status"], "da verificare")
        with self.assertRaisesRegex(ValueError, "cambiati"):
            save_reconciliation(self.db, match)

    def test_bank_to_cash_and_categorized_cash_expense(self):
        with self.db:
            bank_leg = self.db.execute(
                "INSERT INTO transactions(account_id,occurred_at,description,amount,currency,kind,status,source_json) "
                "VALUES(1,'2026-03-02','Prelievo',-60,'EUR','CARD','COMPLETATO','{}')",
            ).lastrowid
        cash_leg = record_cash_movement(self.db, self.cash, "2026-03-02", "Prelievo", "60")
        self.service.link_movements(bank_leg, cash_leg, "prelievo")
        category = self.service.create_category("Vitto")
        subcategory = subcategories.create(self.db, category, "Colazione")
        expense = record_cash_movement(self.db, self.cash, "2026-03-03", "Colazione", "-4.50", category, subcategory)
        bank = self.service.summary("Revolut EUR")[0]
        cash = self.service.summary("Cassa sintetica")[0]
        self.assertEqual((bank["balance"], bank["expenses"]), (Decimal("-60"), Decimal(0)))
        self.assertEqual((cash["balance"], cash["expenses"], cash["income"]),
                         (Decimal("55.50"), Decimal("4.50"), Decimal(0)))
        self.assertEqual(self.db.execute("SELECT subcategory_id FROM transactions WHERE id=?", (expense,)).fetchone()[0],
                         subcategory)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM transactions").fetchone()[0], 3)
        self.assertEqual(self.service.movement_audit(expense)[0]["field"], "movimento_cassa")

    def test_account_management_gui_saves_reconciliation_and_cash_movement(self):
        from contaflow.accounts import show_accounts
        from contaflow.app import App
        from tkinter import TclError, ttk

        save_opening(self.db, self.cash, "2026-03-01", "100")
        try:
            app = App(self.service)
        except TclError as error:
            if "display" in str(error).lower():
                self.skipTest(str(error))
            raise
        try:
            app.withdraw()
            show_accounts(app)
            manager = next(widget for widget in app.winfo_children() if widget.winfo_class() == "Toplevel")
            table = next(widget for widget in manager.winfo_children() if isinstance(widget, ttk.Treeview))
            actions = next(widget for widget in manager.winfo_children() if isinstance(widget, ttk.Frame))
            buttons = {widget.cget("text"): widget for widget in actions.winfo_children()}
            table.selection_set(str(self.cash))
            buttons["Riconciliazione…"].invoke()
            dialog = next(widget for widget in manager.winfo_children() if widget.winfo_class() == "Toplevel")
            dialog.grid_slaves(row=0, column=1)[0].insert(0, "2026-03-01")
            dialog.grid_slaves(row=1, column=1)[0].insert(0, "100")
            dialog.grid_slaves(row=2, column=0)[0].invoke()
            dialog.grid_slaves(row=2, column=1)[0].invoke()
            self.assertEqual(latest_reconciliation(self.db, self.cash)["status"], "confermata")
            table.selection_set(str(self.cash))
            buttons["Movimento di cassa…"].invoke()
            dialog = next(widget for widget in manager.winfo_children() if widget.winfo_class() == "Toplevel")
            for row, value in enumerate(("2026-03-02", "Uscita sintetica", "-10")):
                dialog.grid_slaves(row=row, column=1)[0].insert(0, value)
            dialog.grid_slaves(row=6, column=1)[0].invoke()
            self.assertEqual(self.service.summary("Cassa sintetica")[0]["bank_balance"], Decimal("90"))
        finally:
            app.update_idletasks()
            app.destroy()
