import json
from datetime import date
from decimal import Decimal, InvalidOperation


PROVIDERS = ("REVOLUT", "BPER", "CASH", "UNKNOWN")


def _audit(db, field, before, after):
    db.execute("INSERT INTO audit(field,old_value,new_value) VALUES(?,?,?)",
               (field, json.dumps(before), json.dumps(after)))


def list_accounts(db):
    return db.execute(
        "SELECT a.*, (SELECT MAX(t.occurred_at) FROM transactions t "
        "WHERE t.account_id=a.id AND t.status='COMPLETATO') AS last_movement "
        "FROM accounts a ORDER BY a.archived,a.id"
    ).fetchall()


def save_account(db, name, provider, currency, institution, notes, identifier=None):
    name, currency = name.strip(), currency.strip().upper()
    if not name or name.casefold() == "tutti i conti" or provider not in PROVIDERS or currency not in ("EUR", "CHF"):
        raise ValueError("Indica nome, tipo di conto e valuta EUR o CHF.")
    values = (name, provider, currency, institution.strip(), notes.strip())
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM accounts WHERE id=?", (identifier,)).fetchone()
        if identifier is not None and old is None:
            raise ValueError("Conto non trovato.")
        if db.execute(
            "SELECT 1 FROM accounts WHERE (name=? COLLATE NOCASE OR import_identity=? COLLATE NOCASE) "
            "AND id!=COALESCE(?,0)", (name, name, identifier),
        ).fetchone():
            raise ValueError("Nome già usato da un conto o dal suo identificativo d'importazione.")
        if old is None:
            identifier = db.execute(
                "INSERT INTO accounts(name,provider,currency,institution,notes,import_identity) VALUES(?,?,?,?,?,?)",
                (*values, name),
            ).lastrowid
        else:
            if (currency, provider) != (old["currency"], old["provider"]) and db.execute(
                "SELECT 1 FROM transactions WHERE account_id=? UNION ALL "
                "SELECT 1 FROM opening_balances WHERE account_id=? LIMIT 1", (identifier, identifier),
            ).fetchone():
                raise ValueError("Valuta e tipo non sono modificabili per un conto con movimenti o saldi iniziali.")
            db.execute(
                "UPDATE accounts SET name=?,provider=?,currency=?,institution=?,notes=?,"
                "import_identity=COALESCE(import_identity,?) WHERE id=?", (*values, old["name"], identifier),
            )
        current = db.execute("SELECT * FROM accounts WHERE id=?", (identifier,)).fetchone()
        _audit(db, "conto", dict(old) if old else None, dict(current))
    return identifier


def archive_account(db, identifier, archived):
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT archived FROM accounts WHERE id=?", (identifier,)).fetchone()
        if old is None:
            raise ValueError("Conto non trovato.")
        db.execute("UPDATE accounts SET archived=? WHERE id=?", (int(archived), identifier))
        _audit(db, "archiviazione_conto", {"id": identifier, "archived": old[0]},
               {"id": identifier, "archived": int(archived)})


def parse_date(value):
    value = value.strip()
    try:
        result = date.fromisoformat(value).isoformat()
    except ValueError as error:
        raise ValueError("Usa una data valida nel formato AAAA-MM-GG.") from error
    if result != value:
        raise ValueError("Usa una data nel formato AAAA-MM-GG.")
    return result


def minor_units(value):
    try:
        amount = Decimal(str(value).strip().replace(",", "."))
        minor = amount * 100
        if not amount.is_finite() or abs(minor) > 10**14 or minor != minor.to_integral_value():
            raise ValueError
        return int(minor)
    except (InvalidOperation, ValueError, ArithmeticError) as error:
        raise ValueError("Indica un importo valido con al massimo due decimali.") from error


def opening_balance(db, account_id, through=None):
    return db.execute(
        "SELECT * FROM opening_balances WHERE account_id=? AND confirmed=1 "
        "AND (? IS NULL OR as_of<=?) ORDER BY as_of DESC LIMIT 1", (account_id, through, through),
    ).fetchone()


def save_opening(db, account_id, as_of, value):
    day, minor = parse_date(as_of), minor_units(value)
    with db:
        db.execute("BEGIN IMMEDIATE")
        old = db.execute("SELECT * FROM opening_balances WHERE account_id=? AND as_of=?",
                         (account_id, day)).fetchone()
        db.execute(
            "INSERT INTO opening_balances(account_id,as_of,amount,confirmed,amount_minor) VALUES(?,?,?,1,?) "
            "ON CONFLICT(account_id,as_of) DO UPDATE SET amount=excluded.amount,confirmed=1,"
            "amount_minor=excluded.amount_minor",
            (account_id, day, str(Decimal(minor).scaleb(-2)), minor),
        )
        _audit(db, "saldo_iniziale", dict(old) if old else None,
               {"account_id": account_id, "as_of": day, "amount_minor": minor})


def balance_movements(db, account_id, after=None, through=None):
    return db.execute(
        "SELECT id,occurred_at,description,amount,fee FROM transactions WHERE account_id=? "
        "AND status='COMPLETATO' AND (? IS NULL OR substr(occurred_at,1,10)>?) "
        "AND (? IS NULL OR substr(occurred_at,1,10)<=?) ORDER BY occurred_at,id",
        (account_id, after, after, through, through),
    ).fetchall()


def calculated_balance(opening, rows):
    minor = opening["amount_minor"] if "amount_minor" in opening.keys() else None
    initial = (Decimal(minor).scaleb(-2) if minor is not None
               else Decimal(str(opening["amount"])))
    return initial + sum((Decimal(str(row["amount"])) - Decimal(str(row["fee"])) for row in rows), Decimal(0))
