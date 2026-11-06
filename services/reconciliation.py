import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal

from services.accounts import _audit, balance_movements, calculated_balance, minor_units, opening_balance, parse_date


@dataclass(frozen=True)
class Reconciliation:
    account_id: int
    currency: str
    day: str
    actual_minor: int
    opening_day: str
    calculated: Decimal
    movements: tuple
    duplicates: tuple
    basis: str

    @property
    def actual(self):
        return Decimal(self.actual_minor).scaleb(-2)

    @property
    def difference(self):
        return self.actual - self.calculated


def preview_reconciliation(db, account_id, day, actual):
    day, actual_minor = parse_date(day), minor_units(actual)
    account = db.execute("SELECT currency FROM accounts WHERE id=?", (account_id,)).fetchone()
    if account is None:
        raise ValueError("Conto non trovato.")
    opening = opening_balance(db, account_id, through=day)
    if opening is None:
        raise ValueError("Imposta un saldo iniziale a una data uguale o precedente.")
    rows = tuple(balance_movements(db, account_id, after=opening["as_of"], through=day))
    keys = Counter((row["occurred_at"][:10], row["description"], Decimal(str(row["amount"]))) for row in rows)
    duplicates = tuple((key[0], count) for key, count in keys.items() if count > 1)
    basis = hashlib.sha256(json.dumps((dict(opening), [tuple(row) for row in rows]), sort_keys=True).encode()).hexdigest()
    return Reconciliation(account_id, account["currency"], day, actual_minor, opening["as_of"],
                          calculated_balance(opening, rows), rows, duplicates, basis)


def save_reconciliation(db, preview):
    with db:
        db.execute("BEGIN IMMEDIATE")
        current = preview_reconciliation(db, preview.account_id, preview.day, preview.actual)
        if current.basis != preview.basis or current.currency != preview.currency:
            raise ValueError("I dati sono cambiati. Ripeti il confronto prima di salvare.")
        status = "confermata" if current.difference == 0 else "da verificare"
        previous = db.execute("SELECT * FROM reconciliations WHERE account_id=? AND as_of=?",
                              (current.account_id, current.day)).fetchone()
        values = (current.account_id, current.day, current.currency, current.actual_minor,
                  str(current.calculated), str(current.difference), status, current.basis)
        db.execute(
            "INSERT INTO reconciliations(account_id,as_of,currency,actual_minor,calculated,difference,status,basis) "
            "VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(account_id,as_of) DO UPDATE SET currency=excluded.currency,"
            "actual_minor=excluded.actual_minor,calculated=excluded.calculated,difference=excluded.difference,"
            "status=excluded.status,basis=excluded.basis,updated_at=CURRENT_TIMESTAMP", values,
        )
        saved = db.execute("SELECT * FROM reconciliations WHERE account_id=? AND as_of=?",
                           (current.account_id, current.day)).fetchone()
        _audit(db, "riconciliazione", dict(previous) if previous else None, dict(saved))
    return status


def latest_reconciliation(db, account_id):
    row = db.execute("SELECT * FROM reconciliations WHERE account_id=? ORDER BY as_of DESC LIMIT 1",
                     (account_id,)).fetchone()
    if row is None:
        return None
    result = dict(row)
    if row["status"] == "confermata":
        try:
            current = preview_reconciliation(db, account_id, row["as_of"], Decimal(row["actual_minor"]).scaleb(-2))
            if current.basis == row["basis"] and current.currency == row["currency"]:
                return result
        except ValueError:
            pass
        result["status"] = "da verificare"
    return result
