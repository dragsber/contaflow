import json
from decimal import Decimal

from services.accounts import minor_units, parse_date


def record_cash_movement(db, account_id, day, description, value, category_id=None, subcategory_id=None):
    day, minor = parse_date(day), minor_units(value)
    description = description.strip()
    if not description or minor == 0:
        raise ValueError("Indica descrizione e importo diverso da zero.")
    with db:
        db.execute("BEGIN IMMEDIATE")
        account = db.execute("SELECT currency FROM accounts WHERE id=? AND provider='CASH' AND archived=0",
                             (account_id,)).fetchone()
        if account is None:
            raise ValueError("Seleziona una cassa contanti attiva.")
        if category_id is not None:
            category = db.execute("SELECT category_type FROM categories WHERE id=? AND archived=0",
                                  (category_id,)).fetchone()
            if category is None or category[0] != ("entrata" if minor > 0 else "uscita"):
                raise ValueError("La categoria deve corrispondere al segno dell'importo. "
                                 "Per un trasferimento lascia vuota la categoria e collega le due gambe.")
        if subcategory_id is not None and db.execute(
            "SELECT 1 FROM subcategories WHERE id=? AND category_id=? AND archived=0",
            (subcategory_id, category_id),
        ).fetchone() is None:
            raise ValueError("La sottovoce non appartiene alla categoria.")
        identifier = db.execute(
            "SELECT MAX(value)+1 FROM (SELECT COALESCE(MAX(id),0) value FROM transactions "
            "UNION ALL SELECT COALESCE(MAX(transaction_id),0) FROM audit)"
        ).fetchone()[0]
        db.execute(
            "INSERT INTO transactions(id,account_id,occurred_at,description,amount,currency,kind,status,"
            "source_json,category_id,subcategory_id,classification_status,classification_origin,subcategory_origin) "
            "VALUES(?,?,?,?,?,?,'CASSA_MANUALE','COMPLETATO',?,?,?,?,'manuale',?)",
            (identifier, account_id, day, description, str(Decimal(minor).scaleb(-2)), account["currency"],
             json.dumps({"origine": "registrazione manuale di cassa", "importo_unità_minori": minor}),
             category_id, subcategory_id, "classificato" if category_id is not None else "in_attesa",
             "manuale" if subcategory_id is not None else None),
        )
        db.execute(
            "INSERT INTO audit(transaction_id,field,old_value,new_value) VALUES(?,'movimento_cassa',NULL,?)",
            (identifier, json.dumps({"account_id": account_id, "data": day, "importo_unità_minori": minor,
                                     "descrizione": description, "category_id": category_id,
                                     "subcategory_id": subcategory_id})),
        )
    return identifier
