"""Dati totalmente sintetici in TemporaryDirectory; lettura con SQLite mode=ro."""

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
import sqlite3
import tempfile


@dataclass
class SyntheticSnapshot:
    accounts: list
    summaries: list
    reconciliations: dict
    movements: list


def build_fixture(path):
    """La scrittura è consentita solo su un archivio campione in cartella temporanea."""
    from contaflow.store import Store
    from services.accounts import save_opening
    from services.reconciliation import preview_reconciliation, save_reconciliation

    path = Path(path)
    if not path.parent.exists() or path.name != "campione-ui1.sqlite3":
        raise ValueError("Percorso del campione non autorizzato")
    store = Store(path)
    try:
        db = store.db
        ids = {row["name"]: row["id"] for row in db.execute("SELECT id,name FROM accounts")}
        with db:
            groceries = db.execute("INSERT INTO categories(name,category_type) VALUES('Alimentari','uscita')").lastrowid
            transport = db.execute("INSERT INTO categories(name,category_type) VALUES('Mobilità','uscita')").lastrowid
            salary = db.execute("INSERT INTO categories(name,category_type) VALUES('Stipendio','entrata')").lastrowid
            sub = db.execute("INSERT INTO subcategories(name,category_id) VALUES('Spesa settimanale',?)", (groceries,)).lastrowid
            supplier = db.execute("INSERT INTO suppliers(name) VALUES('ALIMENTARI DEMO')").lastrowid
            samples = (
                ("Revolut EUR", "2026-11-02 08:30:00", "Accredito fittizio", "2400.00", "0", "EUR", "TRANSFER", "classificato", salary, None, None),
                ("Revolut EUR", "2026-11-03 18:25:00", "Alimentari demo", "-56.40", "0", "EUR", "CARD", "classificato", groceries, sub, supplier),
                ("Revolut EUR", "2026-11-04 09:12:00", "POS BAR ESEMPIO", "-8.90", "0", "EUR", "CARD", "proposto", groceries, None, None),
                ("Revolut EUR", "2026-11-05 11:42:00", "Ricarica trasporti", "-25.00", "0", "EUR", "CARD", "in_attesa", None, None, None),
                ("Revolut CHF", "2026-11-03 13:30:00", "Pagamento campione CHF", "-35.20", "0.80", "CHF", "CARD", "classificato", transport, None, None),
                ("Revolut CHF", "2026-11-05 08:20:00", "Accredito campione CHF", "180.00", "0", "CHF", "TRANSFER", "classificato", salary, None, None),
                ("BPER EUR", "2026-11-01 16:00:00", "Pagamento sintetico", "-70.00", "0", "EUR", "CARD", "in_attesa", None, None, None),
                ("BPER EUR", "2026-11-05 12:00:00", "Bonifico dimostrativo", "400.00", "0", "EUR", "TRANSFER", "classificato", salary, None, None),
                ("Cassa contanti", "2026-11-04 12:00:00", "Biglietto esempio", "-12.00", "0", "EUR", "CASH", "classificato", transport, None, None),
            )
            for n, (account, when, description, amount, fee, currency, kind, state, category, subcategory, merchant) in enumerate(samples):
                db.execute(
                    "INSERT INTO transactions(fingerprint,account_id,occurred_at,description,amount,fee,currency,kind,status,source_json,"
                    "classification_status,category_id,subcategory_id,supplier_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (f"ui1-synth-{n}", ids[account], when, description, amount, fee, currency,
                     kind, "COMPLETATO", "{}", state, category, subcategory, merchant),
                )
        save_opening(db, ids["Revolut EUR"], "2026-10-31", "1120.00")
        save_opening(db, ids["Revolut CHF"], "2026-10-31", "500.00")
        from services.accounts import opening_balance, balance_movements, calculated_balance
        opening = opening_balance(db, ids["Revolut CHF"])
        actual = calculated_balance(opening, balance_movements(db, ids["Revolut CHF"], after="2026-10-31"))
        save_reconciliation(db, preview_reconciliation(db, ids["Revolut CHF"], "2026-11-05", str(actual)))
    finally:
        store.db.close()


def read_fixture(path):
    """Legge il campione tramite servizi esistenti, senza utilizzare il DB predefinito."""
    from services.accounts import list_accounts, balance_movements, opening_balance, calculated_balance
    from services.reconciliation import latest_reconciliation
    from services.register import movements
    from services.transfers import account_summary

    class ReadOnlyStore:
        def __init__(self, db):
            self.db = db

    db = sqlite3.connect(Path(path).absolute().as_uri() + "?mode=ro", uri=True)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        accounts = [dict(row) for row in list_accounts(db)]
        summaries = account_summary(ReadOnlyStore(db))
        reconciliations = {}
        for summary in summaries:
            opening = opening_balance(db, summary["id"])
            summary["bank_balance"] = (
                calculated_balance(opening, balance_movements(db, summary["id"], after=opening["as_of"]))
                if opening is not None else None
            )
            reconciliations[summary["id"]] = latest_reconciliation(db, summary["id"])
        entries = [dict(row) for row in movements(db)]
        return SyntheticSnapshot(accounts, summaries, reconciliations, entries)
    finally:
        db.close()


def synthetic_snapshot():
    with tempfile.TemporaryDirectory(prefix="contaflow-ui1-") as temp:
        path = Path(temp) / "campione-ui1.sqlite3"
        build_fixture(path)
        return read_fixture(path)
