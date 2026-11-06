"""Smoke UI-1: soltanto campioni sintetici. Salta se non è disponibile un display."""
import tkinter as tk
import unittest

from prototypes.ui.sample_data import synthetic_snapshot
from prototypes.ui.run import UI1


class UISmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        try:
            probe = tk.Tk()
            probe.withdraw()
            probe.destroy()
        except tk.TclError as exc:
            raise unittest.SkipTest(f"Display non disponibile: {exc}") from exc

    def test_synthetic_fixture_readonly_and_native_gui(self):
        snapshot = synthetic_snapshot()
        self.assertEqual(len(snapshot.movements), 9)
        self.assertEqual({x["currency"] for x in snapshot.movements}, {"EUR", "CHF"})
        app = UI1(snapshot, "nativo")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update_idletasks()
        app.show_screen("movements")
        self.assertEqual(len(app.table.get_children()), 9)
        self.assertEqual(app.count_label.cget("text"), "9 di 9 movimenti")
        app.search_var.set("POS BAR")
        app.refresh()
        self.assertEqual(len(app.table.get_children()), 1)
        app.reset_filters()
        self.assertEqual(len(app.table.get_children()), 9)
        app.show_screen("overview")
        self.assertEqual(app.active, "overview")


if __name__ == "__main__":
    unittest.main()
